"""Seed missing countries into PostgreSQL from JSON files in /tmp/."""
import asyncio
import json
import glob
import os

PG_URL = "postgresql://wcadmin:wc2026pg!dune@10.42.0.98:5432/wc_simulator"

POS_MAP = {
    "GK": "GK", "CB": "DEF", "RB": "DEF", "LB": "DEF", "RWB": "DEF", "LWB": "DEF",
    "CDM": "MID", "CM": "MID", "CAM": "MID", "RM": "MID", "LM": "MID",
    "DM": "MID", "AM": "MID",
    "RW": "FWD", "LW": "FWD", "ST": "FWD", "CF": "FWD",
}

async def main():
    import asyncpg
    conn = await asyncpg.connect(PG_URL)
    
    files = sorted(glob.glob("/tmp/*.json"))
    print(f"Found {len(files)} JSON files")
    total = 0
    
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        players = data.get("players", [])
        if not players:
            print(f"  SKIP {os.path.basename(fp)}: no players")
            continue
        
        first = players[0]
        pn = first.get("primaryNationality", {})
        code = pn.get("nationCode") if isinstance(pn, dict) else None
        if not code:
            print(f"  SKIP {os.path.basename(fp)}: no nationCode")
            continue
        
        # Check country exists
        row = await conn.fetchval("SELECT code FROM countries WHERE code = $1", code)
        if not row:
            print(f"  SKIP {os.path.basename(fp)}: country {code} not in DB")
            continue
        
        # Check if already has players
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM players WHERE country_code = $1", code
        )
        if existing > 0:
            print(f"  SKIP {os.path.basename(fp)}: {code} already has {existing} players")
            continue
        
        count = 0
        for p in players:
            pid = p.get("id", "")
            obj_id = f"{code}-{pid}"
            name = p.get("name", "Unknown")
            
            # Position
            pp = p.get("positionProficiency", {})
            if isinstance(pp, dict) and pp:
                best_pos = max(pp.items(), key=lambda x: x[1])[0].upper()
                position = POS_MAP.get(best_pos, "MID")
            else:
                position = "MID"
            
            # Market value
            asking = p.get("askingPrice", 0) or 0
            mv = int(asking) if asking > 0 else int(p.get("recommendedBuyPrice", 0) or 0)
            
            # Attributes
            ability = p.get("currentAbility", 50) or 50
            strength = max(0, min(99, ability))
            
            physical = p.get("physicalAttribute", {})
            pace = physical.get("pace") if isinstance(physical, dict) else None
            
            photo = f"https://d2utsopg4ciewu.cloudfront.net/{pid}.png"
            
            try:
                await conn.execute(
                    "INSERT INTO players (id,name,country_code,position,detailed_position,"
                    "club,league,age,market_value,photo,strength,"
                    "pace,shooting,passing,dribbling,defending,physic) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17) "
                    "ON CONFLICT DO NOTHING",
                    obj_id, name, code, position, "",
                    p.get("clubName", ""), "", p.get("age", 0) or 0,
                    mv, photo, strength,
                    pace, p.get("shooting"), p.get("playmaking"),
                    p.get("ballControl"), p.get("defending"), p.get("physical")
                )
                count += 1
            except Exception as e:
                if count == 0:
                    print(f"    ERR: {e}")
        
        print(f"  [OK] {os.path.basename(fp)}: {count} players (code={code})")
        total += count
    
    print(f"\nTotal inserted: {total}")
    await conn.close()

asyncio.run(main())
