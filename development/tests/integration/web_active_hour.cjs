// Deterministic DOM/route tests, not browser layout or physical keyboard proof.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.events = {}; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...values) { this.children.push(...values); }
  replaceChildren(...values) { this.children = values; this.text = ''; }
  setAttribute() {}
  addEventListener(key, handler) { this.events[key] = handler; }
}
const all = (node, tag) => [...(node.tag === tag ? [node] : []), ...node.children.flatMap(child => all(child, tag))];
const result = JSON.parse(fs.readFileSync(0, 'utf8')), output = new Node('main');
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output, result, Date, URLSearchParams});
require('../fixtures/web_help_vm.cjs')(vm, context);
for (const file of ['render.js', 'reports.js']) vm.runInContext(fs.readFileSync('src/web/assets/' + file, 'utf8'), context);
// The retired period page is gone; the reusable session-detail rate still renders
// exactly the prepared server values, with reversible unit bindings.
vm.runInContext('for (const metric of result.view.active_hours) output.append(ReportView.element("p", () => ReportView.hourlySummary(metric)))', context);
for (const value of result.view.active_hours) {
  assert.ok(output.textContent.includes(value.display.rate));
  assert.ok(output.textContent.includes(value.display.duration_ms));
  assert.ok(output.textContent.includes(value.display.known_ccost));
}
const first = output.children[0], credits = output.textContent;
vm.runInContext('ReportView.setUnit("usd", output)', context);
assert.equal(first, output.children[0]);
for (const value of result.view.active_hours) assert.ok(output.textContent.includes(value.display_units.usd.rate));
vm.runInContext('ReportView.setUnit("credits", output)', context);
assert.equal(credits, output.textContent);
assert.equal('#/ai-stats', vm.runInContext('ReportRoutes.resolve("#/cost-per-hour").redirect', context));
assert.equal('ai-stats', vm.runInContext('ReportRoutes.resolve("#/ai-stats").request.kind', context));
assert.equal(true, vm.runInContext('ReportRoutes.resolve("#/watch").live', context));
assert.equal(null, vm.runInContext('ReportRoutes.resolve("#/accounts").request', context));
assert.equal(true, vm.runInContext('ReportRoutes.resolve("#/accounts").live', context));
console.log('PASS retired hourly route alias and preserved shared session-rate display/units');
