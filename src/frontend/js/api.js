const API = {
  BASE: '/api/v1',

  // Current tournament context (null = canonical/default)
  _tournamentId: null,
  _manageToken: null,

  setTournament(id, token) {
    this._tournamentId = id;
    this._manageToken = token;
  },

  clearTournament() {
    this._tournamentId = null;
    this._manageToken = null;
  },

  getTournamentId() {
    return this._tournamentId;
  },

  getManageToken() {
    return this._manageToken;
  },

  _addTournamentParam(path) {
    if (!this._tournamentId) return path;
    const sep = path.includes('?') ? '&' : '?';
    return `${path}${sep}tournament_id=${this._tournamentId}`;
  },

  async request(path, opts = {}) {
    const url = `${this.BASE}${this._addTournamentParam(path)}`;
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    if (this._manageToken && (opts.method === 'POST' || opts.method === 'PUT' ||
        opts.method === 'PATCH' || opts.method === 'DELETE')) {
      headers['X-Manage-Token'] = this._manageToken;
    }
    const config = { ...opts, headers };
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

  delete(path) {
    return this.request(path, { method: 'DELETE' });
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

function renderMatchCard(m) {
  const scoreContent = m.status === 'finished'
    ? `<span>${m.score_home}</span><span class="sep">-</span><span>${m.score_away}</span>`
    : `<span class="match-score not-played">vs</span>`;

  const penalties = (m.penalty_home != null)
    ? `<div class="match-penalties">(${m.penalty_home}-${m.penalty_away} pen)</div>`
    : '';

  const homeName = m.home_team || m.home_code || '?';
  const awayName = m.away_team || m.away_code || '?';

  return `
    <div class="match-card" onclick="location.hash='#/match/${m.id}'">
      <div class="match-team">
        ${flagImg(m.home_flag, 28)}
        <span class="match-team-name">${homeName}</span>
      </div>
      <div>
        <div class="match-score ${m.status !== 'finished' ? 'not-played' : ''}">${scoreContent}</div>
        ${penalties}
        <div class="match-meta">${matchStatusBadge(m)}</div>
      </div>
      <div class="match-team away">
        <span class="match-team-name">${awayName}</span>
        ${flagImg(m.away_flag, 28)}
      </div>
    </div>
  `;
}

// ─── Tournament context management ───

const TournamentCtx = {
  _key: 'wcs_tournaments',

  load() {
    // Check if a tournament slug is in the URL hash
    const hash = location.hash || '';
    const match = hash.match(/#\/t\/([a-z0-9]+)/);
    if (match) {
      const slug = match[1];
      const saved = this._getSaved(slug);
      if (saved) {
        API.setTournament(saved.id, saved.token);
      }
      return slug;
    }
    // No tournament context = canonical
    API.clearTournament();
    return null;
  },

  async enter(slug) {
    // Fetch tournament info
    const t = await fetch(`${API.BASE}/tournaments/${slug}`).then(r => r.json());
    const saved = this._getSaved(slug);
    const token = saved?.token || null;
    API.setTournament(t.id, token);
    this._saveTournamentId(slug, t.id, token);
    return t;
  },

  saveToken(slug, id, token) {
    this._saveTournamentId(slug, id, token);
    API.setTournament(id, token);
  },

  hasWriteAccess() {
    return !!API.getManageToken();
  },

  exit() {
    API.clearTournament();
    location.hash = '#/';
  },

  _getSaved(slug) {
    try {
      const all = JSON.parse(localStorage.getItem(this._key) || '{}');
      return all[slug] || null;
    } catch { return null; }
  },

  _saveTournamentId(slug, id, token) {
    try {
      const all = JSON.parse(localStorage.getItem(this._key) || '{}');
      all[slug] = { id, token };
      localStorage.setItem(this._key, JSON.stringify(all));
    } catch {}
  },
};
