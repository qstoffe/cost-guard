// No UI automation, third-party DOM, build or package installation. Run by test_web_views.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; this.text = ''; this.disabled = false; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; this.text = ''; }
  setAttribute(key, value) { this.attrs[key] = value; }
  getAttribute(key) { return this.attrs[key]; }
  removeAttribute(key) { delete this.attrs[key]; }
  addEventListener(key, fn) { this.events[key] = fn; }
  click() { if (!this.disabled) return this.events.click?.(); }
}
const all = (node, tag) => [...(node.tag === tag ? [node] : []), ...node.children.flatMap(child => all(child, tag))];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(condition) {
  const caller = new Error().stack.split('\n')[2].match(/web_views\.cjs:(\d+)/)?.[1];
  for (let i = 0; i < 500; i++) { if (condition()) return; await delay(10); }
  assert.fail('bounded UI condition timed out (web_views.cjs:' + caller + ')');
}
async function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const ids = Object.fromEntries(['status', 'result', 'notice', 'refresh', 'cancel', 'heading', 'skip', 'content', 'scope-controls', 'search'].map(id => [id, new Node('div')]));
  const nav = ['overview', 'sessions', 'watch', 'models', 'accounts', 'reports', 'token-mix'].map(key => {
    const node = new Node('a'); node.setAttribute('href', '#/' + key); return node;
  });
  const handlers = {};
  const location = {hash: '#bootstrap=' + input.credential};
  const history = {replaceState: (_, __, value) => { location.hash = value.slice(value.indexOf('#')); }};
  let cookie = '', requests = 0, offline = false;
  let releaseBootstrap, releaseReport;
  const bootstrapGate = new Promise(resolve => { releaseBootstrap = resolve; });
  const reportGate = new Promise(resolve => { releaseReport = resolve; });
  ids.result.textContent = 'Starting Cost Guard'; // Server-rendered startup shell.
  const wire = async (path, options = {}) => {
    if (offline) throw new Error('offline');
    if (path === '/api/bootstrap') await bootstrapGate;
    if (path === '/api/reports') await reportGate;
    const headers = {...options.headers, Origin: input.origin};
    if (cookie) headers.Cookie = cookie;
    requests++;
    const response = await fetch(input.origin + path, {...options, headers});
    if (response.headers.get('set-cookie')) cookie = response.headers.get('set-cookie').split(';')[0];
    return response;
  };
  const context = vm.createContext({document: {createElement: tag => new Node(tag),
    getElementById: id => ids[id], querySelectorAll: () => nav}, window: {addEventListener: (key, fn) => { handlers[key] = fn; }},
    location, history, URLSearchParams, fetch: wire, setTimeout, Date, console});
  for (const path of ['/render.js', '/reports.js', '/app.js']) {
    const response = await fetch(input.origin + path);
    assert.equal(response.status, 200);
    vm.runInContext(await response.text(), context);
  }
  assert.equal(ids.result.textContent, 'Starting Cost Guard', 'slow authorization retains branded shell');
  assert.equal(location.hash, '#/overview', 'credential erased before waiting');
  releaseBootstrap();
  await until(() => all(ids.result, 'progress').length === 1);
  assert.equal(ids.result.getAttribute('aria-busy'), 'true');
  assert.equal(all(ids.result, 'progress')[0].getAttribute('value'), undefined, 'no invented percentage');
  releaseReport();
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.equal(location.hash, '#/overview');
  assert.match(ids.result.textContent, /CCost = reference valuation/);
  const navigate = key => { location.hash = '#/' + key; handlers.hashchange(); };
  navigate('sessions');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /1–50 of 55/);
  assert.equal(all(ids.result, 'tbody')[0].children.length, 50);
  const next = all(ids.result, 'button').find(node => node.textContent === 'Next');
  next.click();
  assert.match(ids.result.textContent, /51–55 of 55/);
  const sessionLink = all(ids.result, 'a').find(node => node.href === '#/sessions/root-0000');
  assert.ok(sessionLink, 'session locator links are reachable on the last page');
  navigate('sessions/root-0000');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  const snapshot = ids.result.textContent;
  assert.match(snapshot, /Running at snapshot · provisional|1–50 of 151/);
  const headers = all(ids.result, 'th').map(node => node.textContent);
  assert.deepEqual(headers, ['Prompt', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'I/C/W/O %']);
  const totals = all(ids.result, 'tfoot')[0].textContent;
  for (let i = 0; i < 3; i++) all(ids.result, 'button').find(node => node.textContent === 'Next').click();
  assert.match(ids.result.textContent, /151–151 of 151/);
  assert.equal(all(ids.result, 'tfoot')[0].textContent, totals);
  assert.match(ids.result.textContent, /Running at snapshot · provisional/);
  const frozen = ids.result.textContent, count = requests;
  await delay(650);
  assert.equal(ids.result.textContent, frozen);
  assert.equal(requests, count, 'no global Watch or silent refresh');
  navigate('sessions'); // Back-equivalent hash event restores the same list page.
  assert.match(ids.result.textContent, /51–55 of 55/);
  navigate('sessions/root-0000');
  assert.equal(ids.result.textContent, frozen);
  ids.refresh.click();
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.notEqual(ids.result.textContent, snapshot, 'explicit refresh captures a new observation');
  assert.match(ids.result.textContent, /1–50 of 152/);
  const last = ids.result.textContent;
  offline = true;
  ids.refresh.click();
  await until(() => ids.notice.textContent.includes('STALE'));
  assert.equal(ids.result.textContent, last);
  navigate('sessions/unavailable');
  await until(() => ids.notice.textContent.includes('Source/report unavailable'));
  assert.equal(ids.result.getAttribute('aria-busy'), 'false');
  assert.equal(ids.refresh.disabled, false, 'initial report outage remains retryable');
  assert.equal(all(ids.result, 'progress').length, 0);
  offline = false;
  navigate('sessions/missing');
  await until(() => ids.notice.textContent.includes('No matching session'));
  navigate('sessions/root-0001');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /exists but has no prompt rows/);
  navigate('live');
  assert.equal(location.hash, '#/watch', 'legacy global Live is replaced, not pushed');
  assert.equal(ids.heading.textContent, 'Watch');
  assert.equal(nav.find(node => node.getAttribute('href') === '#/watch').attrs['aria-current'], 'page');
  assert.match(ids.notice.textContent, /Live acquisition/);
  assert.equal(ids.refresh.disabled, true);
  navigate('watch');
  assert.equal(ids.heading.textContent, 'Watch');
  assert.match(vm.runInContext("ReportRoutes.resolve('#/sessions/root-0000/live').title", context), /Session root-0000/);
  assert.equal(vm.runInContext("ReportRoutes.resolve('#/sessions/root-0000/live').section", context), 'sessions');
  navigate('overview');
  const overviewTime = ids.result.textContent.match(/Snapshot: ([^·]+)/)[1];
  const beforePresentation = requests;
  navigate('models');
  assert.match(ids.result.textContent, /Reference models/);
  assert.equal(ids.result.textContent.match(/Snapshot: ([^·]+)/)[1], overviewTime);
  navigate('accounts');
  assert.match(ids.result.textContent, /Accounts · independent/);
  assert.equal(requests, beforePresentation, 'normal subviews reuse one frozen acquisition');
  navigate('models/all');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /GitHub USD\/M I\/C\/W\/O/);
  navigate('reports');
  const beforeDate = requests;
  assert.equal(all(ids['scope-controls'], 'form').length, 1);
  assert.equal(requests, beforeDate);
  navigate('reports?date=2026-03-29');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /Inclusive local range 2026-03-29/);
  assert.match(ids.result.textContent, /No prompt rows/);
  navigate('reports?date=2026-02-30');
  await until(() => ids.notice.textContent.includes('Invalid report scope'));
  navigate('sessions?limit=3');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /1–3 of 3/);
  navigate('token-mix');
  const beforeDeep = requests;
  await delay(650);
  assert.equal(requests, beforeDeep, 'deep history never starts from navigation');
  assert.equal(ids.refresh.disabled, false);
  ids.refresh.click();
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /Historical models/);
  assert.match(ids.result.textContent, /Full-report I\/C\/W\/O tokens/);
  const deep = ids.result.textContent;
  navigate('overview'); navigate('token-mix');
  assert.equal(ids.result.textContent, deep, 'history result retained as a frozen immutable observation');
  // Exact sorting of Decimal wire values, even where Number would collapse them.
  const cmp = (a, b) => { context.a = a; context.b = b; return vm.runInContext('ReportView.compare(a, b)', context); };
  assert.equal(cmp('1.00000000000000000001', '1.00000000000000000002'), -1);
  assert.equal(cmp('1E+20', '100000000000000000001'), -1);
  assert.equal(cmp('-0.010', '-0.009'), -1);
  assert.equal(cmp('1.00', '1'), 0);
  navigate('sessions');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  const beforeFilter = requests;
  ids.search.events.input({target: {value: 'root-0000'}});
  assert.match(ids.result.textContent, /1–1 of 1 · 55 full-report rows/);
  assert.equal(requests, beforeFilter, 'presentation filter does not change acquisition');
  ids.search.events.input({target: {value: ''}});
  const column = all(ids.result, 'button').find(node => node.textContent === 'CCost');
  column.click();
  assert.equal(all(ids.result, 'th')[2].attrs['aria-sort'], 'ascending');
  // Actual canonical DTOs exercise compaction, linked-child, running and hostile text.
  for (const [index, result] of input.examples.entries()) {
    context.example = result;
    vm.runInContext('ReportView.render(output, example, {pages: {}})', context);
    const block = result.view.prompt_blocks[0];
    assert.ok(ids.result.textContent.includes('Full-session CCost ' + block.display.total_ccost));
    assert.ok(ids.result.textContent.includes(block.title));
    assert.equal(all(ids.result, 'img').length, 0);
    assert.equal(all(ids.result, 'script').length, 0);
    if (index === 0) assert.match(ids.result.textContent, /Compaction/);
    if (index === 1) assert.match(ids.result.textContent, /Running at snapshot · provisional/);
    if (index === 2) assert.match(ids.result.textContent, /Aborted|Error/);
    if (index === 3) {
      assert.match(ids.result.textContent, /Partial source data/);
      assert.match(ids.result.textContent, /N\/A|\?/);
    }
  }
  assert.match(ids.result.textContent, /Å日本語/);
  context.example = input.overview;
  vm.runInContext('ReportView.render(output, example, {pages: {}})', context);
  assert.match(ids.result.textContent, /Model availability unverified/);
  for (const account of input.overview.view.accounts_quotas.accounts) {
    assert.ok(ids.result.textContent.includes(account.observation.label));
    assert.ok(ids.result.textContent.includes(account.observation.availability));
    assert.ok(ids.result.textContent.includes('Billed today'));
  }
  context.example = input.tier_report;
  vm.runInContext('ReportView.render(output, example, {pages: {}, section: "models"})', context);
  assert.match(ids.result.textContent, /100K/);
  assert.match(ids.result.textContent, /GitHub USD\/M I\/C\/W\/O/);
  for (const row of input.tier_report.view.model_comparison) {
    assert.ok(ids.result.textContent.includes(row.display.price_summary));
    assert.ok(ids.result.textContent.includes(row.display.relative_cost));
    assert.match(row.display.relative_cost, /\d+\.\dx/);
  }
  context.example = input.account_report;
  vm.runInContext('ReportView.render(output, example, {pages: {}, section: "accounts"})', context);
  assert.match(ids.result.textContent, /First/);
  assert.match(ids.result.textContent, /Second/);
  assert.match(ids.result.textContent, /unsupported_auth_method/);
  assert.match(ids.result.textContent, /Unaccounted usage \(estimate\): —/);
  assert.match(ids.result.textContent, /Remaining 75%/);
  // Reload with an ordinary deep link must not erase it or require the bootstrap again.
  location.hash = '#/sessions/root-0000';
  const reloaded = vm.createContext({document: context.document, window: context.window, location, history,
    URLSearchParams, fetch: wire, setTimeout, Date, console});
  vm.runInContext(await (await fetch(input.origin + '/render.js')).text(), reloaded);
  vm.runInContext(await (await fetch(input.origin + '/reports.js')).text(), reloaded);
  ids.notice.textContent = 'reload pending';
  vm.runInContext(await (await fetch(input.origin + '/app.js')).text(), reloaded);
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.equal(location.hash, '#/sessions/root-0000');
  assert.match(ids.heading.textContent, /Session root-0000/);
  // Legacy deep-link reload canonicalizes once. Back/Forward revisit the same entry.
  location.hash = '#/live';
  const watchReload = vm.createContext({document: context.document, window: context.window, location, history,
    URLSearchParams, fetch: wire, setTimeout, Date, console});
  for (const script of ['/render.js', '/reports.js', '/app.js']) {
    vm.runInContext(await (await fetch(input.origin + script)).text(), watchReload);
  }
  await until(() => ids.heading.textContent === 'Watch');
  assert.equal(location.hash, '#/watch');
  navigate('models');
  navigate('watch');
  assert.equal(ids.heading.textContent, 'Watch');
  offline = true;
  ids.result.textContent = 'Starting Cost Guard';
  const unavailable = vm.createContext({document: context.document, window: context.window, location, history,
    URLSearchParams, fetch: wire, setTimeout, Date, console});
  for (const script of ['/render.js', '/reports.js', '/app.js']) {
    vm.runInContext(await (await fetch(input.origin + script)).text(), unavailable);
  }
  await until(() => ids.result.textContent.includes('Unable to establish'));
  assert.equal(ids.result.getAttribute('aria-busy'), 'false');
  assert.match(ids.result.textContent, /tray Open Cost Guard/);
  assert.equal(all(ids.result, 'progress').length, 0, 'failed startup is not an endless activity indicator');
  console.log('web views passed: real HTTP, facade, pagination, frozen/refresh/stale, missing/empty, deep links, safe text');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
