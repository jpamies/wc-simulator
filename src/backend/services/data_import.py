"""Load tournament data (countries, players, calendar) from JSON files into the DB."""

import json
import math
import os
import random
from src.backend.config import TOURNAMENT_DATA_DIR
from src.backend.database import get_db
from src.backend.services.player_data_source import PlayerDataSourceFactory


# Map of calendar team names → country codes (all 48 WC teams)
TEAM_NAME_TO_CODE = {
    "Mexico": "MEX", "South Africa": "RSA", "Korea Republic": "KOR", "Czechia": "CZE",
    "Canada": "CAN", "Bosnia-Herzegovina": "BIH", "Qatar": "QAT", "Switzerland": "SUI",
    "Brazil": "BRA", "Haiti": "HAI", "Morocco": "MAR", "Scotland": "SCO",
    "USA": "USA", "Paraguay": "PAR", "Australia": "AUS", "Türkiye": "TUR",
    "Germany": "GER", "Curaçao": "CUW", "Côte d'Ivoire": "CIV", "Ecuador": "ECU",
    "Netherlands": "NED", "Japan": "JPN", "Sweden": "SWE", "Tunisia": "TUN",
    "Belgium": "BEL", "Egypt": "EGY", "IR Iran": "IRN", "New Zealand": "NZL",
    "Spain": "ESP", "Cabo Verde": "CPV", "Saudi Arabia": "KSA", "Uruguay": "URU",
    "France": "FRA", "Senegal": "SEN", "Iraq": "IRQ", "Norway": "NOR",
    "Argentina": "ARG", "Algeria": "ALG", "Austria": "AUT", "Jordan": "JOR",
    "Portugal": "POR", "Congo DR": "COD", "Uzbekistan": "UZB", "Colombia": "COL",
    "England": "ENG", "Croatia": "CRO", "Ghana": "GHA", "Panama": "PAN",
}

TEAM_FLAGS = {
    "MEX": "https://flagcdn.com/w40/mx.png", "RSA": "https://flagcdn.com/w40/za.png",
    "KOR": "https://flagcdn.com/w40/kr.png", "CZE": "https://flagcdn.com/w40/cz.png",
    "CAN": "https://flagcdn.com/w40/ca.png", "BIH": "https://flagcdn.com/w40/ba.png",
    "QAT": "https://flagcdn.com/w40/qa.png", "SUI": "https://flagcdn.com/w40/ch.png",
    "BRA": "https://flagcdn.com/w40/br.png", "HAI": "https://flagcdn.com/w40/ht.png",
    "MAR": "https://flagcdn.com/w40/ma.png", "SCO": "https://flagcdn.com/w40/gb-sct.png",
    "USA": "https://flagcdn.com/w40/us.png", "PAR": "https://flagcdn.com/w40/py.png",
    "AUS": "https://flagcdn.com/w40/au.png", "TUR": "https://flagcdn.com/w40/tr.png",
    "GER": "https://flagcdn.com/w40/de.png", "CUW": "https://flagcdn.com/w40/cw.png",
    "CIV": "https://flagcdn.com/w40/ci.png", "ECU": "https://flagcdn.com/w40/ec.png",
    "NED": "https://flagcdn.com/w40/nl.png", "JPN": "https://flagcdn.com/w40/jp.png",
    "SWE": "https://flagcdn.com/w40/se.png", "TUN": "https://flagcdn.com/w40/tn.png",
    "BEL": "https://flagcdn.com/w40/be.png", "EGY": "https://flagcdn.com/w40/eg.png",
    "IRN": "https://flagcdn.com/w40/ir.png", "NZL": "https://flagcdn.com/w40/nz.png",
    "ESP": "https://flagcdn.com/w40/es.png", "CPV": "https://flagcdn.com/w40/cv.png",
    "KSA": "https://flagcdn.com/w40/sa.png", "URU": "https://flagcdn.com/w40/uy.png",
    "FRA": "https://flagcdn.com/w40/fr.png", "SEN": "https://flagcdn.com/w40/sn.png",
    "IRQ": "https://flagcdn.com/w40/iq.png", "NOR": "https://flagcdn.com/w40/no.png",
    "ARG": "https://flagcdn.com/w40/ar.png", "ALG": "https://flagcdn.com/w40/dz.png",
    "AUT": "https://flagcdn.com/w40/at.png", "JOR": "https://flagcdn.com/w40/jo.png",
    "POR": "https://flagcdn.com/w40/pt.png", "COD": "https://flagcdn.com/w40/cd.png",
    "UZB": "https://flagcdn.com/w40/uz.png", "COL": "https://flagcdn.com/w40/co.png",
    "ENG": "https://flagcdn.com/w40/gb-eng.png", "CRO": "https://flagcdn.com/w40/hr.png",
    "GHA": "https://flagcdn.com/w40/gh.png", "PAN": "https://flagcdn.com/w40/pa.png",
}

TEAM_CONFEDERATIONS = {
    "MEX": "CONCACAF", "RSA": "CAF", "KOR": "AFC", "CZE": "UEFA",
    "CAN": "CONCACAF", "BIH": "UEFA", "QAT": "AFC", "SUI": "UEFA",
    "BRA": "CONMEBOL", "HAI": "CONCACAF", "MAR": "CAF", "SCO": "UEFA",
    "USA": "CONCACAF", "PAR": "CONMEBOL", "AUS": "AFC", "TUR": "UEFA",
    "GER": "UEFA", "CUW": "CONCACAF", "CIV": "CAF", "ECU": "CONMEBOL",
    "NED": "UEFA", "JPN": "AFC", "SWE": "UEFA", "TUN": "CAF",
    "BEL": "UEFA", "EGY": "CAF", "IRN": "AFC", "NZL": "OFC",
    "ESP": "UEFA", "CPV": "CAF", "KSA": "AFC", "URU": "CONMEBOL",
    "FRA": "UEFA", "SEN": "CAF", "IRQ": "AFC", "NOR": "UEFA",
    "ARG": "CONMEBOL", "ALG": "CAF", "AUT": "UEFA", "JOR": "AFC",
    "POR": "UEFA", "COD": "CAF", "UZB": "AFC", "COL": "CONMEBOL",
    "ENG": "UEFA", "CRO": "UEFA", "GHA": "CAF", "PAN": "CONCACAF",
}

def get_code(team_name: str) -> str | None:
    """Resolve a team name to its country code."""
    return TEAM_NAME_TO_CODE.get(team_name)


async def import_all():
    """Import countries, players, groups and calendar if DB is empty.
    
    Set WCS_FORCE_REIMPORT=1 to force re-import of player data even if DB has data.
    """
    force_reimport = os.environ.get("WCS_FORCE_REIMPORT", "0") == "1"
    
    if force_reimport:
        print("[DATA] WCS_FORCE_REIMPORT=1 detected, clearing all data...")
        db = await get_db()
        try:
            # Delete in FK-safe order (children before parents)
            await db.execute("DELETE FROM player_match_stats")
            await db.execute("DELETE FROM group_standings")
            await db.execute("DELETE FROM squad_selections")
            await db.execute("DELETE FROM matches")
            await db.execute("DELETE FROM matchdays")
            await db.execute("DELETE FROM players")
            await db.execute("DELETE FROM countries")
            await db.commit()
            print("[DATA] All data cleared for reimport")
        finally:
            await db.close()
    else:
        db = await get_db()
        try:
            row = await db.execute_fetchall("SELECT COUNT(*) as c FROM countries")
            if row[0]["c"] > 0:
                return
        finally:
            await db.close()

    await _import_countries_from_groups()
    await _import_calendar()
    await _import_players()


async def _import_countries_from_groups():
    """Create all 48 countries from groups.json."""
    filepath = os.path.join(TOURNAMENT_DATA_DIR, "groups.json")
    if not os.path.exists(filepath):
        return

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = await get_db()
    try:
        for letter, team_names in data.get("groups", {}).items():
            for name in team_names:
                code = TEAM_NAME_TO_CODE.get(name)
                if not code:
                    print(f"⚠️  Unknown team: {name}")
                    continue
                flag = TEAM_FLAGS.get(code, "")
                confederation = TEAM_CONFEDERATIONS.get(code, "")
                await db.execute(
                    """INSERT OR IGNORE INTO countries
                       (code, name, flag, confederation, group_letter)
                       VALUES (?, ?, ?, ?, ?)""",
                    (code, name, flag, confederation, letter),
                )
        await db.commit()
    finally:
        await db.close()


async def _import_calendar():
    """Import matchdays and matches from calendar.json."""
    filepath = os.path.join(TOURNAMENT_DATA_DIR, "calendar.json")
    if not os.path.exists(filepath):
        return

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = await get_db()
    try:
        for md in data:
            await db.execute(
                """INSERT OR IGNORE INTO matchdays (id, name, phase, date, status)
                   VALUES (?, ?, ?, ?, 'scheduled')""",
                (md["id"], md["name"], md["phase"], md["date"]),
            )

            for m in md.get("matches", []):
                home_name = m["home"]
                away_name = m["away"]
                home_code = get_code(home_name)
                away_code = get_code(away_name)

                await db.execute(
                    """INSERT OR IGNORE INTO matches
                       (id, matchday_id, match_number, home_team, away_team,
                        home_code, away_code, kickoff, location, group_name,
                        status, is_simulated)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', 0)""",
                    (m["id"], md["id"], m.get("match_number"),
                     home_name, away_name, home_code, away_code,
                     m["kickoff"], m.get("location"), m.get("group")),
                )

        await db.commit()
    finally:
        await db.close()




async def _import_players():
    """Import player data using auto-detected data source.
    
    Attempts to load players from available data sources in priority order:
    1. EFEM API JSON (data/raw/efeme/)
    2. Raw players format (data/raw/players/)
    
    Players are converted to canonical Player objects and stored in the database.
    """
    try:
        data_source = await PlayerDataSourceFactory.create_source()
        print(f"\n[DATA] Using data source: {data_source.get_source_name()}")
    except FileNotFoundError as e:
        print(f"[WARN] No player data source found. Skipping player import.")
        print(f"   {e}")
        return
    
    # Load players from the selected source
    players = await data_source.load_all_players()
    
    if not players:
        print("[WARN] No players loaded from data source")
        return
    
    # Insert into database
    db = await get_db()
    try:
        imported = 0
        for player in players:
            # Verify country exists in DB
            row = await db.execute_fetchall(
                "SELECT code FROM countries WHERE code = ?", (player.country_code,)
            )
            if not row:
                continue
            
            await db.execute(
                """INSERT OR IGNORE INTO players
                   (id, name, country_code, position, detailed_position,
                    club, league, age, market_value, photo, strength,
                    pace, shooting, passing, dribbling, defending, physic)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (player.id, player.name, player.country_code,
                 player.position, player.detailed_position,
                 player.club, player.league, player.age, player.market_value,
                 player.photo_url, player.strength,
                 player.pace, player.shooting, player.passing,
                 player.dribbling, player.defending, player.physic),
            )
            imported += 1
        
        await db.commit()
        print(f"[OK] {imported} players imported from {data_source.get_source_name()}")
    finally:
        await db.close()

