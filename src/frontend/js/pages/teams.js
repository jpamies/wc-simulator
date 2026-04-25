Router.register('/teams', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [countries, squads] = await Promise.all([
      API.get('/countries'),
      API.get('/squads'),
    ]);

    const squadMap = {};
    squads.forEach(s => { squadMap[s.country_code] = s; });

    app.innerHTML = `
      <div class="squads-header">
        <h1 class="section-title">Selecciones</h1>
        <a href="#/squads" class="btn btn-gold">Convocatorias</a>
      </div>
      <div class="teams-grid">
        ${countries.map(c => {
          const s = squadMap[c.code];
          const hasSquad = s && s.squad_size > 0;
          return `
          <div class="team-card" onclick="location.hash='#/team/${c.code}'">
            <div class="team-flag">${flagImg(c.flag, 48)}</div>
            <div class="team-name">${c.name}</div>
            <div class="team-group">${c.group_letter ? `Grupo ${c.group_letter}` : ''}</div>
            ${hasSquad ? `
              <div class="team-positions">
                <span class="sq-pos sq-gk">${s.gk} GK</span>
                <span class="sq-pos sq-def">${s.defs} DEF</span>
                <span class="sq-pos sq-mid">${s.mids} MID</span>
                <span class="sq-pos sq-fwd">${s.fwds} FWD</span>
              </div>
              <div class="team-extra">
                <span class="team-ovr">${s.avg_strength}</span>
                <span class="team-val">${formatMoney(s.total_value)}</span>
              </div>
            ` : `<div class="team-players">${c.player_count} jugadores</div>`}
          </div>`;
        }).join('')}
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
