Router.register('/bracket', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const calendar = await API.get('/tournament/calendar');

    // Extract knockout matchdays
    const phases = {};
    for (const md of calendar) {
      if (md.phase === 'groups') continue;
      phases[md.id] = md;
    }

    const r32  = phases['R32']   || { matches: [] };
    const r16  = phases['R16']   || { matches: [] };
    const qf   = phases['QF']    || { matches: [] };
    const sf   = phases['SF']    || { matches: [] };
    const fin  = phases['FINAL'] || { matches: [] };

    function matchCell(m) {
      if (!m) return '<div class="bracket-match empty"><span class="bracket-tbd">—</span></div>';

      const homeName = m.home_team || m.home_code || '?';
      const awayName = m.away_team || m.away_code || '?';
      const homeFlag = flagImg(m.home_flag, 18);
      const awayFlag = flagImg(m.away_flag, 18);

      if (m.status !== 'finished') {
        return `
          <div class="bracket-match scheduled" onclick="location.hash='#/match/${m.id}'">
            <div class="bracket-team">${homeFlag} ${homeName}</div>
            <div class="bracket-vs">vs</div>
            <div class="bracket-team">${awayFlag} ${awayName}</div>
          </div>`;
      }

      const hw = m.score_home > m.score_away ||
                 (m.score_home === m.score_away && m.penalty_home > m.penalty_away);
      const aw = !hw;
      const pen = m.penalty_home != null ? ` <small>(${m.penalty_home}-${m.penalty_away}p)</small>` : '';

      return `
        <div class="bracket-match finished" onclick="location.hash='#/match/${m.id}'">
          <div class="bracket-team ${hw ? 'winner' : ''}">${homeFlag} ${homeName} <span class="bracket-score">${m.score_home}</span></div>
          <div class="bracket-team ${aw ? 'winner' : ''}">${awayFlag} ${awayName} <span class="bracket-score">${m.score_away}</span></div>
          ${pen ? `<div class="bracket-pen">${pen}</div>` : ''}
        </div>`;
    }

    function renderRound(title, matches) {
      if (!matches.length) return '';
      return `
        <div class="bracket-round">
          <div class="bracket-round-title">${title}</div>
          ${matches.map(m => matchCell(m)).join('')}
        </div>`;
    }

    // Split R32 into left (8) and right (8) halves for bracket display
    // Left half: M73,M74,M75,M76,M77,M78,M79,M80 → feeds into M89,M90,M91,M92 → M97,M99 → M101
    // Right half: M81,M82,M83,M84,M85,M86,M87,M88 → feeds into M93,M94,M95,M96 → M98,M100 → M102
    const byId = {};
    for (const md of calendar) {
      for (const m of md.matches) {
        byId[m.id] = m;
      }
    }

    const leftR32  = ['M73','M74','M75','M76','M77','M78','M79','M80'].map(id => byId[id]);
    const rightR32 = ['M81','M82','M83','M84','M85','M86','M87','M88'].map(id => byId[id]);
    const leftR16  = ['M89','M90','M91','M92'].map(id => byId[id]);
    const rightR16 = ['M93','M94','M95','M96'].map(id => byId[id]);
    const leftQF   = ['M97','M99'].map(id => byId[id]);
    const rightQF  = ['M98','M100'].map(id => byId[id]);
    const leftSF   = [byId['M101']];
    const rightSF  = [byId['M102']];
    const finalM   = [byId['M104']];
    const thirdM   = [byId['M103']];

    app.innerHTML = `
      <h1 class="section-title">🏆 Cuadro de Eliminatorias</h1>
      <div class="bracket-container">
        <div class="bracket-half">
          ${renderRound('R32', leftR32)}
          ${renderRound('Octavos', leftR16)}
          ${renderRound('Cuartos', leftQF)}
          ${renderRound('Semifinal', leftSF)}
        </div>
        <div class="bracket-center">
          ${renderRound('Final', finalM)}
          ${renderRound('3er puesto', thirdM)}
        </div>
        <div class="bracket-half bracket-right">
          ${renderRound('R32', rightR32)}
          ${renderRound('Octavos', rightR16)}
          ${renderRound('Cuartos', rightQF)}
          ${renderRound('Semifinal', rightSF)}
        </div>
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
