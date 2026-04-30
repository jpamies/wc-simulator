"""Database layer using asyncpg (PostgreSQL).

Provides a thin wrapper around asyncpg that mimics the aiosqlite API used
by routes and services: get_db(), db.execute(), db.execute_fetchall(),
db.commit(), db.close().
"""

import logging
import time
import asyncpg
from src.backend.config import DATABASE_URL, ADMIN_KEY

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
    id TEXT NOT NULL,
    tournament_id INTEGER NOT NULL DEFAULT 1 REFERENCES tournaments(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phase TEXT NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK(status IN ('scheduled','in_progress','completed')),
    PRIMARY KEY (id, tournament_id)
);

-- ─── Matches ───
CREATE TABLE IF NOT EXISTS matches (
    id TEXT NOT NULL,
    tournament_id INTEGER NOT NULL DEFAULT 1 REFERENCES tournaments(id) ON DELETE CASCADE,
    matchday_id TEXT NOT NULL,
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
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id, tournament_id),
    FOREIGN KEY (matchday_id, tournament_id) REFERENCES matchdays(id, tournament_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_matches_matchday ON matches(matchday_id, tournament_id);
CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(home_code);
CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(away_code);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament_id);

-- ─── Player match stats ───
CREATE TABLE IF NOT EXISTS player_match_stats (
    id SERIAL PRIMARY KEY,
    tournament_id INTEGER NOT NULL DEFAULT 1 REFERENCES tournaments(id) ON DELETE CASCADE,
    player_id TEXT NOT NULL REFERENCES players(id),
    match_id TEXT NOT NULL,
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
    UNIQUE(player_id, match_id, tournament_id),
    FOREIGN KEY (match_id, tournament_id) REFERENCES matches(id, tournament_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pms_player ON player_match_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_pms_match ON player_match_stats(match_id, tournament_id);
CREATE INDEX IF NOT EXISTS idx_pms_tournament ON player_match_stats(tournament_id);

-- ─── Group standings (materialised for fast reads) ───
CREATE TABLE IF NOT EXISTS group_standings (
    country_code TEXT NOT NULL REFERENCES countries(code),
    tournament_id INTEGER NOT NULL DEFAULT 1 REFERENCES tournaments(id) ON DELETE CASCADE,
    group_letter TEXT NOT NULL,
    played INTEGER DEFAULT 0,
    won INTEGER DEFAULT 0,
    drawn INTEGER DEFAULT 0,
    lost INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    PRIMARY KEY (country_code, group_letter, tournament_id)
);

-- ─── Tournaments ───
CREATE TABLE IF NOT EXISTS tournaments (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(12) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    owner_name VARCHAR(50) DEFAULT '',
    manage_token_hash TEXT NOT NULL,
    is_canonical BOOLEAN DEFAULT FALSE,
    visibility VARCHAR(10) DEFAULT 'public'
        CHECK(visibility IN ('public','unlisted','private')),
    forked_from INTEGER REFERENCES tournaments(id),
    status VARCHAR(10) DEFAULT 'active'
        CHECK(status IN ('active','archived')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Squad selections ───
CREATE TABLE IF NOT EXISTS squad_selections (
    country_code TEXT NOT NULL REFERENCES countries(code),
    player_id TEXT NOT NULL REFERENCES players(id),
    tournament_id INTEGER NOT NULL DEFAULT 1 REFERENCES tournaments(id) ON DELETE CASCADE,
    PRIMARY KEY (country_code, player_id, tournament_id)
);
CREATE INDEX IF NOT EXISTS idx_squad_country ON squad_selections(country_code, tournament_id);
CREATE INDEX IF NOT EXISTS idx_squad_player ON squad_selections(player_id);

-- ─── Squad stats (pre-computed for fast reads) ───
CREATE TABLE IF NOT EXISTS squad_stats (
    country_code TEXT NOT NULL REFERENCES countries(code),
    tournament_id INTEGER NOT NULL DEFAULT 1 REFERENCES tournaments(id) ON DELETE CASCADE,
    squad_size INTEGER DEFAULT 0,
    gk INTEGER DEFAULT 0,
    defs INTEGER DEFAULT 0,
    mids INTEGER DEFAULT 0,
    fwds INTEGER DEFAULT 0,
    avg_strength REAL DEFAULT 0,
    total_value BIGINT DEFAULT 0,
    PRIMARY KEY (country_code, tournament_id)
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
    """Create tables if they don't exist and run migrations."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    
    async with _pool.acquire() as conn:
        has_countries = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'countries')"
        )
        has_tournaments = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'tournaments')"
        )

        if not has_countries:
            # Fresh install: create full schema
            await conn.execute(SCHEMA)
            print("[DB] PostgreSQL schema created")
        elif not has_tournaments:
            # Migration: old schema exists, add tournaments support
            await _migrate_to_tournaments(conn)
            print("[DB] Migrated to multi-tournament schema")
        else:
            print("[DB] PostgreSQL schema already exists, skipping")

        # Ensure canonical tournament exists
        await _ensure_canonical_tournament(conn)


async def _migrate_to_tournaments(conn: asyncpg.Connection):
    """One-time migration: add tournaments table and tournament_id columns
    to existing tables. Assigns all existing data to tournament_id=1."""
    import hashlib

    # 1. Create tournaments table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id SERIAL PRIMARY KEY,
            slug VARCHAR(12) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            owner_name VARCHAR(50) DEFAULT '',
            manage_token_hash TEXT NOT NULL,
            is_canonical BOOLEAN DEFAULT FALSE,
            visibility VARCHAR(10) DEFAULT 'public',
            forked_from INTEGER REFERENCES tournaments(id),
            status VARCHAR(10) DEFAULT 'active',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # 2. Seed canonical tournament
    token_hash = hashlib.sha256(ADMIN_KEY.encode()).hexdigest()
    await conn.execute("""
        INSERT INTO tournaments (id, slug, name, owner_name, manage_token_hash, is_canonical)
        VALUES (1, 'official', 'FIFA World Cup 2026', 'Admin', $1, TRUE)
        ON CONFLICT (id) DO NOTHING
    """, token_hash)
    # Ensure sequence is past 1
    await conn.execute("SELECT setval('tournaments_id_seq', GREATEST(1, (SELECT MAX(id) FROM tournaments)))")

    # 3. Drop old simulations table
    await conn.execute("DROP TABLE IF EXISTS simulations")

    # 4. Migrate each table: add tournament_id column, update PKs
    # We need to drop and re-create constraints, so we do this carefully

    # -- matchdays: drop PK, add column, create new composite PK --
    has_tid = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='matchdays' AND column_name='tournament_id')"
    )
    if not has_tid:
        await conn.execute("ALTER TABLE matchdays DROP CONSTRAINT IF EXISTS matchdays_pkey")
        await conn.execute("ALTER TABLE matchdays ADD COLUMN tournament_id INTEGER NOT NULL DEFAULT 1")
        await conn.execute("ALTER TABLE matchdays ADD PRIMARY KEY (id, tournament_id)")
        await conn.execute("ALTER TABLE matchdays ADD FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE")

    # -- matches: drop PK, drop old FK, add column, create new PK + FK --
    has_tid = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='matches' AND column_name='tournament_id')"
    )
    if not has_tid:
        # Drop FK to matchdays first
        fks = await conn.fetch("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name='matches' AND constraint_type='FOREIGN KEY'
        """)
        for fk in fks:
            await conn.execute(f"ALTER TABLE matches DROP CONSTRAINT IF EXISTS {fk['constraint_name']}")
        await conn.execute("ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_pkey")
        await conn.execute("ALTER TABLE matches ADD COLUMN tournament_id INTEGER NOT NULL DEFAULT 1")
        await conn.execute("ALTER TABLE matches ADD PRIMARY KEY (id, tournament_id)")
        await conn.execute("ALTER TABLE matches ADD FOREIGN KEY (matchday_id, tournament_id) REFERENCES matchdays(id, tournament_id) ON DELETE CASCADE")
        await conn.execute("ALTER TABLE matches ADD FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament_id)")

    # -- player_match_stats: drop unique, add column, create new unique + FK --
    has_tid = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='player_match_stats' AND column_name='tournament_id')"
    )
    if not has_tid:
        # Drop old unique and FK
        await conn.execute("ALTER TABLE player_match_stats DROP CONSTRAINT IF EXISTS player_match_stats_player_id_match_id_key")
        fks = await conn.fetch("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name='player_match_stats' AND constraint_type='FOREIGN KEY'
        """)
        for fk in fks:
            await conn.execute(f"ALTER TABLE player_match_stats DROP CONSTRAINT IF EXISTS {fk['constraint_name']}")
        await conn.execute("ALTER TABLE player_match_stats ADD COLUMN tournament_id INTEGER NOT NULL DEFAULT 1")
        await conn.execute("ALTER TABLE player_match_stats ADD CONSTRAINT pms_unique_player_match_tid UNIQUE(player_id, match_id, tournament_id)")
        await conn.execute("ALTER TABLE player_match_stats ADD FOREIGN KEY (match_id, tournament_id) REFERENCES matches(id, tournament_id) ON DELETE CASCADE")
        await conn.execute("ALTER TABLE player_match_stats ADD FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE")
        await conn.execute("ALTER TABLE player_match_stats ADD FOREIGN KEY (player_id) REFERENCES players(id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pms_tournament ON player_match_stats(tournament_id)")

    # -- group_standings --
    has_tid = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='group_standings' AND column_name='tournament_id')"
    )
    if not has_tid:
        await conn.execute("ALTER TABLE group_standings DROP CONSTRAINT IF EXISTS group_standings_pkey")
        fks = await conn.fetch("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name='group_standings' AND constraint_type='FOREIGN KEY'
        """)
        for fk in fks:
            await conn.execute(f"ALTER TABLE group_standings DROP CONSTRAINT IF EXISTS {fk['constraint_name']}")
        await conn.execute("ALTER TABLE group_standings ADD COLUMN tournament_id INTEGER NOT NULL DEFAULT 1")
        await conn.execute("ALTER TABLE group_standings ADD PRIMARY KEY (country_code, group_letter, tournament_id)")
        await conn.execute("ALTER TABLE group_standings ADD FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE")
        await conn.execute("ALTER TABLE group_standings ADD FOREIGN KEY (country_code) REFERENCES countries(code)")

    # -- squad_selections --
    has_tid = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='squad_selections' AND column_name='tournament_id')"
    )
    if not has_tid:
        await conn.execute("ALTER TABLE squad_selections DROP CONSTRAINT IF EXISTS squad_selections_pkey")
        fks = await conn.fetch("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name='squad_selections' AND constraint_type='FOREIGN KEY'
        """)
        for fk in fks:
            await conn.execute(f"ALTER TABLE squad_selections DROP CONSTRAINT IF EXISTS {fk['constraint_name']}")
        await conn.execute("ALTER TABLE squad_selections ADD COLUMN tournament_id INTEGER NOT NULL DEFAULT 1")
        await conn.execute("ALTER TABLE squad_selections ADD PRIMARY KEY (country_code, player_id, tournament_id)")
        await conn.execute("ALTER TABLE squad_selections ADD FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE")
        await conn.execute("ALTER TABLE squad_selections ADD FOREIGN KEY (country_code) REFERENCES countries(code)")
        await conn.execute("ALTER TABLE squad_selections ADD FOREIGN KEY (player_id) REFERENCES players(id)")

    # -- squad_stats --
    has_tid = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='squad_stats' AND column_name='tournament_id')"
    )
    if not has_tid:
        await conn.execute("ALTER TABLE squad_stats DROP CONSTRAINT IF EXISTS squad_stats_pkey")
        fks = await conn.fetch("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name='squad_stats' AND constraint_type='FOREIGN KEY'
        """)
        for fk in fks:
            await conn.execute(f"ALTER TABLE squad_stats DROP CONSTRAINT IF EXISTS {fk['constraint_name']}")
        await conn.execute("ALTER TABLE squad_stats ADD COLUMN tournament_id INTEGER NOT NULL DEFAULT 1")
        await conn.execute("ALTER TABLE squad_stats ADD PRIMARY KEY (country_code, tournament_id)")
        await conn.execute("ALTER TABLE squad_stats ADD FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE")
        await conn.execute("ALTER TABLE squad_stats ADD FOREIGN KEY (country_code) REFERENCES countries(code)")


async def _ensure_canonical_tournament(conn: asyncpg.Connection):
    """Ensure the canonical tournament (id=1) exists."""
    import hashlib
    exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM tournaments WHERE id = 1)")
    if not exists:
        token_hash = hashlib.sha256(ADMIN_KEY.encode()).hexdigest()
        await conn.execute("""
            INSERT INTO tournaments (id, slug, name, owner_name, manage_token_hash, is_canonical)
            VALUES (1, 'official', 'FIFA World Cup 2026', 'Admin', $1, TRUE)
            ON CONFLICT (id) DO NOTHING
        """, token_hash)
        await conn.execute("SELECT setval('tournaments_id_seq', GREATEST(1, (SELECT MAX(id) FROM tournaments)))")


async def close_pool():
    """Close the connection pool (call on shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
