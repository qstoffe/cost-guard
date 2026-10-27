const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(n => n.textContent).join(''); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; this.text = ''; }
  setAttribute(key, value) { this.attrs[key] = value; }
}
const all = (n, tag) => [...(n.tag === tag ? [n] : []), ...n.children.flatMap(child => all(child, tag))];
const view = JSON.parse(fs.readFileSync(0, 'utf8')), output = new Node('main');
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output, Date,
  state: {section: 'accounts', pages: {}}, result: {view, observed_at_ms: 1, source: {status: 'acquired'}}});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
vm.runInContext('ReportView.render(output, result, state)', context);
const cards = all(output, 'section');
assert.equal(cards.length, 7);
assert.equal(all(output, 'table').length, 0, 'no quota filter/pager wall');
assert.deepEqual(cards.map(n => all(n, 'h4')[0].textContent), view.accounts_quotas.accounts.map(a => a.observation.label));
for (const text of ['90% remaining', '89 AI credits remaining / 100 AI credits', '$8.99 / $10.00',
  'Billed today: $0.00', 'Billed month: $1.23', 'CCost today: 2', 'CCost this month: 13',
  '29 AI credits/day', 'no workdays left', 'Unaccounted usage (estimate): -0.2', 'Rate limited',
  'Connection failed', 'Window not started', 'Attribution incomplete', 'Quota unavailable; not zero or unlimited.']) {
  assert.ok(output.textContent.includes(text), text);
}
assert.equal(all(cards[0], 'progress')[0].value, '90');
assert.equal(all(cards[1], 'progress')[0].value, '0', 'known zero is determinate');
assert.ok(cards[1].textContent.includes('BLOCKED'));
for (const index of [2, 3, 4, 5]) assert.equal(all(cards[index], 'progress').length, 0, 'unknown/unlimited never empty progress');
assert.ok(cards[2].textContent.includes('Unlimited'));
assert.ok(cards[4].textContent.includes('Remaining unavailable'));
assert.ok(cards[6].textContent.includes('stale'));
assert.equal(all(output, 'details').length, 8, 'one observation disclosure per account plus report help');
for (const text of ['PRIVATE', '0.89876543211', '89.876543211', '1.23456789', 'rate_limited', 'window_active', '9999']) {
  assert.ok(!output.textContent.includes(text), 'no raw diagnostic/fraction/global substituted value: ' + text);
}
// Rendering another section must not acquire or mutate the shared frozen report.
assert.equal(view.accounts_quotas.accounts[0].observation.quotas[0].remaining, '89.876543211');
