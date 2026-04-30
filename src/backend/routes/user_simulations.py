"""User simulation routes — stateless dry-run + share/load snapshots."""

import json
import secrets
import string
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.backend.database import get_db
from src.backend.services.simulation_engine import simulate_match

router = APIRouter(tags=["user-simulations"])


# ─── Dry-run simulation (stateless, no DB writes) ───

class DryRunMatchIn(BaseModel):
    match_id: str
    home_players: list[dict]
    away_players: list[dict]
    is_knockout: bool = False


class DryRunRequest(BaseModel):
    matches: list[DryRunMatchIn]


@router.post("/simulate/dry-run")
async def dry_run_simulation(data: DryRunRequest):
    """Simulate matches without touching the database.
    
    Takes player lists for each match, runs the simulation engine,
    and returns results + player stats. The frontend stores everything
    in localStorage.
    """
    if len(data.matches) > 24:
        raise HTTPException(400, "Max 24 matches per dry-run request")

    results = []
    for m in data.matches:
        sim = simulate_match(
            home_players=m.home_players,
            away_players=m.away_players,
            is_knockout=m.is_knockout,
        )
        results.append({
            "match_id": m.match_id,
            "score_home": sim.score_home,
            "score_away": sim.score_away,
            "penalty_home": sim.penalty_home,
            "penalty_away": sim.penalty_away,
            "home_stats": [
                {
                    "player_id": s.player_id,
                    "position": s.position,
                    "minutes_played": s.minutes_played,
                    "goals": s.goals,
                    "assists": s.assists,
                    "yellow_cards": s.yellow_cards,
                    "red_card": s.red_card,
                    "own_goals": s.own_goals,
                    "penalties_missed": s.penalties_missed,
                    "penalties_saved": s.penalties_saved,
                    "saves": s.saves,
                    "goals_conceded": s.goals_conceded,
                    "clean_sheet": s.clean_sheet,
                    "rating": round(s.rating, 2),
                    "is_starter": s.is_starter,
                }
                for s in sim.home_stats
            ],
            "away_stats": [
                {
                    "player_id": s.player_id,
                    "position": s.position,
                    "minutes_played": s.minutes_played,
                    "goals": s.goals,
                    "assists": s.assists,
                    "yellow_cards": s.yellow_cards,
                    "red_card": s.red_card,
                    "own_goals": s.own_goals,
                    "penalties_missed": s.penalties_missed,
                    "penalties_saved": s.penalties_saved,
                    "saves": s.saves,
                    "goals_conceded": s.goals_conceded,
                    "clean_sheet": s.clean_sheet,
                    "rating": round(s.rating, 2),
                    "is_starter": s.is_starter,
                }
                for s in sim.away_stats
            ],
        })

    return {"results": results}


# ─── Share / Load simulation snapshots ───

def _generate_slug(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class ShareSimulationIn(BaseModel):
    name: str = ""
    author: str = ""
    data: dict  # Full simulation state from localStorage


class SharedSimulationOut(BaseModel):
    slug: str
    name: str
    author: str
    created_at: str | None = None


@router.post("/simulations/share", response_model=SharedSimulationOut)
async def share_simulation(body: ShareSimulationIn):
    """Save a simulation snapshot and return a shareable slug."""
    # Validate size (max ~5MB of JSON)
    data_str = json.dumps(body.data)
    if len(data_str) > 5_000_000:
        raise HTTPException(400, "Simulation data too large (max 5MB)")

    slug = _generate_slug()
    db = await get_db()
    try:
        # Check collision (unlikely)
        existing = await db.execute_fetchall(
            "SELECT slug FROM shared_simulations WHERE slug = $1", (slug,)
        )
        if existing:
            slug = _generate_slug(10)

        await db.execute("""
            INSERT INTO shared_simulations (slug, name, author, data)
            VALUES ($1, $2, $3, $4)
        """, (slug, body.name[:100], body.author[:50], data_str))
        await db.commit()

        return SharedSimulationOut(slug=slug, name=body.name, author=body.author)
    finally:
        await db.close()


@router.get("/simulations/{slug}")
async def load_simulation(slug: str):
    """Load a shared simulation snapshot by slug."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT slug, name, author, data, created_at FROM shared_simulations WHERE slug = $1",
            (slug,)
        )
        if not rows:
            raise HTTPException(404, "Simulation not found")
        r = rows[0]
        return {
            "slug": r["slug"],
            "name": r["name"],
            "author": r["author"],
            "data": json.loads(r["data"]) if isinstance(r["data"], str) else r["data"],
            "created_at": str(r["created_at"]) if r["created_at"] else None,
        }
    finally:
        await db.close()


@router.get("/simulations")
async def list_simulations(limit: int = 20):
    """List recent shared simulations."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT slug, name, author, created_at
            FROM shared_simulations
            ORDER BY created_at DESC
            LIMIT $1
        """, (min(limit, 50),))
        return [
            {
                "slug": r["slug"],
                "name": r["name"],
                "author": r["author"],
                "created_at": str(r["created_at"]) if r["created_at"] else None,
            }
            for r in rows
        ]
    finally:
        await db.close()
