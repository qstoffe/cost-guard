// Pure JavaScript VM, not browser/UI automation. No package dependencies.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const turns = async () => { for (let n = 0; n < 12; n++) await Promise.resolve(); };
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ''; this.dataset = {}; this.events = {}; this.value = ''; this.scrollTop = 0; this.style = {setProperty() {}}; }
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
  setAttribute(name, value) { this[name] = value; }
  addEventListener(kind, fn) { this.events[kind] = fn; }
}
function lifecycle(context, input) {
  vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8'), context);
  vm.runInContext(fs.readFileSync('src/web/assets/watch.js', 'utf8'), context);
  context.parent = new Node('div');
  context.state = {connection: 'Live connected.'};
  let frozenDuration;
  for (const [index, view] of input.lifecycle.entries()) {
    context.example = {state: 'running', view};
    vm.runInContext('ReportView.renderLive(parent, example, state)', context);
    const watch = context.state.watch;
    const card = [...watch.cards.values()].find(card => card.value.session_id === input.stopped);
    assert.ok(card);
    const row = card.body.children[0];
    if (!index) {
      assert.equal(row.className, 'watch-running');
      assert.match(row['aria-label'], /Running/);
    } else {
      assert.notEqual(row.className, 'watch-running');
      assert.ok(!row['aria-label'].includes('Running'));
      if (index === 1) {
        assert.equal(card.running.hidden, true);
        assert.equal(card.background.hidden, true);
      } else assert.equal(card.activity.hidden, true);
      const duration = row.children[1].textContent;
      if (index === 1) frozenDuration = duration;
      else assert.equal(duration, frozenDuration);
      assert.equal(watch.active.children.includes(card.root), index === 1);
      assert.equal(watch.history.children.includes(card.root), index === 2);
    }
  }
  context.state = {connection: 'Live connected.'};
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  const reloaded = [...context.state.watch.cards.values()].find(card => card.value.session_id === input.stopped);
  assert.notEqual(reloaded.body.children[0].className, 'watch-running');
  assert.equal(reloaded.body.children[0].children[1].textContent, frozenDuration);
  console.log('web lifecycle passed');
}
async function tokenMix(context, frames) {
  context.parent = new Node('div'); context.state = {connection:'Live connected.'};
  let snapshot = {instance_id:'mix', sequence:0, values:{live:frames[0]}}, stream;
  context.api = async () => JSON.parse(JSON.stringify(snapshot));
  context.update = live => { context.current = live; vm.runInContext('ReportView.renderLive(parent, current, state)', context); };
  context.status = message => { context.state.connection = message; };
  context.sourceFactory = () => (stream = {listeners:{}, addEventListener(kind, fn) { this.listeners[kind] = fn; }, close() {},
    emit(number, frame) { this.listeners.live({lastEventId:'mix:' + number, data:JSON.stringify(frame)}); }});
  for (const name of ['render', 'watch', 'live']) vm.runInContext(fs.readFileSync('src/web/assets/' + name + '.js', 'utf8'), context);
  vm.runInContext('LiveConnection.connect(api, update, status, sourceFactory)', context);
  await turns(); stream.onopen(); await turns();
  const card = [...context.state.watch.cards.values()].at(-1), row = card.body.children[0];
  const mix = () => row.children[7].textContent;
  const cost = () => row.children[5].textContent;
  const costText = prompt => {
    const d = prompt.display;
    return !d.ccost || d.ccost === 'N/A' ? d.ccost : `${d.ccost} (${d.incoming_context_ccost} + ${d.extra_ccost})`;
  };
  assert.equal(mix(), '100/0/0/0');
  assert.equal(cost(), costText(frames[0].view.active_cards.at(-1).rows[0].prompt));
  for (let index=1; index<frames.length; index++) {
    snapshot = {instance_id:'mix', sequence:index, values:{live:frames[index]}};
    stream.emit(index, frames[index]);
    assert.equal(mix(), ['100/0/0/0','25/75/0/0','20/60/0/20','running','25/75/0/0','N/A'][index]);
    assert.equal(card.body.children[0], row, 'same keyed row updates without reload');
    const acceptedCost = costText(frames[index].view.active_cards.at(-1).rows[0].prompt);
    assert.equal(cost(), acceptedCost);
    stream.emit(index-1, frames[0]);
    assert.equal(cost(), acceptedCost, 'stale event cannot roll back cost components');
    assert.notEqual(mix(), '100/0/0/0', 'stale event cannot roll back usage');
  }
  stream.onerror();
  assert.match(context.state.connection, /interrupted/);
  assert.equal(mix(), 'N/A', 'disconnect retains last observation, not invented current usage');
  stream.onopen(); await turns();
  assert.equal(mix(), 'N/A');
  snapshot.sequence = 10;
  stream.emit(10, frames[0]); await turns();
  assert.equal(mix(), 'N/A', 'gap accepts HTTP snapshot, not unverified event body');
  console.log('web token mix SSE passed');
}
async function main() {
  const streams = [], rendered = [], statuses = [];
  let selected = null;
  let snapshot = {instance_id: 'instance', sequence: 0, values: {live: input}};
  let calls = 0;
  const document = {createElement: tag => new Node(tag), activeElement: null,
    createElementNS: (namespaceURI, tag) => Object.assign(new Node(tag), {namespaceURI})};
  const context = vm.createContext({document, console, setTimeout: () => 1, clearTimeout: () => {},
    window: {getSelection: () => ({isCollapsed: !selected, anchorNode: selected, focusNode: selected}),
      addEventListener() {},matchMedia: () => ({addEventListener() {},removeEventListener() {}})},
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
  if (input.lifecycle) { lifecycle(context, input); return; }
  if (input.tokenMixFrames) { await tokenMix(context, input.tokenMixFrames); return; }
  vm.runInContext(fs.readFileSync('src/web/assets/live.js', 'utf8'), context);
  vm.runInContext('LiveConnection.connect(api, update, status, sourceFactory)', context);
  await turns();
  assert.equal(streams.length, 1);
  const stream = streams[0];
  stream.onopen(); await turns();
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
  assert.match(statuses.at(-1), /RECONNECTING.*live stream interrupted/);
  assert.match(statuses.at(-1), /not live/);
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
  assert.match(context.parent.textContent, /Earlier Prompts/);
  assert.ok(!/Session Total|provisional/.test(context.parent.textContent));
  assert.ok(!/Run CCost|not full session|Observation details|Unaccounted usage|Watch accounts/.test(context.parent.textContent));
  assert.ok(context.parent.textContent.includes(input.view.active_cards[0].title));
  function contains(node, tag) { return node.tag === tag || node.children.some(c => contains(c, tag)); }
  assert.equal(contains(context.parent, 'script'), false);
  assert.equal(contains(context.parent, 'img'), false);
  const watch = context.state.watch;
  const firstCard = [...watch.cards.values()][0];
  const promptRows = () => firstCard.body.children;
  const firstRow = promptRows()[0];
  const firstCell = firstRow.children[0];
  const costText = (prompt, unit) => {
    const d = {...prompt.display, ...prompt.display_units?.[unit]};
    return !d.ccost || d.ccost === 'N/A' ? d.ccost : `${d.ccost} (${d.incoming_context_ccost} + ${d.extra_ccost})`;
  };
  const canonical = input.view.active_cards[0].rows.map(r => costText(r.prompt, 'credits'));
  assert.deepEqual(promptRows().map(r => r.children[5].textContent), canonical);
  const credits = context.parent.textContent, beforeUnits = calls;
  vm.runInContext('ReportView.setUnit("usd", parent)', context);
  assert.deepEqual(promptRows().map(r => r.children[5].textContent), input.view.active_cards[0].rows.map(r =>
    costText(r.prompt, 'usd')));
  assert.equal(promptRows()[0], firstRow);
  assert.equal(firstRow.children[0], firstCell);
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.ok(context.parent.textContent.includes('$'), 'new publication retains unit');
  vm.runInContext('ReportView.setUnit("credits", parent)', context);
  assert.equal(context.parent.textContent, credits);
  assert.equal(calls, beforeUnits, 'switching is not acquisition');
  assert.ok(!firstCard.body.textContent.includes('Running at snapshot'));
  assert.deepEqual(firstCard.root.querySelectorAll('th').map(node => node.children[0].textContent),
    ['Started', 'Duration', 'Prompt', 'Model', 'Effort', 'CCost (I + E)', 'Calls', 'Token Mix %', 'Ictx', 'Δ Ctx']);
  assert.match(firstCard.contextLabel.title, /Not the prompt Ictx or summed usage/);
  for (const header of firstCard.root.querySelectorAll('th')) {
    const [button, help] = header.children;
    assert.equal(button['aria-describedby'], help.id);
    assert.equal(button.title, help.textContent);
    assert.ok(button.events.focus && button.events.click && button.events.pointerenter);
  }
  assert.match(firstRow.children[0].textContent, /^\d\d:\d\d$/);
  assert.equal(firstRow.children[2].children[0].children[0].textContent, '#' + input.view.active_cards[0].rows[0].prompt.prompt_number);
  assert.equal(firstRow.children[7].textContent, input.view.active_cards[0].rows[0].prompt.display.token_mix_percent);
  assert.equal(firstRow.children[8].textContent, input.view.active_cards[0].rows[0].prompt.display.incoming_context_tokens);
  assert.equal(firstRow.children[9].textContent, input.view.active_cards[0].rows[0].live_context.display.watch_delta_context_tokens);
  assert.equal(watch.earlier.open || false, false);
  // Independent keyed cards, no filter/pager or global cap.
  const multiple = JSON.parse(JSON.stringify(input));
  const other = JSON.parse(JSON.stringify(input.view.active_cards[0]));
  other.session_id = 'other-session'; other.title = 'Other session';
  other.rows.at(-1).prompt.aborted = true; other.rows.at(-1).prompt.in_progress = false;
  other.rows.at(-1).prompt.abort_reason = 'quota_limit';
  multiple.view.active_cards.push(other);
  context.example = multiple;
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(context.parent.querySelectorAll('table').length, 2);
  assert.equal(promptRows()[0], firstRow); assert.equal(firstRow.children[0], firstCell);
  assert.ok(context.parent.querySelectorAll('tr').some(row => /Aborted · quota limit/.test(row['aria-label'])));
  assert.equal(context.parent.querySelectorAll('input').length, 0);
  assert.equal(context.parent.querySelectorAll('button').length, 20, 'only column-help controls');
  // A running update cannot destroy selected text; latest data applies on a later tick.
  selected = firstCell;
  multiple.view.active_cards[0].rows[0].prompt.preview = 'Latest running update';
  multiple.view.active_cards[0].rows[0].prompt.display.ccost = '123';
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(firstRow.children[0], firstCell);
  assert.ok(!firstCard.body.textContent.includes('Latest running update'));
  selected = null;
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.match(firstCard.body.textContent, /Latest running update/);
  firstCard.tools.node.open = true;
  firstCard.skills.node.open = true;
  watch.earlier.open = true;
  watch.history.scrollTop = 93;
  document.activeElement = firstCard.tools.summary;
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(document.activeElement, firstCard.tools.summary);
  assert.equal(firstCard.tools.node.open, true); assert.equal(firstCard.skills.node.open, true);
  assert.equal(watch.earlier.open, true); assert.equal(watch.history.scrollTop, 93);
  document.activeElement = null;
  for (const count of [0, 1, 5, 7]) {
    const tool = {counts: Array.from({length: count}, (_, n) => ['tool-' + n, n + 1]), skills: Array.from({length: count}, (_, n) => ({skill_id: 'skill-' + n, failed_count: n === 0 ? 1 : 0}))};
    multiple.view.active_cards[0].rows.at(-1).tool = tool;
    vm.runInContext('ReportView.renderLive(parent, example, state)', context);
    assert.equal(firstCard.tools.list.children.length, count || 1);
    assert.equal(firstCard.skills.list.children.length, count || 1);
    assert.match(firstCard.skills.summary.textContent, new RegExp(count + ' skills'));
    if (count === 7) { assert.match(firstCard.tools.summary.textContent, /3 × other/); assert.match(firstCard.skills.summary.textContent, /2 other/); }
  }
  multiple.view.active_cards = Array.from({length: 100}, (_, n) => ({...other, session_id: 'session-' + n}));
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(watch.active.children.length, 100);
  const anchored = watch.active.children[0];
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(watch.active.children[0], anchored);
  context.state.connection = 'Live offline. Last observation retained; reconnecting.';
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.match(watch.empty.textContent, /last observation retained/);
  context.state.connection = 'source_changed: host stopped. Run the launcher again.';
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.match(watch.empty.textContent, /Live connection interrupted/);
  assert.doesNotMatch(watch.empty.textContent, /Source unavailable/);
  assert.equal(watch.active.children[0], anchored);
  multiple.view.active_cards = []; context.state.connection = 'Live connected.';
  vm.runInContext('ReportView.renderLive(parent, example, state)', context);
  assert.equal(watch.active.children.length, 0);
  assert.match(watch.empty.textContent, /No running prompts/);
  assert.match(watch.history.textContent, /No earlier prompts/);
  console.log('web live passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
