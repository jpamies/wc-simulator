"""Raw players data source adapter.

Loads player data from raw players JSON files (data/raw/players/*.json)
and converts them to canonical Player objects.

This adapter provides backward compatibility with the old raw-players format.
"""

import json
from pathlib import Path
from typing import Optional

from src.backend.services.player_data_source import Player, PlayerDataSource


# Map raw player nationality → Country code
NATIONALITY_TO_CODE = {
    "Algeria": "ALG", "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT",
    "Belgium": "BEL", "Bosnia and Herzegovina": "BIH", "Brazil": "BRA",
    "Cabo Verde": "CPV", "Canada": "CAN", "Colombia": "COL", "Congo DR": "COD",
    "Croatia": "CRO", "Curacao": "CUW", "Czechia": "CZE",
    "Côte d'Ivoire": "CIV",
    "Ecuador": "ECU", "Egypt": "EGY", "England": "ENG",
    "France": "FRA", "Germany": "GER", "Ghana": "GHA",
    "Haiti": "HAI", "Iran": "IRN", "Iraq": "IRQ",
    "Japan": "JPN", "Jordan": "JOR", "Korea Republic": "KOR",
    "Mexico": "MEX", "Morocco": "MAR",
    "Netherlands": "NED", "New Zealand": "NZL", "Norway": "NOR",
    "Panama": "PAN", "Paraguay": "PAR", "Portugal": "POR", "Qatar": "QAT",
    "Saudi Arabia": "KSA", "Scotland": "SCO", "Senegal": "SEN",
    "South Africa": "RSA", "Spain": "ESP", "Sweden": "SWE",
    "Switzerland": "SUI", "Tunisia": "TUN", "Türkiye": "TUR",
    "United States": "USA", "Uruguay": "URU", "Uzbekistan": "UZB",
}

# Map FIFA positions to simplified positions
POS_MAP = {
    "GK": "GK",
    "CB": "DEF", "RB": "DEF", "LB": "DEF", "RWB": "DEF", "LWB": "DEF",
    "CDM": "MID", "CM": "MID", "CAM": "MID", "RM": "MID", "LM": "MID",
    "RW": "FWD", "LW": "FWD", "ST": "FWD", "CF": "FWD",
}


def _map_position(positions_str: str) -> tuple[str, str]:
    """Map FIFA positions string to (simplified_pos, detailed_pos)."""
    primary = positions_str.split(",")[0].strip() if positions_str else "CM"
    simplified = POS_MAP.get(primary, "MID")
    return simplified, positions_str or "CM"


def _safe_int(value) -> Optional[int]:
    """Safely convert value to int, handling None and NaN."""
    if value is None or value != value:  # NaN check
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


class RawPlayerDataSource(PlayerDataSource):
    """Raw players JSON data source.
    
    Loads players from raw format JSON files (data/raw/players/) and converts
    them to canonical Player objects. Provides backward compatibility.
    """
    
    def __init__(self, data_dir: str = "data/raw/players"):
        self.data_dir = Path(data_dir)
    
    async def load_all_players(self) -> list[Player]:
        """Load all players from raw JSON files."""
        players = []
        
        if not self.data_dir.exists():
            print(f"[WARN] Raw players directory not found: {self.data_dir}")
            return players
        
        json_files = sorted([f for f in self.data_dir.glob("*.json")])
        
        print(f"[DATA] Loading raw players from {len(json_files)} country files...")
        
        for filepath in json_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                nationality = data.get("nationality", "Unknown")
                code = NATIONALITY_TO_CODE.get(nationality)
                
                if not code:
                    print(f"  [WARN] Skipping {filepath.name}: Unknown nationality '{nationality}'")
                    continue
                
                players_data = data.get("players", [])
                
                for player_data in players_data:
                    try:
                        player = self._convert_player(player_data, code)
                        players.append(player)
                    except Exception as e:
                        print(f"  [WARN] Error converting player: {e}")
                        continue
                
                print(f"  [OK] {filepath.name}: {len(players_data)} players")
            
            except Exception as e:
                print(f"  [ERR] Error loading {filepath.name}: {e}")
                continue
        
        print(f"[OK] Total: {len(players)} players loaded from raw format")
        return players
    
    def _convert_player(self, player_data: dict, country_code: str) -> Player:
        """Convert a raw player JSON object to canonical Player object."""
        
        player_id = player_data.get("player_id", "")
        player_obj_id = f"{country_code}-{player_id}"
        
        position_str = player_data.get("player_positions", "CM")
        position, detailed_position = _map_position(position_str)
        
        overall = _safe_int(player_data.get("overall", 50)) or 50
        strength = max(30, min(99, overall))
        
        return Player(
            id=player_obj_id,
            name=player_data.get("short_name", player_data.get("long_name", "Unknown")),
            country_code=country_code,
            position=position,
            detailed_position=detailed_position,
            club=player_data.get("club_name", ""),
            league=player_data.get("league_name", ""),
            age=_safe_int(player_data.get("age")) or 0,
            market_value=_safe_int(player_data.get("value_eur")) or 0,
            strength=strength,
            pace=_safe_int(player_data.get("pace")),
            shooting=_safe_int(player_data.get("shooting")),
            passing=_safe_int(player_data.get("passing")),
            dribbling=_safe_int(player_data.get("dribbling")),
            defending=_safe_int(player_data.get("defending")),
            physic=_safe_int(player_data.get("physic")),
            photo_url=player_data.get("player_face_url", ""),
            source="raw",
        )
    
    def get_source_name(self) -> str:
        return "Raw Players JSON"
