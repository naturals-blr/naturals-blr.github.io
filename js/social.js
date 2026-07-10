// ── State ──────────────────────────────────────────────────────────
const state = {
  campaigns: [],
  selected: new Set(),
};

// ── DOM helpers ──────────────────────────────────────────────────
const $ = (s, p) => (p || document).querySelector(s);
const $$ = (s, p) => [...(p || document).querySelectorAll(s)];
const esc = s => { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; };

function updateGooglePostType() {
  const el = document.getElementById('content-type');
  if (!el) return;
  const ct = el.value || 'offer';
  const gpDefault = { offer: 'OFFER', festival: 'OFFER', greeting: 'STANDARD', update: 'STANDARD', announcement: 'STANDARD', testimonial: 'STANDARD' };
  const gp = document.getElementById('google-post-type');
  if (gp) gp.value = gpDefault[ct] || 'STANDARD';
}

// ── Init ─────────────────────────────────────────────────────────
async function init() {
  renderBadges();
  await loadCampaigns();
  updateGooglePostType();

  $('#select-all').addEventListener('change', e => {
    const checked = e.target.checked;
    state.selected = checked ? new Set(state.campaigns.map(c => c.id)) : new Set();
    updateRows();
  });

  $('#btn-publish').addEventListener('click', onPublish);
}

async function renderBadges() {
  try {
    const status = await getStatus();
    const isDry = status.dryRun;
    const el = $('#status-badges');
    el.innerHTML = `
      <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold ${
        isDry ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-red-50 text-red-700 border border-red-200'
      }">
        <span class="badge-dot ${isDry ? 'bg-amber-500' : 'bg-red-500'}"></span>
        ${isDry ? 'DRY RUN' : 'LIVE'}
      </span>
    `;
  } catch (e) {
    log(`Status load failed: ${e.message}`, 'error');
  }
}

// ── Load campaigns ───────────────────────────────────────────────
async function loadCampaigns() {
  const el = $('#campaign-table');
  try {
    const campaigns = await getCampaigns();
    state.campaigns = campaigns;
    state.selected = new Set();
    renderTable();
  } catch (e) {
    el.innerHTML = `<div class="text-center text-red-500 text-sm py-12">${esc(e.message)}</div>`;
    log(`Campaigns load failed: ${e.message}`, 'error');
  }
}

// ── Render table ─────────────────────────────────────────────────
function renderTable() {
  const el = $('#campaign-table');
  const cs = state.campaigns;

  if (cs.length === 0) {
    el.innerHTML = '<div class="text-center text-gray-400 text-sm py-12">No campaigns available for publishing.</div>';
    return;
  }

  el.innerHTML = `
    <div class="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
            <th class="px-4 py-3 w-10"></th>
            <th class="px-4 py-3">Campaign</th>
            <th class="px-4 py-3">Type</th>
            <th class="px-4 py-3">Start</th>
            <th class="px-4 py-3">End</th>
            <th class="px-4 py-3 text-center">FB</th>
            <th class="px-4 py-3 text-center">IG</th>
            <th class="px-4 py-3 text-center">GP</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          ${cs.map(c => renderRow(c)).join('')}
        </tbody>
      </table>
    </div>
  `;

  // Wire row-level checkboxes
  $$('.campaign-check').forEach(cb => {
    cb.addEventListener('change', e => {
      const id = e.target.dataset.id;
      if (e.target.checked) state.selected.add(id);
      else state.selected.delete(id);
      updateRows();
    });
  });

  // Wire per-campaign platform toggles
  $$('.platform-cb').forEach(cb => {
    cb.addEventListener('change', () => updateCount());
  });

  updateRows();
}

function renderRow(c) {
  const checked = state.selected.has(c.id) ? 'checked' : '';
  const expired = c.isExpired ? 'opacity-40' : '';
  const startDate = toDateInputValue(c.startDate);
  const endDate = toDateInputValue(c.endDate);
  return `
    <tr class="campaign-row ${expired}" data-id="${c.id}">
      <td class="px-4 py-3">
        <input type="checkbox" class="campaign-check rounded border-gray-300 text-green-600 focus:ring-green-500" data-id="${c.id}" ${checked}>
      </td>
      <td class="px-4 py-3">
        <div class="font-medium text-gray-800 text-sm leading-tight">${esc(c.title)}</div>
        <div class="text-xs text-gray-400 mt-0.5 leading-tight">${esc(c.body)}</div>
      </td>
      <td class="px-4 py-3">
        <span class="inline-block px-2 py-0.5 rounded text-xs font-medium ${
          c.type === 'offer' ? 'bg-green-100 text-green-700' :
          c.type === 'announcement' ? 'bg-blue-100 text-blue-700' :
          'bg-gray-100 text-gray-600'
        }">${c.type}</span>
      </td>
      <td class="px-4 py-3">
        <input type="date" class="date-start text-xs text-gray-600 border border-gray-200 rounded px-2 py-1 w-36 focus:border-green-400 focus:ring-1 focus:ring-green-400 outline-none" data-id="${c.id}" value="${startDate}">
      </td>
      <td class="px-4 py-3">
        <input type="date" class="date-end text-xs text-gray-600 border border-gray-200 rounded px-2 py-1 w-36 focus:border-green-400 focus:ring-1 focus:ring-green-400 outline-none" data-id="${c.id}" value="${endDate}">
      </td>
      <td class="px-4 py-3 text-center">
        <input type="checkbox" class="platform-cb rounded border-gray-300 text-blue-600 focus:ring-blue-500" data-id="${c.id}" data-platform="facebook" ${c.postFacebook ? 'checked' : ''}>
      </td>
      <td class="px-4 py-3 text-center">
        <input type="checkbox" class="platform-cb rounded border-gray-300 text-pink-600 focus:ring-pink-500" data-id="${c.id}" data-platform="instagram" ${c.postInstagram ? 'checked' : ''}>
      </td>
      <td class="px-4 py-3 text-center">
        <input type="checkbox" class="platform-cb rounded border-gray-300 text-red-600 focus:ring-red-500" data-id="${c.id}" data-platform="google" ${c.postGoogle ? 'checked' : ''}>
      </td>
    </tr>
  `;
}

function toDateInputValue(ddMonYyyy) {
  if (!ddMonYyyy) return '';
  const months = {Jan:'01',Feb:'02',Mar:'03',Apr:'04',May:'05',Jun:'06',Jul:'07',Aug:'08',Sep:'09',Oct:'10',Nov:'11',Dec:'12'};
  const m = ddMonYyyy.match(/^(\d+)-([A-Za-z]{3})-(\d{4})$/);
  if (!m) return '';
  return `${m[3]}-${months[m[2]] || '01'}-${m[1].padStart(2,'0')}`;
}

function toDdMonYyyy(dateInputValue) {
  if (!dateInputValue) return '';
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const m = dateInputValue.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return '';
  return `${parseInt(m[3])}-${months[parseInt(m[2])-1] || 'Jan'}-${m[1]}`;
}

// ── Update helpers ───────────────────────────────────────────────
function updateRows() {
  $$('.campaign-check').forEach(cb => {
    cb.checked = state.selected.has(cb.dataset.id);
  });
  $('#select-all').checked = state.selected.size === state.campaigns.length && state.campaigns.length > 0;
  updateCount();
}

function updateCount() {
  const total = state.selected.size;
  $('#selected-count').textContent = `${total} selected`;
  $('#btn-publish').disabled = total === 0;
}

// ── Publish ──────────────────────────────────────────────────────
async function onPublish() {
  if (state.selected.size === 0) {
    log('No campaigns selected', 'warn');
    return;
  }

  const ids = [...state.selected];
  const statusEl = $('#publish-status');
  const btn = $('#btn-publish');

  const globalFb = $('#platform-fb').checked;
  const globalIg = $('#platform-ig').checked;
  const globalGp = $('#platform-gp').checked;

  // Gather selected stores
  const storeIds = $$('.store-cb:checked').map(cb => cb.dataset.store);
  if (storeIds.length === 0) {
    log('No stores selected', 'warn');
    return;
  }

  // Gather date overrides from editable date inputs
  const dateOverrides = {};
  ids.forEach(id => {
    const startEl = document.querySelector(`.date-start[data-id="${id}"]`);
    const endEl = document.querySelector(`.date-end[data-id="${id}"]`);
    if (startEl && endEl) {
      const sd = toDdMonYyyy(startEl.value);
      const ed = toDdMonYyyy(endEl.value);
      if (sd || ed) dateOverrides[id] = {};
      if (sd) dateOverrides[id].startDate = sd;
      if (ed) dateOverrides[id].endDate = ed;
    }
  });

  // Hide previous results
  $('#result-section').classList.add('hidden');

  btn.disabled = true;
  btn.textContent = '⏳ Publishing...';
  statusEl.textContent = `Publishing ${ids.length} campaign(s)...`;

  log(`Publishing ${ids.length} campaign(s)...`, 'info');

  try {
    const result = await publishSelectedCampaigns(ids, {
      facebook: globalFb,
      instagram: globalIg,
      google: globalGp,
    }, dateOverrides, storeIds);
    statusEl.textContent = '✅ Published successfully';
    log(`Published ${ids.length} campaign(s)`, 'success');
    if (result.output) {
      result.output.split('\n').filter(l => l.trim()).forEach(l => log(`  ${l}`, 'info'));
      showResultTable(result.output, storeIds, { facebook: globalFb, instagram: globalIg, google: globalGp });
    }
  } catch (e) {
    statusEl.textContent = '❌ Failed';
    log(`Publish failed: ${e.message}`, 'error');
    if (e.output) {
      e.output.split('\n').filter(l => l.trim()).forEach(l => log(`  ${l}`, 'error'));
      showResultTable(e.output, storeIds, { facebook: globalFb, instagram: globalIg, google: globalGp });
    }
  }

  btn.disabled = false;
  btn.textContent = '📤 Publish Selected';
  setTimeout(() => { statusEl.textContent = ''; }, 5000);
}

// ── Result table ──────────────────────────────────────────────
function showResultTable(output, storeIds, platforms) {
  const section = $('#result-section');
  section.classList.remove('hidden');

  const activePlatforms = Object.entries(platforms).filter(([,v]) => v).map(([k]) => k);
  if (activePlatforms.length === 0 || !storeIds || storeIds.length === 0) return;

  const storeResults = {};
  storeIds.forEach(s => { storeResults[s] = {}; activePlatforms.forEach(p => { storeResults[s][p] = null; }); });

  const lines = output.split('\n');
  let currentStore = null;
  lines.forEach(line => {
    const storeMatch = line.match(/^📌 (.+?) \(Store_(\w+)\)/);
    if (storeMatch) currentStore = storeMatch[2];
    if (line.includes('Results:') && currentStore) {
      try {
        const resultsMatch = line.match(/\{.*\}/);
        if (resultsMatch) {
          const parsed = JSON.parse(resultsMatch[0].replace(/'/g, '"'));
          Object.entries(parsed).forEach(([k, v]) => { if (storeResults[currentStore]) storeResults[currentStore][k] = v; });
        }
      } catch (_) {}
    }
  });

  let html = '<table class="w-full text-xs border-collapse"><thead><tr class="bg-gray-100">';
  html += '<th class="px-2 py-1.5 text-left font-semibold text-gray-600">Store</th>';
  activePlatforms.forEach(p => { html += `<th class="px-2 py-1.5 text-center font-semibold text-gray-600 capitalize">${p}</th>`; });
  html += '<th class="px-2 py-1.5 text-center font-semibold text-gray-600">Retry</th></tr></thead><tbody>';

  let okCount = 0, totalCount = 0;
  storeIds.forEach(s => {
    html += `<tr class="border-t border-gray-100"><td class="px-2 py-1.5 font-medium">${s}</td>`;
    activePlatforms.forEach(p => {
      const v = storeResults[s]?.[p];
      const ok = v === 'OK';
      if (ok) okCount++;
      totalCount++;
      html += `<td class="px-2 py-1.5 text-center"><span class="inline-block px-1.5 py-0.5 rounded text-xs font-medium ${ok ? 'bg-green-100 text-green-700' : v === null ? 'bg-gray-100 text-gray-400' : 'bg-red-100 text-red-600'}">${ok ? '✅' : v === null ? '—' : '❌'}</span></td>`;
    });
    const hasFailures = activePlatforms.some(p => storeResults[s]?.[p] && storeResults[s][p] !== 'OK');
    html += `<td class="px-2 py-1.5 text-center">${hasFailures ? `<button class="text-xs px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200 font-medium retry-store-btn" data-store="${s}">Retry</button>` : '—'}</td>`;
    html += '</tr>';
  });
  html += '</tbody></table>';

  $('#result-table').innerHTML = html;
  $('#result-summary').textContent = `${okCount}/${totalCount} succeeded`;

  // Retry individual store
  document.querySelectorAll('.retry-store-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = '...';
      const store = btn.dataset.store;
      const fullId = `Store_${store}`;
      const filteredIds = [...state.selected];
      const dateOverrides = {};
      filteredIds.forEach(id => {
        const startEl = document.querySelector(`.date-start[data-id="${id}"]`);
        const endEl = document.querySelector(`.date-end[data-id="${id}"]`);
        if (startEl && endEl) {
          const sd = toDdMonYyyy(startEl.value);
          const ed = toDdMonYyyy(endEl.value);
          if (sd || ed) dateOverrides[id] = {};
          if (sd) dateOverrides[id].startDate = sd;
          if (ed) dateOverrides[id].endDate = ed;
        }
      });
      try {
        const result = await publishSelectedCampaigns(filteredIds, {
          facebook: $('#platform-fb').checked,
          instagram: $('#platform-ig').checked,
          google: $('#platform-gp').checked,
        }, dateOverrides, [store]);
        if (result.output) {
          result.output.split('\n').filter(l => l.trim()).forEach(l => log(`  ${l}`, 'info'));
          showResultTable(result.output, [store], { facebook: $('#platform-fb').checked, instagram: $('#platform-ig').checked, google: $('#platform-gp').checked });
        }
      } catch (e) {
        log(`Retry failed: ${e.message}`, 'error');
      }
    });
  });

  // Retry all failed stores
  const failedStores = storeIds.filter(s => activePlatforms.some(p => storeResults[s]?.[p] && storeResults[s][p] !== 'OK'));
  const retryAllBtn = $('#btn-retry-all');
  if (failedStores.length > 0 && failedStores.length < storeIds.length) {
    retryAllBtn.classList.remove('hidden');
    retryAllBtn.onclick = async () => {
      retryAllBtn.disabled = true;
      retryAllBtn.textContent = '...';
      const dateOverrides = {};
      [...state.selected].forEach(id => {
        const startEl = document.querySelector(`.date-start[data-id="${id}"]`);
        const endEl = document.querySelector(`.date-end[data-id="${id}"]`);
        if (startEl && endEl) {
          const sd = toDdMonYyyy(startEl.value);
          const ed = toDdMonYyyy(endEl.value);
          if (sd || ed) dateOverrides[id] = {};
          if (sd) dateOverrides[id].startDate = sd;
          if (ed) dateOverrides[id].endDate = ed;
        }
      });
      try {
        const result = await publishSelectedCampaigns([...state.selected], {
          facebook: $('#platform-fb').checked,
          instagram: $('#platform-ig').checked,
          google: $('#platform-gp').checked,
        }, dateOverrides, failedStores);
        if (result.output) {
          result.output.split('\n').filter(l => l.trim()).forEach(l => log(`  ${l}`, 'info'));
          showResultTable(result.output, failedStores, { facebook: $('#platform-fb').checked, instagram: $('#platform-ig').checked, google: $('#platform-gp').checked });
        }
      } catch (e) {
        log(`Retry all failed: ${e.message}`, 'error');
      }
      retryAllBtn.disabled = false;
      retryAllBtn.textContent = 'Retry All Failed';
    };
  } else {
    retryAllBtn.classList.add('hidden');
  }
}

// ── Activity log ────────────────────────────────────────────────
function log(message, type = 'info') {
  const el = $('#activity-log');
  const time = new Date().toLocaleTimeString();
  const colors = { info: 'text-blue-600', success: 'text-green-600', error: 'text-red-600', warn: 'text-yellow-600' };
  const icons = { info: '→', success: '✅', error: '❌', warn: '⚪' };
  el.insertAdjacentHTML('afterbegin',
    `<div class="${colors[type] || 'text-gray-500'} py-0.5 flex items-start gap-1.5">
      <span class="shrink-0">${icons[type] || '·'}</span>
      <span>${esc(message)}</span>
      <span class="text-gray-300 ml-auto shrink-0">${time}</span>
    </div>`
  );
}

// ── Bootstrap ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
