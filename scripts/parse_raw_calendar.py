"""
Parse the raw FIFA World Cup 2026 JSON and generate:
  - data/tournament/groups.json
  - data/tournament/calendar.json
"""

import json
import os

RAW_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "fifa-world-cup-2026.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "tournament")


def main():
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        matches = json.load(f)

    # ── Extract groups ──
    groups: dict[str, set[str]] = {}
    for m in matches:
        g = m.get("Group")
        if not g:
            continue
        letter = g.replace("Group ", "")
        groups.setdefault(letter, set())
        groups[letter].add(m["HomeTeam"])
        groups[letter].add(m["AwayTeam"])

    groups_sorted = {k: sorted(v) for k, v in sorted(groups.items())}

    print(f"Groups: {len(groups_sorted)}")
    for letter, teams in groups_sorted.items():
        print(f"  {letter}: {', '.join(teams)}")

    all_teams = set()
    for teams in groups_sorted.values():
        all_teams.update(teams)
    print(f"\nTotal teams: {len(all_teams)}")

    # ── Map round numbers to phases ──
    round_phase = {
        1: "groups", 2: "groups", 3: "groups",
        4: "r32",
        5: "r16",
        6: "quarter",
        7: "semi",
        8: "final",
    }

    round_names = {
        1: "Jornada 1 — Fase de Grupos",
        2: "Jornada 2 — Fase de Grupos",
        3: "Jornada 3 — Fase de Grupos",
        4: "Treintaidosavos de Final",
        5: "Octavos de Final",
        6: "Cuartos de Final",
        7: "Semifinales",
        8: "Final",
    }

    # ── Build calendar ──
    by_round: dict[int, list] = {}
    for m in matches:
        r = m["RoundNumber"]
        by_round.setdefault(r, []).append(m)

    calendar = []
    for round_num in sorted(by_round.keys()):
        round_matches = sorted(by_round[round_num], key=lambda x: x["DateUtc"])

        first_date = round_matches[0]["DateUtc"][:10]

        phase = round_phase.get(round_num, "unknown")
        matchday_id = {
            1: "GS1", 2: "GS2", 3: "GS3",
            4: "R32", 5: "R16", 6: "QF", 7: "SF", 8: "FINAL",
        }.get(round_num, f"R{round_num}")

        match_entries = []
        for m in round_matches:
            home = m["HomeTeam"]
            away = m["AwayTeam"]

            # Skip placeholder teams for knockout rounds
            is_placeholder = home in ("To be announced",) or away in ("To be announced",)
            # Keep bracket references like "1A", "2B", "3ABCDF" etc.
            is_bracket_ref = (not m.get("Group") and not is_placeholder)

            match_entry = {
                "id": f"M{m['MatchNumber']}",
                "match_number": m["MatchNumber"],
                "home": home,
                "away": away,
                "kickoff": m["DateUtc"].replace(" ", "T"),
                "location": m["Location"],
                "group": m.get("Group"),
            }
            match_entries.append(match_entry)

        calendar.append({
            "id": matchday_id,
            "name": round_names.get(round_num, f"Ronda {round_num}"),
            "phase": phase,
            "date": first_date,
            "matches": match_entries,
        })

    # ── Write groups.json ──
    groups_data = {
        "tournament": "FIFA World Cup 2026",
        "format": "48 teams, 12 groups of 4",
        "hosts": ["USA", "Mexico", "Canada"],
        "groups": {k: list(v) for k, v in groups_sorted.items()},
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "groups.json"), "w", encoding="utf-8") as f:
        json.dump(groups_data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ groups.json written")

    # ── Write calendar.json ──
    with open(os.path.join(OUT_DIR, "calendar.json"), "w", encoding="utf-8") as f:
        json.dump(calendar, f, indent=2, ensure_ascii=False)
    print(f"✅ calendar.json written ({sum(len(md['matches']) for md in calendar)} matches)")

    # ── Print summary ──
    for md in calendar:
        gs_matches = [m for m in md["matches"] if m["home"] != "To be announced"]
        print(f"  {md['id']:6s} {md['phase']:8s} — {len(md['matches'])} matches ({md['date']})")


if __name__ == "__main__":
    main()
