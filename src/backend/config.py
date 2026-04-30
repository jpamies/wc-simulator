import os
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent

DATABASE_URL = os.environ.get("WCS_DATABASE_URL", "postgresql://wcadmin:wc2026pg!dune@localhost:5432/wc_simulator")
TOURNAMENT_DATA_DIR = os.environ.get("WCS_TOURNAMENT_DIR", str(_project_root / "data" / "tournament"))
CORS_ORIGINS = os.environ.get("WCS_CORS_ORIGINS", "*")
