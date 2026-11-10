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
const helpText = require('../fixtures/web_help_vm.cjs')(vm, context);
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
const draw = () => vm.runInContext('ReportView.render(output, result, state)', context);
const names = () => all(output, 'tbody')[0].children.map(row => row.children[1].textContent);
const click = title => all(output, 'button').find(n => n.textContent.startsWith(title)).events.click({});
draw();
const relativeHelp = helpText(all(output, 'th')[2].children[0]);
assert.ok(relativeHelp.includes('same recent token mix'));
assert.ok(!/\b(?:Cache|Write):/.test(output.textContent));
assert.deepEqual(names(), order, 'default exact descending tier ranking');
assert.deepEqual(all(output, 'th').map(n => n.textContent), ['Publisher ↕', 'Model ↕', 'Relative Price List Cost ↓', 'Release date ↕']);
assert.equal(all(output, 'h3').length, 0, 'definitions belong to heading help, not cards');
assert.equal(output.children[0].textContent, 'GitHub Reference Pricing(GitHub Copilot · View source)');
assert.equal(output.children[1].className, 'model-tools', 'notices/filters precede table');
assert.equal(output.children[3].className, 'overview-models');
assert.equal(all(output, 'details').length, 0, 'no Models explanations disclosure');
for (const text of ['Pricing/cache metadata', 'Snapshot:', 'Shared global comparison sample', 'full-report rows']) assert.ok(!output.textContent.includes(text));
assert.equal(all(output, 'input').length, 2);
assert.equal(all(output, 'button').length, 5);
assert.ok(!output.textContent.includes('Promotion terms'));
assert.ok(!output.textContent.includes('Final note'));
for (const forbidden of ['CCost today:', 'Billed month:', '5-hour', '36% used']) assert.ok(!output.textContent.includes(forbidden));
assert.ok(!output.textContent.includes('Report Today CCost'), 'no unrelated whole-report totals');
const warnings = all(output, 'p').filter(n => n.className === 'warning').map(n => n.textContent);
assert.ok(!warnings.includes('CCost account attribution unknown.'));
assert.ok(!warnings.includes('Attribution incomplete'));
const relatives = all(output, 'tbody')[0].children.map(row => row.children[2].textContent);
if (fallback) {
  assert.deepEqual(relatives, ['', '', '', ' *', '']);
  assert.ok(relativeHelp.includes('not task performance'));
} else {
  assert.deepEqual(relatives, ['8.0x', '8.0x', '8.0x → 20.0x (>1M)', '8.0x → 16.0x (>200K) *', '1.0x']);
  assert.ok(relativeHelp.includes('1.0x'));
}
// Both names resolve to one presentation; header clicks toggle without a third state.
context.state.section = 'models'; draw(); click('Model');
assert.deepEqual(names(), ['A', 'Reference', 'TierHigh', 'TierLow', 'Z']);
click('Model');
assert.deepEqual(names(), ['Z', 'TierLow', 'TierHigh', 'Reference', 'A']);
click('Model');
assert.deepEqual(names(), ['A', 'Reference', 'TierHigh', 'TierLow', 'Z']);
// Arbitrary precision, equal displayed values, stable ties, unknowns last in both directions.
const base = view.model_comparison[0];
view.model_comparison = [['Higher', '1.00000000000000000002'], ['Lower', '1.00000000000000000001'],
  ['Equal', '1.00000000000000000001'], ['Unknown', null]].map(([model, relative_cost]) => ({...base, model, relative_cost, relative_levels: []}));
draw(); click('Relative Price List Cost'); click('Relative Price List Cost');
assert.deepEqual(names(), ['Lower', 'Equal', 'Higher', 'Unknown']);
click('Relative Price List Cost');
assert.deepEqual(names(), ['Higher', 'Lower', 'Equal', 'Unknown']);
// Passive source caveats do not accompany usable Models; account failures belong to Accounts.
context.state.section = 'overview';
context.result.source.status = 'partial';
view.accounts_quotas.accounts[0].observation.has_error = true;
view.accounts_quotas.accounts[0].observation.error_code = 'transport_failure';
draw();
assert.ok(!output.textContent.includes('Partial source data'));
assert.ok(!all(output, 'p').some(n => n.textContent.includes('Connection failed')), 'account-only warnings stay on Accounts');

// Overview is one coherent table, including every row beyond the former 50-row cap.
for (const count of [0, 1, 49, 50, 51, 123]) {
  view.model_comparison = Array.from({length: count}, (_, index) => ({...base,
    publisher: index % 2 ? 'Publisher B' : 'Publisher A', model: 'Shared ' + Math.floor(index / 2),
    recent: index % 3 === 0, superseded: index % 3 === 1}));
  context.state.pages.models = 2; // a stale page from a retained view must never hide rows
  context.state.models = {all: false, latest: false, sorts: [{index: 2, direction: -1}]};
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
  assert.equal(all(output, 'tbody')[0].tabIndex, undefined, 'document, not body, owns vertical scrolling');
  assert.deepEqual(names(), view.model_comparison.map(row => row.model));
}
