Router.register('/team/:code', async (params) => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [country, players, matches] = await Promise.all([
      API.get(`/countries/${params.code}`),
      API.get(`/countries/${params.code}/players`),
      API.get(`/matches?country=${params.code}`),
    ]);

    const byPos = { GK: [], DEF: [], MID: [], FWD: [] };
    players.forEach(p => (byPos[p.position] || []).push(p));
    for (const pos in byPos) byPos[pos].sort((a, b) => b.strength - a.strength);

    app.innerHTML = `
      <a href="#/teams" class="btn btn-outline btn-sm" style="margin-bottom:1rem;">← Volver</a>

      <div class="card">
        <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;">
          <span style="font-size:3rem;">${flagImg(country.flag, 64)}</span>
          <div>
            <h1 style="margin:0;">${country.name}</h1>
            <span style="color:var(--text-secondary);">${country.name_local || ''} · ${country.confederation || ''} · Grupo ${country.group_letter || '—'}</span>
          </div>
        </div>
      </div>

      <h2 class="section-title">Plantilla (${players.length})</h2>
      ${['GK', 'DEF', 'MID', 'FWD'].map(pos => `
        <div class="card">
          <div class="card-title">${pos} (${byPos[pos].length})</div>
          ${byPos[pos].map(p => `
            <div class="player-row">
              <img src="${p.photo || ''}" alt="" class="player-photo" onerror="this.style.display='none'">
              ${posBadge(p.position)}
              <div class="player-info">
                <span class="player-name">${p.name}</span>
                <span class="player-detail">${p.detailed_position || ''} · ${p.club || ''} · ${p.league || ''}</span>
              </div>
              <span class="player-age">${p.age || ''}y</span>
              <span class="player-value">${formatMoney(p.market_value)}</span>
              <span class="player-ovr">${p.strength}</span>
            </div>
          `).join('')}
        </div>
      `).join('')}

      <h2 class="section-title">Partidos</h2>
      ${matches.length === 0
        ? '<p style="color:var(--text-muted)">Sin partidos registrados</p>'
        : matches.map(m => renderMatchCard(m)).join('')
      }
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
