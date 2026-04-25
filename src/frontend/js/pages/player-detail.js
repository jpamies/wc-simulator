Router.register('/player/:id', async (params) => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const p = await API.get(`/players/${params.id}`);
    const country = await API.get(`/countries/${p.country_code}`);

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
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
