#!/usr/bin/env python3
"""Auto-select squads for specific countries via localhost API."""
import urllib.request
import json

countries = ["SUI", "TUN", "TUR", "URU", "USA", "UZB"]
for c in countries:
    try:
        req = urllib.request.Request(
            f"http://localhost:8000/api/v1/squads/{c}/auto",
            method="POST"
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        print(f"  [OK] {c}: {data.get('squad_size', '?')} players")
    except Exception as e:
        print(f"  [ERR] {c}: {e}")
