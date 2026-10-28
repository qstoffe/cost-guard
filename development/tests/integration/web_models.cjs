// Rendered Models contract over the same canonical report as the terminal.
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
const {view, order, fallback} = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = new Node('main'), controls = new Node('div');
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output, controls,
  state: {pages: {}, section: 'models'}, result: {view, observed_at_ms: 1, source: {status: 'acquired'}}});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('src/web/assets/reports.js', 'utf8'), context);
const draw = () => vm.runInContext('ReportView.render(output, result, state)', context);
const rows = () => all(output, 'tbody')[0].children;
const names = () => rows().map(row => row.children[1].textContent.split(' · ')[0]);
const click = text => all(output, 'button').find(n => n.textContent === text).events.click();
draw();
assert.deepEqual(names(), order);
if (!fallback) {
  assert.ok(output.textContent.includes('Shared global comparison sample'));
  assert.ok(output.textContent.includes('one shared global I/C/W/O mix'));
  assert.ok(output.textContent.includes(`latest ${view.model_comparison_sample_size} completed priceable prompts`));
  assert.ok(!/personalized|generic prior|weight slots|same-publisher/.test(output.textContent));
  for (const row of view.model_comparison) assert.ok(output.textContent.includes(row.display.evidence));
  const first = all(rows()[0], 'span').find(node => node.className?.includes('model-relative'));
  assert.equal(first.title, view.model_comparison[0].display.evidence);
}
assert.ok(all(output, 'table')[0].className.includes('models-table'));
assert.ok(!output.textContent.includes('Accounts Overview'));
const old = rows().find(row => row.children[1].textContent.startsWith('GPT-5.1'));
assert.ok(old.className.includes('superseded'));
assert.equal(old.children[2].textContent, fallback ? '*1 ' : '*1 8.0x → 16.0x (>200K) → 32.0x (≥1M)');
assert.ok(output.textContent.includes('*1 Fixture promotional terms'));
assert.ok(output.textContent.includes('Recent models: Z'));
assert.ok(!output.textContent.includes('8.040000'));
if (fallback) assert.ok(output.textContent.includes('hidden 2/96/1/1'));
else assert.ok(!names().includes('Unknown'), 'CLI excludes models unpriceable for the independent sample');
if (view.kind === 'all-models') {
  assert.ok(output.textContent.includes('2.1234567890123456789/2.1234567890123456789'));
  assert.ok(output.textContent.includes('not billed spend'));
  const base = view.model_comparison[0];
  view.model_comparison = [['Ten', '10'], ['TwoHigher', '2.00000000000000000002'],
    ['Two', '2.00000000000000000001'], ['Unknown', null]].map(([model, price]) =>
      ({...base, model, price_summary: price == null ? 'N/A' : `${price}/0/-/1`, recent: false, superseded: false}));
  draw(); click('GitHub USD/M I/C/W/O');
  assert.deepEqual(names(), ['Two', 'TwoHigher', 'Ten', 'Unknown']);
  click('GitHub USD/M I/C/W/O');
  assert.deepEqual(names(), ['Ten', 'TwoHigher', 'Two', 'Unknown']);
}
const base = view.model_comparison[0];
view.model_comparison = [['Higher', '8.04000000000000000002'], ['Lower', '8.04000000000000000001'],
  ['Equal', '8.04000000000000000001'], ['Unknown', null]].map(([model, relative_cost]) =>
    ({...base, model, relative_cost, recent: false, superseded: false}));
draw(); click('Relative CCost');
assert.deepEqual(names(), ['Lower', 'Equal', 'Higher', 'Unknown']);
click('Relative CCost');
assert.deepEqual(names(), ['Higher', 'Lower', 'Equal', 'Unknown']);
click('CLI default order');
assert.deepEqual(names(), ['Higher', 'Lower', 'Equal', 'Unknown']);
const filter = all(output, 'input')[0]; filter.value = 'Lower'; filter.events.input();
assert.deepEqual(names(), ['Lower']);
view.model_availability_unverified = true; draw();
assert.ok(output.textContent.includes('Model availability unverified'));
view.model_comparison = []; view.model_availability_unverified = false; view.model_availability_empty = true; draw();
assert.ok(output.textContent.includes('No available OpenCode models match'));
for (const kind of ['normal', 'all-models']) {
  context.kind = kind;
  vm.runInContext('ReportRoutes.controls(controls, {section: "models", request: {kind}})', context);
  const links = all(controls, 'a');
  assert.equal(links.filter(n => n.attrs['aria-current'] === 'page').length, 1);
  assert.equal(links.find(n => n.attrs['aria-current'] === 'page').href, kind === 'normal' ? '#/models' : '#/models/all');
}
