// Native empty-period CCost remains independent of Today in the real Accounts renderer.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(n => n.textContent).join(''); }
  append(...nodes) { this.children.push(...nodes); }
  setAttribute() {}
}
const account = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = new Node('main');
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output,
  quota: {accounts: [account]}, Date});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
vm.runInContext('ReportView.overviewAccounts(output, quota, "", true, true)', context);
for (const text of ['0% used', 'Window not started', 'CCost 5-hour: 0', 'CCost today: 604']) {
  assert.ok(output.textContent.includes(text), text + ': ' + output.textContent);
}
assert.ok(!output.textContent.includes('CCost 5-hour: 604'));
