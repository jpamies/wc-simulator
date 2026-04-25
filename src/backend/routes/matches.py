"""Match routes — list matches, update results, get match stats."""

from fastapi import APIRouter, HTTPException
from src.backend.database import get_db
from src.backend.models import (
    MatchOut, MatchResultIn, MatchStatsIn, PlayerStatOut,
)
from src.backend.services.tournament_engine import recalculate_group_standings

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=list[MatchOut])
async def list_matches(
    matchday_id: str | None = None,
    country: str | None = None,
    status: str | None = None,
):
    db = await get_db()
    try:
        query = """
            SELECT m.*, h.flag as home_flag, a.flag as away_flag
            FROM matches m
            LEFT JOIN countries h ON m.home_code = h.code
            LEFT JOIN countries a ON m.away_code = a.code
            WHERE 1=1
        """
        params: list = []
        param_idx = 1

        if matchday_id:
            query += f" AND m.matchday_id = ${param_idx}"
            params.append(matchday_id)
            param_idx += 1
        if country:
            query += f" AND (m.home_code = ${param_idx} OR m.away_code = ${param_idx + 1})"
            params.extend([country, country])
            param_idx += 2
        if status:
            query += f" AND m.status = ${param_idx}"
            params.append(status)
            param_idx += 1

        query += " ORDER BY m.kickoff ASC"
        rows = await db.execute_fetchall(query, params)
        return [MatchOut(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/{match_id}", response_model=MatchOut)
async def get_match(match_id: str):
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT m.*, h.flag as home_flag, a.flag as away_flag
            FROM matches m
            LEFT JOIN countries h ON m.home_code = h.code
            LEFT JOIN countries a ON m.away_code = a.code
            WHERE m.id = $1
        """, (match_id,))
        if not rows:
            raise HTTPException(404, "Match not found")
        return MatchOut(**dict(rows[0]))
    finally:
        await db.close()


@router.patch("/{match_id}/result", response_model=MatchOut)
async def set_match_result(match_id: str, result: MatchResultIn):
    """Set or update a real match result (non-simulated)."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM matches WHERE id = $1", (match_id,)
        )
        if not rows:
            raise HTTPException(404, "Match not found")

        await db.execute("""
            UPDATE matches SET
                score_home = $1, score_away = $2,
                penalty_home = $3, penalty_away = $4,
                status = 'finished', is_simulated = FALSE
            WHERE id = $5
        """, (result.score_home, result.score_away,
              result.penalty_home, result.penalty_away, match_id))
        await db.commit()

        # Recalculate standings if group phase
        match = rows[0]
        md = await db.execute_fetchall(
            "SELECT phase FROM matchdays WHERE id = $1", (match["matchday_id"],)
        )
        if md and md[0]["phase"] == "groups":
            await recalculate_group_standings()

        return await get_match(match_id)
    finally:
        await db.close()


@router.post("/{match_id}/stats")
async def set_match_stats(match_id: str, data: MatchStatsIn):
    """Set individual player stats for a match."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM matches WHERE id = $1", (match_id,)
        )
        if not rows:
            raise HTTPException(404, "Match not found")

        for s in data.stats:
            await db.execute("""
                INSERT INTO player_match_stats
                    (player_id, match_id, minutes_played, goals, assists,
                     yellow_cards, red_card, own_goals, penalties_missed,
                     penalties_saved, saves, goals_conceded, clean_sheet,
                     rating, is_starter)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT(player_id, match_id) DO UPDATE SET
                    minutes_played=excluded.minutes_played,
                    goals=excluded.goals, assists=excluded.assists,
                    yellow_cards=excluded.yellow_cards,
                    red_card=excluded.red_card,
                    own_goals=excluded.own_goals,
                    penalties_missed=excluded.penalties_missed,
                    penalties_saved=excluded.penalties_saved,
                    saves=excluded.saves,
                    goals_conceded=excluded.goals_conceded,
                    clean_sheet=excluded.clean_sheet,
                    rating=excluded.rating,
                    is_starter=excluded.is_starter
            """, (s.player_id, match_id, s.minutes_played, s.goals,
                  s.assists, s.yellow_cards, s.red_card, s.own_goals,
                  s.penalties_missed, s.penalties_saved, s.saves,
                  s.goals_conceded, s.clean_sheet, s.rating, s.is_starter))

        await db.commit()
        return {"status": "ok", "stats_recorded": len(data.stats)}
    finally:
        await db.close()


@router.get("/{match_id}/stats", response_model=list[PlayerStatOut])
async def get_match_stats(match_id: str):
    """Get player stats for a match."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT pms.*, p.name as player_name, p.country_code, p.position
            FROM player_match_stats pms
            JOIN players p ON pms.player_id = p.id
            WHERE pms.match_id = $1
            ORDER BY p.country_code, pms.is_starter DESC, p.position
        """, (match_id,))
        return [PlayerStatOut(**dict(r)) for r in rows]
    finally:
        await db.close()
