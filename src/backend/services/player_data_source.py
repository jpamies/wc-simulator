"""Abstract interface for player data sources.

This module defines the abstraction layer that decouples player data loading
from the specific data format. Any data source (EFEM API JSON, raw players JSON,
database, CSV, etc.) can implement this interface.

The Player object is the canonical representation independent of source format.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Player:
    """Canonical player object, format-agnostic.
    
    This represents the unified player data model that all data sources
    must produce. Database schema and backend logic depend only on this object.
    """
    # Core identification
    id: str                          # Unique ID (format: "{country_code}-{player_id}")
    name: str                        # Player name
    country_code: str                # 3-letter country code (e.g., "ARG", "BRA")
    
    # Position & role
    position: str                    # Simplified position: GK, DEF, MID, FWD
    detailed_position: str           # Detailed positions (e.g., "CB,RB" or "CM")
    roles: Optional[list[str]] = None  # EFEM: specific roles like ["CB", "RB"]
    
    # Club & career
    club: str = ""
    league: str = ""
    age: int = 0
    
    # Valuations & contract
    market_value: int = 0           # EUR (from Transfermarkt or derived from EFEM)
    contract_expiry: Optional[str] = None  # ISO date
    wage_per_week: int = 0          # EUR (EFEM only)
    release_clause: int = 0         # EUR (EFEM only)
    
    # Performance attributes
    strength: int = 50              # Overall rating (0-99)
    pace: Optional[int] = None      # Pace attribute
    shooting: Optional[int] = None  # Shooting attribute
    passing: Optional[int] = None   # Passing attribute
    dribbling: Optional[int] = None # Dribbling attribute
    defending: Optional[int] = None # Defending attribute
    physic: Optional[int] = None    # Physical attribute
    
    # EFEM-specific attributes (optional, for future use)
    efem_score: Optional[float] = None  # EFEM score for AI evaluation
    current_ability: Optional[int] = None  # EFEM current ability
    potential_ability: Optional[int] = None  # EFEM potential ability
    positions: Optional[list[str]] = None  # EFEM position list
    
    # Media
    photo_url: str = ""
    
    # Metadata
    source: str = ""                # Origin of data (e.g., "efem", "raw", "transfermarkt")
    extracted_at: Optional[str] = None  # ISO timestamp


class PlayerDataSource(ABC):
    """Abstract base class for player data sources.
    
    Implementations load player data from different sources (EFEM API JSON,
    raw players JSON, database, etc.) and translate them to Player objects.
    """
    
    @abstractmethod
    async def load_all_players(self) -> list[Player]:
        """Load all players from the source.
        
        Returns:
            List of Player objects in canonical format.
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of this data source (for logging/debugging)."""
        pass


class PlayerDataSourceFactory:
    """Factory to determine and create the appropriate data source.
    
    Detects which data source is available (EFEM → Raw priority)
    and creates the corresponding adapter.
    """
    
    @staticmethod
    async def create_source() -> PlayerDataSource:
        """Auto-detect and create the appropriate data source.
        
        Priority:
        1. EFEM format (data/raw/efeme/)
        2. Raw players format (data/raw/players/) [legacy fallback]
        
        Returns:
            Instantiated PlayerDataSource adapter.
        
        Raises:
            FileNotFoundError: If no data source is found.
        """
        from pathlib import Path
        
        METADATA_FILES = {"import_status.json", "README.md"}
        
        # Try EFEM first
        efem_path = Path("data/raw/efeme")
        if efem_path.exists():
            country_files = [
                f for f in efem_path.glob("*.json")
                if f.name not in METADATA_FILES and not f.name.startswith("_")
            ]
            if country_files:
                from src.backend.services.player_data_sources.efem_source import EFEMPlayerDataSource
                return EFEMPlayerDataSource()
        
        # Fallback to raw players
        raw_path = Path("data/raw/players")
        if raw_path.exists() and any(raw_path.glob("*.json")):
            from src.backend.services.player_data_sources.raw_source import RawPlayerDataSource
            return RawPlayerDataSource()
        
        raise FileNotFoundError(
            "No player data source found. Expected one of:\n"
            "  - data/raw/efeme/*.json (EFEM format)\n"
            "  - data/raw/players/*.json (Raw players format)"
        )
