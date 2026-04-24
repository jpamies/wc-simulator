"""Database layer using asyncpg (PostgreSQL).

Provides a thin wrapper around asyncpg that mimics the aiosqlite API used
by routes and services: get_db(), db.execute(), db.execute_fetchall(),
db.commit(), db.close().
"""

import asyncpg
from src.backend.config import DATABASE_URL

_pool: asyncpg.Pool | None = None

SCHEMA = """
-- ─── Countries ───
CREATE TABLE IF NOT EXISTS countries (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    name_local TEXT,
    flag TEXT,
    confederation TEXT,
    group_letter TEXT
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

-- ─── Simulations ───
CREATE TABLE IF NOT EXISTS simulations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created'
        CHECK(status IN ('created','running','completed')),
    description TEXT
);

-- ─── Squad selections ───
CREATE TABLE IF NOT EXISTS squad_selections (
    country_code TEXT NOT NULL REFERENCES countries(code),
    player_id TEXT NOT NULL REFERENCES players(id),
    PRIMARY KEY (country_code, player_id)
);
CREATE INDEX IF NOT EXISTS idx_squad_country ON squad_selections(country_code);
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
        if params:
            await self._conn.execute(sql, *params)
        else:
            await self._conn.execute(sql)
    
    async def execute_fetchall(self, sql: str, params=None) -> list[dict]:
        """Execute a query and return all rows as list of dicts."""
        if params:
            rows = await self._conn.fetch(sql, *params)
        else:
            rows = await self._conn.fetch(sql)
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
        # Execute entire schema as a single transaction
        await conn.execute(SCHEMA)
    
    print("[DB] PostgreSQL schema initialized")


async def close_pool():
    """Close the connection pool (call on shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
