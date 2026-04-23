Router.register('/teams', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const countries = await API.get('/countries');

    app.innerHTML = `
      <h1 class="section-title">🏴 Selecciones</h1>
      <div class="teams-grid">
        ${countries.map(c => `
          <div class="team-card" onclick="location.hash='#/team/${c.code}'">
            <div class="team-flag">${flagImg(c.flag, 48)}</div>
            <div class="team-name">${c.name}</div>
            <div class="team-group">${c.group_letter ? `Grupo ${c.group_letter}` : ''}</div>
            <div class="team-players">${c.player_count} jugadores</div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
