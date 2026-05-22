Router.register('/', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [overview, countries] = await Promise.all([
      API.get('/tournament/overview'),
      API.get('/countries'),
    ]);

    const countryMap = {};
    countries.forEach(c => { countryMap[c.code] = c; });

    app.innerHTML = `
      <div class="hero">
        <h1>⚽ <span>World Cup 2026</span> Simulator</h1>
        <p>Simula partidos, consulta resultados y sigue el torneo en tiempo real</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">${overview.total_teams}</div>
          <div class="stat-label">Selecciones</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${overview.total_players}</div>
          <div class="stat-label">Jugadores</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${overview.matches_played} / ${overview.total_matches}</div>
          <div class="stat-label">Partidos jugados</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${overview.current_phase}</div>
          <div class="stat-label">Fase actual</div>
        </div>
      </div>

      <div class="sim-controls">
        <button class="btn btn-gold" onclick="location.hash='#/simulate'">🎲 Simular torneo</button>
        <button class="btn btn-primary" onclick="location.hash='#/calendar'">📅 Ver calendario</button>
        <button class="btn btn-outline" onclick="location.hash='#/standings'">📊 Clasificación</button>
      </div>

      <h2 class="section-title">Grupos</h2>
      <div class="groups-grid">
        ${Object.entries(overview.groups).map(([letter, codes]) => `
          <div class="card group-card">
            <div class="group-title">Grupo ${letter}</div>
            <div>${codes.map(c => {
              const ct = countryMap[c] || {};
              return `
              <a href="#/team/${c}" style="text-decoration:none;color:inherit;">
                <div class="player-row" style="cursor:pointer;gap:0.5rem;">
                  ${flagImg(ct.flag, 22)}
                  <span class="match-team-name">${ct.name || c}</span>
                </div>
              </a>`;
            }).join('')}</div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
