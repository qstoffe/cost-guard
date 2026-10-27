'use strict';
// Synthetic DTO transport; real served app/DOM/hash history/layout, no installed history.
let requested, captures = 0;
window.fetch = async (path, options) => {
  let value;
  if (path === '/api/session') value = {csrf: 'synthetic'};
  else if (path === '/api/status') value = {http: 'ready', source: 'fixture', analysis: 'ready', accounts: 'not_requested'};
  else if (path === '/api/reports') { requested = JSON.parse(options.body); captures++; value = {id: 'fixture'}; }
  else if (path === '/api/jobs/fixture') value = {status: 'complete', result:
    requested.kind === 'session' ? INPUT.detail : requested.session_offset ? INPUT.second : INPUT.first};
  else throw new Error('unexpected fixture request');
  return {ok: true, json: async () => value};
};
async function probe() {
  const result = document.getElementById('result'), notice = document.getElementById('notice');
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  async function until(condition) {
    for (let i = 0; i < 200; i++) { if (condition()) return; await new Promise(r => setTimeout(r, 20)); }
    throw new Error('browser condition timeout: ' + notice.textContent);
  }
  const rows = () => [...result.querySelectorAll('tbody tr')].map(row => row.querySelector('a').textContent);
  const captured = () => notice.textContent.includes('Snapshot captured');
  try {
    await until(captured);
    if (!location.hash.includes('offset=')) {
      check(rows().length === 50, 'default bounded 50 rows');
      check(document.querySelector('#scope-controls details').open === false, 'advanced scope collapsed');
      check(rows().join() === INPUT.first.view.session_usage.map(r => r.session_id).join(), 'CLI first-page order');
      const first = rows();
      [...result.querySelectorAll('a')].find(a => a.textContent === 'Next').click();
      await until(() => captured() && rows().length === 5);
      check(rows().every(id => !first.includes(id)), 'older distinct page');
      result.querySelector('tbody a').click();
      await until(() => captured() && document.getElementById('heading').textContent.startsWith('Session '));
      check(location.hash.startsWith('#/sessions/'), 'same web detail');
      history.back();
      await until(() => document.getElementById('heading').textContent === 'Sessions' && rows().length === 5);
      history.back();
      await until(() => rows().length === 50);
      history.forward();
      await until(() => rows().length === 5);
    }
    check(rows().join() === INPUT.second.view.session_usage.map(r => r.session_id).join(), 'deep link/back/forward older-page parity');
    check(result.textContent.includes('51–55 of 55'), 'truthful range');
    const previous = [...result.querySelectorAll('a')].find(a => a.textContent === 'Previous');
    check(previous.getAttribute('aria-label') === 'Previous page: Sessions', 'accessible previous');
    const table = result.querySelector('.table-scroll');
    check(table.clientWidth > 0 && table.scrollWidth >= table.clientWidth, 'bounded scroll region');
    check(document.documentElement.scrollWidth <= innerWidth + 1, 'no document horizontal overflow');
    if (captures > 1) {
      const before = captures;
      [...document.querySelectorAll('#scope-controls a')].find(a => a.textContent.includes('restart browsing')).click();
      await until(() => captured() && captures === before + 1 && rows().length === 50);
      check(!location.hash.includes('revision='), 'restart drops stale revision');
      [...result.querySelectorAll('a')].find(a => a.textContent === 'Next').click();
      await until(() => captured() && captures === before + 2 && rows().length === 5);
    }
    document.getElementById('probe').textContent = JSON.stringify({outcome: 'PASS', captures,
      rows: rows().length, viewport: innerWidth, tableWidth: result.querySelector('.table-scroll').clientWidth,
      scrollWidth: result.querySelector('.table-scroll').scrollWidth});
  } catch (error) {
    document.getElementById('probe').textContent = JSON.stringify({outcome: 'FAIL', reason: error.message});
  }
}
window.addEventListener('load', probe);
