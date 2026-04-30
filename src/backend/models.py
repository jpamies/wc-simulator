"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel
from typing import Optional


# ─── Countries ───

class CountryOut(BaseModel):
    code: str
    name: str
    name_local: Optional[str] = None
    flag: Optional[str] = None
    confederation: Optional[str] = None
    group_letter: Optional[str] = None
    player_count: int = 0


# ─── Players ───

class PlayerOut(BaseModel):
    id: str
    name: str
    country_code: str
    position: str
    detailed_position: Optional[str] = None
    club: Optional[str] = None
    club_logo: Optional[str] = None
    league: Optional[str] = None
    age: Optional[int] = None
    market_value: int = 0
    photo: Optional[str] = None
    strength: int = 50
    pace: Optional[int] = None
    shooting: Optional[int] = None
    passing: Optional[int] = None
    dribbling: Optional[int] = None
    defending: Optional[int] = None
    physic: Optional[int] = None


# ─── Matches ───

class MatchOut(BaseModel):
    id: str
    matchday_id: str
    match_number: Optional[int] = None
    home_team: str
    away_team: str
    home_code: Optional[str] = None
    away_code: Optional[str] = None
    kickoff: str
    location: Optional[str] = None
    group_name: Optional[str] = None
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    penalty_home: Optional[int] = None
    penalty_away: Optional[int] = None
    status: str = "scheduled"
    is_simulated: bool = False
    home_flag: Optional[str] = None
    away_flag: Optional[str] = None


class MatchdayOut(BaseModel):
    id: str
    name: str
    phase: str
    date: str
    status: str = "scheduled"
    matches: list[MatchOut] = []


class MatchResultIn(BaseModel):
    score_home: int
    score_away: int
    penalty_home: Optional[int] = None
    penalty_away: Optional[int] = None


# ─── Player stats ───

class PlayerStatIn(BaseModel):
    player_id: str
    minutes_played: int = 0
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_card: bool = False
    own_goals: int = 0
    penalties_missed: int = 0
    penalties_saved: int = 0
    saves: int = 0
    goals_conceded: int = 0
    clean_sheet: bool = False
    rating: float = 0.0
    is_starter: bool = False


class PlayerStatOut(PlayerStatIn):
    match_id: str
    player_name: Optional[str] = None
    country_code: Optional[str] = None
    position: Optional[str] = None


class MatchStatsIn(BaseModel):
    stats: list[PlayerStatIn]


# ─── Standings ───

class GroupStandingOut(BaseModel):
    country_code: str
    country_name: Optional[str] = None
    flag: Optional[str] = None
    group_letter: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    points: int = 0


# ─── Simulation ───

class SimulateMatchesIn(BaseModel):
    match_ids: list[str] = []
    phase: Optional[str] = None
    matchday_id: Optional[str] = None


# ─── Tournaments ───

class TournamentCreate(BaseModel):
    name: str
    owner_name: str = ""
    visibility: str = "public"
    fork_from_slug: Optional[str] = None


class TournamentOut(BaseModel):
    id: int
    slug: str
    name: str
    owner_name: str = ""
    is_canonical: bool = False
    visibility: str = "public"
    forked_from: Optional[int] = None
    status: str = "active"
    created_at: Optional[str] = None
    current_phase: Optional[str] = None
    matches_played: int = 0
    total_matches: int = 0


class TournamentCreatedOut(TournamentOut):
    manage_token: str


# ─── Tournament overview ───

class TournamentOverview(BaseModel):
    tournament: str
    host: list[str]
    total_teams: int
    total_players: int
    total_matches: int
    matches_played: int
    matches_remaining: int
    current_phase: str
    groups: dict[str, list[str]]
