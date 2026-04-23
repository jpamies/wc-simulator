import aiosqlite
from src.backend.config import DATABASE_PATH

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
    is_simulated BOOLEAN NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_matches_matchday ON matches(matchday_id);
CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(home_code);
CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(away_code);

-- ─── Player match stats ───
CREATE TABLE IF NOT EXISTS player_match_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL REFERENCES players(id),
    match_id TEXT NOT NULL REFERENCES matches(id),
    minutes_played INTEGER DEFAULT 0,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    yellow_cards INTEGER DEFAULT 0,
    red_card BOOLEAN DEFAULT 0,
    own_goals INTEGER DEFAULT 0,
    penalties_missed INTEGER DEFAULT 0,
    penalties_saved INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    goals_conceded INTEGER DEFAULT 0,
    clean_sheet BOOLEAN DEFAULT 0,
    rating REAL DEFAULT 0.0,
    is_starter BOOLEAN DEFAULT 0,
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


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()
