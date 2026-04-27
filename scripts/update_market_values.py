"""Update market_value for all players using recommendedBuyPrice from EFEM JSONs."""
import asyncio, json, glob, os

async def main():
    import asyncpg
    conn = await asyncpg.connect(os.environ.get("PG_URL",
        "postgresql://wcadmin:wc2026pg!dune@10.42.0.98:5432/wc_simulator"))
    
    files = sorted(glob.glob("/tmp/efeme_jsons/*.json"))
    print(f"Found {len(files)} JSON files")
    total = 0
    
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        players = data.get("players", [])
        if not players:
            continue
        
        pn = players[0].get("primaryNationality", {})
        code = pn.get("nationCode") if isinstance(pn, dict) else None
        if not code:
            continue
        
        updated = 0
        for p in players:
            pid = p.get("id", "")
            obj_id = f"{code}-{pid}"
            
            rec = p.get("recommendedBuyPrice", 0) or 0
            asking = p.get("askingPrice", 0) or 0
            mv = int(rec) if rec > 0 else int(asking)
            
            result = await conn.execute(
                "UPDATE players SET market_value = $1 WHERE id = $2 AND market_value != $1",
                mv, obj_id
            )
            if result.split()[-1] != "0":
                updated += 1
        
        print(f"  {os.path.basename(fp)}: {updated} updated (code={code})")
        total += updated
    
    # Also update squad_stats total_value
    await conn.execute("""
        UPDATE squad_stats ss SET total_value = sub.tv
        FROM (
            SELECT s.country_code, COALESCE(SUM(p.market_value), 0) as tv
            FROM squad_selections s JOIN players p ON s.player_id = p.id
            GROUP BY s.country_code
        ) sub
        WHERE ss.country_code = sub.country_code
    """)
    
    print(f"\nTotal updated: {total}")
    await conn.close()

asyncio.run(main())
