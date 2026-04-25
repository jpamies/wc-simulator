"""Squad selection routes — select 26-player squads per country."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.backend.database import get_db
from src.backend.models import PlayerOut

router = APIRouter(prefix="/squads", tags=["squads"])


async def _update_squad_stats(db, country_code: str):
    """Recompute and store squad stats for a country after selection changes."""
    rows = await db.execute_fetchall("""
        SELECT COUNT(*) as squad_size,
               COUNT(*) FILTER (WHERE p.position = 'GK') as gk,
               COUNT(*) FILTER (WHERE p.position = 'DEF') as defs,
               COUNT(*) FILTER (WHERE p.position = 'MID') as mids,
               COUNT(*) FILTER (WHERE p.position = 'FWD') as fwds,
               COALESCE(AVG(p.strength), 0) as avg_strength,
               COALESCE(SUM(p.market_value), 0) as total_value
        FROM squad_selections s
        JOIN players p ON s.player_id = p.id
        WHERE s.country_code = $1
    """, (country_code,))
    r = rows[0]
    await db.execute("""
        INSERT INTO squad_stats (country_code, squad_size, gk, defs, mids, fwds, avg_strength, total_value)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (country_code) DO UPDATE SET
            squad_size = EXCLUDED.squad_size, gk = EXCLUDED.gk, defs = EXCLUDED.defs,
            mids = EXCLUDED.mids, fwds = EXCLUDED.fwds,
            avg_strength = EXCLUDED.avg_strength, total_value = EXCLUDED.total_value
    """, (country_code, r["squad_size"], r["gk"], r["defs"], r["mids"], r["fwds"],
          r["avg_strength"], r["total_value"]))


class SquadIn(BaseModel):
    player_ids: list[str]


class SquadOverview(BaseModel):
    country_code: str
    country_name: str
    flag: str | None = None
    total_players: int
    squad_size: int
    gk: int = 0
    defs: int = 0
    mids: int = 0
    fwds: int = 0
    avg_strength: float = 0
    total_value: int = 0


@router.get("", response_model=list[SquadOverview])
async def list_squads():
    """List all countries with their squad selection status (pre-computed)."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT c.code, c.name, c.flag,
                   COALESCE(c.player_count, 0) as total_players,
                   COALESCE(ss.squad_size, 0) as squad_size,
                   COALESCE(ss.gk, 0) as gk,
                   COALESCE(ss.defs, 0) as defs,
                   COALESCE(ss.mids, 0) as mids,
                   COALESCE(ss.fwds, 0) as fwds,
                   COALESCE(ss.avg_strength, 0) as avg_strength,
                   COALESCE(ss.total_value, 0) as total_value
            FROM countries c
            LEFT JOIN squad_stats ss ON ss.country_code = c.code
            ORDER BY c.name
        """)
        return [SquadOverview(
            country_code=r["code"], country_name=r["name"], flag=r["flag"],
            total_players=r["total_players"], squad_size=r["squad_size"],
            gk=r["gk"], defs=r["defs"], mids=r["mids"], fwds=r["fwds"],
            avg_strength=round(r["avg_strength"], 1), total_value=r["total_value"],
        ) for r in rows]
    finally:
        await db.close()


import time as _time

_squad_players_cache: list | None = None
_squad_players_ts: float = 0
_CACHE_TTL = 300  # 5 minutes


@router.get("/all-players", response_model=list[PlayerOut])
async def get_all_squad_players():
    """Get all squad-selected players across all 48 countries in one call.
    Cached for 5 minutes since squads rarely change."""
    global _squad_players_cache, _squad_players_ts
    
    now = _time.time()
    if _squad_players_cache is not None and (now - _squad_players_ts) < _CACHE_TTL:
        return _squad_players_cache
    
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT p.* FROM players p
            WHERE p.id IN (SELECT player_id FROM squad_selections)
            ORDER BY p.country_code, 
                CASE p.position WHEN 'GK' THEN 1 WHEN 'DEF' THEN 2
                     WHEN 'MID' THEN 3 WHEN 'FWD' THEN 4 END,
                p.strength DESC
        """)
        result = [PlayerOut(**dict(r)) for r in rows]
        _squad_players_cache = result
        _squad_players_ts = now
        return result
    finally:
        await db.close()


@router.get("/{country_code}", response_model=list[PlayerOut])
async def get_squad(country_code: str):
    """Get the selected squad for a country."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT p.* FROM players p
            JOIN squad_selections s ON s.player_id = p.id
            WHERE s.country_code = $1
            ORDER BY
                CASE p.position WHEN 'GK' THEN 1 WHEN 'DEF' THEN 2
                     WHEN 'MID' THEN 3 WHEN 'FWD' THEN 4 END,
                p.strength DESC
        """, (country_code,))
        return [PlayerOut(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.put("/{country_code}")
async def save_squad(country_code: str, data: SquadIn):
    """Save/replace the squad for a country. Max 26 players, max 3 GK."""
    if len(data.player_ids) > 26:
        raise HTTPException(400, "Maximum 26 players per squad")

    db = await get_db()
    try:
        # Verify country exists
        row = await db.execute_fetchall(
            "SELECT code FROM countries WHERE code = $1", (country_code,)
        )
        if not row:
            raise HTTPException(404, "Country not found")

        # Verify all players belong to this country
        if data.player_ids:
            placeholders = ",".join(f"${i+1}" for i in range(len(data.player_ids)))
            players = await db.execute_fetchall(
                f"SELECT id, position FROM players WHERE id IN ({placeholders}) AND country_code = ${len(data.player_ids) + 1}",
                [*data.player_ids, country_code],
            )
            found_ids = {p["id"] for p in players}
            missing = set(data.player_ids) - found_ids
            if missing:
                raise HTTPException(400, f"Players not found for {country_code}: {missing}")

            # Check max 3 GK
            gk_count = sum(1 for p in players if p["position"] == "GK")
            if gk_count > 3:
                raise HTTPException(400, f"Maximum 3 goalkeepers, got {gk_count}")

        # Replace squad
        await db.execute(
            "DELETE FROM squad_selections WHERE country_code = $1", (country_code,)
        )
        for pid in data.player_ids:
            await db.execute(
                "INSERT INTO squad_selections (country_code, player_id) VALUES ($1, $2)",
                (country_code, pid),
            )
        
        await _update_squad_stats(db, country_code)
        await db.commit()
        global _squad_players_cache
        _squad_players_cache = None

        return {"status": "ok", "country_code": country_code, "squad_size": len(data.player_ids)}
    finally:
        await db.close()


@router.post("/{country_code}/auto")
async def auto_select_squad(country_code: str):
    """Auto-select the best 26 players: 3 GK, 8 DEF, 8 MID, 7 FWD."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT code FROM countries WHERE code = $1", (country_code,)
        )
        if not row:
            raise HTTPException(404, "Country not found")

        targets = {"GK": 3, "DEF": 8, "MID": 8, "FWD": 7}
        selected = []

        for pos, count in targets.items():
            rows = await db.execute_fetchall(
                "SELECT id FROM players WHERE country_code = $1 AND position = $2 ORDER BY strength DESC LIMIT $3",
                (country_code, pos, count),
            )
            selected.extend(r["id"] for r in rows)

        # Replace squad
        await db.execute(
            "DELETE FROM squad_selections WHERE country_code = $1", (country_code,)
        )
        for pid in selected:
            await db.execute(
                "INSERT INTO squad_selections (country_code, player_id) VALUES ($1, $2)",
                (country_code, pid),
            )
        
        await _update_squad_stats(db, country_code)
        await db.commit()
        global _squad_players_cache
        _squad_players_cache = None

        return {"status": "ok", "country_code": country_code, "squad_size": len(selected)}
    finally:
        await db.close()


@router.post("/auto-all")
async def auto_select_all_squads():
    """Auto-select squads for all 48 countries."""
    db = await get_db()
    try:
        countries = await db.execute_fetchall("SELECT code FROM countries")
    finally:
        await db.close()

    results = {}
    for c in countries:
        r = await auto_select_squad(c["code"])
        results[c["code"]] = r["squad_size"]

    return {"status": "ok", "squads": results}
