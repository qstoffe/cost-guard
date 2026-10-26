// Pure JavaScript VM, not browser/UI automation. No package dependencies.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const turns = async () => { for (let n = 0; n < 12; n++) await Promise.resolve(); };
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(''); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; this.text = ''; }
  setAttribute() {}
  addEventListener() {}
}
async function main() {
  const streams = [], rendered = [], statuses = [];
  let snapshot = {instance_id: 'instance', sequence: 0, values: {live: input}};
  let calls = 0;
  const context = vm.createContext({document: {createElement: tag => new Node(tag)}, console,
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
  vm.runInContext('ReportView.renderLive(parent, example, {pages: {}})', context);
  assert.match(context.parent.textContent, /Web live engine start/);
  assert.match(context.parent.textContent, /Live prompts/);
  assert.match(context.parent.textContent, /~Ictx/);
  assert.ok(context.parent.textContent.includes(input.view.today_label + ' CCost'));
  assert.match(context.parent.textContent, /not full session/);
  assert.ok(context.parent.textContent.includes(input.view.rows[0].session_title));
  function contains(node, tag) { return node.tag === tag || node.children.some(c => contains(c, tag)); }
  assert.equal(contains(context.parent, 'script'), false);
  assert.equal(contains(context.parent, 'img'), false);
  console.log('web live passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
