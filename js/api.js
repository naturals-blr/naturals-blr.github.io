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
