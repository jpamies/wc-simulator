Router.register('/bracket', async () => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const calendar = await API.get('/tournament/calendar');

    const byId = {};
    for (const md of calendar) {
      for (const m of md.matches) byId[m.id] = m;
    }

    function matchBox(m) {
      if (!m) return `
        <div class="bk-match bk-empty">
          <div class="bk-row"><span class="bk-name bk-tbd">TBD</span><span class="bk-sc">-</span></div>
          <div class="bk-row"><span class="bk-name bk-tbd">TBD</span><span class="bk-sc">-</span></div>
        </div>`;

      const hn = m.home_team || m.home_code || '?';
      const an = m.away_team || m.away_code || '?';
      const hf = flagImg(m.home_flag, 16);
      const af = flagImg(m.away_flag, 16);

      if (m.status !== 'finished') {
        return `
          <div class="bk-match bk-sched" onclick="location.hash='#/match/${m.id}'">
            <div class="bk-row"><span class="bk-name">${hf} ${hn}</span><span class="bk-sc">-</span></div>
            <div class="bk-row"><span class="bk-name">${af} ${an}</span><span class="bk-sc">-</span></div>
          </div>`;
      }

      const hw = m.score_home > m.score_away || (m.score_home === m.score_away && m.penalty_home > m.penalty_away);
      const pen = m.penalty_home != null ? `<div class="bk-pen">(${m.penalty_home}-${m.penalty_away} pen)</div>` : '';

      return `
        <div class="bk-match bk-fin" onclick="location.hash='#/match/${m.id}'">
          <div class="bk-row ${hw ? 'bk-w' : ''}"><span class="bk-name">${hf} ${hn}</span><span class="bk-sc">${m.score_home}</span></div>
          <div class="bk-row ${!hw ? 'bk-w' : ''}"><span class="bk-name">${af} ${an}</span><span class="bk-sc">${m.score_away}</span></div>
          ${pen}
        </div>`;
    }

    // Left bracket: R32(8) → R16(4) → QF(2) → SF(1) → Final(1) ← SF(1) ← QF(2) ← R16(4) ← R32(8)
    // The bracket pairs feed based on FIFA bracket:
    // Left side feeds M89(W74,W77), M90(W73,W75), M91(W76,W78), M92(W79,W80) etc.
    // We reorder R32 to match the bracket flow:
    // M90 = W73 vs W75  →  so R32 pair 1: M73, then M75 (skipping — but for visual bracket,
    //   we pair R32 matches that feed into the same R16 match)
    const leftPairs = [
      // R32 pairs that feed R16
      { r32: ['M74','M77'], r16: 'M89' },
      { r32: ['M73','M75'], r16: 'M90' },
      { r32: ['M76','M78'], r16: 'M91' },
      { r32: ['M79','M80'], r16: 'M92' },
    ];
    const rightPairs = [
      { r32: ['M83','M84'], r16: 'M93' },
      { r32: ['M81','M82'], r16: 'M94' },
      { r32: ['M86','M88'], r16: 'M95' },
      { r32: ['M85','M87'], r16: 'M96' },
    ];

    function renderHalf(pairs, qfIds, sfId, side) {
      const r32Col = pairs.map(p =>
        `<div class="bk-pair">${p.r32.map(id => matchBox(byId[id])).join('')}</div>`
      ).join('');

      const r16Col = pairs.map(p => matchBox(byId[p.r16])).join('');
      const qfCol = qfIds.map(id => matchBox(byId[id])).join('');
      const sfCol = matchBox(byId[sfId]);

      if (side === 'left') {
        return `
          <div class="bk-col bk-r32">${r32Col}</div>
          <div class="bk-col bk-r16">${r16Col}</div>
          <div class="bk-col bk-qf">${qfCol}</div>
          <div class="bk-col bk-sf">${sfCol}</div>`;
      }
      return `
          <div class="bk-col bk-sf bk-right">${sfCol}</div>
          <div class="bk-col bk-qf bk-right">${qfCol}</div>
          <div class="bk-col bk-r16 bk-right">${r16Col}</div>
          <div class="bk-col bk-r32 bk-right">${r32Col}</div>`;
    }

    app.innerHTML = `
      <h1 class="section-title">🏆 Cuadro de Eliminatorias</h1>

      <div class="bk-wrapper">
        <div class="bk-labels">
          <span>R32</span><span>R16</span><span>QF</span><span>SF</span>
          <span>FINAL</span>
          <span>SF</span><span>QF</span><span>R16</span><span>R32</span>
        </div>
        <div class="bk-grid">
          ${renderHalf(leftPairs, ['M97','M99'], 'M101', 'left')}
          <div class="bk-col bk-final">
            ${matchBox(byId['M104'])}
            <div class="bk-third-label">3er puesto</div>
            ${matchBox(byId['M103'])}
          </div>
          ${renderHalf(rightPairs, ['M98','M100'], 'M102', 'right')}
        </div>
      </div>
    `;
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});
