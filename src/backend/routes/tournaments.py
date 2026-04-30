"""Tournament routes — CRUD, fork, admin auth for tournaments."""

from fastapi import APIRouter, HTTPException, Request
from src.backend.database import get_db
from src.backend.config import ADMIN_KEY
from src.backend.models import TournamentCreate, TournamentOut, TournamentCreatedOut
from src.backend.tournament_auth import (
    CANONICAL_ID, hash_token, generate_slug, generate_manage_token,
    require_tournament_write,
)

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.get("", response_model=list[TournamentOut])
async def list_tournaments():
    """List all public and unlisted tournaments."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT t.*,
                   COALESCE(mp.matches_played, 0) as matches_played,
                   COALESCE(mt.total_matches, 0) as total_matches,
                   cp.current_phase
            FROM tournaments t
            LEFT JOIN (
                SELECT tournament_id, COUNT(*) as matches_played
                FROM matches WHERE status = 'finished'
                GROUP BY tournament_id
            ) mp ON mp.tournament_id = t.id
            LEFT JOIN (
                SELECT tournament_id, COUNT(*) as total_matches
                FROM matches GROUP BY tournament_id
            ) mt ON mt.tournament_id = t.id
            LEFT JOIN LATERAL (
                SELECT md.phase as current_phase
                FROM matchdays md
                JOIN matches m ON m.matchday_id = md.id AND m.tournament_id = md.tournament_id
                WHERE md.tournament_id = t.id AND m.status != 'finished'
                ORDER BY md.date ASC LIMIT 1
            ) cp ON TRUE
            WHERE t.status = 'active' AND t.visibility IN ('public', 'unlisted')
            ORDER BY t.is_canonical DESC, t.created_at DESC
        """)
        return [TournamentOut(
            id=r["id"], slug=r["slug"], name=r["name"],
            owner_name=r["owner_name"] or "",
            is_canonical=r["is_canonical"],
            visibility=r["visibility"],
            forked_from=r["forked_from"],
            status=r["status"],
            created_at=str(r["created_at"]) if r["created_at"] else None,
            current_phase=r["current_phase"] or "groups",
            matches_played=r["matches_played"],
            total_matches=r["total_matches"],
        ) for r in rows]
    finally:
        await db.close()


@router.get("/{slug}", response_model=TournamentOut)
async def get_tournament(slug: str):
    """Get tournament details by slug."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT t.*,
                   COALESCE(mp.matches_played, 0) as matches_played,
                   COALESCE(mt.total_matches, 0) as total_matches
            FROM tournaments t
            LEFT JOIN (
                SELECT tournament_id, COUNT(*) as matches_played
                FROM matches WHERE status = 'finished'
                GROUP BY tournament_id
            ) mp ON mp.tournament_id = t.id
            LEFT JOIN (
                SELECT tournament_id, COUNT(*) as total_matches
                FROM matches GROUP BY tournament_id
            ) mt ON mt.tournament_id = t.id
            WHERE t.slug = $1
        """, (slug,))
        if not rows:
            raise HTTPException(404, "Tournament not found")
        r = rows[0]
        return TournamentOut(
            id=r["id"], slug=r["slug"], name=r["name"],
            owner_name=r["owner_name"] or "",
            is_canonical=r["is_canonical"],
            visibility=r["visibility"],
            forked_from=r["forked_from"],
            status=r["status"],
            created_at=str(r["created_at"]) if r["created_at"] else None,
            matches_played=r["matches_played"],
            total_matches=r["total_matches"],
        )
    finally:
        await db.close()


@router.post("", response_model=TournamentCreatedOut)
async def create_tournament(data: TournamentCreate):
    """Create a new tournament, optionally forking from an existing one."""
    slug = generate_slug()
    token = generate_manage_token()
    token_hash = hash_token(token)

    db = await get_db()
    try:
        # Check slug collision (extremely unlikely but be safe)
        exists = await db.execute_fetchall(
            "SELECT id FROM tournaments WHERE slug = $1", (slug,)
        )
        if exists:
            slug = generate_slug(10)

        forked_from_id = None

        if data.fork_from_slug:
            # Find source tournament
            source = await db.execute_fetchall(
                "SELECT id FROM tournaments WHERE slug = $1 AND status = 'active'",
                (data.fork_from_slug,),
            )
            if not source:
                raise HTTPException(404, "Source tournament not found")
            forked_from_id = source[0]["id"]

        # Create tournament
        row = await db.execute_fetchall("""
            INSERT INTO tournaments (slug, name, owner_name, manage_token_hash, visibility, forked_from)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, slug, name, owner_name, is_canonical, visibility, forked_from, status, created_at
        """, (slug, data.name, data.owner_name, token_hash, data.visibility, forked_from_id))
        await db.commit()

        new_id = row[0]["id"]

        if forked_from_id:
            # Fork data from source tournament
            await _fork_tournament_data(forked_from_id, new_id)
        else:
            # Copy calendar from canonical (fresh tournament)
            await _fork_tournament_data(CANONICAL_ID, new_id, calendar_only=True)

        r = row[0]
        return TournamentCreatedOut(
            id=r["id"], slug=r["slug"], name=r["name"],
            owner_name=r["owner_name"] or "",
            is_canonical=r["is_canonical"],
            visibility=r["visibility"],
            forked_from=r["forked_from"],
            status=r["status"],
            created_at=str(r["created_at"]) if r["created_at"] else None,
            manage_token=token,
            matches_played=0,
            total_matches=0,
        )
    finally:
        await db.close()


@router.delete("/{slug}")
async def delete_tournament(slug: str, request: Request):
    """Delete a tournament. Requires manage token."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT id, is_canonical FROM tournaments WHERE slug = $1", (slug,)
        )
        if not rows:
            raise HTTPException(404, "Tournament not found")
        if rows[0]["is_canonical"]:
            raise HTTPException(403, "Cannot delete canonical tournament")

        tid = rows[0]["id"]
        await require_tournament_write(request, tid)

        # CASCADE deletes all related data
        await db.execute("DELETE FROM tournaments WHERE id = $1", (tid,))
        await db.commit()
        return {"status": "deleted", "slug": slug}
    finally:
        await db.close()


@router.post("/{slug}/verify-token")
async def verify_token(slug: str, request: Request):
    """Verify a manage token for a tournament. Used by frontend to check ownership."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT id FROM tournaments WHERE slug = $1", (slug,)
        )
        if not rows:
            raise HTTPException(404, "Tournament not found")

        tid = rows[0]["id"]
        try:
            await require_tournament_write(request, tid)
            return {"valid": True}
        except HTTPException:
            return {"valid": False}
    finally:
        await db.close()


async def _fork_tournament_data(source_id: int, target_id: int, calendar_only: bool = False):
    """Copy tournament state from source to target.
    
    If calendar_only=True, copies only matchdays and matches (blank calendar).
    If False, copies everything including results, squads, standings, and stats.
    """
    db = await get_db()
    try:
        # Copy matchdays
        await db.execute("""
            INSERT INTO matchdays (id, tournament_id, name, phase, date, status)
            SELECT id, $2, name, phase, date,
                   CASE WHEN $3 THEN 'scheduled' ELSE status END
            FROM matchdays WHERE tournament_id = $1
        """, (source_id, target_id, calendar_only))

        # Copy matches
        if calendar_only:
            # Reset results for fresh tournament
            await db.execute("""
                INSERT INTO matches (id, tournament_id, matchday_id, match_number,
                    home_team, away_team, home_code, away_code, kickoff, location,
                    group_name, status, is_simulated)
                SELECT id, $2, matchday_id, match_number,
                    home_team, away_team, home_code, away_code, kickoff, location,
                    group_name, 'scheduled', FALSE
                FROM matches WHERE tournament_id = $1
            """, (source_id, target_id))
        else:
            # Full fork: copy results too
            await db.execute("""
                INSERT INTO matches (id, tournament_id, matchday_id, match_number,
                    home_team, away_team, home_code, away_code, kickoff, location,
                    group_name, score_home, score_away, penalty_home, penalty_away,
                    status, is_simulated)
                SELECT id, $2, matchday_id, match_number,
                    home_team, away_team, home_code, away_code, kickoff, location,
                    group_name, score_home, score_away, penalty_home, penalty_away,
                    status, is_simulated
                FROM matches WHERE tournament_id = $1
            """, (source_id, target_id))

            # Copy player match stats
            await db.execute("""
                INSERT INTO player_match_stats (tournament_id, player_id, match_id,
                    minutes_played, goals, assists, yellow_cards, red_card,
                    own_goals, penalties_missed, penalties_saved, saves,
                    goals_conceded, clean_sheet, rating, is_starter)
                SELECT $2, player_id, match_id,
                    minutes_played, goals, assists, yellow_cards, red_card,
                    own_goals, penalties_missed, penalties_saved, saves,
                    goals_conceded, clean_sheet, rating, is_starter
                FROM player_match_stats WHERE tournament_id = $1
            """, (source_id, target_id))

            # Copy group standings
            await db.execute("""
                INSERT INTO group_standings (country_code, tournament_id, group_letter,
                    played, won, drawn, lost, goals_for, goals_against, points)
                SELECT country_code, $2, group_letter,
                    played, won, drawn, lost, goals_for, goals_against, points
                FROM group_standings WHERE tournament_id = $1
            """, (source_id, target_id))

        # Copy squad selections (always copy, they're part of setup)
        await db.execute("""
            INSERT INTO squad_selections (country_code, player_id, tournament_id)
            SELECT country_code, player_id, $2
            FROM squad_selections WHERE tournament_id = $1
        """, (source_id, target_id))

        # Copy squad stats
        await db.execute("""
            INSERT INTO squad_stats (country_code, tournament_id, squad_size,
                gk, defs, mids, fwds, avg_strength, total_value)
            SELECT country_code, $2, squad_size,
                gk, defs, mids, fwds, avg_strength, total_value
            FROM squad_stats WHERE tournament_id = $1
        """, (source_id, target_id))

        await db.commit()
    finally:
        await db.close()
