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
for (const file of ['render.js', 'reports.js']) vm.runInContext(fs.readFileSync('src/web/assets/' + file, 'utf8'), context);
vm.runInContext('ReportView.render(output, result, {pages: {}, section: "cost-per-hour"})', context);
assert.match(output.textContent, /Today.*Month to date.*Rolling 30 days/);
assert.match(output.textContent, /canonical event\/completion timestamp/);
assert.match(output.textContent, /not agent-worker-hours/);
assert.ok(all(output, 'a').some(a => a.href === '#/sessions'));
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
assert.equal(true, vm.runInContext('ReportRoutes.resolve("#/cost-per-hour").explicit', context));
assert.equal('cost-per-hour', vm.runInContext('ReportRoutes.resolve("#/cost-per-hour").request.kind', context));
assert.equal(true, vm.runInContext('ReportRoutes.resolve("#/watch").live', context));
assert.equal('normal', vm.runInContext('ReportRoutes.resolve("#/accounts").request.kind', context));
console.log('PASS explicit hourly capture route, three scopes, frozen server display and reversible memory-only units');
