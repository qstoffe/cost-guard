// Unified Models: exact tiers, independent filters, accessible multi-sort and routes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.events = {}; this.attrs = {}; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(n => n.textContent).join(''); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; this.text = ''; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(key, handler) { this.events[key] = handler; }
}
const all = (n, tag) => [...(n.tag === tag ? [n] : []), ...n.children.flatMap(c => all(c, tag))];
const {view, fallback, benchmark} = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = new Node('main'), controls = new Node('div');
const state = {pages: {}, section: 'models'};
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output, controls,
  state, result: {view, observed_at_ms: 1, source: {status: 'acquired'}}, URLSearchParams});
const helpText = require('../fixtures/web_help_vm.cjs')(vm, context);
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('src/web/assets/benchmark.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('src/web/assets/reports.js', 'utf8'), context);
const draw = () => vm.runInContext('ReportView.render(output, result, state)', context);
const rows = () => all(output, 'tbody')[0].children;
const names = () => rows().map(row => row.children[1].textContent);
const button = name => all(output, 'button').find(n => n.textContent.startsWith(name));
const click = (name, event = {}) => button(name).events.click(event);
const check = (index, value) => { const input = all(output, 'input')[index]; input.checked = value; input.events.change(); };
draw();
assert.equal(all(output, 'th').length, 10);
assert.equal(all(output, 'input').length, 2);
assert.equal(all(output, 'button').length, 11);
assert.deepEqual(all(output, 'h2').map(n => n.textContent), ['Models Reference Pricing', 'Coding Benchmark – Cost per Task']);
assert.equal(button('Refresh price list').attrs['data-model-control'], 'refresh');
assert.equal(all(output, 'div').filter(n => n.className === 'model-price-controls').length, 1);
assert.ok(!all(output, 'div').some(n => n.className === 'model-prices'), 'toolbar must not inherit price-cell typography');
assert.equal(button('Refresh price list').attrs['aria-pressed'], undefined);
assert.ok(output.textContent.includes('Prices last fetched:'));
assert.ok(!output.textContent.includes('More information'));
assert.equal(all(output, 'details').length, 0);
const explanations = all(output, 'th').slice(0, 4).map(th => helpText(th.children[0]));
assert.equal(new Set(explanations).size, 4);
assert.match(explanations[0], /developer\/manufacturer.*not your subscription/);
assert.match(explanations[1], /published catalog/);
assert.match(explanations[3], /published\/verified.*N\/A/);
assert.equal(explanations[2], 'Reference-price ratio to the cheapest comparable model (1.0x).\n\nUses the same recent token mix for every model and price tier; not task performance.');
let refreshes = 0; state.refreshPrices = () => refreshes++;
state.priceControls(true); click('Refresh price list'); assert.equal(refreshes, 1);
state.loading = state.priceRefreshing = true; state.priceControls(true);
assert.equal(button('Refresh price list').disabled, true);
assert.ok(output.textContent.includes('Refreshing…'));
state.loading = state.priceRefreshing = false; state.priceControls(false);
assert.equal(button('Refresh price list').disabled, true);
assert.ok(!Object.hasOwn(state.models, 'additive'));
assert.ok(!output.textContent.includes('Add sort keys'));
assert.equal(all(output, 'input')[0].checked, false);
assert.equal(all(output, 'input')[1].checked, true);
assert.equal(button('Relative Price List Cost').textContent, 'Relative Price List Cost ↓');
assert.ok(!names().includes('GPT-5.1'));
assert.ok(!output.textContent.includes('Accounts Overview'));
assert.ok(!output.textContent.includes('GitHub USD/M'));
check(1, false);
const old = rows().find(row => row.children[1].textContent === 'GPT-5.1');
assert.ok(!old.className.includes('superseded'));
assert.equal(old.children[2].textContent, fallback ? ' *' : '8.0x → 16.0x (>200K) → 32.0x (≥1M) *');
assert.ok(!output.textContent.includes('*1 Fixture promotional terms'));
assert.equal(helpText(old.children[2].children[0]), 'Price Promotion\nGPT-5.1\n50% off standard GitHub Copilot rates\nPromotion ends: 2026-11-10\nStandard prices resume: 2026-11-11');
assert.equal(old.children[2].children[0].attrs.title, undefined);
assert.ok(!output.textContent.includes('8.040000'));
assert.ok(explanations[2].length < 200, 'technical derivation must not fill the header tooltip');

// Four filter states use table-local conservative flags exported by Python.
const base = view.model_comparison[0];
const sampleSize = view.model_comparison_sample_size;
for (const count of [0, 1, 57]) {
  view.model_comparison_sample_size = count; draw();
  const help = helpText(all(output, 'th')[2].children[0]);
  assert.equal(help, explanations[2], 'sample count does not expand the compact help');
  assert.ok(!help.includes('latest 100 qualifying completed'), 'never invent the maximum sample size');
}
view.model_comparison_sample_size = sampleSize;
const row = (model, selectable, superseded, superseded_selectable, ratios = ['1'], date = '2026-10-01') => ({...base,
  model, publisher: 'OpenAI', selectable, superseded, superseded_selectable, release_date: date,
  relative_cost: ratios[0], relative_levels: ratios.map(relative_cost => ({relative_cost})), display_roles: [], recent: false});
view.model_catalog = {rows: [row('GPT-4.8', true, true, false), row('GPT-5', false, true, false),
  row('GPT-5.5', false, false, false), row('GPT-5 mini', true, false, false),
  row('GPT-6 preview', true, false, false), row('Ambiguous', true, false, false), row('Unknown', true, false, false, [null])],
  promotion_notes: [], recent_notices: []};
state.models = undefined; draw();
assert.deepEqual(names(), ['GPT-4.8', 'GPT-5 mini', 'GPT-6 preview', 'Ambiguous', 'Unknown']);
check(0, true);
assert.deepEqual(names(), ['GPT-5.5', 'GPT-5 mini', 'GPT-6 preview', 'Ambiguous', 'Unknown']);
check(1, false); assert.equal(rows().length, 7);
check(0, false); assert.equal(rows().length, 5);
assert.ok(names().includes('GPT-4.8'));
assert.ok(rows().every(row => !row.className?.includes('superseded')));

// Exact decimals, later tiers BEFORE secondary keys, no threshold ranking, missing last.
view.model_catalog.rows = [row('Z lower tier', true, false, false, ['8.00000000000000000001', '16']),
  row('A higher tier', true, false, false, ['8.00000000000000000001', '32']),
  row('Higher base', true, false, false, ['8.00000000000000000002', '1']),
  row('No tier', true, false, false, ['8.00000000000000000001']), row('Unknown', true, false, false, [null])];
state.models = undefined; draw();
click('Model', {shiftKey: true});
assert.deepEqual(names(), ['Higher base', 'A higher tier', 'Z lower tier', 'No tier', 'Unknown']);
assert.equal(button('Relative Price List Cost').textContent, 'Relative Price List Cost ↓ 1');
assert.equal(button('Model').textContent, 'Model ↑ 2');
assert.equal(all(output, 'th')[2].attrs['aria-sort'], 'descending');
assert.equal(all(output, 'th')[1].attrs['aria-sort'], 'none');
click('Relative Price List Cost', {shiftKey: true});
assert.deepEqual(names(), ['Z lower tier', 'A higher tier', 'No tier', 'Higher base', 'Unknown']);
check(0, true); assert.equal(button('Relative Price List Cost').textContent, 'Relative Price List Cost ↑ 1');
click('Model'); assert.equal(button('Relative Price List Cost').textContent, 'Relative Price List Cost ↕');
click('Publisher', {shiftKey: true});
assert.equal(button('Publisher').textContent, 'Publisher ↑ 2');
let prevented = false;
button('Release date').events.keydown({key: 'Enter', shiftKey: true, preventDefault() { prevented = true; }});
assert.ok(prevented); assert.equal(button('Release date').textContent, 'Release date ↑ 3');
button('Release date').events.keydown({key: ' ', shiftKey: true, preventDefault() {}});
assert.equal(button('Release date').textContent, 'Release date ↓ 3');
click('Publisher');
assert.equal(button('Publisher').textContent, 'Publisher ↓');
assert.equal(button('Model').textContent, 'Model ↕');
assert.equal(all(output, 'th')[0].attrs['aria-sort'], 'descending');

// Valid dates are chronological, invalid rollover and missing stay last both ways.
view.model_catalog.rows = [row('Old', true, false, false, ['1'], '2025-12-31'),
  row('New', true, false, false, ['1'], '2026-01-01'), row('Invalid', true, false, false, ['1'], '2026-02-30'),
  row('Missing', true, false, false, ['1'], null)];
state.models = undefined; draw(); click('Release date');
assert.deepEqual(names(), ['Old', 'New', 'Invalid', 'Missing']);
click('Release date'); assert.deepEqual(names(), ['New', 'Old', 'Invalid', 'Missing']);
for (const count of [0, 1, 51, 123]) {
  view.model_catalog.rows = Array.from({length: count}, (_, i) => row('Model ' + i, true, false, false));
  draw(); assert.equal(rows().length, count); assert.ok(!button('Next'));
}
view.model_availability_unverified = true; draw();
assert.ok(!output.textContent.includes('Model availability unverified'));
view.model_availability_unverified = false; view.model_availability_empty = true; draw();
assert.ok(output.textContent.includes('No available OpenCode models match'));
for (const hash of ['', '#/overview', '#/models/all', '#/models']) {
  context.hash = hash;
  assert.equal(vm.runInContext('ReportRoutes.resolve(hash).section', context), 'models');
  assert.equal(vm.runInContext('ReportRoutes.resolve(hash).request.kind', context), 'normal');
}
vm.runInContext('ReportRoutes.controls(controls, {section: "models"})', context);
assert.equal(controls.children.length, 0);

// The benchmark retains its own six sortable headers, rows and choices.
state.benchmark.data = benchmark; state.benchmark.draw();
const benchmarkRows = () => state.benchmark.body.children;
assert.deepEqual([...state.benchmark.headers].map(([th]) => th.textContent),
  ['Model ↕', 'Coding Client ↕', 'Effort ↕', 'Relative Task Cost ↓', 'USD/Task ↕', 'Solved ↕']);
assert.deepEqual(benchmarkRows().map(r => r.children[3].textContent), ['4.0x', '3.0x', '2.0x', '1.0x', 'N/A']);
assert.equal(benchmarkRows().length, 5);
assert.ok(benchmarkRows().every(r => !r.className?.includes('promotion')));
const referenceOrder = names(), referenceSort = JSON.stringify(state.models);
state.benchmark.headers[0][1].events.click();
assert.deepEqual(benchmarkRows().map(r => r.children[1].textContent).slice(0, 4), ['Claude Code', 'Claude Code', 'Claude Code', 'Other client']);
state.benchmark.headers[4][1].events.click();
assert.deepEqual(names(), referenceOrder);
assert.equal(JSON.stringify(state.models), referenceSort);
const retainedSort = JSON.stringify(state.benchmark.sort); draw();
assert.equal(JSON.stringify(state.benchmark.sort), retainedSort);
assert.ok(state.benchmark.fetched.textContent.includes('Last fetched:'));
assert.equal(all(state.benchmark.root, 'a')[0].href, 'https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4');
state.benchmark.data = {...benchmark, rows: [benchmark.rows[0], benchmark.rows[1]].map((r, i) => ({...r,
  relative_cost: i ? '1.00000000000000000002' : '1.00000000000000000001', relative_text: '1.0x'}))};
state.benchmark.sort = {index:3, direction:-1}; state.benchmark.draw();
assert.equal(benchmarkRows()[0].children[2].textContent, 'high', 'sort uses exact raw values, not identical displayed ratios');
