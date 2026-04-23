"""
Tournament engine — manages standings, bracket progression, and knockout draws.

FIFA World Cup 2026 format:
  - 48 teams in 12 groups of 4
  - Top 2 from each group + 8 best 3rd-place teams → Round of 32
  - R32 → R16 → QF → SF → Final
"""

from src.backend.database import get_db


async def recalculate_group_standings():
    """Recalculate all group standings from finished group-stage matches."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM group_standings")

        rows = await db.execute_fetchall(
            "SELECT code, group_letter FROM countries WHERE group_letter IS NOT NULL"
        )
        for row in rows:
            code, group = row["code"], row["group_letter"]
            await db.execute(
                """INSERT INTO group_standings (country_code, group_letter,
                   played, won, drawn, lost, goals_for, goals_against, points)
                   VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0)""",
                (code, group),
            )

        matches = await db.execute_fetchall("""
            SELECT m.home_code, m.away_code, m.score_home, m.score_away
            FROM matches m
            JOIN matchdays md ON m.matchday_id = md.id
            WHERE m.status = 'finished' AND md.phase = 'groups'
              AND m.home_code IS NOT NULL AND m.away_code IS NOT NULL
        """)

        for m in matches:
            h, a = m["home_code"], m["away_code"]
            sh, sa = m["score_home"], m["score_away"]

            if sh > sa:
                hp, ap, hw, hl, aw, al, hd, ad = 3, 0, 1, 0, 0, 1, 0, 0
            elif sh < sa:
                hp, ap, hw, hl, aw, al, hd, ad = 0, 3, 0, 1, 1, 0, 0, 0
            else:
                hp, ap, hw, hl, aw, al, hd, ad = 1, 1, 0, 0, 0, 0, 1, 1

            await db.execute("""
                UPDATE group_standings SET
                    played = played + 1, won = won + ?, drawn = drawn + ?,
                    lost = lost + ?, goals_for = goals_for + ?,
                    goals_against = goals_against + ?, points = points + ?
                WHERE country_code = ?
            """, (hw, hd, hl, sh, sa, hp, h))

            await db.execute("""
                UPDATE group_standings SET
                    played = played + 1, won = won + ?, drawn = drawn + ?,
                    lost = lost + ?, goals_for = goals_for + ?,
                    goals_against = goals_against + ?, points = points + ?
                WHERE country_code = ?
            """, (aw, ad, al, sa, sh, ap, a))

        await db.commit()
    finally:
        await db.close()


async def get_group_standings() -> dict[str, list[dict]]:
    """Get standings for all groups, sorted by points/GD/GF."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall("""
            SELECT gs.*, c.name as country_name, c.flag
            FROM group_standings gs
            JOIN countries c ON gs.country_code = c.code
            ORDER BY gs.group_letter,
                     gs.points DESC,
                     (gs.goals_for - gs.goals_against) DESC,
                     gs.goals_for DESC,
                     c.name ASC
        """)
        groups: dict[str, list[dict]] = {}
        for r in rows:
            g = r["group_letter"]
            groups.setdefault(g, []).append(dict(r))
        return groups
    finally:
        await db.close()


async def get_best_third_place_teams() -> list[str]:
    """
    Get the 8 best 3rd-place teams across all 12 groups.
    Sorted by points, then GD, then GF.
    """
    standings = await get_group_standings()
    thirds = []
    for group, teams in standings.items():
        if len(teams) >= 3:
            t = teams[2]  # 3rd place (0-indexed)
            thirds.append(t)

    # Sort by points desc, then GD desc, then GF desc
    thirds.sort(
        key=lambda t: (t["points"], t["goals_for"] - t["goals_against"], t["goals_for"]),
        reverse=True,
    )
    return [t["country_code"] for t in thirds[:8]]


def _get_winner(match: dict) -> str | None:
    """Get winner code from a finished match."""
    if match["score_home"] is None:
        return None
    if match["score_home"] > match["score_away"]:
        return match["home_code"]
    elif match["score_away"] > match["score_home"]:
        return match["away_code"]
    elif match["penalty_home"] is not None and match["penalty_away"] is not None:
        if match["penalty_home"] > match["penalty_away"]:
            return match["home_code"]
        else:
            return match["away_code"]
    return None


async def resolve_r32_bracket():
    """
    Resolve the Round of 32 bracket by filling in the actual teams
    based on group standings. The R32 matches already exist from the
    calendar with placeholder names like "1A", "2B", "3ABCDF".
    This function resolves those to actual country codes.
    """
    standings = await get_group_standings()
    best_thirds = await get_best_third_place_teams()

    def get_nth(group: str, pos: int) -> str | None:
        teams = standings.get(group, [])
        return teams[pos]["country_code"] if len(teams) > pos else None

    # Build resolver for bracket references
    # "1A" = 1st in group A, "2B" = 2nd in group B
    # "3ABCDF" = best 3rd from groups A,B,C,D,F (FIFA decides which one)
    resolver: dict[str, str | None] = {}
    for letter in "ABCDEFGHIJKL":
        resolver[f"1{letter}"] = get_nth(letter, 0)
        resolver[f"2{letter}"] = get_nth(letter, 1)

    # For 3rd-place references, assign best available thirds
    # The actual FIFA matching is complex; we simplify by assigning in order
    third_pool = list(best_thirds)

    db = await get_db()
    try:
        r32_matches = await db.execute_fetchall("""
            SELECT m.id, m.home_team, m.away_team
            FROM matches m WHERE m.matchday_id = 'R32'
            ORDER BY m.match_number ASC
        """)

        resolved = []
        for m in r32_matches:
            home_ref = m["home_team"]
            away_ref = m["away_team"]

            home_code = resolver.get(home_ref)
            away_code = None

            if away_ref in resolver:
                away_code = resolver[away_ref]
            elif away_ref.startswith("3") and third_pool:
                # 3rd-place team — assign next available from pool
                away_code = third_pool.pop(0)

            # Also try home as 3rd place
            if home_code is None and home_ref.startswith("3") and third_pool:
                home_code = third_pool.pop(0)

            if home_code and away_code:
                # Look up team names
                home_row = await db.execute_fetchall(
                    "SELECT name FROM countries WHERE code = ?", (home_code,)
                )
                away_row = await db.execute_fetchall(
                    "SELECT name FROM countries WHERE code = ?", (away_code,)
                )
                home_name = home_row[0]["name"] if home_row else home_ref
                away_name = away_row[0]["name"] if away_row else away_ref

                await db.execute("""
                    UPDATE matches SET home_code = ?, away_code = ?,
                        home_team = ?, away_team = ?
                    WHERE id = ?
                """, (home_code, away_code, home_name, away_name, m["id"]))
                resolved.append({
                    "id": m["id"], "home": home_code, "away": away_code,
                    "home_name": home_name, "away_name": away_name,
                })

        await db.commit()
        return resolved
    finally:
        await db.close()


async def resolve_knockout_round(current_phase: str):
    """
    Fill in the next knockout round's teams from the current round's winners.
    The matchday and match slots already exist in the calendar.

    Phase progression: r32 → r16 → quarter → semi → final
    For semi → final: losers go to 3rd place match (first slot), winners to final (second slot).
    """
    phase_to_next_matchday = {
        "r32": "R16",
        "r16": "QF",
        "quarter": "SF",
        "semi": "FINAL",
    }

    next_matchday_id = phase_to_next_matchday.get(current_phase)
    if not next_matchday_id:
        return []

    db = await get_db()
    try:
        # Get finished matches of current phase ordered by match number
        matches = await db.execute_fetchall("""
            SELECT m.id, m.home_code, m.away_code, m.match_number,
                   m.score_home, m.score_away,
                   m.penalty_home, m.penalty_away
            FROM matches m
            JOIN matchdays md ON m.matchday_id = md.id
            WHERE md.phase = ? AND m.status = 'finished'
            ORDER BY m.match_number ASC
        """, (current_phase,))

        # Get next round match slots
        next_matches = await db.execute_fetchall("""
            SELECT id, match_number FROM matches
            WHERE matchday_id = ?
            ORDER BY match_number ASC
        """, (next_matchday_id,))

        if current_phase == "semi":
            # Special handling: slot 0 = 3rd place (losers), slot 1 = final (winners)
            winners = []
            losers = []
            for m in matches:
                w = _get_winner(m)
                if w:
                    winners.append(w)
                    loser = m["away_code"] if w == m["home_code"] else m["home_code"]
                    losers.append(loser)

            pairings = []
            if len(losers) >= 2 and len(next_matches) >= 1:
                pairings.append((losers[0], losers[1]))      # 3rd place match
            if len(winners) >= 2 and len(next_matches) >= 2:
                pairings.append((winners[0], winners[1]))     # Final
        else:
            winners = []
            for m in matches:
                w = _get_winner(m)
                if w:
                    winners.append(w)

            if len(winners) < 2:
                return []

            # Pair winners: 1v2, 3v4, etc.
            pairings = [(winners[i], winners[i + 1])
                        for i in range(0, len(winners) - 1, 2)]

        resolved = []
        for i, (home_code, away_code) in enumerate(pairings):
            if i >= len(next_matches):
                break

            match_id = next_matches[i]["id"]

            home_row = await db.execute_fetchall(
                "SELECT name FROM countries WHERE code = ?", (home_code,)
            )
            away_row = await db.execute_fetchall(
                "SELECT name FROM countries WHERE code = ?", (away_code,)
            )
            home_name = home_row[0]["name"] if home_row else home_code
            away_name = away_row[0]["name"] if away_row else away_code

            await db.execute("""
                UPDATE matches SET home_code = ?, away_code = ?,
                    home_team = ?, away_team = ?
                WHERE id = ?
            """, (home_code, away_code, home_name, away_name, match_id))
            resolved.append({
                "id": match_id, "home": home_code, "away": away_code,
                "home_name": home_name, "away_name": away_name,
            })

        await db.commit()
        return resolved
    finally:
        await db.close()
