// Deterministic DOM assertions, not real-browser or visual evidence.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.events = {}; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  get firstChild() { return this.children[0] || null; }
  append(...values) { for (const node of values) { node.remove?.(); node.parentNode = this; this.children.push(node); } }
  insertBefore(node, before) { node.remove(); node.parentNode = this; const index = this.children.indexOf(before); this.children.splice(index < 0 ? this.children.length : index, 0, node); }
  remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(node => node !== this); this.parentNode = null; }
  replaceChildren(...values) { this.children = values; this.text = ''; }
  setAttribute() {}
  addEventListener(key, handler) { this.events[key] = handler; }
}
const all = (node, tag) => [...(node.tag === tag ? [node] : []), ...node.children.flatMap(child => all(child, tag))];
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = new Node('main');
const context = vm.createContext({document: {createElement: tag => new Node(tag), createElementNS: (_, tag) => new Node(tag)}, output, Date});
const helpText = require('../fixtures/web_help_vm.cjs')(vm, context);
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('src/web/assets/token-mix.js', 'utf8'), context);
for (const [kind, result] of Object.entries(input)) {
  context.result = result;
  vm.runInContext('ReportView.render(output, result, {pages: {}, section: result.view.kind})', context);
   if (kind === 'session') assert.ok(output.textContent.includes('I = Input; C = Cached input; W = Cache write; O = Output'));
  assert.ok(!/\b(?:Cache|Write):/.test(output.textContent));
  assert.ok(!all(output, 'th').some(n => ['Cache', 'Write', 'I/C/W/O %'].includes(n.textContent)));
  for (const node of all(output, 'th')) assert.equal(node.scope, 'col');
  if (kind === 'session') {
    assert.ok(!output.textContent.includes(String(result.scope.start_ms)), 'no epoch range prose');
    assert.doesNotMatch(output.textContent, /Inclusive local range|CCost for range/);
    assert.match(output.textContent, /Next Ictx:/);
    assert.equal(all(output, 'tbody')[0].children.length, 50);
    const raw = result.view.prompt_blocks[0].rows[0].ccost;
    assert.ok(!output.textContent.includes(raw), 'raw cost never leaks into prompt cells');
    assert.ok(all(output, 'a').some(link => link.href === '#/sessions/root-0000'));
    assert.equal(all(output, 'tfoot')[0].children[0].children[1].textContent, result.view.prompt_blocks[0].display.total_ccost);
  } else {
     const metrics = ['Prompts', 'Calls', 'Tokens', 'Input %', 'Cached input %',
       'Cache write %', 'Output %', 'Total CCost ↓'];
     assert.deepEqual(all(output, 'th').map(node => node.textContent), ['Model', ...metrics, 'Publisher', ...metrics]);
     const mix = result.view.model_token_mix[0].mix;
     assert.deepEqual(all(output, 'tbody')[0].children[0].children.slice(3).map(cell => cell.textContent),
        ['total_tokens', ...['input', 'cache', 'write', 'output'].map(key => key + '_share'), 'total_cost'].map(key => mix.display['mix_' + key]));
     assert.ok(output.textContent.indexOf('Total Token Mix') < output.textContent.indexOf('Token Mix % by model'));
     assert.ok(output.textContent.indexOf('Token Mix % by model') < output.textContent.indexOf('Token Mix % by publisher'));
     assert.doesNotMatch(output.textContent, /Snapshot|Reading this report|Sample and price coverage|Token category order|\?/);
     assert.equal(all(output, 'table').length, 2);
     assert.equal(all(output, 'input').length, 0);
    if (result.view.publisher_token_mix.length) {
      const publisher = result.view.publisher_token_mix[0];
      assert.equal(all(output, 'tbody')[1].children[0].children[0].textContent, publisher.publisher);
      assert.deepEqual(all(output, 'tbody')[1].children[0].children.slice(3).map(cell => cell.textContent),
          ['total_tokens', ...['input', 'cache', 'write', 'output'].map(key => key + '_share'), 'total_cost'].map(key => publisher.mix.display['mix_' + key]));
    }
  }
  const credits = output.textContent, tables = all(output, 'table'), rows = all(output, 'tr');
  vm.runInContext('ReportView.setUnit("usd", output)', context);
  assert.notEqual(output.textContent, credits);
  assert.deepEqual(all(output, 'table'), tables, 'unit change keeps table identity');
  assert.deepEqual(all(output, 'tr'), rows, 'unit change keeps ordering and row identity');
  if (kind === 'session') {
    const block = result.view.prompt_blocks[0];
    assert.equal(all(output, 'tfoot')[0].children[0].children[1].textContent, block.display_units.usd.total_ccost);
  } else {
    const mix = result.view.model_token_mix[0].mix;
    assert.deepEqual(all(output, 'tbody')[0].children[0].children.slice(3).map(cell => cell.textContent),
       ['total_tokens', ...['input', 'cache', 'write', 'output'].map(key => key + '_share'), 'total_cost'].map(key => mix.display_units?.usd?.['mix_' + key] ?? mix.display['mix_' + key]));
  }
  vm.runInContext('ReportView.setUnit("credits", output)', context);
  assert.equal(output.textContent, credits, 'reversible without jobs, repricing or replacing DOM');
}
console.log('PASS shared session clocks/context, bounded rows/full totals, CLI historical mix columns');

// A CLI/report USD default never leaks into the independent Web default.
const freshOutput = new Node('main');
const fresh = vm.createContext({document: {createElement: tag => new Node(tag), createElementNS: (_, tag) => new Node(tag)}, output: freshOutput,
  result: {...input.session, view: {...input.session.view, ccost_display_unit: 'usd'}}, Date});
require('../fixtures/web_help_vm.cjs')(vm, fresh);
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), fresh);
vm.runInContext('ReportView.render(output, result, {pages: {}, section: "sessions"})', fresh);
assert.equal(all(freshOutput, 'tfoot')[0].children[0].children[1].textContent,
   input.session.view.prompt_blocks[0].display.total_ccost);
vm.runInContext('ReportView.setUnit("usd", output)', fresh);
assert.equal(all(freshOutput, 'tfoot')[0].children[0].children[1].textContent,
   input.session.view.prompt_blocks[0].display_units.usd.total_ccost);

// Identical rounded labels, very large adjacent integers and partial/unknown volumes.
const sorted = JSON.parse(JSON.stringify(input['token-mix']));
const base = sorted.view.model_token_mix[0];
sorted.view.model_token_mix = [
  ['larger', '9007199254740993', '9007199.3B'],
  ['unknown', null, 'N/A'],
  ['smaller', '9007199254740992', '9007199.3B'],
  ['partial', '999999', '?1M']
].map(([model, raw, label]) => ({...base, model, mix: {...base.mix,
   total_tokens: null, known_total_tokens: raw, display: {...base.mix.display, mix_total_tokens: label.replace('?', 'Partial ')}}}));
context.result = sorted;
vm.runInContext('ReportView.render(output, result, {pages: {}, section: "token-mix"})', context);
const header = all(output, 'th')[3].children[0];
header.events.click();
const names = () => all(output, 'tbody')[0].children.map(row => row.children[0].textContent);
assert.deepEqual(names(), ['partial', 'smaller', 'larger', 'unknown']);
header.events.click();
assert.deepEqual(names(), ['larger', 'smaller', 'partial', 'unknown']);
assert.ok(all(output, 'div').some(node => node.className === 'token-mix-pan' && node.tabIndex === 0));
console.log('PASS raw exact token sorting, partial/unknown volumes, keyboard-scrollable history tables');

context.result = input['token-mix'];
assert.equal(vm.runInContext('TokenMixView.valid(result)', context), true);
for (const mutate of [
  value => { value.view.publisher_token_mix = null; },
  value => { value.view.token_mix.exact_total_tokens = 'NaN'; },
  value => { value.view.model_token_mix[0].mix.exact_totals[0] = 'not an integer'; },
  value => { value.view.token_mix.costs = ['0']; },
  value => { delete value.view.token_mix.display.mix_total_cost; },
  value => { value.view.token_mix_period={period:'today',start_ms:2,end_ms:1}; },
  value => { delete value.source; }
]) {
  context.result = JSON.parse(JSON.stringify(input['token-mix'])); mutate(context.result);
  assert.equal(vm.runInContext('TokenMixView.valid(result)', context), false, 'reject whole malformed refresh before commit');
}
console.log('PASS complete payload validation rejects malformed overview or either table');

// Token Mix alone suppresses noisy qualifiers; wire facts and CLI tokens remain unchanged.
const partial = JSON.parse(JSON.stringify(input['token-mix']));
const partialMix = mix => ({...mix, cost_complete: false, priced_requests: 1, request_count: 3,
  exact_total_tokens: null, known_total_tokens: '842000',
  display: {...mix.display, mix_total_tokens: 'Partial 842K', mix_input_cost: 'Partial 12.34'},
  display_units: {usd: {mix_input_cost: 'Partial $0.12'}}});
partial.view.token_mix = partialMix(partial.view.token_mix);
for (const key of ['model_token_mix', 'publisher_token_mix'])
  partial.view[key] = partial.view[key].map(row => ({...row, mix: partialMix(row.mix)}));
partial.view.timezone_id = 'Europe/Stockholm'; partial.observed_at_ms = Date.parse('2026-03-29T01:30Z');
partial.view.token_mix_period = {period:'today',start_ms:Date.parse('2026-03-28T23:00Z'),end_ms:partial.observed_at_ms};
context.result = partial;
vm.runInContext('globalThis.mixView = new TokenMixView.View(); mixView.update(result); mixView.attach(output)', context);
const title = all(output, 'h2')[0];
assert.doesNotMatch(output.textContent, /Partial|\?|Incomplete token telemetry/);
assert.ok(output.textContent.includes('842K'));
assert.equal(context.mixView.status.hidden, true);
assert.match(helpText(title), /842,000 known recorded tokens for the selected period\n2026-03-29 00:00:00.000 GMT\+01:00 – 2026-03-29 03:30:00.000 GMT\+02:00/);
assert.doesNotMatch(helpText(title), /CLI|Observed|Partial pricing|CCost|Deleted/);
vm.runInContext('ReportView.setUnit("usd", output)', context);
assert.ok(output.textContent.includes('$0.12')); assert.doesNotMatch(output.textContent, /Partial|\?/);
assert.equal(partial.view.token_mix.display.mix_total_tokens, 'Partial 842K', 'not a canonical token rewrite');
context.result = input['token-mix'];
vm.runInContext('mixView.update(result)', context);
assert.doesNotMatch(helpText(title), /Partial pricing:/, 'complete aggregate omits partial-pricing paragraph');
context.result = {...partial, view: {...partial.view, token_mix: {...partial.view.token_mix, request_count: 0}, model_token_mix: [], publisher_token_mix: []}};
vm.runInContext('mixView.update(result)', context);
assert.match(output.textContent, /No available historical usage/);
assert.doesNotMatch(helpText(title), /Partial pricing:/, 'empty usage never claims partial costs');
console.log('PASS quiet Token Mix both units/tables, partial-pricing and telemetry help, live refresh and empty history');
