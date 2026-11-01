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
const {view, fallback} = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = new Node('main'), controls = new Node('div');
const state = {pages: {}, section: 'models'};
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output, controls,
  state, result: {view, observed_at_ms: 1, source: {status: 'acquired'}}, URLSearchParams});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('src/web/assets/reports.js', 'utf8'), context);
const draw = () => vm.runInContext('ReportView.render(output, result, state)', context);
const rows = () => all(output, 'tbody')[0].children;
const names = () => rows().map(row => row.children[1].textContent);
const button = name => all(output, 'button').find(n => n.textContent.startsWith(name));
const click = (name, event = {}) => button(name).events.click(event);
const check = (index, value) => { const input = all(output, 'input')[index]; input.checked = value; input.events.change(); };
draw();
assert.equal(all(output, 'th').length, 4);
assert.equal(all(output, 'input').length, 2);
assert.equal(all(output, 'button').length, 4);
assert.ok(!Object.hasOwn(state.models, 'additive'));
assert.ok(!output.textContent.includes('Add sort keys'));
assert.equal(all(output, 'input')[0].checked, false);
assert.equal(all(output, 'input')[1].checked, true);
assert.equal(button('Relative CCost').textContent, 'Relative CCost ↓');
assert.ok(!names().includes('GPT-5.1'));
assert.ok(!output.textContent.includes('Accounts Overview'));
assert.ok(!output.textContent.includes('GitHub USD/M'));
check(1, false);
const old = rows().find(row => row.children[1].textContent === 'GPT-5.1');
assert.ok(!old.className.includes('superseded'));
assert.equal(old.children[2].textContent, fallback ? '*1 ' : '*1 8.0x → 16.0x (>200K) → 32.0x (≥1M)');
assert.ok(output.textContent.includes('*1 Fixture promotional terms'));
assert.ok(!output.textContent.includes('8.040000'));
if (fallback) assert.ok(output.textContent.includes('hidden 2/96/1/1'));

// Four filter states use table-local conservative flags exported by Python.
const base = view.model_comparison[0];
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
assert.equal(button('Relative CCost').textContent, 'Relative CCost ↓ 1');
assert.equal(button('Model').textContent, 'Model ↑ 2');
assert.equal(all(output, 'th')[2].attrs['aria-sort'], 'descending');
assert.equal(all(output, 'th')[1].attrs['aria-sort'], 'none');
click('Relative CCost', {shiftKey: true});
assert.deepEqual(names(), ['Z lower tier', 'A higher tier', 'No tier', 'Higher base', 'Unknown']);
check(0, true); assert.equal(button('Relative CCost').textContent, 'Relative CCost ↑ 1');
click('Model'); assert.equal(button('Relative CCost').textContent, 'Relative CCost ↕');
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
assert.ok(output.textContent.includes('Model availability unverified'));
view.model_availability_unverified = false; view.model_availability_empty = true; draw();
assert.ok(output.textContent.includes('No available OpenCode models match'));
for (const hash of ['', '#/overview', '#/models/all', '#/models']) {
  context.hash = hash;
  assert.equal(vm.runInContext('ReportRoutes.resolve(hash).section', context), 'models');
  assert.equal(vm.runInContext('ReportRoutes.resolve(hash).request.kind', context), 'normal');
}
vm.runInContext('ReportRoutes.controls(controls, {section: "models"})', context);
assert.equal(controls.children.length, 0);
