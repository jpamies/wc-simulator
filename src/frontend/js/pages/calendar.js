Router.register('/calendar', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const calendar = await API.get('/tournament/calendar');

    app.innerHTML = `
      <h1 class="section-title">📅 Calendario</h1>
      ${calendar.map(md => `
        <div class="sim-phase">
          <div class="sim-phase-title">${md.name}</div>
          <div class="section-subtitle">${md.date} · ${md.status}</div>
          ${md.matches.length === 0
            ? '<p style="color:var(--text-muted)">Partidos por determinar</p>'
            : md.matches.map(m => renderMatchCard(m)).join('')
          }
        </div>
      `).join('')}
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
