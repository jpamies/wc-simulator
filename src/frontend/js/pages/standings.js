Router.register('/standings', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [standings, bestThirds] = await Promise.all([
      API.get('/tournament/standings'),
      API.get('/tournament/best-thirds').catch(() => []),
    ]);
    const bestThirdSet = new Set(bestThirds);

    app.innerHTML = `
      <h1 class="section-title">📊 Clasificación — Fase de Grupos</h1>
      <div class="standings-legend">
        <span class="legend-item"><span class="legend-dot legend-dot-qualified"></span> Clasificado (1º/2º)</span>
        <span class="legend-item"><span class="legend-dot legend-dot-third"></span> Mejor 3º (clasificado)</span>
        <span class="legend-item"><span class="legend-dot legend-dot-eliminated"></span> Eliminado</span>
      </div>
      <div class="groups-grid">
        ${Object.entries(standings).sort().map(([letter, teams]) => `
          <div class="card group-card">
            <div class="group-title">Grupo ${letter}</div>
            <table class="standings-table">
              <thead>
                <tr>
                  <th></th>
                  <th>Equipo</th>
                  <th>PJ</th>
                  <th>G</th>
                  <th>E</th>
                  <th>P</th>
                  <th>GF</th>
                  <th>GC</th>
                  <th>DG</th>
                  <th>Pts</th>
                </tr>
              </thead>
              <tbody>
                ${teams.map((t, i) => {
                  let rowClass = '';
                  if (i < 2) rowClass = 'qualified';
                  else if (i === 2 && bestThirdSet.has(t.country_code)) rowClass = 'qualified-third';
                  return `
                  <tr class="${rowClass}">
                    <td>${flagImg(t.flag, 20)}</td>
                    <td>
                      <a href="#/team/${t.country_code}" style="color:inherit;text-decoration:none;">
                        ${t.country_name || t.country_code}
                      </a>
                    </td>
                    <td>${t.played}</td>
                    <td>${t.won}</td>
                    <td>${t.drawn}</td>
                    <td>${t.lost}</td>
                    <td>${t.goals_for}</td>
                    <td>${t.goals_against}</td>
                    <td>${t.goal_difference}</td>
                    <td><strong>${t.points}</strong></td>
                  </tr>
                `}).join('')}
              </tbody>
            </table>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
