Router.register('/stats', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [scorers, assists, rated, cards, keepers] = await Promise.all([
      API.get('/stats/top-scorers?limit=10'),
      API.get('/stats/top-assists?limit=10'),
      API.get('/stats/top-rated?limit=10'),
      API.get('/stats/top-cards?limit=10'),
      API.get('/stats/top-keepers?limit=10'),
    ]);

    const hasData = scorers.length > 0;

    if (!hasData) {
      app.innerHTML = `
        <h1 class="section-title">Estadisticas</h1>
        <div class="card"><p>No hay estadisticas todavia. Simula algunos partidos primero.</p></div>
      `;
      return;
    }

    // stats: [{value, highlight?}, ...] in same order as labels in header
    function playerRow(p, stats, idx) {
      const cells = stats.map(s => `<span class="stat-cell ${s.highlight ? 'stat-cell-main' : ''}">${s.value}</span>`).join('');
      return `
        <div class="stat-row" style="cursor:pointer" onclick="location.hash='#/player/${p.id}'">
          <span class="stat-rank">${idx + 1}</span>
          <div class="stat-photo-row">
            <img src="${p.photo || ''}" alt="" class="stat-photo" referrerpolicy="no-referrer" onerror="this.style.display='none'">
            ${posBadge(p.position || 'GK')}
          </div>
          <div class="stat-name-col">
            <span class="stat-player-name" title="${p.name}">${p.name}</span>
            <span class="stat-name-flag">${flagImg(p.country_flag, 16)}</span>
          </div>
          <div class="stat-cells">${cells}</div>
        </div>`;
    }

    function statHeader(labels) {
      const cells = labels.map(l => `<span class="stat-cell">${l}</span>`).join('');
      return `<div class="stat-row stat-header">
        <span class="stat-rank"></span>
        <div class="stat-photo-row" style="visibility:hidden"><div class="stat-photo"></div></div>
        <div class="stat-name-col"></div>
        <div class="stat-cells">${cells}</div>
      </div>`;
    }

    app.innerHTML = `
      <h1 class="section-title">Estadisticas del Torneo</h1>

      <div class="stats-grid">
        <div class="card">
          <div class="card-title">Goleadores</div>
          ${scorers.length ? statHeader(['GOL', 'AST', 'PJ']) + scorers.map((p, i) => playerRow(p, [
            {value: p.goals, highlight: true},
            {value: p.assists},
            {value: p.matches},
          ], i)).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>

        <div class="card">
          <div class="card-title">Asistentes</div>
          ${assists.length ? statHeader(['AST', 'GOL', 'PJ']) + assists.map((p, i) => playerRow(p, [
            {value: p.assists, highlight: true},
            {value: p.goals},
            {value: p.matches},
          ], i)).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>

        <div class="card">
          <div class="card-title">Mejor Puntuacion</div>
          ${rated.length ? statHeader(['MEDIA', 'GOL', 'PJ']) + rated.map((p, i) => playerRow(p, [
            {value: p.avg_rating, highlight: true},
            {value: p.goals},
            {value: p.matches},
          ], i)).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>

        <div class="card">
          <div class="card-title">Tarjetas</div>
          ${cards.length ? statHeader(['TA', 'TR', 'PJ']) + cards.map((p, i) => playerRow(p, [
            {value: `<span style="color:#eab308">${p.yellows}</span>`, highlight: true},
            {value: `<span style="color:#ef4444">${p.reds}</span>`, highlight: true},
            {value: p.matches},
          ], i)).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>

        <div class="card">
          <div class="card-title">Porteros</div>
          ${keepers.length ? statHeader(['IMB', 'PAR', 'GC', 'MED']) + keepers.map((p, i) => playerRow(p, [
            {value: p.clean_sheets, highlight: true},
            {value: p.saves},
            {value: p.goals_conceded},
            {value: p.avg_rating},
          ], i)).join('') : '<p class="stat-empty">Sin datos</p>'}
        </div>
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
