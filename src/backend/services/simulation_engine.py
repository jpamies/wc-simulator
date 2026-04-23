"""
Simulation engine for the World Cup 2026 simulator.

Generates realistic match results based on team/player strength using a
Poisson xG model. Produces per-player stats with coherent timelines:
substitution times align with goals/assists, and individual events
(cards, saves, etc.) are context-aware.

Design decisions:
- Team strength derived from top players per position
- xG uses attack, midfield control, and opponent defense+GK
- Home advantage: +8% xG boost
- Goals distributed minute-by-minute via Poisson process
- Subs enter at realistic times; can score/assist after entering
- Cards weighted by match context (losing team fouls more)
- GK saves derived from opponent shots (xG-based)
- Penalty shootouts follow real format (alternating, sudden death)
"""

import random
import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes — public interface consumed by routes
# ---------------------------------------------------------------------------

@dataclass
class TeamStrength:
    code: str
    name: str
    overall: float          # 30-99
    attack: float
    midfield: float
    defense: float
    goalkeeper: float


@dataclass
class MatchEvent:
    """A single event that happened during the match."""
    minute: int
    event_type: str         # "goal", "assist", "yellow", "red", "sub_in", "sub_out", "own_goal", "pen_miss", "pen_save"
    player_id: str
    detail: str = ""        # e.g. "penalty", "header"


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
    events: list[MatchEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Team strength computation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# xG model
# ---------------------------------------------------------------------------

def _expected_goals(attack: float, midfield: float,
                    opp_defense: float, opp_gk: float, opp_midfield: float) -> float:
    """
    Estimate expected goals using attack + midfield possession
    vs opponent defense + GK + midfield.
    """
    mid_ratio = midfield / max(1, midfield + opp_midfield)  # 0.0-1.0

    attack_factor = attack / 50.0
    def_factor = (opp_defense * 0.65 + opp_gk * 0.35) / 50.0

    base_xg = 1.25  # WC average goals per team per match
    possession_modifier = 0.6 + 0.8 * mid_ratio  # range ~0.6 to 1.4

    return base_xg * (attack_factor / def_factor) * possession_modifier


def _sample_goals(xg: float) -> int:
    """Sample actual goals from expected goals using Poisson distribution."""
    xg = max(0.15, min(xg, 5.0))
    goals = 0
    p = math.exp(-xg)
    s = p
    u = random.random()
    while u > s and goals < 10:
        goals += 1
        p *= xg / goals
        s += p
    return goals


# ---------------------------------------------------------------------------
# Squad and lineup selection
# ---------------------------------------------------------------------------

def _select_squad(players: list[dict], size: int = 26) -> list[dict]:
    """Select a tournament squad from the full player pool."""
    by_pos = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for p in players:
        by_pos.setdefault(p.get("position", "MID"), []).append(p)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda x: x.get("strength", 50), reverse=True)

    targets = {"GK": 3, "DEF": 8, "MID": 8, "FWD": 7}
    squad = []
    for pos, count in targets.items():
        squad.extend(by_pos[pos][:count])
    return squad[:size]


def _pick_starters(players: list[dict]) -> tuple[list[dict], list[dict]]:
    """Select 11 starters and the rest as subs, by position priority."""
    by_pos = {"GK": [], "DEF": [], "MID": [], "FWD": []}
    for p in players:
        by_pos.setdefault(p.get("position", "MID"), []).append(p)
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


# ---------------------------------------------------------------------------
# Substitutions — realistic timing
# ---------------------------------------------------------------------------

def _plan_substitutions(starters: list[dict], subs: list[dict],
                        is_losing: bool) -> list[tuple[int, dict, dict]]:
    """
    Plan substitutions as (minute, player_out, player_in).
    Losing teams sub earlier and use more subs (FIFA allows 5 in 3 windows + HT).
    """
    if not subs:
        return []

    if is_losing:
        num_subs = random.choices([2, 3, 4, 5], weights=[5, 20, 40, 35])[0]
    else:
        num_subs = random.choices([0, 1, 2, 3, 4, 5], weights=[3, 7, 20, 35, 25, 10])[0]

    num_subs = min(num_subs, len(subs))
    if num_subs == 0:
        return []

    # Substitution windows: HT(46), 60-70, 75-85
    windows = []
    if num_subs >= 1:
        windows.append(random.randint(46, 50) if random.random() < 0.25 else random.randint(55, 65))
    if num_subs >= 2:
        windows.append(random.randint(60, 72))
    if num_subs >= 3:
        windows.append(random.randint(70, 80))
    if num_subs >= 4:
        windows.append(random.randint(75, 85))
    if num_subs >= 5:
        windows.append(random.randint(80, 88))

    windows.sort()

    # Pick outgoing starters (not GK)
    outfield_starters = [s for s in starters if s.get("position") != "GK"]
    random.shuffle(outfield_starters)
    outs = outfield_starters[:num_subs]

    # Match sub positions: prefer same position replacement
    subs_available = list(subs)
    result = []
    for i, out_player in enumerate(outs):
        same_pos = [s for s in subs_available if s.get("position") == out_player.get("position")]
        if same_pos:
            in_player = same_pos[0]
        elif subs_available:
            in_player = subs_available[0]
        else:
            break
        subs_available.remove(in_player)
        result.append((windows[i], out_player, in_player))

    return result


# ---------------------------------------------------------------------------
# Goal timeline — minute-by-minute with realistic distribution
# ---------------------------------------------------------------------------

def _generate_goal_minutes(total_goals: int) -> list[int]:
    """
    Generate sorted goal minutes approximating real WC distribution:
    late goals more common, with occasional stoppage time.
    """
    if total_goals == 0:
        return []

    minute_weights = []
    for m in range(1, 91):
        if m <= 15:
            w = 1.0
        elif m <= 30:
            w = 1.2
        elif m <= 45:
            w = 1.4
        elif m <= 60:
            w = 1.1
        elif m <= 75:
            w = 1.3
        else:
            w = 1.5
        minute_weights.append(w)

    minutes = random.choices(range(1, 91), weights=minute_weights, k=total_goals)
    for i in range(len(minutes)):
        if minutes[i] == 45 and random.random() < 0.3:
            minutes[i] = 45 + random.randint(1, 4)
        elif minutes[i] >= 88 and random.random() < 0.4:
            minutes[i] = 90 + random.randint(1, 5)

    return sorted(minutes)


# ---------------------------------------------------------------------------
# Goal distribution — who scores and assists, respecting sub timings
# ---------------------------------------------------------------------------

def _get_active_players(starters: list[dict], substitutions: list[tuple[int, dict, dict]],
                        minute: int) -> list[dict]:
    """Return players on the pitch at a given minute."""
    active = list(starters)
    for sub_min, out_player, in_player in substitutions:
        if minute >= sub_min:
            if out_player in active:
                active.remove(out_player)
            if in_player not in active:
                active.append(in_player)
    return active


def _pick_scorer(active_players: list[dict]) -> dict:
    """Pick a goal scorer weighted by position and strength."""
    weights = []
    for p in active_players:
        pos = p.get("position", "MID")
        s = p.get("strength", 50)
        w = {"FWD": 5.0, "MID": 2.0, "DEF": 0.4, "GK": 0.02}[pos]
        weights.append(w * (s / 50.0))
    return random.choices(active_players, weights=weights, k=1)[0]


def _pick_assister(active_players: list[dict], scorer_id: str) -> dict | None:
    """Pick an assist provider (different from scorer). ~65% of goals have assists."""
    if random.random() < 0.35:
        return None

    candidates = [p for p in active_players if p["id"] != scorer_id]
    if not candidates:
        return None

    weights = []
    for p in candidates:
        pos = p.get("position", "MID")
        s = p.get("strength", 50)
        w = {"FWD": 2.0, "MID": 4.0, "DEF": 1.0, "GK": 0.05}[pos]
        weights.append(w * (s / 50.0))
    return random.choices(candidates, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Cards — context-aware (losing team fouls more)
# ---------------------------------------------------------------------------

def _generate_cards(active_players: list[dict], goals_for: int,
                    goals_against: int) -> list[tuple[str, str]]:
    """
    Generate yellow/red cards for a ~15-min block.
    Losing teams commit ~40% more fouls.
    """
    cards = []
    is_behind = goals_for < goals_against
    base_yellow_prob = 0.015
    if is_behind:
        base_yellow_prob *= 1.4

    for p in active_players:
        pos = p.get("position", "MID")
        pos_mult = {"GK": 0.2, "DEF": 1.3, "MID": 1.2, "FWD": 0.8}[pos]
        if random.random() < base_yellow_prob * pos_mult:
            cards.append((p["id"], "yellow"))

    return cards


# ---------------------------------------------------------------------------
# GK saves — derived from opponent xG
# ---------------------------------------------------------------------------

def _generate_gk_saves(opp_xg: float, goals_conceded: int) -> int:
    """
    Estimate saves from expected shots.
    Shots ≈ xG × 3.5, saves = shots on target - goals conceded.
    """
    shots = max(1, round(opp_xg * 3.5 + random.gauss(0, 1.5)))
    shots_on_target = max(goals_conceded, round(shots * random.uniform(0.3, 0.5)))
    return max(0, shots_on_target - goals_conceded)


# ---------------------------------------------------------------------------
# Penalty shootout — realistic alternating format
# ---------------------------------------------------------------------------

def _simulate_penalty_shootout() -> tuple[int, int]:
    """
    Simulate penalty shootout with alternating kicks and sudden death.
    Returns (home_score, away_score) where they differ.
    """
    home_score = 0
    away_score = 0

    home_remaining = 5
    away_remaining = 5
    for _round in range(5):
        if random.random() < 0.75:
            home_score += 1
        home_remaining -= 1

        if away_score + away_remaining < home_score:
            break

        if random.random() < 0.75:
            away_score += 1
        away_remaining -= 1

        if home_score + home_remaining < away_score:
            break

    # Sudden death if tied
    while home_score == away_score:
        h = random.random() < 0.75
        a = random.random() < 0.75
        if h:
            home_score += 1
        if a:
            away_score += 1
        if home_score != away_score:
            break

    return home_score, away_score


# ---------------------------------------------------------------------------
# Player ratings — context-aware
# ---------------------------------------------------------------------------

def _compute_rating(player: dict, goals: int, assists: int, yellow_cards: int,
                    red_card: bool, own_goals: int, clean_sheet: bool,
                    is_starter: bool, minutes: int, team_won: bool,
                    saves: int) -> float:
    """Compute a 1-10 match rating based on strength and performance events."""
    if minutes == 0:
        return 0.0

    base = 5.5 + (player.get("strength", 50) - 50) * 0.03

    base += goals * 1.0
    base += assists * 0.5
    base -= yellow_cards * 0.3
    base -= 1.5 if red_card else 0
    base -= own_goals * 1.2
    base += 0.5 if clean_sheet and player.get("position") in ("GK", "DEF") else 0
    base += 0.3 if team_won else -0.2
    base += saves * 0.15 if player.get("position") == "GK" else 0

    # Less time → rating regresses towards 6.0
    minutes_factor = min(1.0, minutes / 60.0)
    base = 6.0 + (base - 6.0) * minutes_factor

    base += random.gauss(0, 0.2)

    return round(max(1.0, min(10.0, base)), 1)


# ---------------------------------------------------------------------------
# Main simulation entry point
# ---------------------------------------------------------------------------

def simulate_match(
    home_players: list[dict],
    away_players: list[dict],
    is_knockout: bool = False,
) -> SimulatedMatch:
    """
    Simulate a single match with coherent timeline.

    1. Select squads and lineups
    2. Compute team strengths and xG
    3. Sample goals and assign minutes
    4. Plan substitutions (adjusted to HT score)
    5. Assign scorers/assisters only from players on the pitch at that minute
    6. Generate cards, saves, and individual stats
    7. Penalty shootout if knockout draw
    """
    home_squad = _select_squad(home_players)
    away_squad = _select_squad(away_players)

    if not home_squad or not away_squad:
        return SimulatedMatch(
            score_home=0 if not home_squad else 3,
            score_away=0 if not away_squad else 3,
            penalty_home=None, penalty_away=None,
            home_stats=[], away_stats=[],
        )

    # --- Team strengths ---
    home_str = compute_team_strength(home_squad)
    away_str = compute_team_strength(away_squad)

    # --- xG with home advantage ---
    HOME_BOOST = 1.08
    home_xg = _expected_goals(
        home_str.attack * HOME_BOOST, home_str.midfield,
        away_str.defense, away_str.goalkeeper, away_str.midfield
    )
    away_xg = _expected_goals(
        away_str.attack, away_str.midfield,
        home_str.defense, home_str.goalkeeper, home_str.midfield
    )

    # --- Sample goals ---
    score_home = _sample_goals(home_xg)
    score_away = _sample_goals(away_xg)

    # --- Goal minutes ---
    home_goal_minutes = _generate_goal_minutes(score_home)
    away_goal_minutes = _generate_goal_minutes(score_away)

    # --- Lineups ---
    home_starters, home_subs = _pick_starters(home_squad)
    away_starters, away_subs = _pick_starters(away_squad)

    # --- Plan subs based on HT score tendency ---
    ht_home = sum(1 for m in home_goal_minutes if m <= 45)
    ht_away = sum(1 for m in away_goal_minutes if m <= 45)
    home_substitutions = _plan_substitutions(home_starters, home_subs, is_losing=(ht_home < ht_away))
    away_substitutions = _plan_substitutions(away_starters, away_subs, is_losing=(ht_away < ht_home))

    # --- Assign scorers and assisters from players on pitch at that minute ---
    events: list[MatchEvent] = []
    home_goal_events: list[SimulatedGoal] = []
    away_goal_events: list[SimulatedGoal] = []

    for minute in home_goal_minutes:
        active = _get_active_players(home_starters, home_substitutions, minute)
        if not active:
            continue

        if random.random() < 0.02:  # own goal
            opp_active = _get_active_players(away_starters, away_substitutions, minute)
            defenders = [p for p in opp_active if p.get("position") == "DEF"]
            og_player = random.choice(defenders) if defenders else random.choice(opp_active)
            home_goal_events.append(SimulatedGoal(minute, og_player["id"], None, is_own_goal=True))
            events.append(MatchEvent(minute, "own_goal", og_player["id"]))
        else:
            is_pen = random.random() < 0.10
            scorer = _pick_scorer(active)
            assister = None if is_pen else _pick_assister(active, scorer["id"])
            home_goal_events.append(SimulatedGoal(
                minute, scorer["id"], assister["id"] if assister else None, is_penalty=is_pen
            ))
            events.append(MatchEvent(minute, "goal", scorer["id"],
                                     detail="penalty" if is_pen else ""))
            if assister:
                events.append(MatchEvent(minute, "assist", assister["id"]))

    for minute in away_goal_minutes:
        active = _get_active_players(away_starters, away_substitutions, minute)
        if not active:
            continue

        if random.random() < 0.02:
            opp_active = _get_active_players(home_starters, home_substitutions, minute)
            defenders = [p for p in opp_active if p.get("position") == "DEF"]
            og_player = random.choice(defenders) if defenders else random.choice(opp_active)
            away_goal_events.append(SimulatedGoal(minute, og_player["id"], None, is_own_goal=True))
            events.append(MatchEvent(minute, "own_goal", og_player["id"]))
        else:
            is_pen = random.random() < 0.10
            scorer = _pick_scorer(active)
            assister = None if is_pen else _pick_assister(active, scorer["id"])
            away_goal_events.append(SimulatedGoal(
                minute, scorer["id"], assister["id"] if assister else None, is_penalty=is_pen
            ))
            events.append(MatchEvent(minute, "goal", scorer["id"],
                                     detail="penalty" if is_pen else ""))
            if assister:
                events.append(MatchEvent(minute, "assist", assister["id"]))

    # --- Sub events ---
    for minute, out_p, in_p in home_substitutions:
        events.append(MatchEvent(minute, "sub_out", out_p["id"]))
        events.append(MatchEvent(minute, "sub_in", in_p["id"]))
    for minute, out_p, in_p in away_substitutions:
        events.append(MatchEvent(minute, "sub_out", out_p["id"]))
        events.append(MatchEvent(minute, "sub_in", in_p["id"]))

    # --- Cards in 3 blocks (context-aware) ---
    home_card_counts: dict[str, int] = {}
    away_card_counts: dict[str, int] = {}
    home_reds: set[str] = set()
    away_reds: set[str] = set()

    for block_start, block_end in [(1, 30), (31, 60), (61, 90)]:
        block_min = (block_start + block_end) // 2
        h_goals_so_far = sum(1 for g in home_goal_events if g.minute <= block_end)
        a_goals_so_far = sum(1 for g in away_goal_events if g.minute <= block_end)

        h_active = _get_active_players(home_starters, home_substitutions, block_min)
        a_active = _get_active_players(away_starters, away_substitutions, block_min)

        for pid, _card_type in _generate_cards(h_active, h_goals_so_far, a_goals_so_far):
            prev = home_card_counts.get(pid, 0)
            if prev == 0:
                home_card_counts[pid] = 1
                events.append(MatchEvent(random.randint(block_start, block_end), "yellow", pid))
            elif prev == 1 and pid not in home_reds:
                home_reds.add(pid)
                events.append(MatchEvent(random.randint(block_start, block_end), "red", pid))

        for pid, _card_type in _generate_cards(a_active, a_goals_so_far, h_goals_so_far):
            prev = away_card_counts.get(pid, 0)
            if prev == 0:
                away_card_counts[pid] = 1
                events.append(MatchEvent(random.randint(block_start, block_end), "yellow", pid))
            elif prev == 1 and pid not in away_reds:
                away_reds.add(pid)
                events.append(MatchEvent(random.randint(block_start, block_end), "red", pid))

    # --- Penalty shootout ---
    penalty_home = None
    penalty_away = None
    if is_knockout and score_home == score_away:
        penalty_home, penalty_away = _simulate_penalty_shootout()

    # --- GK saves ---
    home_gk_saves = _generate_gk_saves(away_xg, score_away)
    away_gk_saves = _generate_gk_saves(home_xg, score_home)

    # --- Winner for rating context ---
    if penalty_home is not None:
        home_won = penalty_home > penalty_away
    else:
        home_won = score_home > score_away
    away_won = not home_won and score_home != score_away

    # --- Build per-player stats ---
    home_stats = _build_player_stats(
        home_starters, home_subs, home_substitutions,
        home_goal_events, away_goal_events,
        home_card_counts, home_reds,
        score_away, home_gk_saves, home_won,
    )
    away_stats = _build_player_stats(
        away_starters, away_subs, away_substitutions,
        away_goal_events, home_goal_events,
        away_card_counts, away_reds,
        score_home, away_gk_saves, away_won,
    )

    events.sort(key=lambda e: e.minute)

    return SimulatedMatch(
        score_home=score_home,
        score_away=score_away,
        penalty_home=penalty_home,
        penalty_away=penalty_away,
        home_stats=home_stats,
        away_stats=away_stats,
        events=events,
    )


# ---------------------------------------------------------------------------
# Build per-player stats from timeline
# ---------------------------------------------------------------------------

def _build_player_stats(
    starters: list[dict],
    subs: list[dict],
    substitutions: list[tuple[int, dict, dict]],
    goals_for_events: list[SimulatedGoal],
    goals_against_events: list[SimulatedGoal],
    card_counts: dict[str, int],
    reds: set[str],
    goals_conceded: int,
    gk_saves: int,
    team_won: bool,
) -> list[SimulatedPlayerStats]:
    """Build final stats for each player in the squad."""

    sub_out_map = {out_p["id"]: minute for minute, out_p, _ in substitutions}
    sub_in_map = {in_p["id"]: minute for minute, _, in_p in substitutions}
    subs_used_ids = set(sub_in_map.keys())

    player_goals: dict[str, int] = {}
    player_assists: dict[str, int] = {}
    player_own_goals: dict[str, int] = {}

    for g in goals_for_events:
        if g.is_own_goal:
            player_own_goals[g.scorer_id] = player_own_goals.get(g.scorer_id, 0) + 1
        else:
            player_goals[g.scorer_id] = player_goals.get(g.scorer_id, 0) + 1
            if g.assist_id:
                player_assists[g.assist_id] = player_assists.get(g.assist_id, 0) + 1

    clean_sheet = goals_conceded == 0
    stats = []

    # --- Starters ---
    for p in starters:
        pid = p["id"]
        pos = p.get("position", "MID")

        if pid in sub_out_map:
            minutes = sub_out_map[pid]
        elif pid in reds:
            minutes = random.randint(30, 85)
        else:
            minutes = 90

        g = player_goals.get(pid, 0)
        a = player_assists.get(pid, 0)
        og = player_own_goals.get(pid, 0)
        yc = min(card_counts.get(pid, 0), 2)
        rc = pid in reds
        sv = gk_saves if pos == "GK" else 0
        gc = goals_conceded if pos in ("GK", "DEF") and minutes >= 60 else 0
        cs = clean_sheet and pos in ("GK", "DEF") and minutes >= 60

        rating = _compute_rating(p, g, a, yc, rc, og, cs, True, minutes, team_won, sv)

        stats.append(SimulatedPlayerStats(
            player_id=pid, position=pos, minutes_played=minutes,
            goals=g, assists=a, yellow_cards=yc, red_card=rc,
            own_goals=og, penalties_missed=0, penalties_saved=0,
            saves=sv, goals_conceded=gc, clean_sheet=cs,
            rating=rating, is_starter=True,
        ))

    # --- Subs ---
    for p in subs:
        pid = p["id"]
        pos = p.get("position", "MID")

        if pid not in subs_used_ids:
            stats.append(SimulatedPlayerStats(
                player_id=pid, position=pos, minutes_played=0,
                goals=0, assists=0, yellow_cards=0, red_card=False,
                own_goals=0, penalties_missed=0, penalties_saved=0,
                saves=0, goals_conceded=0, clean_sheet=False,
                rating=0.0, is_starter=False,
            ))
            continue

        entered = sub_in_map[pid]
        minutes = 90 - entered

        g = player_goals.get(pid, 0)
        a = player_assists.get(pid, 0)
        og = player_own_goals.get(pid, 0)
        yc = min(card_counts.get(pid, 0), 2)
        rc = pid in reds
        gc = goals_conceded if pos in ("GK", "DEF") and minutes >= 30 else 0
        cs = clean_sheet and pos in ("GK", "DEF") and minutes >= 30

        rating = _compute_rating(p, g, a, yc, rc, og, cs, False, minutes, team_won, 0)

        stats.append(SimulatedPlayerStats(
            player_id=pid, position=pos, minutes_played=minutes,
            goals=g, assists=a, yellow_cards=yc, red_card=rc,
            own_goals=og, penalties_missed=0, penalties_saved=0,
            saves=0, goals_conceded=gc, clean_sheet=cs,
            rating=rating, is_starter=False,
        ))

    return stats
