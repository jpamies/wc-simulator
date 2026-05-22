"""
Split players.json.gz into one JSON file per country under data/raw/players/.
Keeps ALL players per country, no filtering.
"""

import gzip
import json
import os
import re
from collections import defaultdict

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUT_DIR = os.path.join(RAW_DIR, "players")

# FIFA nationality name → filesystem-safe slug
def slugify(name):
    s = name.lower()
    s = s.replace("'", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def main():
    src = os.path.join(RAW_DIR, "players.json.gz")
    with gzip.open(src, "rt", encoding="utf-8") as f:
        players = json.load(f)

    print(f"Total players loaded: {len(players)}")

    # Group by nationality
    by_country = defaultdict(list)
    for p in players:
        by_country[p["nationality_name"]].append(p)

    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Countries found: {len(by_country)}")
    print()

    for nation in sorted(by_country.keys()):
        squad = sorted(by_country[nation], key=lambda x: x["overall"], reverse=True)
        slug = slugify(nation)
        filepath = os.path.join(OUT_DIR, f"{slug}.json")

        doc = {
            "nationality": nation,
            "total_players": len(squad),
            "players": squad,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        top = squad[0]["overall"] if squad else 0
        print(f"  {nation:30s}  {len(squad):4d} players  (top OVR {top})  → {slug}.json")

    print(f"\nDone. {len(by_country)} files written to {OUT_DIR}")


if __name__ == "__main__":
    main()
