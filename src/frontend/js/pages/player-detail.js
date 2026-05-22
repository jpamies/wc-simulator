Router.register('/player/:id', async (params) => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [p, careerData] = await Promise.all([
      API.get(`/players/${params.id}`),
      API.get(`/stats/player/${params.id}`).catch(() => ({ summary: {}, matches: [] })),
    ]);
    const country = await API.get(`/countries/${p.country_code}`);
    const cs = careerData.summary || {};
    const matchHistory = careerData.matches || [];
    const hasStats = cs.matches > 0;

    const attrs = [
      { label: 'Ritmo', key: 'pace', color: '#2dd4bf' },
      { label: 'Disparo', key: 'shooting', color: '#f59e0b' },
      { label: 'Pase', key: 'passing', color: '#818cf8' },
      { label: 'Regate', key: 'dribbling', color: '#34d399' },
      { label: 'Defensa', key: 'defending', color: '#60a5fa' },
      { label: 'Físico', key: 'physic', color: '#f472b6' },
    ];

    app.innerHTML = `
      <a href="#/team/${p.country_code}" class="btn btn-outline btn-sm" style="margin-bottom:1rem;">← ${country.name}</a>

      <div class="pd-header card">
        <div class="pd-photo-wrap">
          <img src="${p.photo || ''}" alt="" class="pd-photo" referrerpolicy="no-referrer"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 120 120%22><rect fill=%22%23374151%22 width=%22120%22 height=%22120%22/><text x=%2260%22 y=%2270%22 text-anchor=%22middle%22 fill=%22%239ca3af%22 font-size=%2240%22>&#9917;</text></svg>'">
          <div class="pd-ovr">${p.strength}</div>
        </div>
        <div class="pd-info">
          <h1 class="pd-name">${p.name}</h1>
          <div class="pd-meta">
            ${flagImg(country.flag, 24)}
            <span>${country.name}</span>
            <span class="pd-sep">·</span>
            ${posBadge(p.position)}
            <span>${p.detailed_position || p.position}</span>
          </div>
          <div class="pd-meta">
            <span>${p.club || 'Sin club'}</span>
            ${p.league ? `<span class="pd-sep">·</span><span>${p.league}</span>` : ''}
          </div>
          <div class="pd-meta-row">
            <div class="pd-chip">
              <span class="pd-chip-label">Edad</span>
              <span class="pd-chip-val">${p.age || '—'}</span>
            </div>
            <div class="pd-chip">
              <span class="pd-chip-label">Valor</span>
              <span class="pd-chip-val pd-val-money">${formatMoney(p.market_value)}</span>
            </div>
            <div class="pd-chip">
              <span class="pd-chip-label">OVR</span>
              <span class="pd-chip-val pd-val-ovr">${p.strength}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Atributos</div>
        <div class="pd-attrs">
          ${attrs.map(a => {
            const val = p[a.key];
            const pct = val != null ? val : 0;
            return `
            <div class="pd-attr">
              <span class="pd-attr-label">${a.label}</span>
              <div class="pd-attr-bar-bg">
                <div class="pd-attr-bar" style="width:${pct}%;background:${a.color}"></div>
              </div>
              <span class="pd-attr-val" style="color:${a.color}">${val != null ? val : '—'}</span>
            </div>`;
          }).join('')}
        </div>
      </div>

      ${hasStats ? `
      <div class="card">
        <div class="card-title">Estadisticas del Torneo</div>
        <div class="pd-career">
          <div class="pd-career-stat"><span class="pd-career-val">${cs.matches}</span><span class="pd-career-label">Partidos</span></div>
          <div class="pd-career-stat"><span class="pd-career-val">${cs.starts}</span><span class="pd-career-label">Titular</span></div>
          <div class="pd-career-stat"><span class="pd-career-val">${cs.minutes}</span><span class="pd-career-label">Minutos</span></div>
          <div class="pd-career-stat"><span class="pd-career-val">${cs.goals}</span><span class="pd-career-label">Goles</span></div>
          <div class="pd-career-stat"><span class="pd-career-val">${cs.assists}</span><span class="pd-career-label">Asist.</span></div>
          <div class="pd-career-stat"><span class="pd-career-val">${cs.avg_rating}</span><span class="pd-career-label">Media</span></div>
          <div class="pd-career-stat"><span class="pd-career-val" style="color:#eab308">${cs.yellows}</span><span class="pd-career-label">Amarillas</span></div>
          <div class="pd-career-stat"><span class="pd-career-val" style="color:#ef4444">${cs.reds}</span><span class="pd-career-label">Rojas</span></div>
          ${p.position === 'GK' ? `
            <div class="pd-career-stat"><span class="pd-career-val">${cs.saves}</span><span class="pd-career-label">Paradas</span></div>
            <div class="pd-career-stat"><span class="pd-career-val">${cs.goals_conceded}</span><span class="pd-career-label">GC</span></div>
            <div class="pd-career-stat"><span class="pd-career-val">${cs.clean_sheets}</span><span class="pd-career-label">Imbatido</span></div>
          ` : ''}
        </div>
      </div>

      <div class="card">
        <div class="card-title">Historial de Partidos</div>
        ${matchHistory.map(m => {
          const ratingColor = m.rating >= 7.5 ? 'var(--accent-green)' : m.rating >= 6.5 ? 'var(--accent-gold)' : 'var(--text-muted)';
          return `
          <div class="pd-match-row">
            <span class="pd-match-result">${m.score_home}-${m.score_away}</span>
            <span style="flex:1;font-size:0.8rem">${m.home_team} vs ${m.away_team}</span>
            <div class="pd-match-stats">
              ${m.goals ? `<span>${m.goals}g</span>` : ''}
              ${m.assists ? `<span>${m.assists}a</span>` : ''}
              ${m.yellow_cards ? `<span style="color:#eab308">${m.yellow_cards}TA</span>` : ''}
              ${m.red_card ? `<span style="color:#ef4444">TR</span>` : ''}
              ${m.saves ? `<span>${m.saves}sv</span>` : ''}
              <span>${m.minutes_played}'</span>
            </div>
            <span class="pd-match-rating" style="color:${ratingColor}">${m.rating}</span>
          </div>`;
        }).join('')}
      </div>
      ` : ''}
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
