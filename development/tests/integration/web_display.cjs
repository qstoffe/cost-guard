// Deterministic DOM model, not browser/UI automation or visual acceptance.
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
const view = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = new Node('main');
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output,
  result: {observed_at_ms: 1, source: {status: 'acquired', atomicity: 'per_root_snapshot'}, view}, Date});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
vm.runInContext('ReportView.render(output, result, {pages: {}, section: "models"})', context);
assert.ok(output.textContent.includes('0.1x'));
assert.ok(!output.textContent.includes('0.123456789012345'));
assert.ok(output.textContent.includes('0.000000123456789/0/0/2'), 'native rates stay exact');
assert.ok(output.textContent.indexOf('Promo notice') > output.textContent.indexOf('Release date'));
assert.ok(output.textContent.indexOf('New notice') > output.textContent.indexOf('Promo notice'));
assert.ok(output.textContent.indexOf('Tail note') > output.textContent.indexOf('New notice'));
assert.deepEqual(all(output, 'th').map(n => n.textContent), ['Publisher', 'Model', 'Relative CCost', 'GitHub USD/M I/C/W/O', 'Release date']);
assert.ok(all(output, 'span').some(n => n.className === 'promotion' && n.textContent.includes('0.1x')));
assert.ok(all(output, 'span').some(n => n.className === 'new' && n.textContent.includes('M')));
// Equal display strings cannot decide ordering; raw decimal strings still do.
const first = view.model_comparison[0];
view.model_comparison = [{...first, model: 'higher', relative_cost: '1.00000000000000000002'},
  {...first, model: 'lower', relative_cost: '1.00000000000000000001'}];
vm.runInContext('ReportView.render(output, result, {pages: {}, section: "models"})', context);
all(output, 'button').find(n => n.textContent === 'Relative CCost').events.click();
assert.ok(all(output, 'tbody')[0].children[0].textContent.includes('lower'));
all(output, 'button').find(n => n.textContent === 'Relative CCost').events.click();
assert.ok(all(output, 'tbody')[0].children[0].textContent.includes('higher'));
// Unversioned/missing display tokens fail closed, not as raw numeric cells.
delete first.display;
view.model_comparison = [first];
vm.runInContext('ReportView.render(output, result, {pages: {}, section: "models"})', context);
assert.ok(!output.textContent.includes('0.123456789012345'));
assert.ok(output.textContent.includes('N/A'));
