let squadState = { country: null, players: [], selected: new Set(), filter: 'all' };

Router.register('/squad/:code', async (params) => {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const [country, allPlayers, currentSquad] = await Promise.all([
      API.get(`/countries/${params.code}`),
      API.get(`/countries/${params.code}/players`),
      API.get(`/squads/${params.code}`),
    ]);

    squadState.country = country;
    squadState.players = allPlayers.sort((a, b) => b.strength - a.strength);
    squadState.selected = new Set(currentSquad.map(p => p.id));
    squadState.filter = 'all';

    renderSquadBuilder();
  } catch (e) {
    app.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
});

function renderSquadBuilder() {
  const { country, players, selected, filter } = squadState;
  const app = document.getElementById('app');

  const squadPlayers = players.filter(p => selected.has(p.id));
  const byPos = { GK: [], DEF: [], MID: [], FWD: [] };
  squadPlayers.forEach(p => byPos[p.position].push(p));

  const filtered = filter === 'all'
    ? players
    : players.filter(p => p.position === filter);

  const avgOvr = squadPlayers.length > 0
    ? (squadPlayers.reduce((a, p) => a + p.strength, 0) / squadPlayers.length).toFixed(1)
    : '—';
  const totalValue = squadPlayers.reduce((a, p) => a + (p.market_value || 0), 0);
  const avgAge = squadPlayers.length > 0
    ? (squadPlayers.reduce((a, p) => a + (p.age || 0), 0) / squadPlayers.length).toFixed(1)
    : '—';

  app.innerHTML = `
    <div class="sb-header">
      <a href="#/squads" class="btn btn-outline btn-sm">← Plantillas</a>
      <div class="sb-country">
        ${flagImg(country.flag, 48)}
        <div>
          <h1 class="sb-title">${country.name}</h1>
          <span class="sb-subtitle">${country.confederation || ''} · Grupo ${country.group_letter || '—'}</span>
        </div>
      </div>
    </div>

    <div class="sb-stats">
      <div class="sb-stat">
        <span class="sb-stat-val ${selected.size >= 23 ? 'sb-stat-ok' : ''}">${selected.size}</span>
        <span class="sb-stat-lbl">/26 jugadores</span>
      </div>
      <div class="sb-stat"><span class="sb-stat-val">${avgOvr}</span><span class="sb-stat-lbl">Media OVR</span></div>
      <div class="sb-stat"><span class="sb-stat-val">${formatMoney(totalValue)}</span><span class="sb-stat-lbl">Valor total</span></div>
      <div class="sb-stat"><span class="sb-stat-val">${avgAge}</span><span class="sb-stat-lbl">Edad media</span></div>
    </div>

    <div class="sb-layout">
      <!-- Player pool -->
      <div class="sb-pool">
        <div class="sb-pool-header">
          <h3>Jugadores disponibles (${filtered.length})</h3>
          <div class="sb-filters">
            ${['all','GK','DEF','MID','FWD'].map(f => `
              <button class="sb-filter ${filter === f ? 'active' : ''}" onclick="setSquadFilter('${f}')">${f === 'all' ? 'Todos' : f}</button>
            `).join('')}
          </div>
        </div>
        <div class="sb-players" id="sb-players">
          ${filtered.map(p => {
            const isSel = selected.has(p.id);
            return `
            <div class="sb-player-card ${isSel ? 'sb-selected' : ''}" onclick="toggleSquadPlayer('${p.id}')">
              <img src="${p.photo || ''}" alt="" class="sb-player-photo" referrerpolicy="no-referrer" onerror="this.style.display='none'">
              <div class="sb-player-main">
                <span class="sb-player-name">${p.name}</span>
                <span class="sb-player-meta">${p.detailed_position || p.position} · ${p.club || ''}</span>
              </div>
              <span class="sb-player-age">${p.age || ''}y</span>
              <span class="player-ovr">${p.strength}</span>
              ${posBadge(p.position)}
              <span class="sb-toggle">${isSel ? '✓' : '+'}</span>
            </div>`;
          }).join('')}
        </div>
      </div>

      <!-- Selected squad -->
      <div class="sb-squad">
        <div class="sb-squad-header">
          <h3>Convocatoria</h3>
          <div class="sb-squad-actions">
            <button class="btn btn-sm btn-outline" onclick="autoSelectCountry('${country.code}')">⚡ Auto</button>
            <button class="btn btn-sm btn-outline" onclick="clearSquad('${country.code}')">🗑️</button>
            <button class="btn btn-sm btn-gold" onclick="saveSquad('${country.code}')">💾 Guardar</button>
          </div>
        </div>

        ${['GK','DEF','MID','FWD'].map(pos => {
          const maxLabel = pos === 'GK' ? '/3' : '';
          return `
          <div class="sb-pos-group">
            <h4 class="sb-pos-title">${pos} <span class="sb-pos-count">(${byPos[pos].length}${maxLabel})</span></h4>
            <div class="sb-pos-list">
              ${byPos[pos].sort((a,b) => b.strength - a.strength).map(p => `
                <div class="sb-squad-badge" onclick="toggleSquadPlayer('${p.id}')">
                  <img src="${p.photo || ''}" alt="" class="sb-badge-photo" referrerpolicy="no-referrer" onerror="this.style.display='none'">
                  <span class="sb-badge-name">${p.name}</span>
                  <span class="sb-badge-ovr">${p.strength}</span>
                  <span class="sb-badge-remove">×</span>
                </div>
              `).join('')}
              ${byPos[pos].length === 0 ? '<span class="sb-empty">Sin jugadores</span>' : ''}
            </div>
          </div>`;
        }).join('')}
      </div>
    </div>
  `;
}

function setSquadFilter(f) {
  squadState.filter = f;
  renderSquadBuilder();
}

function toggleSquadPlayer(playerId) {
  const { selected, players } = squadState;
  const player = players.find(p => p.id === playerId);
  if (!player) return;

  if (selected.has(playerId)) {
    selected.delete(playerId);
  } else {
    if (selected.size >= 26) {
      showToast('Máximo 26 jugadores', 'error');
      return;
    }
    if (player.position === 'GK') {
      const gkCount = players.filter(p => selected.has(p.id) && p.position === 'GK').length;
      if (gkCount >= 3) {
        showToast('Máximo 3 porteros', 'error');
        return;
      }
    }
    selected.add(playerId);
  }
  renderSquadBuilder();
}

async function saveSquad(code) {
  try {
    const ids = [...squadState.selected];
    await API.put(`/squads/${code}`, { player_ids: ids });
    showToast(`Plantilla de ${squadState.country.name} guardada (${ids.length} jugadores)`, 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function clearSquad(code) {
  if (!confirm('¿Borrar la plantilla?')) return;
  squadState.selected = new Set();
  try {
    await API.put(`/squads/${code}`, { player_ids: [] });
    showToast('Plantilla eliminada', 'info');
    renderSquadBuilder();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function autoSelectCountry(code) {
  try {
    await API.post(`/squads/${code}/auto`);
    const squad = await API.get(`/squads/${code}`);
    squadState.selected = new Set(squad.map(p => p.id));
    showToast('Plantilla auto-seleccionada', 'success');
    renderSquadBuilder();
  } catch (e) {
    showToast(e.message, 'error');
  }
}
