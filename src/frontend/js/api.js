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
