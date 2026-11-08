'use strict';
// Execute the shipped api function, not a duplicated header policy.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/web/assets/app.js', 'utf8');
const start = source.indexOf('async function api(');
const end = source.indexOf('\n}', start) + 2;
assert(start >= 0 && end > start);
const calls = [];
const request = {kind: 'normal'};
const state = {section: 'models', request, active: 'one'};
const sandbox = {AbortController, document: {hidden: false}, current: state, csrf: 'synthetic',
  hostState: {}, hostInstance: null, setTimeout: () => 1, clearTimeout: () => {},
  fetch: async (path, options) => {
    calls.push({path, options});
    return {ok: true, headers: {get: () => null}, json: async () => ({})};
  }};
vm.createContext(sandbox);
vm.runInContext(source.slice(start, end), sandbox);
async function check(path, value, viewed) {
  await sandbox.api(path, value);
  const options = calls.at(-1).options;
  assert.equal(options.headers?.['X-CG-Viewed'] === '1', viewed, path);
  assert.equal(options.credentials, 'same-origin');
  if (value !== undefined) assert.equal(options.headers['X-CG-CSRF'], 'synthetic');
}
(async () => {
  await check('/api/data', {request, retry: false}, true);
  await check('/api/data', {request: {kind: 'token-mix'}, retry: false}, false);
  await check('/api/jobs/one', undefined, true);
  await check('/api/jobs/hidden-report', undefined, false);
  sandbox.document.hidden = true;
  await check('/api/jobs/one', undefined, false);
  await check('/api/data', {request}, false);
  // Visible PiP owns its interest even with a hidden opener.
  await check('/api/interest', {section: 'watch', visible: true, history: true}, true);
  await check('/api/interest', {section: 'watch', visible: false}, false);
  sandbox.document.hidden = false;
  await check('/api/status', undefined, false);
  await check('/api/sessions', {}, false);
  state.section = 'sessions';
  await check('/api/sessions', {}, true);
  state.detail = {};
  await check('/api/detail', {action: 'page'}, true);
  sandbox.document.hidden = true;
  await check('/api/detail', {action: 'page'}, false);
  console.log('PASS shipped api visible/selected, hidden, polling, PiP and CSRF demand headers');
})().catch(error => { console.error(error); process.exitCode = 1; });
