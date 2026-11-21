// Deterministic response-order and retained selection checks against the shipped view.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Node {
  constructor(tag, text = '', className) {
    Object.assign(this, {tag, textContent: text, className, children: [], attributes: {}, events: {}, style: {},
      clientWidth: 480, scrollLeft: 0, offsetWidth: 200, offsetHeight: 100,
      classList: {toggle() {}}, style: {setProperty() {}}});
  }
  append(...nodes) { for (const node of nodes) this.insertBefore(typeof node === 'string' ? new Node('#text', node) : node, null); }
  insertBefore(node, before) {
    node.remove();
    this.children.splice(before ? this.children.indexOf(before) : this.children.length, 0, node);
    node.parent = this;
  }
  remove() {
    if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1);
    this.parent = null;
  }
  replaceChildren(...nodes) {
    for (const child of [...this.children]) child.remove();
    this.append(...nodes);
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(name, fn) { this.events[name] = fn; }
  hidePopover() {}
  matches() { return false; }
  getBoundingClientRect() { return {left: 0, top: 0, right: 480, bottom: 220}; }
}

const context = vm.createContext({
  document: {documentElement: {lang: 'en'}, addEventListener() {}, createElementNS: (_, tag) => new Node(tag)},
  innerWidth: 480, innerHeight: 640,
  setTimeout() {}, clearTimeout() {},
  ReportView: {
    element: (...args) => new Node(...args),
    text: (el, value) => { el.textContent = value; },
    timestamp: ms => new Date(ms).toISOString().slice(0, 16).replace('T', ' '),
    compare: (a, b) => Number(a) - Number(b),
    display: item => item.display.amount
  }
});
vm.runInContext(fs.readFileSync('src/web/assets/account-timeline.js', 'utf8') +
  '; globalThis.View = AccountTimelineView.View;', context);

const point = {amount: '100', display: {credits: '100', usd: '$1.00'}};
const first = {id: '00000000', account: 'Account A',
  points: [point, null], total: point, peak: '100', ticks: [{amount: '0', display: {credits: '0', usd: '$0.00'}}, point]};
const second = {...first, id: '00000008', account: 'Account B'};
const start = Date.UTC(2026, 10, 1), day = 86_400_000;
const frame = (scope, revision, pending, series, initial = pending, acquiring = true, price = 'price') =>
  ({scope, revision, acquiring,
  view: {period: 'month', timezone_id: 'UTC', start_ms: start, end_ms: start + 2 * day,
    buckets: [[start, start + day], [start + day, start + 2 * day]], partial_buckets: [],
    pending_buckets: pending, initial_pending_buckets: initial, price_revision: price, series}});

async function check() {
  const calls = [];
  let demand = 0;
  const chart = new context.View((path, request) =>
    new Promise(resolve => calls.push({path, request, resolve})), () => demand++);
  chart.active(true);
  chart.setScope('old');
  const old = chart.refresh();
  chart.setScope('current');
  calls.at(-1).resolve(frame('old', 1, [0], [first, second]));
  await old;
  assert.equal(chart.view, undefined);

  const abandoned = chart.refresh();
  chart.select('today');
  chart.select('month');
  calls.at(-1).resolve(frame('current', 2, [0], [first, second]));
  await abandoned;
  assert.equal(chart.view, undefined, 'even a same-period reply from before a switch must be discarded');

  const pending = chart.refresh();
  calls.at(-1).resolve(frame('current', 3, [1], [first, second]));
  await pending;
  assert.equal(chart.shades.children.length, 1);
  assert.equal(chart.empty.hidden, true, 'a partial frame has only bucket-local loading');
  const rings = () => chart.layers.children.filter(node => node.attributes.class === 'account-timeline-ring').length;
  assert.equal(rings(), 1);
  const stalled = chart.refresh();
  calls.at(-1).resolve({scope: 'current', unchanged: true, acquiring: false});
  await stalled;
  assert.equal(rings(), 0);
  assert.equal(chart.shades.children.length, 1, 'stalled history remains distinguishable');
  assert.ok(chart.layers.children.some(node => node.attributes.class === 'account-timeline-hourglass'));
  chart.choose(1);
  assert.equal(chart.tipTitle.textContent, '2026-11-02 Monday');
  assert.equal(chart.tipState.textContent, '');
  assert.equal(chart.announce.textContent, '2026-11-02 Monday. Account A: —. Account B: —');
  assert.equal(chart.selectedLegend.children[0].children[2].textContent, '100');
  chart.inspect(null);
  assert.equal(chart.selectedLegend.children[0].children[2].textContent, '100', 'closing the tooltip never clears totals');
  chart.choose(1);
  const check = chart.entries.get(second.id).input;
  assert.equal(check.checked, true, 'every available account starts selected');
  check.checked = false;
  check.events.change();
  assert.equal(demand, 2, 'selection is frontend-only');
  assert.equal(chart.tipTitle.textContent, '2026-11-02 Monday', 'selection retains the inspected date');
  assert.equal(chart.layers.children.filter(node => node.attributes.class === 'account-timeline-bar').length, 1);
  assert.equal(chart.selectedLegend.children.length, 1);
  const originalInk = chart.colors.get(second.id);

  const settled = chart.refresh();
  assert.equal(calls.at(-1).request.revision, 3);
  calls.at(-1).resolve(frame('current', 4, [], [{...second, account: 'Renamed account'}, first]));
  await settled;
  assert.equal(chart.shades.children.length, 0);
  assert.equal(chart.tipTitle.textContent, '2026-11-02 Monday', 'a compatible update retains the inspected date');
  assert.equal(chart.tipState.textContent, '');
  assert.equal(chart.entries.get(second.id).input, check);
  assert.equal(chart.colors.get(second.id), originalInk);
  assert.equal(check.checked, false);
  check.checked = true;
  check.events.change();
  assert.match(chart.entries.get(second.id).name.textContent, /^Renamed account/);
  assert.match(chart.selectedLegend.children[0].children[1].textContent, /^Renamed account/);

  const provisional = chart.refresh();
  const estimated = {amount: '0.00001', display: {credits: '~<0.1', usd: '~<$0.01'}};
  calls.at(-1).resolve(frame('current', 5, [0, 1], [{...first, points: [estimated, null]}, second]));
  await provisional;
  assert.equal(rings(), 1, 'one cue across two pending cells; never animate an already displayed value');
  assert.equal(chart.shades.children.length, 1);
  const tiny = chart.layers.children.find(node => node.attributes['data-ink'] === String(chart.colors.get(first.id)));
  assert.ok(Number(tiny.attributes.height) > 0);
  chart.choose(0);
  const polite = chart.announce.textContent;
  assert.equal(chart.tipState.textContent, '');
  assert.match(polite, /Account A: ~<0.1/);

  const quiet = chart.refresh();
  calls.at(-1).resolve(frame('current', 6, [0], [first, second], []));
  await quiet;
  assert.equal(rings(), 0);
  assert.equal(chart.shades.children.length, 0);
  assert.equal(chart.view.series[0].points[0], point, 'in-flight revision retains the last usable value');
  assert.equal(chart.announce.textContent, polite, 'passive refresh never re-announces');
  chart.active(false);
  chart.active(true);
  assert.equal(rings(), 0, 'reentry does not flash a stale cue');

  const revised = chart.refresh(), newPoint = {...point, amount: '45'};
  calls.at(-1).resolve(frame('current', 7, [], [{...first, points: [newPoint, null]}, second], [], false));
  await revised;
  assert.equal(chart.view.series[0].points[0], newPoint);
  assert.equal(rings(), 0);

  const repriced = chart.refresh();
  calls.at(-1).resolve(frame('current', 8, [0], [{...first, points: [null, null]}, second],
    [], false, 'new price'));
  await repriced;
  assert.equal(chart.view.series[0].points[0], null, 'never reuse a last-good amount with an incompatible valuation');
}

async function checkWaitingProgress() {
  let response;
  const chart = new context.View(async () => response, () => {});
  chart.setScope('current');
  chart.active(true);
  const zero = {...point, amount: '0', display: {credits: '0', usd: '$0.00'}};
  const estimated = {...point, display: {credits: '~100', usd: '~$1.00'}};
  const cues = () => chart.layers.children
    .filter(node => /ring|hourglass/.test(node.attributes.class))
    .map(node => [Number(node.attributes['data-bucket']), node.attributes.class.split('-').at(-1)]);
  for (const period of ['today', '7-days', '30-days', 'month']) {
    chart.setScope(null);
    chart.setScope('current');
    chart.select(period);
    const slot = period === 'today' ? 3_600_000 : day;
    const publish = async (revision, waiting, points, acquiring = true) => {
      response = {scope: 'current', revision, acquiring, view: {period, timezone_id: 'UTC', start_ms: start,
        end_ms: start + 4 * slot, buckets: Array.from({length: 5}, (_, i) => [start + i * slot, start + (i + 1) * slot]),
        future_buckets: [4], partial_buckets: [0, 3], pending_buckets: waiting, initial_pending_buckets: waiting,
        series: [{...first, points}]}};
      await chart.refresh();
      assert.equal(chart.layers.children.filter(node => node.tag === 'circle').length, 0);
      assert.equal(chart.shades.children.filter(node => node.attributes.class === 'account-timeline-future').length, 1);
    };
    await publish(1, [0, 1, 2, 3], [null, null, estimated, null, null]);
    assert.deepEqual(cues(), [[0, 'ring'], [1, 'hourglass'], [3, 'hourglass']], period);
    chart.choose(3);
    chart.inspect(1);
    assert.deepEqual(cues(), [[0, 'ring'], [1, 'hourglass'], [3, 'hourglass']], 'inspection does not advance acquisition');
    response = {scope: 'current', unchanged: true, acquiring: false};
    await chart.refresh();
    assert.deepEqual(cues(), [[0, 'hourglass'], [1, 'hourglass'], [3, 'hourglass']]);
    await publish(2, [0, 2, 3], [null, zero, estimated, null, null]);
    assert.deepEqual(cues(), [[0, 'ring'], [3, 'hourglass']], 'an out-of-order settled zero leaves the cursor in place');
    await publish(3, [2, 3], [point, zero, estimated, null, null]);
    assert.deepEqual(cues(), [[3, 'ring']], 'a settled first slot moves the cursor to the last unread slot');
    await publish(4, [], [point, zero, point, zero, null]);
    assert.deepEqual(cues(), []);
  }
}

check().then(checkWaitingProgress).catch(error => { console.error(error); process.exitCode = 1; });
