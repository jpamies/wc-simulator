const API = {
  BASE: '/api/v1',

  async request(path, opts = {}) {
    const url = `${this.BASE}${path}`;
    const config = { headers: { 'Content-Type': 'application/json' }, ...opts };
    const res = await fetch(url, config);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
  },

  get(path) { return this.request(path); },

  post(path, body) {
    return this.request(path, { method: 'POST', body: JSON.stringify(body) });
  },

  patch(path, body) {
    return this.request(path, { method: 'PATCH', body: JSON.stringify(body) });
  },

  put(path, body) {
    return this.request(path, { method: 'PUT', body: JSON.stringify(body) });
  },
};

function formatMoney(val) {
  if (!val) return '—';
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M€`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K€`;
  return `${val}€`;
}

function posBadge(pos) {
  return `<span class="player-pos pos-${pos}">${pos}</span>`;
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function flagImg(url, size = 24) {
  if (!url) return '';
  return `<img src="${url}" alt="" class="flag-img" width="${size}" height="${Math.round(size * 0.67)}" loading="lazy">`;
}

function matchStatusBadge(match) {
  if (match.is_simulated) return '<span class="badge badge-simulated">SIM</span>';
  if (match.status === 'finished') return '<span class="badge badge-real">REAL</span>';
  return '<span class="badge badge-scheduled">POR JUGAR</span>';
}

function renderMatchCard(m, opts = {}) {
  const isLocal = opts.local || false;
  const localResult = isLocal ? SimState.getMatchResult(m.id) : null;
  const displayMatch = localResult ? { ...m, ...localResult, status: 'finished' } : m;

  const scoreContent = displayMatch.status === 'finished'
    ? `<span>${displayMatch.score_home}</span><span class="sep">-</span><span>${displayMatch.score_away}</span>`
    : `<span class="match-score not-played">vs</span>`;

  const penalties = (displayMatch.penalty_home != null)
    ? `<div class="match-penalties">(${displayMatch.penalty_home}-${displayMatch.penalty_away} pen)</div>`
    : '';

  const homeName = displayMatch.home_team || displayMatch.home_code || '?';
  const awayName = displayMatch.away_team || displayMatch.away_code || '?';

  const badge = localResult
    ? '<span class="badge badge-simulated">LOCAL</span>'
    : matchStatusBadge(displayMatch);

  return `
    <div class="match-card" onclick="location.hash='#/match/${m.id}'">
      <div class="match-team">
        ${flagImg(displayMatch.home_flag, 28)}
        <span class="match-team-name">${homeName}</span>
      </div>
      <div>
        <div class="match-score ${displayMatch.status !== 'finished' ? 'not-played' : ''}">${scoreContent}</div>
        ${penalties}
        <div class="match-meta">${badge}</div>
      </div>
      <div class="match-team away">
        <span class="match-team-name">${awayName}</span>
        ${flagImg(displayMatch.away_flag, 28)}
      </div>
    </div>
  `;
}


// ─── SimState: localStorage simulation state manager ───

const SimState = {
  _key: 'wcs_sim',

  _load() {
    try { return JSON.parse(localStorage.getItem(this._key) || '{}'); }
    catch { return {}; }
  },

  _save(state) {
    localStorage.setItem(this._key, JSON.stringify(state));
  },

  isActive() {
    const s = this._load();
    return !!s.active;
  },

  getName() {
    return this._load().name || 'Mi simulación';
  },

  start(name = 'Mi simulación') {
    this._save({ active: true, name, matches: {}, stats: {}, squads: {} });
  },

  clear() {
    localStorage.removeItem(this._key);
  },

  // ─── Match results ───
  getMatchResult(matchId) {
    const s = this._load();
    return s.matches?.[matchId] || null;
  },

  setMatchResult(matchId, result) {
    const s = this._load();
    if (!s.matches) s.matches = {};
    s.matches[matchId] = result;
    this._save(s);
  },

  getAllMatchResults() {
    return this._load().matches || {};
  },

  // ─── Player stats ───
  getMatchStats(matchId) {
    const s = this._load();
    return s.stats?.[matchId] || [];
  },

  setMatchStats(matchId, stats) {
    const s = this._load();
    if (!s.stats) s.stats = {};
    s.stats[matchId] = stats;
    this._save(s);
  },

  // ─── Squad overrides ───
  getSquad(countryCode) {
    const s = this._load();
    return s.squads?.[countryCode] || null;
  },

  setSquad(countryCode, playerIds) {
    const s = this._load();
    if (!s.squads) s.squads = {};
    s.squads[countryCode] = playerIds;
    this._save(s);
  },

  getAllSquads() {
    return this._load().squads || {};
  },

  // ─── Export/import for sharing ───
  exportState() {
    return this._load();
  },

  importState(state) {
    this._save({ ...state, active: true });
  },

  // ─── Standings calculation from local results ───
  calcGroupStandings(groups, allMatches) {
    // groups = {A: ["MEX","RSA",...], B: [...], ...}
    // allMatches = [{id, matchday_id, home_code, away_code, group_name, ...}]
    const localResults = this.getAllMatchResults();
    const standings = {};

    for (const [letter, codes] of Object.entries(groups)) {
      standings[letter] = codes.map(code => ({
        country_code: code, group_letter: letter,
        played: 0, won: 0, drawn: 0, lost: 0,
        goals_for: 0, goals_against: 0, points: 0,
      }));
    }

    for (const m of allMatches) {
      if (!m.group_name) continue;
      // Use local result if available, else DB result
      const result = localResults[m.id] || (m.status === 'finished' ? m : null);
      if (!result || result.score_home == null) continue;

      const group = standings[m.group_name];
      if (!group) continue;

      const home = group.find(t => t.country_code === m.home_code);
      const away = group.find(t => t.country_code === m.away_code);
      if (!home || !away) continue;

      const sh = result.score_home, sa = result.score_away;
      home.played++; away.played++;
      home.goals_for += sh; home.goals_against += sa;
      away.goals_for += sa; away.goals_against += sh;

      if (sh > sa) { home.won++; home.points += 3; away.lost++; }
      else if (sa > sh) { away.won++; away.points += 3; home.lost++; }
      else { home.drawn++; home.points += 1; away.drawn++; away.points += 1; }
    }

    // Sort each group
    for (const teams of Object.values(standings)) {
      teams.sort((a, b) =>
        (b.points - a.points) ||
        ((b.goals_for - b.goals_against) - (a.goals_for - a.goals_against)) ||
        (b.goals_for - a.goals_for)
      );
    }
    return standings;
  },

  // ─── Best third-place teams ───
  getBestThirds(standings) {
    const thirds = [];
    for (const [group, teams] of Object.entries(standings)) {
      if (teams.length >= 3) thirds.push({ ...teams[2], _group: group });
    }
    thirds.sort((a, b) =>
      (b.points - a.points) ||
      ((b.goals_for - b.goals_against) - (a.goals_for - a.goals_against)) ||
      (b.goals_for - a.goals_for)
    );
    return thirds.slice(0, 8);
  },
};
