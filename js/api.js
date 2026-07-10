let apiBase = '/api';

async function api(path, options) {
  const res = await fetch(apiBase + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await res.json();
  if (!body.ok) {
    const err = new Error(body.error || 'Request failed');
    err.output = body.output || '';
    err.statusCode = res.status;
    throw err;
  }
  return body.data;
}

async function getStatus() { return api('/status'); }
async function getReplyMode() { return api('/settings/reply-mode'); }
async function setReplyMode(mode) { return api('/settings/reply-mode', { method: 'POST', body: JSON.stringify({ mode }) }); }
async function getStores() { return api('/stores'); }
async function getReviews(store, limit) { return api(`/reviews?store=${encodeURIComponent(store)}&limit=${limit || 10}`); }
async function generateReply(store, review, aiProvider) { return api('/replies/generate', { method: 'POST', body: JSON.stringify({ store, review, aiProvider }) }); }
async function postReply(store, review, reply) { return api('/replies/post', { method: 'POST', body: JSON.stringify({ store, review, reply }) }); }
async function processStore(store, count) { return api('/stores/process', { method: 'POST', body: JSON.stringify({ store, count }) }); }
async function getDryRun() { return api('/settings/dry-run'); }
async function setDryRun(dryRun) { return api('/settings/dry-run', { method: 'POST', body: JSON.stringify({ dryRun }) }); }
async function syncSheets() { return api('/sync-sheets', { method: 'POST' }); }
async function publishSocial() { return api('/publish-social', { method: 'POST' }); }
async function getCampaigns() { return api('/campaigns'); }
async function publishSelectedCampaigns(campaignIds, platforms, dateOverrides, storeIds) { return api('/publish-selective', { method: 'POST', body: JSON.stringify({ campaignIds, platforms, dateOverrides, storeIds }) }); }
async function refreshBuildData() { return api('/data/refresh', { method: 'POST' }); }
async function testTokens() {
  const res = await fetch(apiBase + '/tokens/test');
  const body = await res.json();
  if (!body.ok) throw new Error(body.error || 'Token test failed');
  return body.data;
}

// ── Image Modal (Lightbox) ──
let _modalEl = null;

function _initModal() {
  if (_modalEl) return;
  _modalEl = document.createElement('div');
  _modalEl.id = 'image-modal';
  _modalEl.innerHTML = [
    '<div class="modal-overlay" id="modal-overlay">',
    '  <button class="modal-close" id="modal-close-btn">&times;</button>',
    '  <img class="modal-image" id="modal-image" src="" alt="Preview">',
    '</div>'
  ].join('');
  document.body.appendChild(_modalEl);

  document.getElementById('modal-overlay').addEventListener('click', function(e) {
    if (e.target === this) closeImageModal();
  });
  document.getElementById('modal-close-btn').addEventListener('click', closeImageModal);
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeImageModal();
  });

  if (!document.getElementById('modal-style')) {
    const style = document.createElement('style');
    style.id = 'modal-style';
    style.textContent = [
      '#image-modal { display: none; }',
      '#image-modal.active { display: block; }',
      '#image-modal .modal-overlay {',
      '  position: fixed; inset: 0; z-index: 9999;',
      '  background: rgba(0,0,0,0.85);',
      '  display: flex; align-items: center; justify-content: center;',
      '  padding: 2rem;',
      '}',
      '#image-modal .modal-close {',
      '  position: fixed; top: 1rem; right: 1.5rem; z-index: 10000;',
      '  background: none; border: none; color: #fff;',
      '  font-size: 2.5rem; cursor: pointer; line-height: 1;',
      '  opacity: 0.8; font-family: inherit;',
      '}',
      '#image-modal .modal-close:hover { opacity: 1; }',
      '#image-modal .modal-image {',
      '  max-width: 95vw; max-height: 90vh;',
      '  border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);',
      '  object-fit: contain;',
      '}',
    ].join('\n');
    document.head.appendChild(style);
  }
}

function openImageModal(src) {
  _initModal();
  const img = document.getElementById('modal-image');
  img.src = src;
  img.onerror = function() { this.alt = 'Failed to load image'; };
  _modalEl.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeImageModal() {
  if (!_modalEl) return;
  _modalEl.classList.remove('active');
  document.body.style.overflow = '';
}

function enableImageModals(containerOrSelector) {
  const container = typeof containerOrSelector === 'string'
    ? document.querySelector(containerOrSelector)
    : containerOrSelector;
  if (!container) return;
  container.addEventListener('click', function(e) {
    const img = e.target.closest('img');
    if (!img) return;
    if (img.closest('.no-modal')) return;
    const src = img.getAttribute('src');
    if (!src) return;
    e.preventDefault();
    e.stopPropagation();
    openImageModal(src);
  });
}
