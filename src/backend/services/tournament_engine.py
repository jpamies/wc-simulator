"""
Tournament engine — manages standings, bracket progression, and knockout draws.

FIFA World Cup 2026 format:
  - 48 teams in 12 groups of 4
  - Top 2 from each group + 8 best 3rd-place teams → Round of 32
  - R32 → R16 → QF → SF → 3rd place + Final

Bracket is deterministic (FIFA rules):
  - R32 match slots are predefined (1A vs 2B, 1E vs 3rd, etc.)
  - 3rd-place assignment depends on which 8 of 12 groups qualify
  - R16/QF/SF/Final follow fixed winner-of-match pairings
"""

from src.backend.database import get_db


# ---------------------------------------------------------------------------
# FIFA bracket definitions
# ---------------------------------------------------------------------------

# R32 match slots: match_id → (home_ref, away_ref)
# home_ref/away_ref are "1A", "2B", "3ABCDF", etc. from calendar.json.

# R16 bracket: match_id → (home = winner of match X, away = winner of match Y)
R16_BRACKET = {
    "M89": ("M74", "M77"),
    "M90": ("M73", "M75"),
    "M91": ("M76", "M78"),
    "M92": ("M79", "M80"),
    "M93": ("M83", "M84"),
    "M94": ("M81", "M82"),
    "M95": ("M86", "M88"),
    "M96": ("M85", "M87"),
}

# QF bracket
QF_BRACKET = {
    "M97": ("M89", "M90"),
    "M98": ("M93", "M94"),
    "M99": ("M91", "M92"),
    "M100": ("M95", "M96"),
}

# SF bracket
SF_BRACKET = {
    "M101": ("M97", "M98"),
    "M102": ("M99", "M100"),
}

# 3rd place match (losers of semis)
THIRD_PLACE = {
    "M103": ("M101", "M102"),  # losers
}

# Final (winners of semis)
FINAL_BRACKET = {
    "M104": ("M101", "M102"),  # winners
}

# 3rd-place slot eligible groups (from calendar references)
# M74 away = "3ABCDF" means the 3rd-place team from one of groups A,B,C,D,F
THIRD_PLACE_SLOTS = {
    "M74": set("ABCDF"),
    "M77": set("CDFGH"),
    "M79": set("CEFHI"),
    "M80": set("EHIJK"),
    "M81": set("BEFIJ"),
    "M82": set("AEHIJ"),
    "M85": set("EFGIJ"),
    "M87": set("DEIJL"),
}


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
    based on group standings.

    R32 matches already exist from the calendar with placeholder names
    like "1A", "2B", "3ABCDF". This function resolves those to actual
    country codes using group standings + FIFA 3rd-place assignment rules.
    """
    standings = await get_group_standings()
    best_thirds = await get_best_third_place_teams()

    def get_nth(group: str, pos: int) -> str | None:
        teams = standings.get(group, [])
        return teams[pos]["country_code"] if len(teams) > pos else None

    # Build resolver for 1st and 2nd place references
    resolver: dict[str, str | None] = {}
    for letter in "ABCDEFGHIJKL":
        resolver[f"1{letter}"] = get_nth(letter, 0)
        resolver[f"2{letter}"] = get_nth(letter, 1)

    # Determine which groups' 3rd-place teams qualified
    qualifying_groups = set()
    third_by_group: dict[str, str] = {}  # group_letter → country_code
    for code in best_thirds:
        for group, teams in standings.items():
            if len(teams) >= 3 and teams[2]["country_code"] == code:
                qualifying_groups.add(group)
                third_by_group[group] = code
                break

    # Assign 3rd-place teams to R32 slots using constraint satisfaction
    # Each slot has eligible groups; we must find a valid assignment
    third_assignment = _assign_third_place_teams(qualifying_groups, third_by_group)

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

            # Resolve home
            if home_ref in resolver:
                home_code = resolver[home_ref]
            elif home_ref.startswith("3"):
                home_code = third_assignment.get(m["id"])
            else:
                home_code = None

            # Resolve away
            if away_ref in resolver:
                away_code = resolver[away_ref]
            elif away_ref.startswith("3"):
                away_code = third_assignment.get(m["id"])
            else:
                away_code = None

            if home_code and away_code:
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


def _assign_third_place_teams(
    qualifying_groups: set[str],
    third_by_group: dict[str, str],
) -> dict[str, str]:
    """
    Assign qualifying 3rd-place teams to R32 match slots using
    backtracking constraint satisfaction.

    Each slot (match ID) can only receive a 3rd from its eligible groups.
    Each 3rd-place team can only be used once.

    Returns dict of match_id → country_code.
    """
    slots = list(THIRD_PLACE_SLOTS.keys())
    assignment: dict[str, str] = {}
    used_groups: set[str] = set()

    # Sort slots by number of eligible qualifying groups (most constrained first)
    def eligible_count(slot: str) -> int:
        return len(THIRD_PLACE_SLOTS[slot] & qualifying_groups - used_groups)

    def backtrack(idx: int) -> bool:
        if idx == len(slots):
            return True
        # Re-sort remaining slots by most constrained
        remaining = slots[idx:]
        remaining.sort(key=eligible_count)
        slots[idx:] = remaining

        slot = slots[idx]
        eligible = THIRD_PLACE_SLOTS[slot] & qualifying_groups - used_groups
        for group in sorted(eligible):
            used_groups.add(group)
            assignment[slot] = third_by_group[group]
            if backtrack(idx + 1):
                return True
            used_groups.discard(group)
            del assignment[slot]
        return False

    backtrack(0)
    return assignment


async def resolve_knockout_round(current_phase: str):
    """
    Fill in the next knockout round's teams based on the FIFA bracket.

    Uses the fixed bracket mappings (R16_BRACKET, QF_BRACKET, etc.)
    to determine which winners/losers feed into which match slots.

    Phase progression: r32 → r16 → quarter → semi → final
    """
    if current_phase == "r32":
        bracket = R16_BRACKET
        use_winners = True
    elif current_phase == "r16":
        bracket = QF_BRACKET
        use_winners = True
    elif current_phase == "quarter":
        bracket = SF_BRACKET
        use_winners = True
    elif current_phase == "semi":
        # Semi produces both 3rd place match (losers) and final (winners)
        return await _resolve_semi_to_final()
    else:
        return []

    db = await get_db()
    try:
        resolved = []
        for next_match_id, (source_a_id, source_b_id) in bracket.items():
            # Get source matches
            source_a = await db.execute_fetchall(
                "SELECT * FROM matches WHERE id = ?", (source_a_id,)
            )
            source_b = await db.execute_fetchall(
                "SELECT * FROM matches WHERE id = ?", (source_b_id,)
            )
            if not source_a or not source_b:
                continue

            home_code = _get_winner(dict(source_a[0]))
            away_code = _get_winner(dict(source_b[0]))

            if not home_code or not away_code:
                continue

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
            """, (home_code, away_code, home_name, away_name, next_match_id))
            resolved.append({
                "id": next_match_id, "home": home_code, "away": away_code,
                "home_name": home_name, "away_name": away_name,
            })

        await db.commit()
        return resolved
    finally:
        await db.close()


async def _resolve_semi_to_final():
    """
    After semis: losers → 3rd place match (M103), winners → final (M104).
    """
    db = await get_db()
    try:
        resolved = []

        # 3rd place match: losers of M101 and M102
        for next_match_id, (src_a_id, src_b_id) in THIRD_PLACE.items():
            src_a = await db.execute_fetchall("SELECT * FROM matches WHERE id = ?", (src_a_id,))
            src_b = await db.execute_fetchall("SELECT * FROM matches WHERE id = ?", (src_b_id,))
            if not src_a or not src_b:
                continue
            a, b = dict(src_a[0]), dict(src_b[0])
            wa, wb = _get_winner(a), _get_winner(b)
            if not wa or not wb:
                continue
            # Losers
            home_code = a["away_code"] if wa == a["home_code"] else a["home_code"]
            away_code = b["away_code"] if wb == b["home_code"] else b["home_code"]

            home_row = await db.execute_fetchall("SELECT name FROM countries WHERE code = ?", (home_code,))
            away_row = await db.execute_fetchall("SELECT name FROM countries WHERE code = ?", (away_code,))
            home_name = home_row[0]["name"] if home_row else home_code
            away_name = away_row[0]["name"] if away_row else away_code

            await db.execute("""
                UPDATE matches SET home_code = ?, away_code = ?, home_team = ?, away_team = ? WHERE id = ?
            """, (home_code, away_code, home_name, away_name, next_match_id))
            resolved.append({"id": next_match_id, "home": home_code, "away": away_code,
                             "home_name": home_name, "away_name": away_name})

        # Final: winners of M101 and M102
        for next_match_id, (src_a_id, src_b_id) in FINAL_BRACKET.items():
            src_a = await db.execute_fetchall("SELECT * FROM matches WHERE id = ?", (src_a_id,))
            src_b = await db.execute_fetchall("SELECT * FROM matches WHERE id = ?", (src_b_id,))
            if not src_a or not src_b:
                continue
            wa = _get_winner(dict(src_a[0]))
            wb = _get_winner(dict(src_b[0]))
            if not wa or not wb:
                continue

            home_row = await db.execute_fetchall("SELECT name FROM countries WHERE code = ?", (wa,))
            away_row = await db.execute_fetchall("SELECT name FROM countries WHERE code = ?", (wb,))
            home_name = home_row[0]["name"] if home_row else wa
            away_name = away_row[0]["name"] if away_row else wb

            await db.execute("""
                UPDATE matches SET home_code = ?, away_code = ?, home_team = ?, away_team = ? WHERE id = ?
            """, (wa, wb, home_name, away_name, next_match_id))
            resolved.append({"id": next_match_id, "home": wa, "away": wb,
                             "home_name": home_name, "away_name": away_name})

        await db.commit()
        return resolved
    finally:
        await db.close()
