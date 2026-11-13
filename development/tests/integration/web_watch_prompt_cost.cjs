// Full Watch DOM cost regression with Python-prepared display variants, no valuation.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ''; this.dataset = {}; this.events = {}; this.style = {setProperty() {}}; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...items) { for (const item of items) { item.remove(); this.children.push(item); item.parentNode = this; } }
  replaceChildren(...items) { this.children.forEach(child => child.parentNode = null); this.children = []; this.text = ''; this.append(...items); }
  insertBefore(child, before) { child.remove(); this.children.splice(before ? this.children.indexOf(before) : this.children.length, 0, child); child.parentNode = this; }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  contains(node) { return this === node || this.children.some(child => child.contains(node)); }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(kind, handler) { this.events[kind] = handler; }
}
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
input.view.history_state = 'observed'; // This fixture supplies a complete fixed history.
const context = vm.createContext({input, parent:new Node('div'), document:{createElement:tag => new Node(tag),
  createElementNS:(namespaceURI,tag) => Object.assign(new Node(tag), {namespaceURI})},
  window:{addEventListener() {}, matchMedia:() => ({addEventListener() {}, removeEventListener() {}})}});
const helpText = require('../fixtures/web_help_vm.cjs')(vm, context);
for (const name of ['render', 'account-cards', 'watch']) vm.runInContext(fs.readFileSync(`src/web/assets/${name}.js`, 'utf8'), context);
vm.runInContext('globalThis.state={connection:"Live connected."}; ReportView.renderLive(parent,input,state)', context);
const cards = [...context.state.watch.cards.values()];
assert.equal(cards.length, 2);
const credits = ['1250', '?12', '100', '0', 'N/A', '2', '0', '<0.1', '?<0.1', '12', '12', '0', 'N/A', '', '0', '<0.1'];
const usd = ['$12.50', '?$0.12', '$1.00', '$0.00', 'N/A', '$0.01', '$0.00', '$0.00', '?$0.00', '$0.12', '$0.12', '$0.00', 'N/A', '', '$0.00', '$0.00'];
const canonical = JSON.stringify(input);
for (const [unit, expected] of [['credits', credits], ['usd', usd], ['credits', credits]]) {
  vm.runInContext(`ReportView.setUnit('${unit}',parent)`, context);
  vm.runInContext('ReportView.renderLive(parent,input,state)', context);
  for (const card of cards) {
    assert.deepEqual(card.body.children.map(row => row.children[5].textContent), expected);
    const [button] = card.root.children[2].children[0].children[0].children[0].children[5].children;
    assert.equal(button.textContent, 'CCost');
    const explanation = helpText(button);
    assert.equal(button['aria-describedby'], 'context-help');
    assert.equal(button.title, undefined, 'no overlapping native title');
    assert.ok(button.events.focus && button.events.click && button.events.pointerenter);
    assert.match(explanation, /not your bill[\s\S]*value[\s\S]*Incoming\/Extra CCost[\s\S]*model\/subagent details/);
    assert.doesNotMatch(explanation, /displayed zero|N\/A|not zero|cannot be priced|Input token share/);
    for (const [index, row] of card.body.children.entries()) {
      assert.equal(row.children.length, 10);
      const target = row.children[5].children[0];
      const prompt = card.value.rows[index].prompt, d = {...prompt.display, ...prompt.display_units[unit]};
      if (!expected[index]) { assert.ok(!target.className?.includes('help-value')); continue; }
      const help = helpText(target);
      assert.ok(help.startsWith(`Incoming Context CCost (I): ${d.incoming_context_ccost}\nExtra CCost (E): ${d.extra_ccost}\n`), JSON.stringify({index,unit,help,d}));
      assert.match(help, /first attributed request[\s\S]*Output, later requests and linked subagents[\s\S]*unavailable, not zero/);
      assert.ok(help.endsWith(d.cost_detail_help), 'entire prepared rich breakdown survives unchanged');
      assert.match(help, /Main prompt — fixture\/main · High[\s\S]*Subagent 1 — fixture\/child-a · Low[\s\S]*Number of prompts: 1[\s\S]*Subagent 2 — fixture\/child-b · Medium[\s\S]*incomplete boundaries[\s\S]*Cached input: N\/A[\s\S]*Partial pricing[\s\S]*Total CCost:/);
      assert.equal((help.match(/Total CCost:/g) || []).length, 1);
      assert.ok(target.events.focus && target.events.click && target.events.pointerenter);
      if (expected[index] === 'N/A') assert.match(help, /CCost cannot be calculated/);
    }
  }
}
assert.equal(JSON.stringify(input), canonical, 'presentation never rewrites raw costs, calls or component evidence');
console.log('watch prompt cost passed');
