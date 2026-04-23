import os
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent

DATABASE_PATH = os.environ.get("WCS_DATABASE_PATH", str(_project_root / "data" / "wc_simulator.db"))
TRANSFERMARKT_DATA_DIR = os.environ.get("WCS_DATA_DIR", str(_project_root / "data" / "transfermarkt"))
RAW_PLAYERS_DIR = os.environ.get("WCS_RAW_PLAYERS_DIR", str(_project_root / "data" / "raw" / "players"))
TOURNAMENT_DATA_DIR = os.environ.get("WCS_TOURNAMENT_DIR", str(_project_root / "data" / "tournament"))
CORS_ORIGINS = os.environ.get("WCS_CORS_ORIGINS", "*")
