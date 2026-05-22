Router.register('/match/:id', async (params) => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const match = await API.get(`/matches/${params.id}`);
    let statsHtml = '';

    if (match.status === 'finished') {
      try {
        const stats = await API.get(`/matches/${params.id}/stats`);
        if (stats.length > 0) {
          const homePlayers = stats.filter(s => s.country_code === match.home_code);
          const awayPlayers = stats.filter(s => s.country_code === match.away_code);
          const homeLabel = match.home_team || match.home_code;
          const awayLabel = match.away_team || match.away_code;

          const renderStats = (players, teamName) => `
            <div class="card">
              <div class="card-title">${teamName}</div>
              <table>
                <thead>
                  <tr>
                    <th>Jugador</th><th>Pos</th><th>Min</th><th>Gol</th>
                    <th>Ast</th><th>TA</th><th>TR</th><th>Nota</th>
                  </tr>
                </thead>
                <tbody>
                  ${players.sort((a, b) => b.is_starter - a.is_starter || b.minutes_played - a.minutes_played).map(s => `
                    <tr style="${!s.is_starter ? 'opacity:0.7' : ''}">
                      <td>${s.player_name || s.player_id} ${s.is_starter ? '' : '🔄'}</td>
                      <td>${posBadge(s.position)}</td>
                      <td>${s.minutes_played}'</td>
                      <td>${s.goals || ''}</td>
                      <td>${s.assists || ''}</td>
                      <td>${s.yellow_cards ? '🟨' : ''}</td>
                      <td>${s.red_card ? '🟥' : ''}</td>
                      <td>${s.rating > 0 ? s.rating.toFixed(1) : '—'}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `;

          statsHtml = `
            <h2 class="section-title">Estadísticas de jugadores</h2>
            ${renderStats(homePlayers, homeLabel)}
            ${renderStats(awayPlayers, awayLabel)}
          `;
        }
      } catch (_) {
        // No stats available
      }
    }

    const scoreDisplay = match.status === 'finished'
      ? `<span style="font-size:3rem;font-weight:700;">${match.score_home} - ${match.score_away}</span>`
      : `<span style="font-size:1.5rem;color:var(--text-muted);">Por jugar</span>`;

    const penalties = match.penalty_home != null
      ? `<div style="color:var(--accent-gold);font-size:1rem;">(${match.penalty_home}-${match.penalty_away} pen)</div>`
      : '';

    const homeName = match.home_team || match.home_code || '?';
    const awayName = match.away_team || match.away_code || '?';

    app.innerHTML = `
      <a href="#/calendar" class="btn btn-outline btn-sm" style="margin-bottom:1rem;">← Calendario</a>

      <div class="card" style="text-align:center;padding:2rem;">
        <div style="display:flex;justify-content:center;align-items:center;gap:2rem;margin-bottom:1rem;">
          <div>
            <div style="font-size:3rem;">${flagImg(match.home_flag, 64)}</div>
            <div style="font-weight:600;">${homeName}</div>
          </div>
          <div>
            ${scoreDisplay}
            ${penalties}
            <div style="margin-top:0.5rem;">${matchStatusBadge(match)}</div>
          </div>
          <div>
            <div style="font-size:3rem;">${flagImg(match.away_flag, 64)}</div>
            <div style="font-weight:600;">${awayName}</div>
          </div>
        </div>
        <div style="color:var(--text-muted);font-size:0.85rem;">
          ${match.kickoff} · ${match.matchday_id}${match.location ? ' · ' + match.location : ''}
        </div>
      </div>

      ${statsHtml}
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
