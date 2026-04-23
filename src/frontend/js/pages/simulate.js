Router.register('/simulate', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const progress = await API.get('/tournament/progress');

    const gs1 = progress['GS1'] || {};
    const gs2 = progress['GS2'] || {};
    const gs3 = progress['GS3'] || {};
    const r32 = progress['R32'] || {};
    const r16 = progress['R16'] || {};
    const qf  = progress['QF']  || {};
    const sf  = progress['SF']  || {};
    const fin = progress['FINAL'] || {};

    const groupsDone = gs1.done && gs2.done && gs3.done;
    const r32Resolved = r32.resolved === r32.total && r32.total > 0;

    function btn(label, onclick, enabled, done) {
      if (done) return `<button class="btn btn-done" disabled>✅ ${label}</button>`;
      if (!enabled) return `<button class="btn btn-locked" disabled>🔒 ${label}</button>`;
      return `<button class="btn btn-primary" onclick="${onclick}">${label}</button>`;
    }

    app.innerHTML = `
      <h1 class="section-title">🎲 Simulador</h1>
      <p class="section-subtitle">
        Simula partidos individuales, fases completas o todo el torneo.
      </p>

      <div class="sim-controls">
        <button class="btn btn-gold" onclick="simFullTournament()">
          ⚡ Simular todo el torneo
        </button>
        <button class="btn btn-danger btn-sm" onclick="resetSim()">
          🗑️ Borrar simulaciones
        </button>
      </div>

      <div class="sim-phase">
        <div class="sim-phase-title">📋 Fase de Grupos</div>
        <div class="sim-controls">
          ${btn('Jornada 1', "simMatchday('GS1')", true, gs1.done)}
          ${btn('Jornada 2', "simMatchday('GS2')", gs1.done, gs2.done)}
          ${btn('Jornada 3', "simMatchday('GS3')", gs2.done, gs3.done)}
        </div>
      </div>

      <div class="sim-phase">
        <div class="sim-phase-title">🏆 Eliminatorias</div>
        <div class="sim-controls">
          ${btn('R32', "simKnockout('r32')", r32Resolved, r32.done)}
          ${btn('Octavos', "simKnockout('r16')", r32.done, r16.done)}
          ${btn('Cuartos', "simKnockout('quarter')", r16.done, qf.done)}
          ${btn('Semifinales', "simKnockout('semi')", qf.done, sf.done)}
          ${btn('3er puesto + Final', "simKnockout('final')", sf.done, fin.done)}
        </div>
      </div>

      <div id="sim-progress" style="display:none;" class="card">
        <div class="card-title">Progreso</div>
        <div class="sim-log" id="sim-log"></div>
      </div>

      <div id="sim-results"></div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});

function logSim(msg) {
  const logEl = document.getElementById('sim-log');
  const progress = document.getElementById('sim-progress');
  if (progress) progress.style.display = 'block';
  if (logEl) logEl.innerHTML += `<div class="log-entry">${msg}</div>`;
}

async function simMatchday(matchdayId) {
  logSim(`⏳ Simulando ${matchdayId}...`);
  try {
    const results = await API.post(`/simulate/matchday/${matchdayId}`);
    logSim(`<span class="log-score">✅ ${results.length} partidos simulados (${matchdayId})</span>`);
    results.forEach(m => {
      logSim(`<span class="log-match">${m.home_team || m.home_code} ${m.score_home} - ${m.score_away} ${m.away_team || m.away_code}</span>`);
    });

    // Auto-resolve bracket after GS3
    if (matchdayId === 'GS3') {
      logSim('⏳ Generando cuadro de eliminatorias...');
      const bracket = await API.post('/simulate/generate-bracket');
      logSim(`<span class="log-score">✅ ${bracket.count} partidos resueltos para R32</span>`);
    }

    showToast(`${matchdayId}: ${results.length} partidos simulados`, 'success');
    // Refresh buttons after short delay so log stays visible
    setTimeout(() => location.hash = '#/simulate', 1500);
  } catch (e) {
    logSim(`❌ Error: ${e.message}`);
    showToast(e.message, 'error');
  }
}

async function simPhase(phase) {
  logSim(`⏳ Simulando fase: ${phase}...`);
  try {
    const results = await API.post('/simulate/matches', { phase });
    logSim(`<span class="log-score">✅ ${results.length} partidos simulados</span>`);
    results.forEach(m => {
      logSim(`<span class="log-match">${m.home_team || m.home_code} ${m.score_home} - ${m.score_away} ${m.away_team || m.away_code}</span>`);
    });
    showToast(`${results.length} partidos simulados`, 'success');
  } catch (e) {
    logSim(`❌ Error: ${e.message}`);
    showToast(e.message, 'error');
  }
}

async function genBracket() {
  logSim('⏳ Generando cuadro de eliminatorias...');
  try {
    const result = await API.post('/simulate/generate-bracket');
    logSim(`<span class="log-score">✅ ${result.count} partidos resueltos para R32</span>`);
    (result.r32_matches || []).forEach(m => {
      logSim(`<span class="log-match">${m.home_name || m.home} vs ${m.away_name || m.away}</span>`);
    });
    showToast('Cuadro de eliminatorias generado', 'success');
  } catch (e) {
    logSim(`❌ Error: ${e.message}`);
    showToast(e.message, 'error');
  }
}

async function simKnockout(phase) {
  logSim(`⏳ Simulando ronda: ${phase}...`);
  try {
    const result = await API.post(`/simulate/knockout-round/${phase}`);
    const matches = result.simulated_matches || [];
    logSim(`<span class="log-score">✅ ${matches.length} partidos simulados</span>`);
    matches.forEach(m => {
      const pen = m.penalty_home != null ? ` (${m.penalty_home}-${m.penalty_away} pen)` : '';
      logSim(`<span class="log-match">${m.home_team || m.home_code} ${m.score_home} - ${m.score_away} ${m.away_team || m.away_code}${pen}</span>`);
    });
    if (result.next_round?.length) {
      logSim(`<span class="log-score">→ Siguiente ronda: ${result.next_round.length} partidos generados</span>`);
    }
    showToast(`Ronda ${phase} simulada`, 'success');
    setTimeout(() => location.hash = '#/simulate', 1500);
  } catch (e) {
    logSim(`❌ Error: ${e.message}`);
    showToast(e.message, 'error');
  }
}

async function simFullTournament() {
  logSim('⚡ Simulando torneo completo...');
  try {
    const result = await API.post('/simulate/full-tournament');
    logSim(`<span class="log-score">✅ Torneo completado</span>`);
    for (const [key, val] of Object.entries(result.summary)) {
      logSim(`<span class="log-match">${key}: ${val}</span>`);
    }
    showToast('¡Torneo simulado completo!', 'success');
    setTimeout(() => location.hash = '#/simulate', 2000);
  } catch (e) {
    logSim(`❌ Error: ${e.message}`);
    showToast(e.message, 'error');
  }
}

async function resetSim() {
  if (!confirm('¿Borrar todos los resultados simulados?')) return;
  logSim('🗑️ Reseteando simulaciones...');
  try {
    await API.post('/simulate/reset');
    logSim('<span class="log-score">✅ Simulaciones eliminadas</span>');
    showToast('Simulaciones reseteadas', 'success');
    setTimeout(() => location.hash = '#/simulate', 1000);
  } catch (e) {
    logSim(`❌ Error: ${e.message}`);
    showToast(e.message, 'error');
  }
}
