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
    assert.deepEqual(all(output, 'th').map(node => node.textContent), ['Model', 'Prompts', 'Calls', 'Input', 'Cache', 'Write', 'Output', 'CCost']);
    const mix = result.view.model_token_mix[0].mix;
    assert.deepEqual(all(output, 'tbody')[0].children[0].children.slice(3).map(cell => cell.textContent),
      ['input', 'cache', 'write', 'output', 'total_cost'].map(key => mix.display[key]));
    assert.ok(output.textContent.indexOf('Total Token Mix') < output.textContent.indexOf('Historical models'));
  }
}
console.log('PASS date scope, configured prompt clocks/context, bounded rows/full totals, CLI historical mix columns');
