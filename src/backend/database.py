"""Database layer using asyncpg (PostgreSQL).

Provides a thin wrapper around asyncpg that mimics the aiosqlite API used
by routes and services: get_db(), db.execute(), db.execute_fetchall(),
db.commit(), db.close().
"""

import logging
import time
import asyncpg
from src.backend.config import DATABASE_URL

_pool: asyncpg.Pool | None = None
logger = logging.getLogger("wc-simulator.db")
SLOW_QUERY_MS = 100  # Log queries slower than this

SCHEMA = """
-- ─── Countries ───
CREATE TABLE IF NOT EXISTS countries (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    name_local TEXT,
    flag TEXT,
    confederation TEXT,
    group_letter TEXT,
    player_count INTEGER DEFAULT 0
);

-- ─── Players ───
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country_code TEXT NOT NULL REFERENCES countries(code),
    position TEXT NOT NULL CHECK(position IN ('GK','DEF','MID','FWD')),
    detailed_position TEXT,
    club TEXT,
    club_logo TEXT,
    league TEXT,
    age INTEGER,
    market_value INTEGER DEFAULT 0,
    photo TEXT,
    strength INTEGER DEFAULT 50 CHECK(strength BETWEEN 1 AND 99),
    pace INTEGER,
    shooting INTEGER,
    passing INTEGER,
    dribbling INTEGER,
    defending INTEGER,
    physic INTEGER
);
CREATE INDEX IF NOT EXISTS idx_players_country ON players(country_code);
CREATE INDEX IF NOT EXISTS idx_players_position ON players(position);
CREATE INDEX IF NOT EXISTS idx_players_country_pos_str ON players(country_code, position, strength DESC);
CREATE INDEX IF NOT EXISTS idx_players_country_str ON players(country_code, strength DESC);

-- ─── Matchdays ───
CREATE TABLE IF NOT EXISTS matchdays (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phase TEXT NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK(status IN ('scheduled','in_progress','completed'))
);

-- ─── Matches ───
CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    matchday_id TEXT NOT NULL REFERENCES matchdays(id),
    match_number INTEGER,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_code TEXT,
    away_code TEXT,
    kickoff TEXT NOT NULL,
    location TEXT,
    group_name TEXT,
    score_home INTEGER,
    score_away INTEGER,
    penalty_home INTEGER,
    penalty_away INTEGER,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK(status IN ('scheduled','live','finished')),
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_matches_matchday ON matches(matchday_id);
CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(home_code);
CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(away_code);

-- ─── Player match stats ───
CREATE TABLE IF NOT EXISTS player_match_stats (
    id SERIAL PRIMARY KEY,
    player_id TEXT NOT NULL REFERENCES players(id),
    match_id TEXT NOT NULL REFERENCES matches(id),
    minutes_played INTEGER DEFAULT 0,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    yellow_cards INTEGER DEFAULT 0,
    red_card BOOLEAN DEFAULT FALSE,
    own_goals INTEGER DEFAULT 0,
    penalties_missed INTEGER DEFAULT 0,
    penalties_saved INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    goals_conceded INTEGER DEFAULT 0,
    clean_sheet BOOLEAN DEFAULT FALSE,
    rating REAL DEFAULT 0.0,
    is_starter BOOLEAN DEFAULT FALSE,
    UNIQUE(player_id, match_id)
);
CREATE INDEX IF NOT EXISTS idx_pms_player ON player_match_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_pms_match ON player_match_stats(match_id);

-- ─── Group standings (materialised for fast reads) ───
CREATE TABLE IF NOT EXISTS group_standings (
    country_code TEXT NOT NULL REFERENCES countries(code),
    group_letter TEXT NOT NULL,
    played INTEGER DEFAULT 0,
    won INTEGER DEFAULT 0,
    drawn INTEGER DEFAULT 0,
    lost INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    PRIMARY KEY (country_code, group_letter)
);

-- ─── Shared simulations (user snapshots for sharing) ───
CREATE TABLE IF NOT EXISTS shared_simulations (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_shared_sims_created ON shared_simulations(created_at DESC);

-- ─── Squad selections ───
CREATE TABLE IF NOT EXISTS squad_selections (
    country_code TEXT NOT NULL REFERENCES countries(code),
    player_id TEXT NOT NULL REFERENCES players(id),
    PRIMARY KEY (country_code, player_id)
);
CREATE INDEX IF NOT EXISTS idx_squad_country ON squad_selections(country_code);
CREATE INDEX IF NOT EXISTS idx_squad_player ON squad_selections(player_id);

-- ─── Squad stats (pre-computed for fast reads) ───
CREATE TABLE IF NOT EXISTS squad_stats (
    country_code TEXT PRIMARY KEY REFERENCES countries(code),
    squad_size INTEGER DEFAULT 0,
    gk INTEGER DEFAULT 0,
    defs INTEGER DEFAULT 0,
    mids INTEGER DEFAULT 0,
    fwds INTEGER DEFAULT 0,
    avg_strength REAL DEFAULT 0,
    total_value BIGINT DEFAULT 0
);
"""


class PgConnection:
    """Thin wrapper around asyncpg.Connection that provides an API compatible
    with the aiosqlite patterns used throughout the codebase.
    
    Usage:
        db = await get_db()
        try:
            rows = await db.execute_fetchall("SELECT * FROM t WHERE id = $1", (val,))
            await db.execute("INSERT INTO t VALUES ($1, $2)", (a, b))
            await db.commit()
        finally:
            await db.close()
    """
    
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn
        self._tx = None
    
    async def execute(self, sql: str, params=None):
        """Execute a statement (INSERT/UPDATE/DELETE/DDL)."""
        if self._tx is None:
            self._tx = self._conn.transaction()
            await self._tx.start()
        start = time.perf_counter()
        if params:
            await self._conn.execute(sql, *params)
        else:
            await self._conn.execute(sql)
        ms = (time.perf_counter() - start) * 1000
        if ms > SLOW_QUERY_MS:
            logger.warning(f"SLOW EXEC ({ms:.0f}ms): {sql[:120]}")
    
    async def execute_fetchall(self, sql: str, params=None) -> list[dict]:
        """Execute a query and return all rows as list of dicts."""
        start = time.perf_counter()
        if params:
            rows = await self._conn.fetch(sql, *params)
        else:
            rows = await self._conn.fetch(sql)
        ms = (time.perf_counter() - start) * 1000
        if ms > SLOW_QUERY_MS:
            logger.warning(f"SLOW QUERY ({ms:.0f}ms, {len(rows)} rows): {sql[:120]}")
        return [dict(r) for r in rows]
    
    async def commit(self):
        """Commit the current transaction."""
        if self._tx is not None:
            await self._tx.commit()
            self._tx = None
    
    async def close(self):
        """Release the connection back to the pool."""
        if self._tx is not None:
            try:
                await self._tx.rollback()
            except Exception:
                pass
            self._tx = None
        await _pool.release(self._conn)


async def get_db() -> PgConnection:
    """Get a database connection from the pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    conn = await _pool.acquire()
    return PgConnection(conn)


async def init_db():
    """Create tables if they don't exist."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    
    async with _pool.acquire() as conn:
        # Check if schema already exists (countries is always the first table)
        row = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'countries')"
        )
        if not row:
            await conn.execute(SCHEMA)
            print("[DB] PostgreSQL schema created")
        else:
            print("[DB] PostgreSQL schema already exists, skipping")
            # Migrate: drop old tables from failed tournament_id migration + old simulations
            await _cleanup_old_tables(conn)
            # Ensure shared_simulations table exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shared_simulations (
                    slug TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    author TEXT NOT NULL DEFAULT '',
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shared_sims_created ON shared_simulations(created_at DESC)"
            )


async def _cleanup_old_tables(conn):
    """Remove remnants from the failed tournament_id migration attempt."""
    has_tournaments = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'tournaments')"
    )
    if not has_tournaments:
        # No migration remnants, just drop old simulations table
        await conn.execute("DROP TABLE IF EXISTS simulations")
        return

    print("[DB] Cleaning up failed tournament_id migration...")

    # 1. Drop all FK constraints that reference tournament_id or tournaments table
    #    Work from leaf tables inward to avoid dependency issues
    tables_with_tid = []
    for table in ('player_match_stats', 'matches', 'matchdays',
                  'group_standings', 'squad_selections', 'squad_stats'):
        has_tid = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name=$1 AND column_name='tournament_id')", table
        )
        if has_tid:
            tables_with_tid.append(table)

    # Drop ALL foreign key constraints on affected tables (we'll let the schema re-create them)
    for table in tables_with_tid:
        fks = await conn.fetch("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = $1 AND constraint_type = 'FOREIGN KEY'
        """, table)
        for fk in fks:
            await conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fk['constraint_name']}")

    # 2. Drop tournament_id columns
    for table in tables_with_tid:
        await conn.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tournament_id")
        print(f"[DB]   Removed tournament_id from {table}")

    # 3. Restore original primary keys (the migration changed them to composites)
    # matchdays: should be (id) not (id, tournament_id)
    has_matchdays_pk = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='matchdays_pkey')"
    )
    if not has_matchdays_pk:
        await conn.execute("ALTER TABLE matchdays ADD PRIMARY KEY (id)")

    # matches: should be (id) not (id, tournament_id)
    has_matches_pk = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='matches_pkey')"
    )
    if not has_matches_pk:
        await conn.execute("ALTER TABLE matches ADD PRIMARY KEY (id)")

    # Restore FK: matches.matchday_id → matchdays.id
    await conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='matches_matchday_id_fkey') THEN
                ALTER TABLE matches ADD CONSTRAINT matches_matchday_id_fkey
                    FOREIGN KEY (matchday_id) REFERENCES matchdays(id);
            END IF;
        END $$
    """)

    # Restore FK: player_match_stats.match_id → matches.id
    await conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='player_match_stats_match_id_fkey') THEN
                ALTER TABLE player_match_stats ADD CONSTRAINT player_match_stats_match_id_fkey
                    FOREIGN KEY (match_id) REFERENCES matches(id);
            END IF;
        END $$
    """)

    # Restore FK: player_match_stats.player_id → players.id
    await conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='player_match_stats_player_id_fkey') THEN
                ALTER TABLE player_match_stats ADD CONSTRAINT player_match_stats_player_id_fkey
                    FOREIGN KEY (player_id) REFERENCES players(id);
            END IF;
        END $$
    """)

    # Restore UNIQUE on player_match_stats(player_id, match_id)
    await conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='player_match_stats_player_id_match_id_key') THEN
                ALTER TABLE player_match_stats ADD CONSTRAINT player_match_stats_player_id_match_id_key
                    UNIQUE (player_id, match_id);
            END IF;
        END $$
    """)

    # group_standings: PK should be (country_code, group_letter)
    has_gs_pk = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='group_standings_pkey')"
    )
    if not has_gs_pk:
        await conn.execute("ALTER TABLE group_standings ADD PRIMARY KEY (country_code, group_letter)")
    await conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='group_standings_country_code_fkey') THEN
                ALTER TABLE group_standings ADD CONSTRAINT group_standings_country_code_fkey
                    FOREIGN KEY (country_code) REFERENCES countries(code);
            END IF;
        END $$
    """)

    # squad_selections: PK should be (country_code, player_id)
    has_ss_pk = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='squad_selections_pkey')"
    )
    if not has_ss_pk:
        await conn.execute("ALTER TABLE squad_selections ADD PRIMARY KEY (country_code, player_id)")
    await conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='squad_selections_country_code_fkey') THEN
                ALTER TABLE squad_selections ADD CONSTRAINT squad_selections_country_code_fkey
                    FOREIGN KEY (country_code) REFERENCES countries(code);
            END IF;
        END $$
    """)
    await conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='squad_selections_player_id_fkey') THEN
                ALTER TABLE squad_selections ADD CONSTRAINT squad_selections_player_id_fkey
                    FOREIGN KEY (player_id) REFERENCES players(id);
            END IF;
        END $$
    """)

    # squad_stats: PK should be (country_code)
    has_sqst_pk = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='squad_stats_pkey')"
    )
    if not has_sqst_pk:
        await conn.execute("ALTER TABLE squad_stats ADD PRIMARY KEY (country_code)")
    await conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='squad_stats_country_code_fkey') THEN
                ALTER TABLE squad_stats ADD CONSTRAINT squad_stats_country_code_fkey
                    FOREIGN KEY (country_code) REFERENCES countries(code);
            END IF;
        END $$
    """)

    # 4. Drop tournaments table and old simulations table
    await conn.execute("DROP TABLE IF EXISTS tournaments CASCADE")
    await conn.execute("DROP TABLE IF EXISTS simulations")
    # Drop indexes from old migration
    await conn.execute("DROP INDEX IF EXISTS idx_matches_tournament")
    await conn.execute("DROP INDEX IF EXISTS idx_pms_tournament")

    print("[DB] Migration cleanup complete — schema restored to original")


async def close_pool():
    """Close the connection pool (call on shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
