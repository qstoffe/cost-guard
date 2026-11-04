// No UI automation, third-party DOM, build or package installation. Run by test_web_views.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.dataset = {}; this.events = {}; this.text = ''; this.disabled = false; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  get firstChild() { return this.children[0] || null; }
  append(...children) { for (const child of children) { if (child.parentNode) child.parentNode.children = child.parentNode.children.filter(node => node !== child); child.parentNode = this; this.children.push(child); } }
  insertBefore(child, before) { this.append(child); this.children = this.children.filter(node => node !== child); const index = this.children.indexOf(before); this.children.splice(index < 0 ? this.children.length : index, 0, child); }
  querySelector(selector) { return all(this, selector.startsWith('.') ? null : selector).find(node => selector.startsWith('.') ? (node.className || '').split(' ').includes(selector.slice(1)) : node.tag === selector) || null; }
  replaceChildren(...children) { this.children = children; this.text = ''; }
  setAttribute(key, value) { this.attrs[key] = value; }
  getAttribute(key) { return this.attrs[key]; }
  removeAttribute(key) { delete this.attrs[key]; }
  addEventListener(key, fn) { this.events[key] = fn; }
  click() { if (!this.disabled) return this.events.click?.(); }
  focus() { this.focused = true; }
}
const all = (node, tag) => [...(!tag || node.tag === tag ? [node] : []), ...node.children.flatMap(child => all(child, tag))];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(condition) {
  const caller = new Error().stack.split('\n')[2].match(/web_views\.cjs:(\d+)/)?.[1];
  for (let i = 0; i < 500; i++) { if (condition()) return; await delay(10); }
  assert.fail('bounded UI condition timed out (web_views.cjs:' + caller + ')');
}
async function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const ids = Object.fromEntries(['product-version', 'host-state', 'host-message', 'host-details', 'status', 'result', 'notice', 'refresh', 'cancel', 'heading', 'skip', 'content', 'scope-controls', 'search'].map(id => [id, new Node('div')]));
  const toolbar = new Node('div');
  ids['host-state'].append(ids['host-message'], ids['host-details']);
  const nav = ['models', 'sessions', 'watch', 'accounts', 'reports', 'token-mix', 'settings'].map(key => {
    const node = new Node('a'); node.setAttribute('href', '#/' + key); return node;
  });
  const handlers = {};
  const location = {hash: '#bootstrap=' + input.credential};
  const history = {replaceState: (_, __, value) => { location.hash = value.slice(value.indexOf('#')); }};
  let cookie = '', requests = 0, offline = false;
  const bootstrapStatuses = [];
  let releaseBootstrap, releaseReport;
  const bootstrapGate = new Promise(resolve => { releaseBootstrap = resolve; });
  const reportGate = new Promise(resolve => { releaseReport = resolve; });
  ids.result.textContent = 'Starting Cost Guard'; // Server-rendered startup shell.
  const wire = async (path, options = {}) => {
    if (offline) throw new Error('offline');
    if (path === '/api/bootstrap') {
      assert.equal(location.hash, '#/models', 'erase bootstrap before any exchange request');
      await bootstrapGate;
    }
    if (path === '/api/reports') await reportGate;
    const headers = {...options.headers, Origin: input.origin};
    if (cookie) headers.Cookie = cookie;
    requests++;
    const response = await fetch(input.origin + path, {...options, headers});
    if (path === '/api/bootstrap') bootstrapStatuses.push(response.status);
    if (response.headers.get('set-cookie')) cookie = response.headers.get('set-cookie').split(';')[0];
    return response;
  };
  // Finite-page harness isolates transport; live lifecycle has its own VM/browser tests.
  const transport = {connect(api, update, status) {
    status('Live connected.', {kind: 'connected', writable: true, terminal: false});
    return {resync() {}};
  }};
  const context = vm.createContext({LiveConnection: transport, AbortController, clearTimeout, document: {documentElement: new Node('html'), body: new Node('body'), querySelector: () => toolbar, createElement: tag => new Node(tag),
    getElementById: id => ids[id], querySelectorAll: () => nav, addEventListener() {}}, window: {addEventListener: (key, fn) => { handlers[key] = fn; }},
    location, history, URLSearchParams, fetch: wire, setTimeout, Date, console});
  require('../fixtures/web_help_vm.cjs')(vm, context);
  for (const path of ['/render.js', '/reports.js', '/settings.js', '/app.js']) {
    const response = await fetch(input.origin + path);
    assert.equal(response.status, 200);
    vm.runInContext(await response.text(), context);
  }
  assert.match(ids.result.textContent, /≈0%.*Authorizing browser session/, 'slow authorization has only approximate progress');
  assert.equal(location.hash, '#/models', 'credential erased before waiting');
  assert.equal(ids['product-version'].textContent, '', 'no invented version before authentication');
  // Observations generated by real Normal sampling, availability, separate month
  // history and DTO packaging, not the obsolete assumed phase order.
  context.observations = input.normal_progress;
  const progressFacts = vm.runInContext(`(() => {
    const state = {}, values = [], stages = {};
    observations.forEach((event, index) => {
      overviewProgress(state, {...event, sequence: index + 1});
      values.push(state.percent);
      (stages[event.stage] ||= []).push(state.percent);
    });
    const latest = state.stage, value = state.percent;
    overviewProgress(state, {phase:'history',stage:'sampling',completed:1,sequence:1});
    overviewProgress(state, {...observations.at(-1),sequence:observations.length});
    return {values, stages, latest, value, retained:state.stage, retainedValue:state.percent};
  })()`, context);
  assert.deepEqual([...progressFacts.values], [...progressFacts.values].sort((a,b) => a-b));
  assert.ok(new Set(progressFacts.stages.sampling).size >= 6);
  assert.ok(new Set(progressFacts.stages['account-analysis']).size >= 10);
  assert.ok(Math.max(...progressFacts.stages.availability) <= 50, 'availability cannot exhaust later history');
  assert.ok(Math.max(...progressFacts.stages['account-analysis']) <= 88, 'genuine preparation retains room');
  assert.ok(Math.max(...progressFacts.values) < 100);
  assert.equal(progressFacts.retained, progressFacts.latest, 'stale polling/event labels ignored');
  assert.equal(progressFacts.retainedValue, progressFacts.value);
  vm.runInContext('Object.assign(current,{percent:99,progressSequence:999,progressStart:94,stagedProgress:true})', context);
  releaseBootstrap();
  await until(() => all(ids.result, 'progress').length === 1);
  assert.equal(all(ids.result, 'progress')[0].max, 100);
  await until(() => ids['product-version'].textContent !== '');
  assert.equal(ids['product-version'].textContent, ' v91.7', 'running fixture version appears while Models loads');
  assert.equal(vm.runInContext('current.percent', context), 5, 'genuinely new acquisition resets prior progress');
  assert.match(all(ids.result, 'progress')[0].getAttribute('aria-valuetext'), /Approximately/, 'never an invented exact global percentage');
  releaseReport();
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.equal(location.hash, '#/models');
  assert.match(ids.result.textContent, /Estimated reference cost, not your bill/);
  const creditsText = ids.result.textContent, beforeToggle = requests;
  const retainedChildren = [...ids.result.children];
  vm.runInContext('applySettings({webSettings: {theme: "classic", ccostDisplayUnit: "usd", miniWatchPlacement: "remember-last", quotaDisplayMode: "used"}, webSettingsChoices: {theme: "classic", ccostDisplayUnit: "usd", miniWatchPlacement: "default", quotaDisplayMode: "default"}, webSettingsDefaults: {theme: "classic", ccostDisplayUnit: "credits", miniWatchPlacement: "remember-last", quotaDisplayMode: "used"}})', context);
  assert.notEqual(ids.result.textContent, creditsText);
  assert.match(ids.result.textContent, /\$\d+\.\d{2}/);
  assert.deepEqual(ids.result.children, retainedChildren, 'unit change retains DOM');
  vm.runInContext('applySettings({webSettings: {theme: "classic", ccostDisplayUnit: "credits", miniWatchPlacement: "remember-last", quotaDisplayMode: "used"}, webSettingsChoices: {theme: "default", ccostDisplayUnit: "default", miniWatchPlacement: "default", quotaDisplayMode: "default"}, webSettingsDefaults: {theme: "classic", ccostDisplayUnit: "credits", miniWatchPlacement: "remember-last", quotaDisplayMode: "used"}})', context);
  assert.equal(ids.result.textContent, creditsText, 'exact reversible display');
  assert.equal(requests, beforeToggle, 'toggle never requests a report/provider');
  const overviewTable = all(ids.result, 'table')[0];
  const overviewScroll = all(ids.result, 'tbody')[0];
  overviewScroll.scrollTop = 317;
  const beforeHeartbeat = requests;
  vm.runInContext("connectionStatus('Live connected.', {kind:'connected', writable:true})", context);
  assert.equal(all(ids.result, 'table')[0], overviewTable, 'host heartbeat must retain the actual Overview DOM');
  assert.equal(overviewScroll.scrollTop, 317);
  assert.equal(requests, beforeHeartbeat, 'no hidden reacquisition');
  assert.equal(ids['host-state'].hidden, true, 'healthy operation has no persistent banner');
  assert.equal(ids.status.textContent, 'Live connected.', 'one compact accessible status');
  assert.equal(ids.status.title, undefined, 'hidden status does not duplicate visible connection details');
  ids.search.events.input({target: {value: 'no matching model'}});
  assert.ok(all(ids.result, 'tbody')[0].children.length, 'Overview ignores hidden legacy search state');
  ids.search.events.input({target: {value: ''}});
  assert.ok(all(ids.result, 'tbody')[0].children.length);
  const navigate = key => {
    ids.content.focused = false;
    location.hash = '#/' + key; handlers.hashchange();
    assert.equal(ids['product-version'].textContent, ' v91.7', 'persistent server version across routes');
    if (['models', 'overview', 'models/all'].includes(key)) assert.equal(ids.content.focused, true, 'Models route receives keyboard focus');
  };
  const retainedHeartbeat = () => {
    const children = [...ids.result.children], before = requests;
    const scroll = all(ids.result, 'div').find(node => node.className === 'table-scroll');
    if (scroll) { scroll.scrollTop = 317; scroll.scrollLeft = 91; }
    vm.runInContext("connectionStatus('Live connected.', {kind:'connected', writable:true})", context);
    assert.equal(ids.result.children.length, children.length);
    assert.ok(ids.result.children.every((node, index) => node === children[index]), 'host health must retain every frozen report DOM');
    if (scroll) {
      assert.equal(scroll.scrollTop, 317);
      assert.equal(scroll.scrollLeft, 91);
    }
    assert.equal(requests, before, 'health must not reacquire frozen reports');
  };
  const frozenModels = ids.result.textContent;
  navigate('settings');
  await until(() => all(ids.result, 'select')[0]?.disabled === false);
  assert.equal(all(ids.result, 'select').length, 4, 'Theme, CCost display, Mini placement and quota orientation');
  assert.match(ids.result.textContent, /Web settings/);
  assert.equal(all(ids.result, 'button').length, 0, 'no save or apply action');
  assert.equal(ids.heading.textContent, 'Settings');
  assert.equal(nav.at(-1).getAttribute('aria-current'), 'page');
  const settingsRequests = requests;
  vm.runInContext("connectionStatus('Live connected.', {kind:'connected', writable:true})", context);
  assert.equal(requests, settingsRequests, 'health does not poll settings');
  const unitSelect = all(ids.result, 'select').find(node => node.id === 'ccost-unit');
  context.retainedBlock = input.examples[0].view.prompt_blocks[0];
  vm.runInContext(`const retainedDetail = ReportView.element('section');
    retainedDetail.append(ReportView.element('span', () => ReportView.display(retainedBlock, 'total_ccost')));
    views.set('retained-unit-fixture', {detail: {root: retainedDetail, detach() {}}});`, context);
  unitSelect.value = 'usd'; await unitSelect.events.change();
  assert.match(ids.result.textContent, /CCost display saved/);
  assert.equal(requests, settingsRequests + 1, 'selection uses one fixed settings write');
  assert.equal(vm.runInContext('retainedDetail.textContent', context), context.retainedBlock.display_units.usd.total_ccost,
    'a confirmed save immediately updates detached retained detail DOM');
  navigate('models');
  assert.notEqual(ids.result.textContent, frozenModels, 'saved unit applies to frozen models');
  assert.match(ids.result.textContent, /\$\d+\.\d{2}/);
  assert.equal(all(ids.result, 'select').length, 0, 'no old interactive CCost control');
  assert.equal(requests, settingsRequests + 1, 'settings does not reacquire models');
  navigate('settings');
  await until(() => all(ids.result, 'select')[0]?.disabled === false);
  unitSelect.value = 'credits'; await unitSelect.events.change();
  assert.equal(vm.runInContext('retainedDetail.textContent', context), context.retainedBlock.display.total_ccost);
  vm.runInContext('views.delete("retained-unit-fixture")', context);
  navigate('models');
  assert.equal(ids.result.textContent, frozenModels, 'confirmed credits restores existing display tokens');
  navigate('sessions');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  retainedHeartbeat();
  assert.match(ids.result.textContent, /1–50 of 55/);
  assert.equal(all(ids.result, 'tbody')[0].children.length, 50);
   const next = all(ids.result, 'a').find(node => node.textContent === 'Next');
   const olderPage = next.href;
   assert.equal(all(ids['scope-controls'], 'details').length, 1, 'scope is optional/advanced');
   navigate(olderPage.slice(2));
   await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /51–55 of 55/);
  const sessionLink = all(ids.result, 'a').find(node => node.href === '#/sessions/root-0000');
  assert.ok(sessionLink, 'session locator links are reachable on the last page');
  navigate('sessions/root-0000');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  const snapshot = ids.result.textContent;
  assert.match(snapshot, /Running at snapshot · provisional|1–50 of 151/);
  const headers = all(ids.result, 'th').map(node => node.textContent);
  assert.deepEqual(headers, ['Prompt', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'Token Mix %']);
  const totals = all(ids.result, 'tfoot')[0].textContent;
  for (let i = 0; i < 3; i++) all(ids.result, 'button').find(node => node.textContent === 'Next').click();
  assert.match(ids.result.textContent, /151–151 of 151/);
  assert.equal(all(ids.result, 'tfoot')[0].textContent, totals);
  assert.match(ids.result.textContent, /Running at snapshot · provisional/);
  const frozen = ids.result.textContent, count = requests;
  await delay(650);
  assert.equal(ids.result.textContent, frozen);
  assert.equal(requests, count, 'no global Watch or silent refresh');
   navigate(olderPage.slice(2)); // Back-equivalent hash event restores the same list page.
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
  const overviewTime = vm.runInContext('current.result.observed_at_ms', context);
  const beforePresentation = requests;
  navigate('models');
  retainedHeartbeat();
  assert.equal(all(ids.result, 'table')[0].attrs['aria-label'], 'Reference models');
  assert.equal(vm.runInContext('current.result.observed_at_ms', context), overviewTime);
  navigate('accounts');
  retainedHeartbeat();
  assert.match(ids.result.textContent, /Accounts · independent/);
  assert.equal(requests, beforePresentation, 'normal subviews reuse one frozen acquisition');
  navigate('models/all');
  assert.equal(location.hash, '#/models');
  assert.equal(requests, beforePresentation, 'legacy alias never reacquires a different catalog');
  assert.equal(nav.find(node => node.getAttribute('href') === '#/models').attrs['aria-current'], 'page');
  assert.doesNotMatch(ids.result.textContent, /GitHub USD\/M I\/C\/W\/O/);
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
   assert.match(ids.result.textContent, /1–50 of 55.*0 matches on this page only/);
   assert.equal(all(ids.result, 'tbody')[0].children.length, 0, 'older root is not in the loaded slice');
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
  assert.equal(all(ids.result, 'section').filter(node => node.className === 'account-card').length, 0);
  vm.runInContext('ReportView.render(output, example, {pages: {}, section: "accounts"})', context);
  for (const account of input.overview.view.accounts_quotas.accounts) {
    assert.ok(ids.result.textContent.includes(account.observation.label));
    assert.ok(ids.result.textContent.includes(account.observation.availability));
    if (account.billed_today != null) {
      assert.ok(ids.result.textContent.includes('Billed today: ' + account.display.billed_today));
    }
  }
  context.example = input.tier_report;
  vm.runInContext('ReportView.render(output, example, {pages: {}, section: "models"})', context);
  assert.match(ids.result.textContent, /100K/);
  assert.doesNotMatch(ids.result.textContent, /GitHub USD\/M I\/C\/W\/O/);
  for (const row of input.tier_report.view.model_comparison) {
    assert.ok(ids.result.textContent.includes(row.display.relative_cost));
    assert.match(row.display.relative_cost, /\d+\.\dx/);
  }
  context.example = input.account_report;
  vm.runInContext('ReportView.render(output, example, {pages: {}, section: "accounts"})', context);
  assert.match(ids.result.textContent, /First/);
  assert.match(ids.result.textContent, /Second/);
  assert.match(ids.result.textContent, /Unsupported authentication method/);
  assert.doesNotMatch(ids.result.textContent, /unsupported_auth_method/);
  assert.match(ids.result.textContent, /Unaccounted usage \(estimate\): —/);
  assert.match(ids.result.textContent, /25% used/);
  // Reload with an ordinary deep link must not erase it or require the bootstrap again.
  location.hash = '#/sessions/root-0000';
  const reloaded = vm.createContext({LiveConnection: transport, AbortController, clearTimeout, document: context.document, window: context.window, location, history,
    URLSearchParams, fetch: wire, setTimeout, Date, console});
  require('../fixtures/web_help_vm.cjs')(vm, reloaded);
  vm.runInContext(await (await fetch(input.origin + '/render.js')).text(), reloaded);
  vm.runInContext(await (await fetch(input.origin + '/reports.js')).text(), reloaded);
  vm.runInContext(await (await fetch(input.origin + '/settings.js')).text(), reloaded);
  ids.notice.textContent = 'reload pending';
  vm.runInContext(await (await fetch(input.origin + '/app.js')).text(), reloaded);
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.equal(location.hash, '#/sessions/root-0000');
  assert.match(ids.heading.textContent, /Session root-0000/);
  // Legacy deep-link reload canonicalizes once. Back/Forward revisit the same entry.
  location.hash = '#/live';
  const watchReload = vm.createContext({LiveConnection: transport, AbortController, clearTimeout, document: context.document, window: context.window, location, history,
    URLSearchParams, fetch: wire, setTimeout, Date, console});
  require('../fixtures/web_help_vm.cjs')(vm, watchReload);
  for (const script of ['/render.js', '/reports.js', '/settings.js', '/app.js']) {
    vm.runInContext(await (await fetch(input.origin + script)).text(), watchReload);
  }
  await until(() => ids.heading.textContent === 'Watch');
  assert.equal(location.hash, '#/watch');
  await until(() => vm.runInContext('Boolean(csrf)', watchReload));
  navigate('models');
  navigate('watch');
  assert.equal(ids.heading.textContent, 'Watch');
  navigate('models');
  await until(() => vm.runInContext('Boolean(current?.result) && !current.loading', watchReload));
  const retained = ids.result.textContent, terminalRequests = requests;
  vm.runInContext("connectionStatus('STOPPED — NOT LIVE. Use the OS launcher.', {kind: 'stopped', terminal: true, writable: false})", watchReload);
  assert.match(ids['host-state'].textContent, /STOPPED — NOT LIVE/);
  assert.equal(ids['host-state'].hidden, false, 'terminal notice is never hidden');
  assert.match(ids['host-details'].textContent, /Reports stay frozen/);
  assert.match(ids.notice.textContent, /not updating/);
  assert.equal(ids.refresh.disabled, true);
  assert.equal(ids.cancel.disabled, true);
  assert.equal(ids['scope-controls'].inert, true);
  assert.equal(ids.result.textContent, retained, 'terminal state retains the exact frozen report');
  assert.equal(ids['product-version'].textContent, ' v91.7', 'retained view keeps its original server version');
  ids.refresh.click();
  await delay(20);
  assert.equal(requests, terminalRequests, 'disabled terminal refresh cannot start acquisition');
  offline = true;
  ids.result.textContent = 'Starting Cost Guard';
  const unavailable = vm.createContext({LiveConnection: transport, AbortController, clearTimeout, document: context.document, window: context.window, location, history,
    URLSearchParams, fetch: wire, setTimeout, Date, console});
  require('../fixtures/web_help_vm.cjs')(vm, unavailable);
  for (const script of ['/render.js', '/reports.js', '/settings.js', '/app.js']) {
    vm.runInContext(await (await fetch(input.origin + script)).text(), unavailable);
  }
  await until(() => ids.result.textContent.includes('Unable to establish'));
  assert.equal(ids.result.getAttribute('aria-busy'), 'false');
  assert.match(ids.result.textContent, /tray Open Cost Guard/);
  assert.equal(all(ids.result, 'progress').length, 0, 'failed startup is not an endless activity indicator');
  // A pasted handoff can change only the hash of an already-terminal error page.
  // It must bypass that page's terminal API guard, never the HTTP security guards.
  let reloads = 0;
  location.reload = () => { reloads++; assert.equal(location.hash, '#/models'); };
  vm.runInContext("hostState = {kind:'authorization_required',terminal:true,writable:false}", unavailable);
  offline = false; cookie = '';
  location.hash = '#bootstrap=' + input.handoff_credential;
  await handlers.hashchange();
  assert.equal(bootstrapStatuses.at(-1), 200, 'fresh pasted handoff authorizes previously unauthorized tab');
  assert.notEqual(cookie, '', 'existing endpoint issues normal cookie');
  assert.equal(reloads, 1);
  cookie = '';
  location.hash = '#bootstrap=' + input.handoff_credential;
  await handlers.hashchange();
  assert.equal(bootstrapStatuses.at(-1), 401, 'replay still rejected in a fresh browser');
  assert.equal(cookie, '');
  assert.equal(reloads, 2);
  offline = true;
  location.hash = '#bootstrap=synthetic-network-failure';
  await handlers.hashchange();
  assert.equal(reloads, 3, 'network failure also leaves only the clean URL');
  assert.doesNotMatch(ids.result.textContent, /synthetic-network-failure/);
  console.log('web views passed: real HTTP, facade, pagination, frozen/refresh/stale, missing/empty, deep links, safe text');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
