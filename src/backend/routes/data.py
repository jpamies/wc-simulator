"""Country and player data routes."""

from fastapi import APIRouter, Query
from src.backend.database import get_db
from src.backend.models import CountryOut, PlayerOut

router = APIRouter(tags=["data"])


# ─── Countries ───

@router.get("/countries", response_model=list[CountryOut])
async def list_countries():
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT c.*, COUNT(p.id) as player_count
            FROM countries c
            LEFT JOIN players p ON p.country_code = c.code
            GROUP BY c.code
            ORDER BY c.name ASC
        """)
        return [CountryOut(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/countries/{code}", response_model=CountryOut)
async def get_country(code: str):
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT c.*, COUNT(p.id) as player_count
            FROM countries c
            LEFT JOIN players p ON p.country_code = c.code
            WHERE c.code = $1
            GROUP BY c.code
        """, (code,))
        if not rows:
            from fastapi import HTTPException
            raise HTTPException(404, "Country not found")
        return CountryOut(**dict(rows[0]))
    finally:
        await db.close()


@router.get("/countries/{code}/players", response_model=list[PlayerOut])
async def get_country_players(code: str):
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM players WHERE country_code = $1 ORDER BY position, name",
            (code,),
        )
        return [PlayerOut(**dict(r)) for r in rows]
    finally:
        await db.close()


# ─── Players ───

@router.get("/players", response_model=list[PlayerOut])
async def list_players(
    country: str | None = None,
    position: str | None = None,
    search: str | None = None,
    sort: str = Query("market_value", pattern="^(market_value|name|age|strength)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = await get_db()
    try:
        query = "SELECT * FROM players WHERE 1=1"
        params: list = []
        param_idx = 1

        if country:
            query += f" AND country_code = ${param_idx}"
            params.append(country)
            param_idx += 1
        if position:
            query += f" AND position = ${param_idx}"
            params.append(position)
            param_idx += 1
        if search:
            query += f" AND name LIKE ${param_idx}"
            params.append(f"%{search}%")
            param_idx += 1

        order = {"market_value": "market_value DESC", "name": "name ASC",
                 "age": "age ASC", "strength": "strength DESC"}
        query += f" ORDER BY {order.get(sort, 'market_value DESC')}"
        query += f" LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        rows = await db.execute_fetchall(query, params)
        return [PlayerOut(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/players/{player_id}", response_model=PlayerOut)
async def get_player(player_id: str):
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM players WHERE id = $1", (player_id,)
        )
        if not rows:
            from fastapi import HTTPException
            raise HTTPException(404, "Player not found")
        return PlayerOut(**dict(rows[0]))
    finally:
        await db.close()
