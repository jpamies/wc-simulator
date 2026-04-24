Router.register('/squads', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [squads, countries] = await Promise.all([
      API.get('/squads'),
      API.get('/countries'),
    ]);

    const countryMap = {};
    countries.forEach(c => { countryMap[c.code] = c; });

    app.innerHTML = `
      <div class="squads-header">
        <h1 class="section-title">Convocatorias</h1>
        <div class="squads-actions">
          <button class="btn btn-gold" onclick="autoSelectAll()">Auto-seleccionar todas</button>
        </div>
      </div>

      <div class="squads-summary" id="squads-summary"></div>

      <div class="squads-grid" id="squads-grid">
        ${squads.map(s => {
          const ct = countryMap[s.country_code] || {};
          const complete = s.squad_size >= 23;
          return `
          <div class="squad-card ${complete ? 'squad-complete' : ''}" onclick="location.hash='#/squad/${s.country_code}'">
            <div class="squad-card-flag">${flagImg(ct.flag, 40)}</div>
            <div class="squad-card-info">
              <div class="squad-card-name">${s.country_name}</div>
              <div class="squad-card-count">${s.squad_size}/26</div>
            </div>
            <div class="squad-card-positions">
              <span class="sq-pos sq-gk">${s.gk}</span>
              <span class="sq-pos sq-def">${s.defs}</span>
              <span class="sq-pos sq-mid">${s.mids}</span>
              <span class="sq-pos sq-fwd">${s.fwds}</span>
            </div>
            ${complete ? '<span class="squad-check">✓</span>' : ''}
          </div>`;
        }).join('')}
      </div>
    `;

    // Summary
    const withSquad = squads.filter(s => s.squad_size > 0).length;
    const completedSquads = squads.filter(s => s.squad_size >= 23).length;
    const totalPlayers = squads.reduce((a, s) => a + s.squad_size, 0);
    document.getElementById('squads-summary').innerHTML = `
      <div class="summary-stat"><span class="summary-val">${withSquad}</span><span class="summary-label">Con convocatoria</span></div>
      <div class="summary-stat"><span class="summary-val">${completedSquads}</span><span class="summary-label">Completas</span></div>
      <div class="summary-stat"><span class="summary-val">${totalPlayers}</span><span class="summary-label">Jugadores</span></div>
      <div class="summary-stat"><span class="summary-val">${48 - withSquad}</span><span class="summary-label">Pendientes</span></div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});

async function autoSelectAll() {
  if (!confirm('¿Auto-seleccionar las mejores convocatorias para las 48 selecciones?')) return;
  showToast('Seleccionando convocatorias...', 'info');
  try {
    await API.post('/squads/auto-all');
    showToast('48 convocatorias generadas', 'success');
    location.hash = '#/squads';
    Router.handleRoute();
  } catch (e) {
    showToast(e.message, 'error');
  }
}
