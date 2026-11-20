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
  append(...nodes) { for (const node of nodes) this.insertBefore(node, null); }
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
    quotaLabel: item => item.label,
    display: item => item.display.amount
  }
});
vm.runInContext(fs.readFileSync('src/web/assets/account-timeline.js', 'utf8') +
  '; globalThis.View = AccountTimelineView.View;', context);

const point = {amount: '100', display: {credits: '100', usd: '$1.00'}};
const primary = {id: '00000000', primary: true, account: 'Account A', quota: '5-hour',
  points: [point, null], peak: '100', ticks: [{amount: '0', display: {credits: '0', usd: '$0.00'}}, point]};
const secondary = {...primary, id: '00000008', primary: false, quota: 'Weekly'};
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
  calls.at(-1).resolve(frame('old', 1, [0], [primary, secondary]));
  await old;
  assert.equal(chart.view, undefined);

  const abandoned = chart.refresh();
  chart.select('today');
  chart.select('month');
  calls.at(-1).resolve(frame('current', 2, [0], [primary, secondary]));
  await abandoned;
  assert.equal(chart.view, undefined, 'even a same-period reply from before a switch must be discarded');

  const pending = chart.refresh();
  calls.at(-1).resolve(frame('current', 3, [1], [primary, secondary]));
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
  chart.choose(1);
  assert.equal(chart.tipTitle.textContent, '2026-11-02');
  assert.equal(chart.tipState.textContent, 'Loading');
  const check = chart.entries.get(secondary.id).input;
  check.checked = true;
  check.events.change();
  assert.equal(demand, 2, 'selection is frontend-only');
  assert.equal(chart.tipTitle.textContent, '2026-11-02', 'selection retains the inspected date');
  assert.equal(chart.layers.children.filter(node => node.attributes.class === 'account-timeline-bar').length, 2);
  assert.equal(chart.selectedLegend.children.length, 2);

  const settled = chart.refresh();
  assert.equal(calls.at(-1).request.revision, 3);
  calls.at(-1).resolve(frame('current', 4, [], [{...secondary, account: 'Renamed account'}, primary]));
  await settled;
  assert.equal(chart.shades.children.length, 0);
  assert.equal(chart.tipTitle.textContent, '2026-11-02', 'a compatible update retains the inspected date');
  assert.equal(chart.tipState.textContent, '');
  assert.equal(chart.entries.get(secondary.id).input, check);
  assert.equal(check.checked, true);
  assert.match(chart.entries.get(secondary.id).name.textContent, /^Renamed account/);
  assert.match(chart.selectedLegend.children[0].children[1].textContent, /^Renamed account/);

  const provisional = chart.refresh();
  calls.at(-1).resolve(frame('current', 5, [0, 1], [primary, secondary]));
  await provisional;
  assert.equal(rings(), 1, 'one cue across two pending cells; never animate an already displayed value');
  assert.equal(chart.shades.children.length, 2);
  chart.choose(0);
  const polite = chart.announce.textContent;
  assert.equal(chart.tipState.textContent, 'Partial');

  const quiet = chart.refresh();
  calls.at(-1).resolve(frame('current', 6, [0], [primary, secondary], []));
  await quiet;
  assert.equal(rings(), 0);
  assert.equal(chart.shades.children.length, 0);
  assert.equal(chart.view.series[0].points[0], point, 'in-flight revision retains the last usable value');
  assert.equal(chart.announce.textContent, polite, 'passive refresh never re-announces');
  chart.active(false);
  chart.active(true);
  assert.equal(rings(), 0, 'reentry does not flash a stale cue');

  const revised = chart.refresh(), newPoint = {...point, amount: '45'};
  calls.at(-1).resolve(frame('current', 7, [], [{...primary, points: [newPoint, null]}, secondary], [], false));
  await revised;
  assert.equal(chart.view.series[0].points[0], newPoint);
  assert.equal(rings(), 0);

  const repriced = chart.refresh();
  calls.at(-1).resolve(frame('current', 8, [0], [{...primary, points: [null, null]}, secondary],
    [], false, 'new price'));
  await repriced;
  assert.equal(chart.view.series[0].points[0], null, 'never reuse a last-good amount with an incompatible valuation');
}

check().catch(error => { console.error(error); process.exitCode = 1; });
