"""Simulation routes — run simulations on matches or full tournament."""

from fastapi import APIRouter, HTTPException, Query, Request
from src.backend.database import get_db
from src.backend.models import SimulateMatchesIn, MatchOut
from src.backend.services.simulation_engine import simulate_match
from src.backend.services.tournament_engine import (
    recalculate_group_standings,
    resolve_r32_bracket,
    resolve_knockout_round,
)
from src.backend.tournament_auth import CANONICAL_ID, require_tournament_write

router = APIRouter(prefix="/simulate", tags=["simulation"])


@router.post("/matches", response_model=list[MatchOut])
async def simulate_matches(
    data: SimulateMatchesIn,
    request: Request,
    tournament_id: int = Query(CANONICAL_ID),
):
    """
    Simulate specific matches or all scheduled matches in a phase.
    This writes simulated results into the main DB (is_simulated=1).
    """
    await require_tournament_write(request, tournament_id)
    db = await get_db()
    try:
        # Determine which matches to simulate
        if data.match_ids:
            placeholders = ",".join(f"${i+2}" for i in range(len(data.match_ids)))
            matches = await db.execute_fetchall(
                f"SELECT * FROM matches WHERE tournament_id = $1 AND id IN ({placeholders}) AND status = 'scheduled'",
                [tournament_id, *data.match_ids],
            )
        elif data.matchday_id:
            matches = await db.execute_fetchall(
                "SELECT * FROM matches WHERE tournament_id = $1 AND matchday_id = $2 AND status = 'scheduled'",
                (tournament_id, data.matchday_id),
            )
        elif data.phase:
            matches = await db.execute_fetchall("""
                SELECT m.* FROM matches m
                JOIN matchdays md ON m.matchday_id = md.id AND m.tournament_id = md.tournament_id
                WHERE md.phase = $1 AND m.status = 'scheduled' AND m.tournament_id = $2
            """, (data.phase, tournament_id))
        else:
            raise HTTPException(400, "Provide match_ids, matchday_id, or phase")

        if not matches:
            raise HTTPException(404, "No scheduled matches found")

        # Filter out matches without resolved teams (knockout placeholders)
        simulatable = [m for m in matches if m["home_code"] and m["away_code"]]
        if not simulatable:
            raise HTTPException(400, "No matches with resolved teams to simulate. Resolve bracket first.")

        results = []
        for match in simulatable:
            home_code = match["home_code"]
            away_code = match["away_code"]

            # Use squad if available, otherwise all players (engine will auto-select 26)
            for code, label in [(home_code, "home"), (away_code, "away")]:
                has_squad = await db.execute_fetchall(
                    "SELECT COUNT(*) as c FROM squad_selections WHERE country_code = $1 AND tournament_id = $2",
                    (code, tournament_id)
                )
                if has_squad[0]["c"] > 0:
                    rows = await db.execute_fetchall("""
                        SELECT p.id, p.name, p.position, p.strength, p.country_code
                        FROM players p JOIN squad_selections s ON s.player_id = p.id
                        WHERE s.country_code = $1 AND s.tournament_id = $2
                    """, (code, tournament_id))
                else:
                    rows = await db.execute_fetchall(
                        "SELECT id, name, position, strength, country_code FROM players WHERE country_code = $1",
                        (code,),
                    )
                if label == "home":
                    home_players = rows
                else:
                    away_players = rows

            home_list = [dict(p) for p in home_players]
            away_list = [dict(p) for p in away_players]

            # Determine if knockout
            md = await db.execute_fetchall(
                "SELECT phase FROM matchdays WHERE id = $1 AND tournament_id = $2",
                (match["matchday_id"], tournament_id)
            )
            is_knockout = md[0]["phase"] != "groups" if md else False

            sim = simulate_match(home_list, away_list, is_knockout=is_knockout)

            # Update match result
            await db.execute("""
                UPDATE matches SET
                    score_home = $1, score_away = $2,
                    penalty_home = $3, penalty_away = $4,
                    status = 'finished', is_simulated = TRUE
                WHERE id = $5 AND tournament_id = $6
            """, (sim.score_home, sim.score_away,
                  sim.penalty_home, sim.penalty_away, match["id"], tournament_id))

            # Store player stats
            all_stats = sim.home_stats + sim.away_stats
            for s in all_stats:
                await db.execute("""
                    INSERT INTO player_match_stats
                        (tournament_id, player_id, match_id, minutes_played, goals, assists,
                         yellow_cards, red_card, own_goals, penalties_missed,
                         penalties_saved, saves, goals_conceded, clean_sheet,
                         rating, is_starter)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                    ON CONFLICT(player_id, match_id, tournament_id) DO UPDATE SET
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
                """, (tournament_id, s.player_id, match["id"], s.minutes_played, s.goals,
                      s.assists, s.yellow_cards, s.red_card, s.own_goals,
                      s.penalties_missed, s.penalties_saved, s.saves,
                      s.goals_conceded, s.clean_sheet, s.rating, s.is_starter))

            results.append(match["id"])

        await db.commit()

        # Recalculate standings
        await recalculate_group_standings(tournament_id)

        # Return updated matches
        placeholders = ",".join(f"${i+2}" for i in range(len(results)))
        updated = await db.execute_fetchall(f"""
            SELECT m.*, h.flag as home_flag, a.flag as away_flag
            FROM matches m
            LEFT JOIN countries h ON m.home_code = h.code
            LEFT JOIN countries a ON m.away_code = a.code
            WHERE m.tournament_id = $1 AND m.id IN ({placeholders})
            ORDER BY m.kickoff
        """, [tournament_id, *results])
        return [MatchOut(**dict(m)) for m in updated]
    finally:
        await db.close()


@router.post("/matchday/{matchday_id}", response_model=list[MatchOut])
async def simulate_matchday(matchday_id: str, request: Request, tournament_id: int = Query(CANONICAL_ID)):
    """Simulate all scheduled matches in a specific matchday (GS1, GS2, GS3, R32, etc.)."""
    return await simulate_matches(SimulateMatchesIn(matchday_id=matchday_id), request, tournament_id)


@router.post("/next-match", response_model=list[MatchOut])
async def simulate_next_match(request: Request, tournament_id: int = Query(CANONICAL_ID)):
    """Simulate the next scheduled match (by kickoff order)."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT m.id FROM matches m
            WHERE m.tournament_id = $1 AND m.status = 'scheduled'
              AND m.home_code IS NOT NULL AND m.away_code IS NOT NULL
            ORDER BY m.kickoff ASC, m.match_number ASC
            LIMIT 1
        """, (tournament_id,))
        if not rows:
            raise HTTPException(404, "No scheduled matches with resolved teams")
        match_id = rows[0]["id"]
    finally:
        await db.close()
    
    return await simulate_matches(SimulateMatchesIn(match_ids=[match_id]), request, tournament_id)


@router.post("/group-stage", response_model=list[MatchOut])
async def simulate_group_stage(request: Request, tournament_id: int = Query(CANONICAL_ID)):
    """Simulate all remaining group stage matches."""
    return await simulate_matches(SimulateMatchesIn(phase="groups"), request, tournament_id)


@router.post("/generate-bracket")
async def generate_bracket(request: Request, tournament_id: int = Query(CANONICAL_ID)):
    """
    Resolve R32 bracket from group standings (top 2 + best 8 thirds).
    Call after group stage is complete.
    """
    await require_tournament_write(request, tournament_id)
    resolved = await resolve_r32_bracket(tournament_id)
    return {"r32_matches": resolved, "count": len(resolved)}


@router.post("/knockout-round/{phase}")
async def simulate_knockout_round(phase: str, request: Request, tournament_id: int = Query(CANONICAL_ID)):
    """
    Simulate all matches in a knockout phase and resolve the next round.
    Phases: r32, r16, quarter, semi, final
    """
    if phase not in ("r32", "r16", "quarter", "semi", "final"):
        raise HTTPException(400, "Invalid phase. Use: r32, r16, quarter, semi, final")

    # Simulate all matches in this phase
    result = await simulate_matches(SimulateMatchesIn(phase=phase), request, tournament_id)

    # Resolve next round if not final
    next_round = []
    if phase != "final":
        next_round = await resolve_knockout_round(phase, tournament_id)

    return {
        "simulated_matches": [m.model_dump() for m in result],
        "next_round": next_round,
    }


@router.post("/full-tournament")
async def simulate_full_tournament(request: Request, tournament_id: int = Query(CANONICAL_ID)):
    """Simulate the entire remaining tournament from current state."""
    await require_tournament_write(request, tournament_id)
    results = {}

    # 1. Simulate group stage by matchday
    for gs_id in ("GS1", "GS2", "GS3"):
        db = await get_db()
        try:
            remaining = await db.execute_fetchall(
                "SELECT COUNT(*) as c FROM matches WHERE tournament_id = $1 AND matchday_id = $2 AND status = 'scheduled'",
                (tournament_id, gs_id),
            )
        finally:
            await db.close()
        if remaining[0]["c"] > 0:
            try:
                gs_results = await simulate_matches(SimulateMatchesIn(matchday_id=gs_id), request, tournament_id)
                results[gs_id] = len(gs_results)
            except HTTPException:
                pass

    # 2. Resolve R32 bracket
    r32 = await resolve_r32_bracket(tournament_id)
    results["r32_resolved"] = len(r32)

    # 3. Simulate through each knockout phase
    knockout_phases = [
        ("r32", "r32"),
        ("r16", "r16"),
        ("quarter", "qf"),
        ("semi", "sf"),
        ("final", "final"),
    ]
    for phase, key in knockout_phases:
        try:
            phase_results = await simulate_matches(SimulateMatchesIn(phase=phase), request, tournament_id)
            results[f"{key}_simulated"] = len(phase_results)
        except HTTPException:
            break

        if phase != "final":
            resolved = await resolve_knockout_round(phase, tournament_id)
            results[f"{key}_next_resolved"] = len(resolved)
            if not resolved:
                break

    return {"status": "completed", "summary": results}


@router.post("/reset")
async def reset_simulation(request: Request, tournament_id: int = Query(CANONICAL_ID)):
    """Reset all simulated results, keeping real (non-simulated) results."""
    await require_tournament_write(request, tournament_id)
    db = await get_db()
    try:
        # Delete stats for simulated matches
        await db.execute("""
            DELETE FROM player_match_stats WHERE tournament_id = $1 AND match_id IN (
                SELECT id FROM matches WHERE tournament_id = $1 AND is_simulated = TRUE
            )
        """, (tournament_id,))

        # Reset simulated matches to scheduled
        await db.execute("""
            UPDATE matches SET
                score_home = NULL, score_away = NULL,
                penalty_home = NULL, penalty_away = NULL,
                status = 'scheduled', is_simulated = FALSE
            WHERE tournament_id = $1 AND is_simulated = TRUE
        """, (tournament_id,))

        # Reset knockout matches back to placeholder names
        # (re-import from calendar would be cleaner but this is simpler)
        import json, os
        from src.backend.config import TOURNAMENT_DATA_DIR
        cal_path = os.path.join(TOURNAMENT_DATA_DIR, "calendar.json")
        if os.path.exists(cal_path):
            with open(cal_path, "r", encoding="utf-8") as f:
                cal = json.load(f)
            for md in cal:
                if md["phase"] == "groups":
                    continue
                for m in md.get("matches", []):
                    await db.execute("""
                        UPDATE matches SET
                            home_team = $1, away_team = $2,
                            home_code = NULL, away_code = NULL
                        WHERE id = $3 AND tournament_id = $4
                    """, (m["home"], m["away"], m["id"], tournament_id))

        await db.commit()
        await recalculate_group_standings(tournament_id)

        return {"status": "reset", "message": "Simulated results cleared"}
    finally:
        await db.close()
