Router.register('/stats', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [scorers, assists, rated, cards, keepers] = await Promise.all([
      API.get('/stats/top-scorers?limit=15'),
      API.get('/stats/top-assists?limit=15'),
      API.get('/stats/top-rated?limit=15'),
      API.get('/stats/top-cards?limit=15'),
      API.get('/stats/top-keepers?limit=15'),
    ]);

    const hasData = scorers.length > 0;

    if (!hasData) {
      app.innerHTML = `
        <h1 class="section-title">Estadisticas</h1>
        <div class="card"><p>No hay estadisticas todavia. Simula algunos partidos primero.</p></div>
      `;
      return;
    }

    function playerRow(p, mainStat, mainLabel, extraStats) {
      return `
        <div class="stat-row" style="cursor:pointer" onclick="location.hash='#/player/${p.id}'">
          <img src="${p.photo || ''}" alt="" class="stat-photo" referrerpolicy="no-referrer" onerror="this.style.display='none'">
          ${posBadge(p.position || 'GK')}
          <div class="stat-player-info">
            <span class="stat-player-name">${p.name}</span>
            <span class="stat-player-meta">${p.country_code} · ${p.club || ''}</span>
          </div>
          <div class="stat-numbers">
            <span class="stat-main">${mainStat}</span>
            <span class="stat-label">${mainLabel}</span>
          </div>
          ${extraStats}
        </div>`;
    }

    app.innerHTML = `
      <h1 class="section-title">Estadisticas del Torneo</h1>

      <div class="stats-grid">
        <div class="card">
          <div class="card-title">Goleadores</div>
          ${scorers.length ? scorers.map((p, i) => playerRow(p, p.goals, 'goles',
            `<div class="stat-numbers"><span class="stat-secondary">${p.assists}</span><span class="stat-label">ast</span></div>
             <div class="stat-numbers"><span class="stat-secondary">${p.matches}</span><span class="stat-label">PJ</span></div>`
          )).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>

        <div class="card">
          <div class="card-title">Asistentes</div>
          ${assists.length ? assists.map((p, i) => playerRow(p, p.assists, 'ast',
            `<div class="stat-numbers"><span class="stat-secondary">${p.goals}</span><span class="stat-label">goles</span></div>
             <div class="stat-numbers"><span class="stat-secondary">${p.matches}</span><span class="stat-label">PJ</span></div>`
          )).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>

        <div class="card">
          <div class="card-title">Mejor Puntuacion</div>
          ${rated.length ? rated.map((p, i) => playerRow(p, p.avg_rating, 'media',
            `<div class="stat-numbers"><span class="stat-secondary">${p.goals}</span><span class="stat-label">goles</span></div>
             <div class="stat-numbers"><span class="stat-secondary">${p.matches}</span><span class="stat-label">PJ</span></div>`
          )).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>

        <div class="card">
          <div class="card-title">Tarjetas</div>
          ${cards.length ? cards.map((p, i) => playerRow(p,
            `<span style="color:#eab308">${p.yellows}</span>/<span style="color:#ef4444">${p.reds}</span>`, 'TA/TR',
            `<div class="stat-numbers"><span class="stat-secondary">${p.matches}</span><span class="stat-label">PJ</span></div>`
          )).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>

        <div class="card">
          <div class="card-title">Porteros</div>
          ${keepers.length ? keepers.map((p, i) => playerRow(p, p.clean_sheets, 'imbatido',
            `<div class="stat-numbers"><span class="stat-secondary">${p.saves}</span><span class="stat-label">paradas</span></div>
             <div class="stat-numbers"><span class="stat-secondary">${p.goals_conceded}</span><span class="stat-label">GC</span></div>
             <div class="stat-numbers"><span class="stat-secondary">${p.avg_rating}</span><span class="stat-label">media</span></div>`
          )).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
