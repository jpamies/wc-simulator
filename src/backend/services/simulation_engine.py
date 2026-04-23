"""
Simulation engine for the World Cup 2026 simulator.

Generates realistic match results based on team/player strength,
produces individual player stats, and advances the tournament bracket.
"""

import random
import math
from dataclasses import dataclass


@dataclass
class TeamStrength:
    code: str
    name: str
    overall: float          # 1-99
    attack: float
    midfield: float
    defense: float
    goalkeeper: float


@dataclass
class SimulatedGoal:
    minute: int
    scorer_id: str
    assist_id: str | None
    is_penalty: bool = False
    is_own_goal: bool = False


@dataclass
class SimulatedPlayerStats:
    player_id: str
    position: str
    minutes_played: int
    goals: int
    assists: int
    yellow_cards: int
    red_card: bool
    own_goals: int
    penalties_missed: int
    penalties_saved: int
    saves: int
    goals_conceded: int
    clean_sheet: bool
    rating: float
    is_starter: bool


@dataclass
class SimulatedMatch:
    score_home: int
    score_away: int
    penalty_home: int | None
    penalty_away: int | None
    home_stats: list[SimulatedPlayerStats]
    away_stats: list[SimulatedPlayerStats]


def compute_team_strength(players: list[dict]) -> TeamStrength:
    """Compute aggregate team strength from player list."""
    if not players:
        return TeamStrength("", "", 50, 50, 50, 50, 50)

    by_pos = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for p in players:
        pos = p.get("position", "MID")
        by_pos.setdefault(pos, []).append(p.get("strength", 50))

    def avg_top(vals, n):
        if not vals:
            return 50.0
        sorted_vals = sorted(vals, reverse=True)
        return sum(sorted_vals[:n]) / min(n, len(sorted_vals))

    gk = avg_top(by_pos["GK"], 1)
    defense = avg_top(by_pos["DEF"], 4)
    midfield = avg_top(by_pos["MID"], 3)
    attack = avg_top(by_pos["FWD"], 3)

    overall = gk * 0.10 + defense * 0.30 + midfield * 0.30 + attack * 0.30
    return TeamStrength(
        code=players[0].get("country_code", ""),
        name="",
        overall=overall,
        attack=attack,
        midfield=midfield,
        defense=defense,
        goalkeeper=gk,
    )


def _expected_goals(attack: float, opp_defense: float, opp_gk: float) -> float:
    """Estimate expected goals based on attack vs opponent defense+gk."""
    attack_factor = attack / 50.0
    def_factor = (opp_defense * 0.7 + opp_gk * 0.3) / 50.0
    base_xg = 1.3  # average goals per team in WC
    return base_xg * (attack_factor / def_factor)


def _sample_goals(xg: float) -> int:
    """Sample actual goals from expected goals using Poisson-like distribution."""
    # Clamp xg to reasonable range
    xg = max(0.2, min(xg, 5.0))
    # Poisson sampling
    goals = 0
    p = math.exp(-xg)
    s = p
    u = random.random()
    while u > s and goals < 10:
        goals += 1
        p *= xg / goals
        s += p
    return goals


def _select_squad(players: list[dict], size: int = 26) -> list[dict]:
    """Select a tournament squad from the full player pool."""
    by_pos = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for p in players:
        by_pos.setdefault(p.get("position", "MID"), []).append(p)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda x: x.get("strength", 50), reverse=True)

    # Pick best players per position: 3 GK, 8 DEF, 8 MID, 7 FWD
    targets = {"GK": 3, "DEF": 8, "MID": 8, "FWD": 7}
    squad = []
    for pos, count in targets.items():
        squad.extend(by_pos[pos][:count])
    return squad[:size]


def simulate_match(
    home_players: list[dict],
    away_players: list[dict],
    is_knockout: bool = False,
) -> SimulatedMatch:
    """
    Simulate a single match.

    Args:
        home_players: list of player dicts with id, position, strength, name
        away_players: same for away team
        is_knockout: if True, ties go to penalties

    Returns:
        SimulatedMatch with scores and per-player stats.
    """
    home_players = _select_squad(home_players)
    away_players = _select_squad(away_players)

    # If either team has no players, generate a default result
    if not home_players or not away_players:
        return SimulatedMatch(
            score_home=0 if not home_players else 3,
            score_away=0 if not away_players else 3,
            penalty_home=None, penalty_away=None,
            home_stats=[], away_stats=[],
        )

    home = compute_team_strength(home_players)
    away = compute_team_strength(away_players)

    # Home advantage
    home_boost = 1.08

    home_xg = _expected_goals(home.attack * home_boost, away.defense, away.goalkeeper)
    away_xg = _expected_goals(away.attack, home.defense, home.goalkeeper)

    score_home = _sample_goals(home_xg)
    score_away = _sample_goals(away_xg)

    penalty_home = None
    penalty_away = None

    if is_knockout and score_home == score_away:
        # Penalty shootout
        pen_h = 0
        pen_a = 0
        for _ in range(5):
            if random.random() < 0.75:
                pen_h += 1
            if random.random() < 0.75:
                pen_a += 1
        while pen_h == pen_a:
            if random.random() < 0.75:
                pen_h += 1
            if random.random() < 0.75:
                pen_a += 1
            if pen_h != pen_a:
                break
        penalty_home = pen_h
        penalty_away = pen_a

    home_stats = _generate_player_stats(home_players, score_home, score_away, is_home=True)
    away_stats = _generate_player_stats(away_players, score_away, score_home, is_home=False)

    return SimulatedMatch(
        score_home=score_home,
        score_away=score_away,
        penalty_home=penalty_home,
        penalty_away=penalty_away,
        home_stats=home_stats,
        away_stats=away_stats,
    )


def _pick_starters(players: list[dict]) -> tuple[list[dict], list[dict]]:
    """Select 11 starters and the rest as subs, by position priority."""
    by_pos = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for p in players:
        by_pos.setdefault(p.get("position", "MID"), []).append(p)

    # Sort each position by strength descending
    for pos in by_pos:
        by_pos[pos].sort(key=lambda x: x.get("strength", 50), reverse=True)

    targets = {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3}
    starters = []
    subs = []

    for pos, count in targets.items():
        pool = by_pos.get(pos, [])
        starters.extend(pool[:count])
        subs.extend(pool[count:])

    return starters, subs


def _generate_player_stats(
    players: list[dict],
    goals_for: int,
    goals_against: int,
    is_home: bool,
) -> list[SimulatedPlayerStats]:
    """Generate individual match stats for all players in a squad."""
    starters, subs = _pick_starters(players)
    stats = []

    # Decide which starters scored
    scorers = _distribute_goals(starters, goals_for)
    # Decide assists
    assists = _distribute_assists(starters, goals_for, scorers)

    # Number of subs used (0-3)
    num_subs = min(random.choices([0, 1, 2, 3], weights=[5, 15, 40, 40])[0], len(subs))
    sub_minutes = sorted(random.sample(range(46, 90), min(num_subs, 44))) if num_subs else []
    subbed_out = random.sample(
        [s for s in starters if s.get("position") != "GK"],
        min(num_subs, len([s for s in starters if s.get("position") != "GK"])),
    ) if num_subs else []

    sub_map = {}
    for i, player in enumerate(subbed_out):
        if i < len(sub_minutes):
            sub_map[player["id"]] = sub_minutes[i]

    subs_used = subs[:num_subs]
    sub_in_map = {}
    for i, player in enumerate(subs_used):
        if i < len(sub_minutes):
            sub_in_map[player["id"]] = sub_minutes[i]

    clean_sheet = goals_against == 0

    for p in starters:
        pid = p["id"]
        pos = p.get("position", "MID")
        subbed_minute = sub_map.get(pid)
        minutes = subbed_minute if subbed_minute else 90

        g = scorers.get(pid, 0)
        a = assists.get(pid, 0)
        yc = 1 if random.random() < 0.12 else 0
        rc = yc == 0 and random.random() < 0.01
        og = 1 if random.random() < 0.008 else 0
        pm = 1 if g > 0 and random.random() < 0.05 else 0
        ps = 1 if pos == "GK" and random.random() < 0.08 else 0
        sv = random.randint(1, 6) if pos == "GK" else 0
        gc = goals_against if pos in ("GK", "DEF") and minutes >= 60 else 0
        cs = clean_sheet and pos in ("GK", "DEF") and minutes >= 60

        base_rating = 6.0 + (p.get("strength", 50) - 50) / 50
        rating = round(min(10.0, max(1.0, base_rating + g * 0.8 + a * 0.4 - yc * 0.3 - og * 1.0 + random.gauss(0, 0.3))), 1)

        stats.append(SimulatedPlayerStats(
            player_id=pid, position=pos, minutes_played=minutes,
            goals=g, assists=a, yellow_cards=yc, red_card=rc,
            own_goals=og, penalties_missed=pm, penalties_saved=ps,
            saves=sv, goals_conceded=gc, clean_sheet=cs,
            rating=rating, is_starter=True,
        ))

    for p in subs_used:
        pid = p["id"]
        pos = p.get("position", "MID")
        entered = sub_in_map.get(pid, 75)
        minutes = 90 - entered

        stats.append(SimulatedPlayerStats(
            player_id=pid, position=pos, minutes_played=minutes,
            goals=0, assists=0, yellow_cards=1 if random.random() < 0.08 else 0,
            red_card=False, own_goals=0, penalties_missed=0,
            penalties_saved=0, saves=0, goals_conceded=0,
            clean_sheet=False, rating=round(6.0 + random.gauss(0, 0.4), 1),
            is_starter=False,
        ))

    # Unused subs get 0 minutes
    for p in subs[num_subs:]:
        stats.append(SimulatedPlayerStats(
            player_id=p["id"], position=p.get("position", "MID"),
            minutes_played=0, goals=0, assists=0, yellow_cards=0,
            red_card=False, own_goals=0, penalties_missed=0,
            penalties_saved=0, saves=0, goals_conceded=0,
            clean_sheet=False, rating=0.0, is_starter=False,
        ))

    return stats


def _distribute_goals(starters: list[dict], total_goals: int) -> dict[str, int]:
    """Distribute goals among starters weighted by position and strength."""
    if total_goals == 0 or not starters:
        return {}

    weights = []
    for p in starters:
        pos = p.get("position", "MID")
        s = p.get("strength", 50)
        w = {"FWD": 5.0, "MID": 2.5, "DEF": 0.5, "GK": 0.05}[pos]
        weights.append(w * (s / 50.0))

    scorers: dict[str, int] = {}
    for _ in range(total_goals):
        idx = random.choices(range(len(starters)), weights=weights, k=1)[0]
        pid = starters[idx]["id"]
        scorers[pid] = scorers.get(pid, 0) + 1

    return scorers


def _distribute_assists(
    starters: list[dict],
    total_goals: int,
    scorers: dict[str, int],
) -> dict[str, int]:
    """Distribute assists — not all goals have assists, and assister != scorer."""
    if total_goals == 0:
        return {}

    assists: dict[str, int] = {}
    scorer_ids = []
    for pid, count in scorers.items():
        scorer_ids.extend([pid] * count)

    for scorer_id in scorer_ids:
        if random.random() < 0.35:
            # No assist for this goal
            continue
        candidates = [p for p in starters if p["id"] != scorer_id]
        if not candidates:
            continue
        weights = []
        for p in candidates:
            pos = p.get("position", "MID")
            w = {"FWD": 2.0, "MID": 4.0, "DEF": 1.0, "GK": 0.1}[pos]
            weights.append(w * (p.get("strength", 50) / 50.0))
        idx = random.choices(range(len(candidates)), weights=weights, k=1)[0]
        aid = candidates[idx]["id"]
        assists[aid] = assists.get(aid, 0) + 1

    return assists
