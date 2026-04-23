Router.register('/team/:code', async (params) => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [country, allPlayers, squad, matches] = await Promise.all([
      API.get(`/countries/${params.code}`),
      API.get(`/countries/${params.code}/players`),
      API.get(`/squads/${params.code}`),
      API.get(`/matches?country=${params.code}`),
    ]);

    // Use squad if available, otherwise fall back to all players
    const players = squad.length > 0 ? squad : allPlayers;
    const squadLabel = squad.length > 0 ? 'Convocatoria' : 'Plantilla completa';

    const byPos = { GK: [], DEF: [], MID: [], FWD: [] };
    players.forEach(p => (byPos[p.position] || []).push(p));
    for (const pos in byPos) byPos[pos].sort((a, b) => b.strength - a.strength);

    // Team stats
    const n = players.length || 1;
    const avgOvr = (players.reduce((a, p) => a + (p.strength || 0), 0) / n).toFixed(1);
    const avgAge = (players.reduce((a, p) => a + (p.age || 0), 0) / n).toFixed(1);
    const totalValue = players.reduce((a, p) => a + (p.market_value || 0), 0);

    // Attribute averages by role
    const fwdMid = players.filter(p => p.position === 'FWD' || p.position === 'MID');
    const defGk = players.filter(p => p.position === 'DEF' || p.position === 'GK');
    const avg = (arr, key) => arr.length ? (arr.reduce((a, p) => a + (p[key] || 0), 0) / arr.length).toFixed(0) : '—';

    const atkRating = fwdMid.length ? Math.round((
      fwdMid.reduce((a, p) => a + (p.shooting || 0) + (p.dribbling || 0) + (p.pace || 0), 0)
    ) / (fwdMid.length * 3)) : '—';
    const defRating = defGk.length ? Math.round((
      defGk.reduce((a, p) => a + (p.defending || 0) + (p.physic || 0), 0)
    ) / (defGk.length * 2)) : '—';
    const midRating = avg(players.filter(p => p.position === 'MID'), 'passing');

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

        <div class="team-stats-grid">
          <div class="team-stat">
            <span class="team-stat-val">${avgOvr}</span>
            <span class="team-stat-lbl">Media OVR</span>
          </div>
          <div class="team-stat">
            <span class="team-stat-val team-stat-atk">${atkRating}</span>
            <span class="team-stat-lbl">⚔️ Ataque</span>
          </div>
          <div class="team-stat">
            <span class="team-stat-val team-stat-mid">${midRating}</span>
            <span class="team-stat-lbl">🎯 Creación</span>
          </div>
          <div class="team-stat">
            <span class="team-stat-val team-stat-def">${defRating}</span>
            <span class="team-stat-lbl">🛡️ Defensa</span>
          </div>
          <div class="team-stat">
            <span class="team-stat-val">${formatMoney(totalValue)}</span>
            <span class="team-stat-lbl">Valor total</span>
          </div>
          <div class="team-stat">
            <span class="team-stat-val">${avgAge}</span>
            <span class="team-stat-lbl">Edad media</span>
          </div>
        </div>
      </div>

      <h2 class="section-title">${squadLabel} (${players.length})</h2>
      ${['GK', 'DEF', 'MID', 'FWD'].map(pos => `
        <div class="card">
          <div class="card-title">${pos} (${byPos[pos].length})</div>
          ${byPos[pos].map(p => `
            <div class="player-row">
              <img src="${p.photo || ''}" alt="" class="player-photo" referrerpolicy="no-referrer" onerror="this.style.display='none'">
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
