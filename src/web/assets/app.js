'use strict';
// Erase the one-use bootstrap fragment before issuing any request or navigation.
let credential = new URLSearchParams(location.hash.slice(1)).get('bootstrap');
history.replaceState(null, '', '/');
const statusLine = document.getElementById('status');
const output = document.getElementById('result');
const run = document.getElementById('run');
const cancel = document.getElementById('cancel');
let csrf = null;
let active = null;
async function api(path, value) {
  const options = {credentials: 'same-origin', cache: 'no-store'};
  if (value !== undefined) Object.assign(options, {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CG-CSRF': csrf || ''}, body: JSON.stringify(value)});
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'request_unavailable');
  return data;
}
async function connect() {
  try {
    const session = credential ? await api('/api/bootstrap', {credential}) : await api('/api/session');
    csrf = session.csrf;
    const state = await api('/api/status');
    statusLine.textContent = `HTTP ${state.http}; analysis ${state.analysis}; source ${state.source}; accounts ${state.accounts}.`;
    run.disabled = false;
  } catch (_) {
    statusLine.textContent = 'Browser session unavailable. Use the fresh one-use link from the foreground host; restart it if expired.';
  } finally { credential = null; }
}
run.addEventListener('click', async () => {
  run.disabled = true;
  try {
    const kind = document.getElementById('kind').value;
    const target = document.getElementById('target').value;
    const request = {kind};
    if (kind === 'session') request.session_id = target;
    if (kind === 'date') request.date_text = target;
    active = (await api('/api/reports', request)).id;
    cancel.disabled = false;
    while (active) {
      const job = await api(`/api/jobs/${active}`);
      statusLine.textContent = `Report ${job.status}.`;
      // Only text nodes: source titles/prompts never become markup or script.
      output.textContent = JSON.stringify(job.result || job.error || job.progress, null, 2);
      if (!['queued', 'running'].includes(job.status)) break;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  } catch (_) { statusLine.textContent = 'Report unavailable. Retry or check the local source.'; }
  finally { active = null; cancel.disabled = true; run.disabled = false; }
});
cancel.addEventListener('click', async () => {
  if (active) {
    try { await api(`/api/jobs/${active}/cancel`, {}); }
    catch (_) { statusLine.textContent = 'Cancellation unavailable.'; }
  }
});
connect();
