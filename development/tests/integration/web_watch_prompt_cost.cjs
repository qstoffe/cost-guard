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
const context = vm.createContext({input, parent:new Node('div'), document:{createElement:tag => new Node(tag),
  createElementNS:(namespaceURI,tag) => Object.assign(new Node(tag), {namespaceURI})},
  window:{addEventListener() {}, matchMedia:() => ({addEventListener() {}, removeEventListener() {}})}});
const helpText = require('../fixtures/web_help_vm.cjs')(vm, context);
for (const name of ['render', 'watch']) vm.runInContext(fs.readFileSync(`src/web/assets/${name}.js`, 'utf8'), context);
vm.runInContext('globalThis.state={connection:"Live connected."}; ReportView.renderLive(parent,input,state)', context);
const cards = [...context.state.watch.cards.values()];
assert.equal(cards.length, 2);
const credits = ['1250 (900 + 350)', '?12 (5 + N/A)', '100 (N/A + N/A)', '0 (0 + 0)', 'N/A', '2 (2 + <0.1)', ''];
const usd = ['$12.50 ($9.00 + $3.50)', '?$0.12 ($0.05 + N/A)', '$1.00 (N/A + N/A)', '$0.00 ($0.00 + $0.00)', 'N/A', '$0.01 ($0.01 + $0.00)', ''];
for (const [unit, expected] of [['credits', credits], ['usd', usd], ['credits', credits]]) {
  vm.runInContext(`ReportView.setUnit('${unit}',parent)`, context);
  for (const card of cards) {
    assert.deepEqual(card.body.children.map(row => row.children[5].textContent), expected);
    const [button] = card.root.children[2].children[0].children[0].children[0].children[5].children;
    assert.equal(button.textContent, 'CCost (I + E)');
    const explanation = helpText(button);
    assert.equal(button['aria-describedby'], 'context-help');
    assert.equal(button.title, undefined, 'no overlapping native title');
    assert.ok(button.events.focus && button.events.click && button.events.pointerenter);
    assert.match(explanation, /not your bill[\s\S]*I — Incoming context cost on the first model request\.[\s\S]*E — Other cost[\s\S]*linked subagents[\s\S]*fully priced[\s\S]*rounding[\s\S]*N\/A[\s\S]*not zero[\s\S]*cannot be priced[\s\S]*not the Input token share/);
  }
}
console.log('watch prompt cost passed');
