"""Statistics routes — tournament-wide player and team stats."""

from fastapi import APIRouter, Query
from src.backend.database import get_db
from src.backend.tournament_auth import CANONICAL_ID

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/top-scorers")
async def top_scorers(limit: int = Query(20, ge=1, le=100), tournament_id: int = Query(CANONICAL_ID)):
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT p.id, p.name, p.country_code, c.flag as country_flag, p.position, p.photo, p.club,
                   SUM(pms.goals) as goals,
                   SUM(pms.assists) as assists,
                   COUNT(pms.id) as matches,
                   SUM(pms.minutes_played) as minutes
            FROM player_match_stats pms
            JOIN players p ON pms.player_id = p.id
            LEFT JOIN countries c ON c.code = p.country_code
            WHERE pms.tournament_id = $2 AND (pms.goals > 0 OR pms.assists > 0)
            GROUP BY p.id, c.flag
            ORDER BY goals DESC, assists DESC
            LIMIT $1
        """, (limit, tournament_id))
        return rows
    finally:
        await db.close()


@router.get("/top-assists")
async def top_assists(limit: int = Query(20, ge=1, le=100), tournament_id: int = Query(CANONICAL_ID)):
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT p.id, p.name, p.country_code, c.flag as country_flag, p.position, p.photo, p.club,
                   SUM(pms.assists) as assists,
                   SUM(pms.goals) as goals,
                   COUNT(pms.id) as matches,
                   SUM(pms.minutes_played) as minutes
            FROM player_match_stats pms
            JOIN players p ON pms.player_id = p.id
            LEFT JOIN countries c ON c.code = p.country_code
            WHERE pms.tournament_id = $2 AND pms.assists > 0
            GROUP BY p.id, c.flag
            ORDER BY assists DESC, goals DESC
            LIMIT $1
        """, (limit, tournament_id))
        return rows
    finally:
        await db.close()


@router.get("/top-rated")
async def top_rated(limit: int = Query(20, ge=1, le=100), tournament_id: int = Query(CANONICAL_ID)):
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT p.id, p.name, p.country_code, c.flag as country_flag, p.position, p.photo, p.club,
                   ROUND(AVG(pms.rating)::numeric, 2) as avg_rating,
                   COUNT(pms.id) as matches,
                   SUM(pms.goals) as goals,
                   SUM(pms.assists) as assists,
                   SUM(pms.minutes_played) as minutes
            FROM player_match_stats pms
            JOIN players p ON pms.player_id = p.id
            LEFT JOIN countries c ON c.code = p.country_code
            WHERE pms.tournament_id = $2 AND pms.minutes_played > 0
            GROUP BY p.id, c.flag
            HAVING COUNT(pms.id) >= 1
            ORDER BY avg_rating DESC
            LIMIT $1
        """, (limit, tournament_id))
        return rows
    finally:
        await db.close()


@router.get("/top-cards")
async def top_cards(limit: int = Query(20, ge=1, le=100), tournament_id: int = Query(CANONICAL_ID)):
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT p.id, p.name, p.country_code, c.flag as country_flag, p.position, p.photo, p.club,
                   SUM(pms.yellow_cards) as yellows,
                   SUM(CASE WHEN pms.red_card THEN 1 ELSE 0 END) as reds,
                   COUNT(pms.id) as matches,
                   SUM(pms.minutes_played) as minutes
            FROM player_match_stats pms
            JOIN players p ON pms.player_id = p.id
            LEFT JOIN countries c ON c.code = p.country_code
            WHERE pms.tournament_id = $2 AND (pms.yellow_cards > 0 OR pms.red_card = TRUE)
            GROUP BY p.id, c.flag
            ORDER BY reds DESC, yellows DESC
            LIMIT $1
        """, (limit, tournament_id))
        return rows
    finally:
        await db.close()


@router.get("/top-keepers")
async def top_keepers(limit: int = Query(20, ge=1, le=100), tournament_id: int = Query(CANONICAL_ID)):
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT p.id, p.name, p.country_code, c.flag as country_flag, p.photo, p.club,
                   COUNT(pms.id) as matches,
                   SUM(pms.saves) as saves,
                   SUM(pms.goals_conceded) as goals_conceded,
                   SUM(CASE WHEN pms.clean_sheet THEN 1 ELSE 0 END) as clean_sheets,
                   ROUND(AVG(pms.rating)::numeric, 2) as avg_rating,
                   SUM(pms.minutes_played) as minutes
            FROM player_match_stats pms
            JOIN players p ON pms.player_id = p.id
            LEFT JOIN countries c ON c.code = p.country_code
            WHERE p.position = 'GK' AND pms.minutes_played > 0 AND pms.tournament_id = $2
            GROUP BY p.id, c.flag
            HAVING COUNT(pms.id) >= 1
            ORDER BY clean_sheets DESC, saves DESC
            LIMIT $1
        """, (limit, tournament_id))
        return rows
    finally:
        await db.close()


@router.get("/team-stats")
async def team_stats(tournament_id: int = Query(CANONICAL_ID)):
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT c.code, c.name, c.flag,
                   COUNT(DISTINCT m.id) as matches_played,
                   SUM(CASE
                       WHEN (m.home_code = c.code AND m.score_home > m.score_away) OR
                            (m.away_code = c.code AND m.score_away > m.score_home) THEN 1
                       ELSE 0 END) as wins,
                   SUM(CASE
                       WHEN m.score_home = m.score_away AND m.penalty_home IS NULL THEN 1
                       ELSE 0 END) as draws,
                   SUM(CASE
                       WHEN (m.home_code = c.code AND m.score_home < m.score_away) OR
                            (m.away_code = c.code AND m.score_away < m.score_home) THEN 1
                       ELSE 0 END) as losses,
                   SUM(CASE WHEN m.home_code = c.code THEN m.score_home ELSE m.score_away END) as goals_for,
                   SUM(CASE WHEN m.home_code = c.code THEN m.score_away ELSE m.score_home END) as goals_against
            FROM countries c
            JOIN matches m ON (m.home_code = c.code OR m.away_code = c.code)
            WHERE m.status = 'finished' AND m.tournament_id = $1
            GROUP BY c.code, c.name, c.flag
            ORDER BY goals_for DESC
        """, (tournament_id,))
        return rows
    finally:
        await db.close()


@router.get("/player/{player_id}")
async def player_stats(player_id: str, tournament_id: int = Query(CANONICAL_ID)):
    """Get aggregated career stats for a player."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT
                COUNT(pms.id) as matches,
                SUM(pms.minutes_played) as minutes,
                SUM(CASE WHEN pms.is_starter THEN 1 ELSE 0 END) as starts,
                SUM(pms.goals) as goals,
                SUM(pms.assists) as assists,
                SUM(pms.yellow_cards) as yellows,
                SUM(CASE WHEN pms.red_card THEN 1 ELSE 0 END) as reds,
                SUM(pms.own_goals) as own_goals,
                SUM(pms.penalties_missed) as pens_missed,
                SUM(pms.penalties_saved) as pens_saved,
                SUM(pms.saves) as saves,
                SUM(pms.goals_conceded) as goals_conceded,
                SUM(CASE WHEN pms.clean_sheet THEN 1 ELSE 0 END) as clean_sheets,
                ROUND(AVG(pms.rating)::numeric, 2) as avg_rating
            FROM player_match_stats pms
            WHERE pms.player_id = $1 AND pms.tournament_id = $2
        """, (player_id, tournament_id))
        
        # Match-by-match breakdown
        history = await db.execute_fetchall("""
            SELECT pms.match_id, m.home_team, m.away_team, m.score_home, m.score_away,
                   m.home_code, m.away_code,
                   pms.minutes_played, pms.goals, pms.assists,
                   pms.yellow_cards, pms.red_card, pms.saves,
                   pms.goals_conceded, pms.clean_sheet, pms.rating, pms.is_starter
            FROM player_match_stats pms
            JOIN matches m ON pms.match_id = m.id AND pms.tournament_id = m.tournament_id
            WHERE pms.player_id = $1 AND pms.tournament_id = $2
            ORDER BY m.kickoff
        """, (player_id, tournament_id))
        
        summary = rows[0] if rows else {}
        return {"summary": summary, "matches": history}
    finally:
        await db.close()
