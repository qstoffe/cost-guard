// Deterministic rendered DOM assertions; screenshots are separate evidence.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.events = {}; this.attrs = {}; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...values) { this.children.push(...values); }
  replaceChildren(...values) { this.children = values; this.text = ''; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(key, handler) { this.events[key] = handler; }
}
const all = (node, tag) => [...(node.tag === tag ? [node] : []), ...node.children.flatMap(child => all(child, tag))];
const {view, order, fallback} = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = new Node('main');
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output,
  state: {pages: {}, section: 'overview'}, result: {observed_at_ms: 1,
    source: {status: 'acquired', atomicity: 'per_root_snapshot'}, view}, Date});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
const draw = () => vm.runInContext('ReportView.render(output, result, state)', context);
const names = () => all(output, 'tbody')[0].children.map(row => row.children[1].textContent);
const click = title => all(output, 'button').find(n => n.textContent === title).events.click();
draw();
assert.ok(output.textContent.includes('I = Input; C = Cached input; W = Cache write; O = Output'));
assert.ok(!/\b(?:Cache|Write):/.test(output.textContent));
assert.deepEqual(names(), order, 'default rendered order must match CLI, not a local sort');
assert.deepEqual(all(output, 'th').map(n => n.textContent), ['Publisher', 'Model', 'Relative CCost', 'Release date']);
assert.deepEqual(all(output, 'h3').map(n => n.textContent), ['CCost', 'Token Mix %', 'Relative CCost']);
assert.equal(output.children[0].className, 'overview-models', 'table is first');
assert.equal(output.children[1].children[0].textContent, 'More information');
assert.ok(!output.children[1].open, 'explanations start collapsed');
for (const text of ['Pricing/cache metadata', 'Snapshot:', 'Shared global comparison sample', 'full-report rows']) assert.ok(!output.textContent.includes(text));
assert.equal(all(output, 'input').length, 0);
assert.equal(all(output, 'button').length, 0);
for (const [first, second] of [['Release date', 'Promotion terms'], ['Promotion terms', 'New models'],
  ['New models', 'CCost today'], ['CCost today', 'Final note']]) {
  assert.ok(output.textContent.indexOf(first) < output.textContent.indexOf(second));
}
assert.ok(output.textContent.includes('CCost today: 2'));
assert.ok(output.textContent.includes('Billed month: $2.34'));
assert.ok(output.textContent.includes('5-hour'));
assert.ok(output.textContent.includes('36% used'));
assert.ok(!output.textContent.includes('Report Today CCost'), 'no unrelated whole-report totals');
const warnings = all(output, 'p').filter(n => n.className === 'warning').map(n => n.textContent);
assert.ok(warnings.includes('CCost account attribution unknown.'));
assert.ok(warnings.includes('Attribution incomplete'));
const relatives = all(output, 'tbody')[0].children.map(row => row.children[2].textContent);
if (fallback) {
  assert.deepEqual(relatives, ['', '', '', '*1 ', '']);
  assert.ok(output.textContent.includes('hidden 2/96/1/1 mix'));
} else {
  assert.deepEqual(relatives, ['8.0x', '8.0x', '8.0x → 20.0x (>1M)', '*1 8.0x → 16.0x (>200K)', '1.0x']);
  assert.ok(output.textContent.includes('Input: 20% (2) · Cached input: 60% (6) · Cache write: 10% (1) · Output: 10% (1)'));
  assert.ok(output.textContent.includes('20/60/10/10 tokens · CCost 2/6/1/1'));
}
// Dedicated Models retains its independent sort/filter controls.
context.state.section = 'models'; draw(); click('Model');
assert.deepEqual(names(), ['A', 'Reference', 'TierHigh', 'TierLow', 'Z']);
click('Model');
assert.deepEqual(names(), ['Z', 'TierLow', 'TierHigh', 'Reference', 'A']);
click('Model');
assert.deepEqual(names(), order, 'third click restores tier-aware server order, even without a sample');
click('Model'); click('CLI default order');
assert.deepEqual(names(), order);
// Arbitrary precision, equal displayed values, stable ties, unknowns last in both directions.
const base = view.model_comparison[0];
view.model_comparison = [['Higher', '1.00000000000000000002'], ['Lower', '1.00000000000000000001'],
  ['Equal', '1.00000000000000000001'], ['Unknown', null]].map(([model, relative_cost]) => ({...base, model, relative_cost}));
draw(); click('Relative CCost');
assert.deepEqual(names(), ['Lower', 'Equal', 'Higher', 'Unknown']);
click('Relative CCost');
assert.deepEqual(names(), ['Higher', 'Lower', 'Equal', 'Unknown']);
click('CLI default order');
assert.deepEqual(names(), ['Higher', 'Lower', 'Equal', 'Unknown']);
// Partial sources and failed accounts stay visible, not hidden in disclosure widgets.
context.state.section = 'overview';
context.result.source.status = 'partial';
view.accounts_quotas.accounts[0].observation.has_error = true;
view.accounts_quotas.accounts[0].observation.error_code = 'transport_failure';
draw();
assert.ok(all(output, 'p').some(n => n.className === 'warning' && n.textContent.includes('Partial source data')));
assert.ok(all(output, 'p').some(n => n.textContent.includes('Connection failed')));

// Overview is one coherent table, including every row beyond the former 50-row cap.
for (const count of [0, 1, 49, 50, 51, 123]) {
  view.model_comparison = Array.from({length: count}, (_, index) => ({...base,
    publisher: index % 2 ? 'Publisher B' : 'Publisher A', model: 'Shared ' + Math.floor(index / 2),
    recent: index % 3 === 0, superseded: index % 3 === 1}));
  context.state.pages.models = 2; // a stale page from a retained view must never hide rows
  draw();
  const rows = all(output, 'tbody')[0].children;
  assert.equal(rows.length, count);
  assert.deepEqual(rows.map(row => row.children.slice(0, 2).map(cell => cell.textContent)),
    view.model_comparison.map(row => [row.publisher, row.model]));
  assert.ok(!all(output, 'button').some(n => ['Previous', 'Next'].includes(n.textContent)));
  const scroll = all(output, 'div').find(n => n.className === 'overview-models');
  assert.equal(scroll.tabIndex, 0, 'complete table remains keyboard scrollable');
  assert.equal(scroll.attrs['role'], 'region');
  assert.ok(!output.textContent.includes('full-report rows'));
  assert.equal(all(output, 'tbody')[0].tabIndex, 0);
  assert.deepEqual(names(), view.model_comparison.map(row => row.model));
}
