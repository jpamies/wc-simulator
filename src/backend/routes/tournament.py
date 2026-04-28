"""Tournament routes — tournament overview, calendar, standings."""

from fastapi import APIRouter
from src.backend.database import get_db
from src.backend.models import (
    TournamentOverview, MatchdayOut, MatchOut, GroupStandingOut,
)
from src.backend.services.tournament_engine import (
    get_group_standings, recalculate_group_standings,
    get_best_third_place_teams,
)

router = APIRouter(prefix="/tournament", tags=["tournament"])


@router.get("/overview", response_model=TournamentOverview)
async def overview():
    db = await get_db()
    try:
        countries = await db.execute_fetchall("SELECT COUNT(*) as c FROM countries")
        players = await db.execute_fetchall("SELECT COUNT(*) as c FROM players")
        total = await db.execute_fetchall("SELECT COUNT(*) as c FROM matches")
        played = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM matches WHERE status = 'finished'"
        )
        groups_raw = await db.execute_fetchall(
            "SELECT code, group_letter FROM countries WHERE group_letter IS NOT NULL ORDER BY group_letter, code"
        )

        groups: dict[str, list[str]] = {}
        for r in groups_raw:
            groups.setdefault(r["group_letter"], []).append(r["code"])

        # Determine current phase
        phase_row = await db.execute_fetchall("""
            SELECT md.phase FROM matchdays md
            JOIN matches m ON m.matchday_id = md.id
            WHERE m.status != 'finished'
            ORDER BY md.date ASC LIMIT 1
        """)
        current_phase = phase_row[0]["phase"] if phase_row else "completed"

        return TournamentOverview(
            tournament="FIFA World Cup 2026",
            host=["USA", "Mexico", "Canada"],
            total_teams=countries[0]["c"],
            total_players=players[0]["c"],
            total_matches=total[0]["c"],
            matches_played=played[0]["c"],
            matches_remaining=total[0]["c"] - played[0]["c"],
            current_phase=current_phase,
            groups=groups,
        )
    finally:
        await db.close()


@router.get("/calendar", response_model=list[MatchdayOut])
async def calendar():
    db = await get_db()
    try:
        matchdays = await db.execute_fetchall(
            "SELECT * FROM matchdays ORDER BY date ASC"
        )
        result = []
        for md in matchdays:
            matches = await db.execute_fetchall("""
                SELECT m.*, h.flag as home_flag, a.flag as away_flag
                FROM matches m
                LEFT JOIN countries h ON m.home_code = h.code
                LEFT JOIN countries a ON m.away_code = a.code
                WHERE m.matchday_id = $1
                ORDER BY m.kickoff ASC
            """, (md["id"],))
            result.append(MatchdayOut(
                id=md["id"], name=md["name"], phase=md["phase"],
                date=md["date"], status=md["status"],
                matches=[MatchOut(**dict(m)) for m in matches],
            ))
        return result
    finally:
        await db.close()


@router.get("/standings", response_model=dict[str, list[GroupStandingOut]])
async def standings():
    raw = await get_group_standings()
    result: dict[str, list[GroupStandingOut]] = {}
    for group, teams in raw.items():
        result[group] = [
            GroupStandingOut(
                country_code=t["country_code"],
                country_name=t.get("country_name"),
                flag=t.get("flag"),
                group_letter=t["group_letter"],
                played=t["played"], won=t["won"], drawn=t["drawn"], lost=t["lost"],
                goals_for=t["goals_for"], goals_against=t["goals_against"],
                goal_difference=t["goals_for"] - t["goals_against"],
                points=t["points"],
            )
            for t in teams
        ]
    return result


@router.get("/best-thirds")
async def best_thirds():
    """Return the 8 best 3rd-place country codes that would qualify for R32."""
    codes = await get_best_third_place_teams()
    return codes


@router.get("/progress")
async def tournament_progress():
    """Return per-matchday/phase completion status for the simulate UI."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT md.id as matchday_id, md.phase,
                   COUNT(*) as total,
                   SUM(CASE WHEN m.status = 'finished' THEN 1 ELSE 0 END) as finished,
                   SUM(CASE WHEN m.home_code IS NOT NULL AND m.away_code IS NOT NULL THEN 1 ELSE 0 END) as resolved
            FROM matchdays md
            JOIN matches m ON m.matchday_id = md.id
            GROUP BY md.id, md.phase
            ORDER BY md.date ASC
        """)
        matchdays = {}
        for r in rows:
            matchdays[r["matchday_id"]] = {
                "phase": r["phase"],
                "total": r["total"],
                "finished": r["finished"],
                "resolved": r["resolved"],
                "done": r["finished"] == r["total"],
            }
        return matchdays
    finally:
        await db.close()
