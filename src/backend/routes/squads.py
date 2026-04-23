"""Squad selection routes — select 26-player squads per country."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.backend.database import get_db
from src.backend.models import PlayerOut

router = APIRouter(prefix="/squads", tags=["squads"])


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


@router.get("", response_model=list[SquadOverview])
async def list_squads():
    """List all countries with their squad selection status."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT c.code, c.name, c.flag,
                   (SELECT COUNT(*) FROM players p WHERE p.country_code = c.code) as total_players,
                   (SELECT COUNT(*) FROM squad_selections s WHERE s.country_code = c.code) as squad_size,
                   (SELECT COUNT(*) FROM squad_selections s
                    JOIN players p ON s.player_id = p.id
                    WHERE s.country_code = c.code AND p.position = 'GK') as gk,
                   (SELECT COUNT(*) FROM squad_selections s
                    JOIN players p ON s.player_id = p.id
                    WHERE s.country_code = c.code AND p.position = 'DEF') as defs,
                   (SELECT COUNT(*) FROM squad_selections s
                    JOIN players p ON s.player_id = p.id
                    WHERE s.country_code = c.code AND p.position = 'MID') as mids,
                   (SELECT COUNT(*) FROM squad_selections s
                    JOIN players p ON s.player_id = p.id
                    WHERE s.country_code = c.code AND p.position = 'FWD') as fwds
            FROM countries c
            ORDER BY c.name
        """)
        return [SquadOverview(
            country_code=r["code"], country_name=r["name"], flag=r["flag"],
            total_players=r["total_players"], squad_size=r["squad_size"],
            gk=r["gk"], defs=r["defs"], mids=r["mids"], fwds=r["fwds"],
        ) for r in rows]
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
            WHERE s.country_code = ?
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
            "SELECT code FROM countries WHERE code = ?", (country_code,)
        )
        if not row:
            raise HTTPException(404, "Country not found")

        # Verify all players belong to this country
        if data.player_ids:
            placeholders = ",".join("?" for _ in data.player_ids)
            players = await db.execute_fetchall(
                f"SELECT id, position FROM players WHERE id IN ({placeholders}) AND country_code = ?",
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
            "DELETE FROM squad_selections WHERE country_code = ?", (country_code,)
        )
        for pid in data.player_ids:
            await db.execute(
                "INSERT INTO squad_selections (country_code, player_id) VALUES (?, ?)",
                (country_code, pid),
            )
        await db.commit()

        return {"status": "ok", "country_code": country_code, "squad_size": len(data.player_ids)}
    finally:
        await db.close()


@router.post("/{country_code}/auto")
async def auto_select_squad(country_code: str):
    """Auto-select the best 26 players: 3 GK, 8 DEF, 8 MID, 7 FWD."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT code FROM countries WHERE code = ?", (country_code,)
        )
        if not row:
            raise HTTPException(404, "Country not found")

        targets = {"GK": 3, "DEF": 8, "MID": 8, "FWD": 7}
        selected = []

        for pos, count in targets.items():
            rows = await db.execute_fetchall(
                "SELECT id FROM players WHERE country_code = ? AND position = ? ORDER BY strength DESC LIMIT ?",
                (country_code, pos, count),
            )
            selected.extend(r["id"] for r in rows)

        # Replace squad
        await db.execute(
            "DELETE FROM squad_selections WHERE country_code = ?", (country_code,)
        )
        for pid in selected:
            await db.execute(
                "INSERT INTO squad_selections (country_code, player_id) VALUES (?, ?)",
                (country_code, pid),
            )
        await db.commit()

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
