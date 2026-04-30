// ─── My Simulation page: local-first simulation with share/load ───

Router.register('/my-sim', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    // Load base data from server
    const [calendar, overview, squadsOverview] = await Promise.all([
      API.get('/tournament/calendar'),
      API.get('/tournament/overview'),
      API.get('/squads'),
    ]);

    // Check if local sim is active
    const isActive = SimState.isActive();

    // Compute local progress
    const localResults = SimState.getAllMatchResults();
    const allMatches = calendar.flatMap(md => md.matches.map(m => ({ ...m, _md: md.id, _phase: md.phase })));

    function localProgress(mdId) {
      const mdMatches = allMatches.filter(m => m._md === mdId);
      const total = mdMatches.length;
      const finished = mdMatches.filter(m => localResults[m.id] || m.status === 'finished').length;
      const resolved = mdMatches.filter(m => m.home_code && m.away_code).length;
      return { total, finished, resolved, done: finished === total && total > 0 };
    }

    const gs1 = localProgress('GS1'), gs2 = localProgress('GS2'), gs3 = localProgress('GS3');
    const r32 = localProgress('R32'), r16 = localProgress('R16');
    const qf = localProgress('QF'), sf = localProgress('SF'), fin = localProgress('FINAL');
    const groupsDone = gs1.done && gs2.done && gs3.done;

    function btn(label, onclick, enabled, done) {
      if (done) return `<button class="btn btn-done" disabled>✅ ${label}</button>`;
      if (!enabled) return `<button class="btn btn-locked" disabled>🔒 ${label}</button>`;
      return `<button class="btn btn-primary" onclick="${onclick}">${label}</button>`;
    }

    const simName = SimState.getName();
    const resultCount = Object.keys(localResults).length;
    const squadCount = Object.keys(SimState.getAllSquads()).length;

    app.innerHTML = `
      <h1 class="section-title">🎮 Mi Simulación</h1>
      <p class="section-subtitle">
        Simula el mundial a tu manera. Todo se guarda en tu navegador.
        Cuando quieras, compártelo con un link.
      </p>

      ${!isActive ? `
        <div class="card" style="text-align:center;padding:2rem;">
          <p style="margin-bottom:1rem;">No tienes ninguna simulación en curso.</p>
          <div style="display:flex;gap:0.75rem;justify-content:center;flex-wrap:wrap;">
            <button class="btn btn-gold" onclick="startNewSim()">🆕 Nueva simulación</button>
            <button class="btn btn-outline" onclick="loadSharedSimPrompt()">📥 Cargar compartida</button>
          </div>
        </div>
      ` : `
        <div class="card" style="margin-bottom:1rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
            <div>
              <strong>${simName}</strong>
              <span style="color:var(--text-muted);margin-left:0.5rem;">${resultCount} partidos · ${squadCount} convocatorias editadas</span>
            </div>
            <div style="display:flex;gap:0.5rem;">
              <button class="btn btn-primary btn-sm" onclick="shareSim()">📤 Compartir</button>
              <button class="btn btn-outline btn-sm" onclick="location.hash='#/my-sim/squads'">📋 Convocatorias</button>
              <button class="btn btn-danger btn-sm" onclick="clearSim()">🗑️ Borrar</button>
            </div>
          </div>
        </div>

        <div class="sim-phase">
          <div class="sim-phase-title">📋 Fase de Grupos</div>
          <div class="sim-controls">
            ${btn('Jornada 1', "localSimMatchday('GS1')", true, gs1.done)}
            ${btn('Jornada 2', "localSimMatchday('GS2')", gs1.done, gs2.done)}
            ${btn('Jornada 3', "localSimMatchday('GS3')", gs2.done, gs3.done)}
          </div>
        </div>

        <div class="sim-phase">
          <div class="sim-phase-title">🏆 Eliminatorias</div>
          <div class="sim-controls">
            ${btn('Generar cuadro R32', "localResolveR32()", groupsDone, r32.resolved > 0)}
            ${btn('R32', "localSimMatchday('R32')", r32.resolved === r32.total && r32.total > 0, r32.done)}
            ${btn('Octavos', "localSimMatchday('R16')", r32.done, r16.done)}
            ${btn('Cuartos', "localSimMatchday('QF')", r16.done, qf.done)}
            ${btn('Semifinales', "localSimMatchday('SF')", qf.done, sf.done)}
            ${btn('3er puesto + Final', "localSimMatchday('FINAL')", sf.done, fin.done)}
          </div>
        </div>

        <div class="sim-controls" style="margin-top:1rem;">
          <button class="btn btn-gold" onclick="localSimFullTournament()">
            ⚡ Simular todo el torneo
          </button>
          <button class="btn btn-outline" onclick="localResetResults()">
            🔄 Reiniciar resultados
          </button>
        </div>

        <div id="sim-progress" class="card">
          <div class="card-title" style="display:flex;justify-content:space-between;align-items:center">
            <span>🖥️ Consola</span>
            <button class="btn btn-sm" onclick="clearSimLog()" style="opacity:.7">🗑️</button>
          </div>
          <div class="sim-log" id="sim-log"></div>
        </div>
      `}
    `;

    if (isActive) renderSimLog();
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});

// ─── Cache for calendar data ───
let _calendarCache = null;
let _squadsCache = {};

async function _getCalendar() {
  if (!_calendarCache) _calendarCache = await API.get('/tournament/calendar');
  return _calendarCache;
}

async function _getSquadPlayers(code) {
  if (!_squadsCache[code]) {
    // Check local override first
    const localSquad = SimState.getSquad(code);
    if (localSquad) {
      // Fetch full player data for the IDs
      const allPlayers = await API.get(`/countries/${code}/players?limit=500`);
      const idSet = new Set(localSquad);
      _squadsCache[code] = allPlayers.filter(p => idSet.has(p.id));
    } else {
      const squad = await API.get(`/squads/${code}`);
      if (squad.length > 0) {
        _squadsCache[code] = squad;
      } else {
        // No squad selected, use all players (engine will auto-select)
        _squadsCache[code] = await API.get(`/countries/${code}/players?limit=500`);
      }
    }
  }
  return _squadsCache[code];
}

// ─── Local simulation functions ───

async function localSimMatchday(matchdayId) {
  if (!SimState.isActive()) { startNewSim(); }
  logSim(`⏳ Simulando ${matchdayId}...`);

  try {
    const calendar = await _getCalendar();
    const md = calendar.find(m => m.id === matchdayId);
    if (!md) { logSim('❌ Jornada no encontrada'); return; }

    // Filter matches that need simulation (no local result yet and have teams)
    const toSim = md.matches.filter(m =>
      !SimState.getMatchResult(m.id) && m.home_code && m.away_code && m.status !== 'finished'
    );

    if (toSim.length === 0) {
      logSim(`<span class="log-score">✅ ${matchdayId} ya completada</span>`);
      _refreshSimPage();
      return;
    }

    // Fetch players for all teams involved
    const codes = new Set();
    toSim.forEach(m => { codes.add(m.home_code); codes.add(m.away_code); });
    const squadPromises = [...codes].map(c => _getSquadPlayers(c).then(p => [c, p]));
    const squads = Object.fromEntries(await Promise.all(squadPromises));

    // Build dry-run request
    const dryRunMatches = toSim.map(m => ({
      match_id: m.id,
      home_players: squads[m.home_code] || [],
      away_players: squads[m.away_code] || [],
      is_knockout: md.phase !== 'groups',
    }));

    const { results } = await API.post('/simulate/dry-run', { matches: dryRunMatches });

    // Store results locally
    for (const r of results) {
      SimState.setMatchResult(r.match_id, {
        score_home: r.score_home,
        score_away: r.score_away,
        penalty_home: r.penalty_home,
        penalty_away: r.penalty_away,
        is_simulated: true,
      });
      SimState.setMatchStats(r.match_id, [...r.home_stats, ...r.away_stats]);

      const m = toSim.find(x => x.id === r.match_id);
      const pen = r.penalty_home != null ? ` (${r.penalty_home}-${r.penalty_away} pen)` : '';
      logSim(`<span class="log-match">${m?.home_team || m?.home_code} ${r.score_home} - ${r.score_away} ${m?.away_team || m?.away_code}${pen}</span>`);
    }

    logSim(`<span class="log-score">✅ ${results.length} partidos simulados (${matchdayId})</span>`);
    showToast(`${matchdayId}: ${results.length} partidos simulados`, 'success');
    _calendarCache = null; // Invalidate
    _refreshSimPage();
  } catch (e) {
    logSim(`❌ Error: ${e.message}`);
    showToast(e.message, 'error');
  }
}

async function localResolveR32() {
  logSim('⏳ Generando cuadro R32...');
  try {
    // Use the server endpoint — it writes to DB but that's the canonical R32
    const bracket = await API.post('/simulate/generate-bracket');
    logSim(`<span class="log-score">✅ ${bracket.count} partidos resueltos para R32</span>`);
    _calendarCache = null;
    _refreshSimPage();
  } catch (e) {
    logSim(`❌ Error: ${e.message}`);
  }
}

async function localSimFullTournament() {
  if (!SimState.isActive()) startNewSim();
  logSim('⚡ Simulando torneo completo...');

  for (const mdId of ['GS1', 'GS2', 'GS3']) {
    await localSimMatchday(mdId);
  }

  // Resolve bracket using server (canonical bracket resolution)
  try {
    await API.post('/simulate/generate-bracket');
    logSim('<span class="log-score">✅ Cuadro R32 generado</span>');
    _calendarCache = null;
  } catch (e) {
    logSim(`⚠️ Bracket: ${e.message}`);
  }

  for (const mdId of ['R32', 'R16', 'QF', 'SF', 'FINAL']) {
    // Need to resolve knockout from local results
    // For now, use server bracket + local simulation
    await localSimMatchday(mdId);
  }

  logSim('<span class="log-score">🏆 Torneo completado!</span>');
  showToast('¡Torneo simulado completo!', 'success');
}

function localResetResults() {
  if (!confirm('¿Borrar todos los resultados locales?')) return;
  const s = SimState.exportState();
  SimState.start(s.name);
  // Keep squads
  if (s.squads) {
    for (const [code, ids] of Object.entries(s.squads)) {
      SimState.setSquad(code, ids);
    }
  }
  _calendarCache = null;
  _squadsCache = {};
  logSim('<span class="log-score">🔄 Resultados reiniciados</span>');
  _refreshSimPage();
}

function startNewSim() {
  const name = prompt('Nombre de tu simulación:', 'Mi Mundial 2026') || 'Mi Mundial 2026';
  SimState.start(name);
  _calendarCache = null;
  _squadsCache = {};
  location.hash = '#/my-sim';
}

function clearSim() {
  if (!confirm('¿Eliminar tu simulación local? No se puede deshacer.')) return;
  SimState.clear();
  _calendarCache = null;
  _squadsCache = {};
  location.hash = '#/my-sim';
}

async function shareSim() {
  const state = SimState.exportState();
  const author = prompt('Tu nombre (opcional):') || '';
  try {
    const res = await API.post('/simulations/share', {
      name: state.name || 'Simulación compartida',
      author,
      data: state,
    });
    const url = `${location.origin}/#/sim/${res.slug}`;
    await navigator.clipboard.writeText(url).catch(() => {});
    showToast(`Link copiado: ${url}`, 'success');
    logSim(`<span class="log-score">📤 Compartida: <a href="#/sim/${res.slug}" style="color:var(--accent)">${res.slug}</a></span>`);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function loadSharedSimPrompt() {
  const input = prompt('Pega el link o el código de la simulación:');
  if (!input) return;
  const slug = input.match(/sim\/([a-z0-9]+)/)?.[1] || input.trim();
  if (slug) location.hash = `#/sim/${slug}`;
}

function _refreshSimPage() {
  setTimeout(() => Router.handleRoute(), 300);
}


// ─── Load shared simulation ───
Router.register('/sim/:slug', async (params) => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const sim = await API.get(`/simulations/${params.slug}`);
    app.innerHTML = `
      <h1 class="section-title">📥 ${sim.name || 'Simulación compartida'}</h1>
      <div class="card">
        <p>${sim.author ? `Creada por <strong>${sim.author}</strong>` : 'Simulación anónima'}
           ${sim.created_at ? ` · ${new Date(sim.created_at).toLocaleDateString()}` : ''}</p>
        <p style="color:var(--text-muted);margin-top:0.5rem;">
          ${Object.keys(sim.data?.matches || {}).length} partidos simulados ·
          ${Object.keys(sim.data?.squads || {}).length} convocatorias editadas
        </p>
        <div style="display:flex;gap:0.75rem;margin-top:1rem;">
          <button class="btn btn-gold" onclick="importSharedSim('${params.slug}')">
            Cargar en mi navegador
          </button>
          <button class="btn btn-outline" onclick="location.hash='#/my-sim'">Volver</button>
        </div>
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Simulación no encontrada (${e.message})</p><a href="#/my-sim">Volver</a></div>`;
  }
});

async function importSharedSim(slug) {
  try {
    const sim = await API.get(`/simulations/${slug}`);
    SimState.importState(sim.data);
    showToast('Simulación cargada', 'success');
    location.hash = '#/my-sim';
  } catch (e) {
    showToast(e.message, 'error');
  }
}


// ─── Squad editing page ───
Router.register('/my-sim/squads', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const countries = await API.get('/countries');
    const localSquads = SimState.getAllSquads();

    app.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:1rem;">
        <button class="btn btn-outline btn-sm" onclick="location.hash='#/my-sim'">← Simulación</button>
        <h1 class="section-title" style="margin:0;">📋 Convocatorias</h1>
      </div>
      <p class="section-subtitle">Edita las convocatorias de 26 jugadores por selección. Los cambios se guardan en tu navegador.</p>

      <div class="groups-grid">
        ${countries.map(c => {
          const hasLocal = !!localSquads[c.code];
          return `
            <div class="card" style="cursor:pointer;${hasLocal ? 'border-color:var(--accent);' : ''}"
                 onclick="location.hash='#/my-sim/squad/${c.code}'">
              <div style="display:flex;align-items:center;gap:0.5rem;">
                ${flagImg(c.flag, 24)}
                <strong>${c.name}</strong>
                ${hasLocal ? '<span class="badge badge-simulated" style="margin-left:auto;">EDITADA</span>' : ''}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});


Router.register('/my-sim/squad/:code', async (params) => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  const code = params.code;
  try {
    const [country, allPlayers] = await Promise.all([
      API.get(`/countries/${code}`),
      API.get(`/countries/${code}/players?limit=500`),
    ]);

    // Current selection: local override or server squad
    let selectedIds;
    const localSquad = SimState.getSquad(code);
    if (localSquad) {
      selectedIds = new Set(localSquad);
    } else {
      const serverSquad = await API.get(`/squads/${code}`);
      selectedIds = new Set(serverSquad.map(p => p.id));
    }

    const positions = ['GK', 'DEF', 'MID', 'FWD'];
    const byPos = {};
    for (const pos of positions) {
      byPos[pos] = allPlayers.filter(p => p.position === pos);
    }

    function renderList() {
      const count = selectedIds.size;
      const gk = allPlayers.filter(p => selectedIds.has(p.id) && p.position === 'GK').length;

      return `
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:1rem;">
          <button class="btn btn-outline btn-sm" onclick="location.hash='#/my-sim/squads'">← Convocatorias</button>
          <h1 class="section-title" style="margin:0;">${flagImg(country.flag, 28)} ${country.name}</h1>
          <span style="color:var(--text-muted);margin-left:auto;">${count}/26 seleccionados</span>
        </div>
        <div style="display:flex;gap:0.5rem;margin-bottom:1rem;flex-wrap:wrap;">
          <button class="btn btn-primary btn-sm" onclick="autoSelectSquad('${code}')">Auto-seleccionar (3-8-8-7)</button>
          <button class="btn btn-outline btn-sm" onclick="clearSquad('${code}')">Deseleccionar todos</button>
          <button class="btn btn-outline btn-sm" onclick="resetSquad('${code}')">Restaurar original</button>
        </div>
        ${positions.map(pos => `
          <h3>${pos} (${byPos[pos].filter(p => selectedIds.has(p.id)).length})</h3>
          <div class="players-list">
            ${byPos[pos].map(p => `
              <div class="player-row ${selectedIds.has(p.id) ? 'selected' : ''}"
                   onclick="togglePlayer('${code}', '${p.id}')"
                   style="cursor:pointer;padding:0.4rem 0.6rem;border-radius:6px;
                          ${selectedIds.has(p.id) ? 'background:rgba(var(--accent-rgb,59,130,246),0.15);' : ''}">
                <span style="width:1.5rem;text-align:center;">${selectedIds.has(p.id) ? '✅' : '⬜'}</span>
                ${posBadge(p.position)}
                <span style="flex:1;">${p.name}</span>
                <span style="color:var(--text-muted);font-size:0.85rem;">${p.strength}</span>
                <span style="color:var(--text-muted);font-size:0.8rem;">${p.club || ''}</span>
              </div>
            `).join('')}
          </div>
        `).join('')}
      `;
    }

    // Store in window for toggle function
    window._squadState = { code, allPlayers, selectedIds, byPos, country, renderList };
    app.innerHTML = renderList();
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});

function togglePlayer(code, playerId) {
  const s = window._squadState;
  if (!s || s.code !== code) return;
  if (s.selectedIds.has(playerId)) {
    s.selectedIds.delete(playerId);
  } else {
    if (s.selectedIds.size >= 26) {
      showToast('Máximo 26 jugadores', 'error');
      return;
    }
    // Max 3 GK
    const player = s.allPlayers.find(p => p.id === playerId);
    if (player?.position === 'GK') {
      const gkCount = s.allPlayers.filter(p => s.selectedIds.has(p.id) && p.position === 'GK').length;
      if (gkCount >= 3) { showToast('Máximo 3 porteros', 'error'); return; }
    }
    s.selectedIds.add(playerId);
  }
  SimState.setSquad(code, [...s.selectedIds]);
  _squadsCache = {}; // Invalidate
  document.getElementById('app').innerHTML = s.renderList();
}

function autoSelectSquad(code) {
  const s = window._squadState;
  if (!s || s.code !== code) return;
  const targets = { GK: 3, DEF: 8, MID: 8, FWD: 7 };
  s.selectedIds.clear();
  for (const [pos, count] of Object.entries(targets)) {
    s.byPos[pos].slice(0, count).forEach(p => s.selectedIds.add(p.id));
  }
  SimState.setSquad(code, [...s.selectedIds]);
  _squadsCache = {};
  document.getElementById('app').innerHTML = s.renderList();
  showToast('Convocatoria auto-seleccionada', 'success');
}

function clearSquad(code) {
  const s = window._squadState;
  if (!s || s.code !== code) return;
  s.selectedIds.clear();
  SimState.setSquad(code, []);
  _squadsCache = {};
  document.getElementById('app').innerHTML = s.renderList();
}

function resetSquad(code) {
  const s = window._squadState;
  if (!s || s.code !== code) return;
  // Remove local override — will use server squad next render
  const state = SimState.exportState();
  delete state.squads?.[code];
  SimState.importState(state);
  _squadsCache = {};
  location.hash = `#/my-sim/squad/${code}`;
  Router.handleRoute();
}
