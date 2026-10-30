// Deterministic DOM assertions, not real-browser or visual evidence.
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
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = new Node('main');
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, output, Date});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
for (const [kind, result] of Object.entries(input)) {
  context.result = result;
  vm.runInContext('ReportView.render(output, result, {pages: {}, section: "reports"})', context);
  assert.ok(output.textContent.includes('I = Input; C = Cached input; W = Cache write; O = Output'));
  assert.ok(!/\b(?:Cache|Write):/.test(output.textContent));
  assert.ok(!all(output, 'th').some(n => ['Cache', 'Write', 'I/C/W/O %'].includes(n.textContent)));
  for (const node of all(output, 'th')) assert.equal(node.scope, 'col');
  if (kind === 'date') {
    assert.ok(!output.textContent.includes(String(result.scope.start_ms)), 'no epoch range prose');
    assert.match(output.textContent, /2026-10-26:2026-10-27.*Europe\/Stockholm/);
    assert.match(output.textContent, /Next Ictx:/);
    assert.equal(all(output, 'tbody')[0].children.length, 50);
    const raw = result.view.prompt_blocks[0].rows[0].ccost;
    assert.ok(!output.textContent.includes(raw), 'raw cost never leaks into prompt cells');
    assert.ok(all(output, 'a').some(link => link.href === '#/sessions/root-0000'));
    assert.equal(all(output, 'tfoot')[0].children[0].children[1].textContent, result.view.prompt_blocks[0].display.total_ccost);
  } else {
    assert.deepEqual(all(output, 'th').map(node => node.textContent),
       ['Model', 'Prompts', 'Calls', 'Tokens', 'Input', 'Cached input', 'Cache write', 'Output', 'CCost',
        'Publisher', 'Prompts', 'Calls', 'Tokens', 'Input', 'Cached input', 'Cache write', 'Output', 'CCost']);
    const mix = result.view.model_token_mix[0].mix;
    assert.deepEqual(all(output, 'tbody')[0].children[0].children.slice(3).map(cell => cell.textContent),
       ['total_tokens', 'input', 'cache', 'write', 'output', 'total_cost'].map(key => mix.display[key]));
    assert.ok(output.textContent.indexOf('Total Token Mix') < output.textContent.indexOf('Historical models'));
    assert.ok(output.textContent.indexOf('Historical models') < output.textContent.indexOf('Historical publishers'));
    if (result.view.publisher_token_mix.length) {
      const publisher = result.view.publisher_token_mix[0];
      assert.equal(all(output, 'tbody')[1].children[0].children[0].textContent, publisher.publisher);
      assert.deepEqual(all(output, 'tbody')[1].children[0].children.slice(3).map(cell => cell.textContent),
         ['total_tokens', 'input', 'cache', 'write', 'output', 'total_cost'].map(key => publisher.mix.display[key]));
    }
  }
  const credits = output.textContent, tables = all(output, 'table'), rows = all(output, 'tr');
  vm.runInContext('ReportView.setUnit("usd", output)', context);
  assert.notEqual(output.textContent, credits);
  assert.deepEqual(all(output, 'table'), tables, 'unit change keeps table identity');
  assert.deepEqual(all(output, 'tr'), rows, 'unit change keeps ordering and row identity');
  if (kind === 'date') {
    const block = result.view.prompt_blocks[0];
    assert.equal(all(output, 'tfoot')[0].children[0].children[1].textContent, block.display_units.usd.total_ccost);
    assert.ok(output.textContent.includes('CCost for range: ' + result.view.range_comparison.display_units.usd.known_ccost));
  } else {
    const mix = result.view.model_token_mix[0].mix;
    assert.deepEqual(all(output, 'tbody')[0].children[0].children.slice(3).map(cell => cell.textContent),
      ['total_tokens', 'input', 'cache', 'write', 'output', 'total_cost'].map(key => mix.display_units?.usd?.[key] ?? mix.display[key]));
  }
  vm.runInContext('ReportView.setUnit("credits", output)', context);
  assert.equal(output.textContent, credits, 'reversible without jobs, repricing or replacing DOM');
}
console.log('PASS date scope, configured prompt clocks/context, bounded rows/full totals, CLI historical mix columns');

// Independent page contexts start from configuration, not another tab's choice.
const freshOutput = new Node('main');
const fresh = vm.createContext({document: {createElement: tag => new Node(tag)}, output: freshOutput,
  result: {...input.date, view: {...input.date.view, ccost_display_unit: 'usd'}}, Date});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), fresh);
vm.runInContext('ReportView.render(output, result, {pages: {}, section: "reports"})', fresh);
assert.equal(all(freshOutput, 'tfoot')[0].children[0].children[1].textContent,
  input.date.view.prompt_blocks[0].display_units.usd.total_ccost);

// Identical rounded labels, very large adjacent integers and partial/unknown volumes.
const sorted = JSON.parse(JSON.stringify(input['token-mix']));
const base = sorted.view.model_token_mix[0];
sorted.view.model_token_mix = [
  ['larger', '9007199254740993', '9007199.3B'],
  ['unknown', null, 'N/A'],
  ['smaller', '9007199254740992', '9007199.3B'],
  ['partial', '999999', '?1M']
].map(([model, raw, label]) => ({...base, model, mix: {...base.mix,
  total_tokens: null, known_total_tokens: raw, display: {...base.mix.display, total_tokens: label}}}));
context.result = sorted;
vm.runInContext('ReportView.render(output, result, {pages: {}, section: "reports"})', context);
const header = all(output, 'th')[3].children[0];
header.events.click();
const names = () => all(output, 'tbody')[0].children.map(row => row.children[0].textContent);
assert.deepEqual(names(), ['partial', 'smaller', 'larger', 'unknown']);
header.events.click();
assert.deepEqual(names(), ['larger', 'smaller', 'partial', 'unknown']);
assert.ok(all(output, 'div').some(node => node.className === 'table-scroll' && node.tabIndex === 0));
console.log('PASS raw exact token sorting, partial/unknown volumes, keyboard-scrollable history tables');
