// ─── Tournaments listing page ───
Router.register('/tournaments', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const tournaments = await fetch(`${API.BASE}/tournaments`).then(r => r.json());

    const canonical = tournaments.find(t => t.is_canonical);
    const userTournaments = tournaments.filter(t => !t.is_canonical);

    app.innerHTML = `
      <h1 class="section-title">🏆 Torneos</h1>
      <p class="section-subtitle">
        Explora el torneo oficial o crea tu propia simulación del Mundial 2026.
      </p>

      ${canonical ? `
        <div class="card" style="border: 2px solid var(--accent); margin-bottom: 1.5rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
            <div>
              <span class="badge badge-real" style="margin-right:0.5rem">OFICIAL</span>
              <strong style="font-size:1.1rem">${canonical.name}</strong>
            </div>
            <div style="display:flex;gap:0.5rem;">
              <button class="btn btn-primary btn-sm" onclick="enterTournament('official')">
                Ver torneo
              </button>
              <button class="btn btn-outline btn-sm" onclick="forkTournament('official')">
                Forkear
              </button>
            </div>
          </div>
          <div class="stats-grid" style="margin-top:0.75rem;">
            <div class="stat-card"><div class="stat-value">${canonical.matches_played}</div><div class="stat-label">Jugados</div></div>
            <div class="stat-card"><div class="stat-value">${canonical.total_matches}</div><div class="stat-label">Total</div></div>
            <div class="stat-card"><div class="stat-value">${canonical.current_phase || 'groups'}</div><div class="stat-label">Fase</div></div>
          </div>
        </div>
      ` : ''}

      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
        <h2 class="section-title" style="margin:0;">Simulaciones</h2>
        <button class="btn btn-gold" onclick="showCreateTournament()">+ Crear simulación</button>
      </div>

      <div id="create-tournament-form" style="display:none;" class="card" style="margin-bottom:1rem;">
        <h3>Nueva simulación</h3>
        <div style="display:flex;flex-direction:column;gap:0.75rem;max-width:400px;">
          <input type="text" id="new-t-name" placeholder="Nombre del torneo" class="input"
                 style="padding:0.5rem;border-radius:6px;border:1px solid var(--border);background:var(--card-bg);color:var(--text);">
          <input type="text" id="new-t-owner" placeholder="Tu nombre (opcional)" class="input"
                 style="padding:0.5rem;border-radius:6px;border:1px solid var(--border);background:var(--card-bg);color:var(--text);">
          <label style="display:flex;align-items:center;gap:0.5rem;">
            <input type="checkbox" id="new-t-fork" checked>
            Partir del estado actual del torneo oficial
          </label>
          <div style="display:flex;gap:0.5rem;">
            <button class="btn btn-primary" onclick="createTournament()">Crear</button>
            <button class="btn btn-outline" onclick="document.getElementById('create-tournament-form').style.display='none'">Cancelar</button>
          </div>
        </div>
      </div>

      <div id="tournaments-list">
        ${userTournaments.length === 0 ? '<p style="color:var(--text-muted)">Aún no hay simulaciones. ¡Crea la primera!</p>' : ''}
        ${userTournaments.map(t => `
          <div class="card" style="margin-bottom:0.75rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
              <div>
                <strong>${t.name}</strong>
                ${t.owner_name ? `<span style="color:var(--text-muted);margin-left:0.5rem">por ${t.owner_name}</span>` : ''}
              </div>
              <div style="display:flex;gap:0.5rem;align-items:center;">
                <span style="color:var(--text-muted);font-size:0.85rem">${t.matches_played}/${t.total_matches} partidos</span>
                <button class="btn btn-primary btn-sm" onclick="enterTournament('${t.slug}')">Entrar</button>
                <button class="btn btn-outline btn-sm" onclick="forkTournament('${t.slug}')">Forkear</button>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});

function showCreateTournament() {
  document.getElementById('create-tournament-form').style.display = 'block';
}

async function createTournament() {
  const name = document.getElementById('new-t-name').value.trim();
  if (!name) { showToast('Introduce un nombre', 'error'); return; }
  const owner = document.getElementById('new-t-owner').value.trim();
  const fork = document.getElementById('new-t-fork').checked;

  try {
    const body = { name, owner_name: owner };
    if (fork) body.fork_from_slug = 'official';

    const res = await fetch(`${API.BASE}/tournaments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => r.json());

    if (res.manage_token) {
      TournamentCtx.saveToken(res.slug, res.id, res.manage_token);
      showToast('Simulación creada', 'success');
      location.hash = `#/t/${res.slug}`;
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function enterTournament(slug) {
  location.hash = `#/t/${slug}`;
}

async function forkTournament(sourceSlug) {
  const name = prompt('Nombre para tu simulación:');
  if (!name) return;
  const owner = prompt('Tu nombre (opcional):') || '';

  try {
    const res = await fetch(`${API.BASE}/tournaments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, owner_name: owner, fork_from_slug: sourceSlug }),
    }).then(r => r.json());

    if (res.manage_token) {
      TournamentCtx.saveToken(res.slug, res.id, res.manage_token);
      showToast('Simulación creada a partir de ' + sourceSlug, 'success');
      location.hash = `#/t/${res.slug}`;
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── Tournament detail page (entry point for a specific tournament) ───
Router.register('/t/:slug', async (params) => {
  const slug = params.slug;
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const t = await TournamentCtx.enter(slug);
    const hasWrite = TournamentCtx.hasWriteAccess();

    // If it's the canonical tournament, check for admin key
    if (t.is_canonical && !hasWrite) {
      // Show admin key prompt
      app.innerHTML = `
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:1rem;">
          <button class="btn btn-outline btn-sm" onclick="TournamentCtx.exit()">← Torneos</button>
          <span class="badge badge-real">OFICIAL</span>
          <strong style="font-size:1.1rem">${t.name}</strong>
        </div>
        <div class="card">
          <p>Este es el torneo oficial. Puedes consultar resultados y estadísticas.</p>
          <p>Para simular, puedes <a href="#" onclick="forkTournament('official');return false;" style="color:var(--accent);">forkear a tu propia simulación</a>
             o introducir la clave de admin.</p>
          <div style="display:flex;gap:0.5rem;margin-top:0.75rem;max-width:400px;">
            <input type="password" id="admin-key-input" placeholder="Clave de admin"
                   style="flex:1;padding:0.5rem;border-radius:6px;border:1px solid var(--border);background:var(--card-bg);color:var(--text);">
            <button class="btn btn-primary btn-sm" onclick="verifyAdminKey('${slug}')">Verificar</button>
          </div>
        </div>
        <div style="margin-top:1rem;">
          <button class="btn btn-primary" onclick="location.hash='#/t/${slug}/home'">Continuar como lectura</button>
        </div>
      `;
    } else {
      // Go directly to the tournament home
      location.hash = `#/t/${slug}/home`;
    }
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});

async function verifyAdminKey(slug) {
  const key = document.getElementById('admin-key-input').value.trim();
  if (!key) return;

  try {
    const res = await fetch(`${API.BASE}/tournaments/${slug}/verify-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Manage-Token': key },
    }).then(r => r.json());

    if (res.valid) {
      const t = await fetch(`${API.BASE}/tournaments/${slug}`).then(r => r.json());
      TournamentCtx.saveToken(slug, t.id, key);
      showToast('Clave de admin válida', 'success');
      location.hash = `#/t/${slug}/home`;
    } else {
      showToast('Clave incorrecta', 'error');
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── Tournament sub-pages: re-use existing pages but scoped ───
// These register under /t/:slug/... and set tournament context before rendering

function registerTournamentPage(subPath, originalHandler) {
  Router.register(`/t/:slug${subPath}`, async (params, queryParams) => {
    await TournamentCtx.enter(params.slug);
    await originalHandler(params, queryParams);

    // Add tournament banner at top
    const app = document.getElementById('app');
    const existing = app.innerHTML;
    const saved = JSON.parse(localStorage.getItem('wcs_tournaments') || '{}');
    const info = saved[params.slug];
    const isCanonical = params.slug === 'official';
    const hasWrite = TournamentCtx.hasWriteAccess();

    const banner = `
      <div class="tournament-banner" style="display:flex;align-items:center;gap:0.5rem;margin-bottom:1rem;padding:0.5rem 0.75rem;border-radius:8px;background:var(--card-bg);border:1px solid var(--border);">
        <button class="btn btn-outline btn-sm" onclick="location.hash='#/tournaments'" style="padding:0.25rem 0.5rem;">← Torneos</button>
        ${isCanonical ? '<span class="badge badge-real">OFICIAL</span>' : '<span class="badge badge-simulated">SIM</span>'}
        <strong id="tournament-name-banner">${params.slug}</strong>
        ${hasWrite ? '<span style="color:var(--accent);font-size:0.8rem;">✏️ Escritura</span>' : '<span style="color:var(--text-muted);font-size:0.8rem;">👁 Lectura</span>'}
        ${!isCanonical && hasWrite ? `<button class="btn btn-danger btn-sm" onclick="deleteTournament('${params.slug}')" style="margin-left:auto;padding:0.25rem 0.5rem;">🗑️</button>` : ''}
      </div>
    `;
    app.innerHTML = banner + existing;

    // Fetch tournament name for banner
    try {
      const t = await fetch(`${API.BASE}/tournaments/${params.slug}`).then(r => r.json());
      const el = document.getElementById('tournament-name-banner');
      if (el) el.textContent = t.name;
    } catch {}
  });
}

async function deleteTournament(slug) {
  if (!confirm('¿Eliminar esta simulación? No se puede deshacer.')) return;
  try {
    await API.delete(`/tournaments/${slug}`);
    TournamentCtx.exit();
    showToast('Simulación eliminada', 'success');
    location.hash = '#/tournaments';
  } catch (e) {
    showToast(e.message, 'error');
  }
}
