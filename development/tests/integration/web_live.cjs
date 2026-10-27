// Pure JavaScript VM, not browser/UI automation. No package dependencies.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const turns = async () => { for (let n = 0; n < 12; n++) await Promise.resolve(); };
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ''; this.dataset = {}; this.events = {}; this.value = ''; this.scrollTop = 0; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(''); }
  get firstElementChild() { return this.children[0]; }
  get isConnected() { return Boolean(this.parentNode); }
  append(...children) { for (const child of children) { child.remove(); this.children.push(child); child.parentNode = this; } }
  replaceChildren(...children) { for (const child of this.children) child.parentNode = null; this.children = []; this.text = ''; this.append(...children); }
  insertBefore(child, before) { child.remove(); this.children.splice(before ? this.children.indexOf(before) : this.children.length, 0, child); child.parentNode = this; }
  remove() { if (this.parentNode) { this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; } }
  contains(child) { return child === this || this.children.some(c => c.contains(child)); }
  querySelectorAll(tag) { return this.children.flatMap(c => [...(c.tag === tag ? [c] : []), ...c.querySelectorAll(tag)]); }
  getBoundingClientRect() { return {top: 100}; }
  setAttribute() {}
  addEventListener(kind, fn) { this.events[kind] = fn; }
}
async function main() {
  const streams = [], rendered = [], statuses = [];
  let selected = null;
  let snapshot = {instance_id: 'instance', sequence: 0, values: {live: input}};
  let calls = 0;
  const document = {createElement: tag => new Node(tag), activeElement: null};
  const context = vm.createContext({document, console,
    window: {getSelection: () => ({isCollapsed: !selected, anchorNode: selected, focusNode: selected})},
    api: async path => { assert.equal(path, '/api/live'); calls++; return JSON.parse(JSON.stringify(snapshot)); },
    update: live => rendered.push(live), status: text => statuses.push(text),
    sourceFactory: url => {
      assert.equal(url, '/api/events');
      const source = {listeners: {}, closed: false, close() { this.closed = true; },
        addEventListener(kind, fn) { this.listeners[kind] = fn; },
        emit(kind, number, data, instance = 'instance') {
          this.listeners[kind]({lastEventId: instance + ':' + number, data: JSON.stringify(data)});
        }};
      streams.push(source); return source;
    }});
  vm.runInContext(fs.readFileSync('src/web/assets/live.js', 'utf8'), context);
  vm.runInContext('LiveConnection.connect(api, update, status, sourceFactory)', context);
  await turns();
  assert.equal(streams.length, 1);
  const stream = streams[0];
  stream.emit('live', 1, input);
  const count = rendered.length;
  stream.emit('live', 1, {view: null});
  stream.emit('live', 0, {view: null});
  assert.equal(rendered.length, count, 'duplicates/older updates cannot replace state');
  snapshot = {...snapshot, sequence: 5};
  stream.emit('live', 5, {view: null});
  await turns();
  assert.ok(calls >= 2, 'gap requires authoritative HTTP snapshot');
  assert.ok(rendered.at(-1).view, 'gap event is not invented continuation');
  stream.onerror();
  assert.match(statuses.at(-1), /offline/);
  assert.equal(streams.length, 1, 'offline/reconnect cannot create duplicate stream owners');
  stream.emit('live', 6, {view: null}, 'old-instance');
  assert.equal(stream.closed, true);
  assert.match(statuses.at(-1), /identity changed/);
  // A received terminal event ends retry even when the source changed.
  vm.runInContext('LiveConnection.connect(api, update, status, sourceFactory)', context);
  await turns();
  streams[1].emit('terminal', 9, {reason: 'source_changed'});
  assert.equal(streams[1].closed, true);
  assert.match(statuses.at(-1), /Run the launcher again/);
  // Canonical projection renders literal hostile text and Watch, not month, scopes.
  context.example = input;
  context.parent = new Node('div');
  vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
  vm.runInContext(fs.readFileSync('src/web/assets/watch.js', 'utf8'), context);
  vm.runInContext("globalThis.state = {pages: {}, connection: 'Live connected.'}; ReportView.renderLive(parent, example, state)", context);
  assert.match(context.parent.textContent, /Web live engine start/);
  assert.match(context.parent.textContent, /Watch prompts/);
  assert.match(context.parent.textContent, /Next Ictx/);
  assert.ok(context.parent.textContent.includes(input.view.today_label + ' CCost'));
  assert.match(context.parent.textContent, /not full session/);
  assert.ok(context.parent.textContent.includes(input.view.rows[0].session_title));
  function contains(node, tag) { return node.tag === tag || node.children.some(c => contains(c, tag)); }
  assert.equal(contains(context.parent, 'script'), false);
  assert.equal(contains(context.parent, 'img'), false);
  const watch = context.state.watch;
  const promptRows = () => watch.body.children.filter(r => r.dataset.id?.startsWith('['));
  const firstRow = promptRows()[0], filter = watch.filter, next = watch.next;
  const firstCell = firstRow.children[0];
  const canonical = input.view.rows.map(r => r.prompt.display.ccost);
  assert.deepEqual(promptRows().map(r => r.children[2].textContent), canonical);
  const normalized = value => value.replace(/\s+/g, ' ').trim();
  assert.deepEqual(promptRows().map(r => r.children.slice(2, 6).map(c => normalized(c.textContent))),
    input.cli_cells.map(row => row.map(normalized)), 'same projection has CLI-equivalent cost/calls/running duration/context');
  assert.ok(!watch.body.textContent.includes('Running at snapshot'));
  // Multiple sessions, even with quotas, share exactly one primary table and one pager.
  const multiple = JSON.parse(JSON.stringify(input));
  const other = JSON.parse(JSON.stringify(input.view.rows[0]));
  other.session_id = 'other-session'; other.session_title = 'Other session';
  other.prompt.aborted = true; other.prompt.in_progress = false;
  multiple.view.rows.push(other);
  multiple.view.session_subtotals.push({...multiple.view.session_subtotals[0], session_id: other.session_id});
  context.example = multiple;
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(context.parent.querySelectorAll('table').length, 1);
  assert.equal(watch.body.children.filter(r => r.className === 'watch-session').length, 2);
  assert.equal(promptRows()[0], firstRow); assert.equal(firstRow.children[0], firstCell);
  assert.equal(watch.filter, filter); assert.equal(watch.next, next);
  assert.ok(watch.body.textContent.includes('Aborted'));
  // A running update cannot destroy selected text; latest data applies on a later tick.
  selected = firstCell;
  multiple.view.rows[0].prompt.preview = 'Latest running update';
  multiple.view.rows[0].prompt.display.ccost = '123';
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(firstRow.children[0], firstCell);
  assert.ok(!watch.body.textContent.includes('Latest running update'));
  selected = null;
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.match(watch.body.textContent, /Latest running update/);
  document.activeElement = filter;
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(document.activeElement, filter);
  filter.value = 'Other session'; filter.events.input();
  assert.equal(promptRows().length, 1);
  assert.match(watch.totals.textContent, /Run CCost/);
  filter.value = ''; filter.events.input();
  // Canonical order and bounded 50-row pages survive repeated publications.
  multiple.view.rows = Array.from({length: 125}, (_, n) => ({...other,
    prompt: {...other.prompt, event_id: 'event-' + n, prompt_number: n}}));
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(promptRows().length, 50);
  next.events.click(); assert.equal(watch.page, 1);
  const anchored = promptRows()[0];
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(watch.page, 1); assert.equal(promptRows()[0], anchored);
  context.state.connection = 'Live offline. Last observation retained; reconnecting.';
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.match(watch.status.textContent, /Stale \/ retained/);
  assert.ok(!watch.status.textContent.includes('Updating'));
  context.state.connection = 'source_changed: host stopped. Run the launcher again.';
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.match(watch.status.textContent, /host stopped/);
  assert.equal(promptRows()[0], anchored);
  console.log('web live passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
