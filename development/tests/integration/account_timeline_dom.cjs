// Deterministic response-order, selection and presentation checks against the shipped view.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Node {
  constructor(tag, text = '', className) {
    Object.assign(this, {tag, textContent: text, className, children: [], attributes: {}, events: {}, style: {},
      clientWidth: 480, scrollLeft: 0, offsetWidth: 200, offsetHeight: 100,
      classList: {toggle() {}, add() {}}, style: {setProperty() {}}});
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
  removeAttribute(name) { delete this.attributes[name]; }
  get parentNode() { return this.parent; }
  get parentElement() { return this.parent; }
  get isConnected() { return true; }
  after(node) { this.parent.append(node); }
  addEventListener(name, fn) { this.events[name] = fn; }
  hidePopover() {}
  matches() { return false; }
  getBoundingClientRect() { return {left: 0, top: 0, right: 480, bottom: 220}; }
}

let unit = 'credits';
const context = vm.createContext({
  document: {documentElement: {lang: 'en'}, addEventListener() {}, createElementNS: (_, tag) => new Node(tag)},
  innerWidth: 480, innerHeight: 640, AbortController, performance,
  setTimeout() {}, clearTimeout() {},
  fakeReportView: {
    element: (...args) => new Node(...args),
    text: (el, value) => { el.textContent = value; },
    compare: (a, b) => Number(a) - Number(b),
    display: item => item.display_units?.[unit]?.amount ?? item.display.amount
  }
});
vm.runInContext(fs.readFileSync('src/web/assets/render.js', 'utf8').replace(
  'const ReportView =', 'const formatter =') +
  '; const ReportView = {...formatter, ...fakeReportView};', context);
vm.runInContext(fs.readFileSync('src/web/assets/report-loading.js', 'utf8'), context);
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
  const chart = new context.View((path, request, signal) =>
    new Promise(resolve => calls.push({path, request, signal, resolve})), () => demand++);
  chart.active(true);
  chart.setScope('old');
  const old = chart.refresh();
  chart.setScope('current');
  calls.at(-1).resolve(frame('old', 1, [0], [first, second]));
  await old;
  assert.equal(chart.view, undefined);

  const abandoned = chart.refresh();
  const beforeSwitch = calls.at(-1);
  chart.select('today');
  const today = calls.at(-1);
  chart.select('month');
  const month = calls.at(-1);
  assert.deepEqual([today.request.period, month.request.period], ['today', 'month']);
  assert.ok(today.signal.aborted && beforeSwitch.signal.aborted && !month.signal.aborted);
  today.resolve(frame('current', 2, [], [second]));
  beforeSwitch.resolve(frame('current', 2, [0], [first, second]));
  await abandoned;
  assert.equal(chart.view, undefined, 'even a same-period reply from before a switch must be discarded');

  month.resolve(frame('current', 3, [1], [first, second]));
  await new Promise(resolve => setImmediate(resolve));
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
  assert.ok(polite.includes('Account A: <0.1'), polite);

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
    response = {scope: 'current', unchanged: true};
    chart.setScope(null);
    chart.setScope('current');
    chart.select(period);
    await new Promise(resolve => setImmediate(resolve));
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

async function checkPeriodLoading() {
  let now = 0;
  const timers = new Map(), calls = [];
  context.performance = {now: () => now};
  context.setTimeout = (fn, ms) => { timers.set(fn, now + ms); return fn; };
  context.clearTimeout = fn => timers.delete(fn);
  const advance = ms => {
    now += ms;
    for (const [fn, due] of [...timers]) if (due <= now) { timers.delete(fn); fn(); }
  };
  const chart = new context.View((_, request) => new Promise((resolve, reject) => calls.push({request, resolve, reject})), () => {});
  chart.sharedHistory = chart.cacheEvents = true;
  chart.setScope('current');
  chart.active(true);
  const button = period => chart.buttons.find(([key]) => key === period)[1];
  const spinning = period => button(period).children.some(node => node.className === 'metric-spinner');
  const select = period => {
    chart.select(period);
    assert.equal(calls.at(-1).request.period, period, 'dispatch cannot wait for a spinner');
    return calls.at(-1);
  };
  const answer = async (call, revision, complete) => {
    const result = frame('current', revision, [], [first]);
    Object.assign(result.view, {period: call.request.period, history_progress: {complete}});
    call.resolve(result);
    await new Promise(resolve => setImmediate(resolve));
  };
  const fast = select('today');
  advance(299);
  assert.ok(!spinning('today'));
  await answer(fast, 1, true);
  advance(1);
  assert.ok(!spinning('today'));

  const old = select('7-days');
  advance(200);
  const slow = select('30-days');
  advance(100);
  assert.ok(!spinning('7-days') && !spinning('30-days'));
  await answer(old, 2, true);
  advance(199);
  assert.ok(!spinning('30-days'));
  advance(1);
  assert.ok(spinning('30-days'));
  await answer(slow, 3, false);
  assert.ok(spinning('30-days'), 'HTTP success does not complete missing history');
  const refresh = chart.refresh();
  await answer(calls.at(-1), 4, true);
  await refresh;
  assert.ok(!spinning('30-days'), 'settlement clears the indicator without a minimum duration');

  const abandoned = select('7-days');
  chart.active(false);
  advance(300);
  await answer(abandoned, 5, false);
  assert.ok(!spinning('7-days'), 'a retired route does not paint a late indicator');

  chart.active(true);
  const reject = async (call, retryable) => {
    call.reject(Object.assign(new Error(retryable ? 'busy' : 'invalid_request'), {retryable}));
    await new Promise(resolve => setImmediate(resolve));
  };
  const superseded = select('month'), failed = select('7-days');
  advance(50);
  await reject(superseded, false);
  assert.ok(chart.historyError?.hidden !== false, 'superseded rejection stays quiet');
  await reject(failed, false);
  advance(250);
  assert.equal(button('7-days').attributes['aria-pressed'], 'true');
  assert.ok(!spinning('7-days') && !button('7-days').attributes['aria-busy']);
  assert.equal(chart.historyError.hidden, false);
  assert.match(chart.historyError.textContent, /retry/i);

  const retry = select('7-days');
  await reject(retry, true);
  const beforeRetry = calls.length;
  advance(350);
  assert.equal(calls.length, beforeRetry + 1);
  await reject(calls.at(-1), true);
  advance(10_000);
  assert.equal(calls.length, beforeRetry + 1, 'a retry is not an endless refresh loop');
  assert.ok(!spinning('7-days') && !chart.historyError.hidden);
  await answer(select('7-days'), 6, true);
  assert.ok(chart.historyError.hidden);

  chart.wake('new-cache-revision', false);
  advance(0);
  await reject(calls.at(-1), true);
  const background = calls.length;
  advance(10_000);
  assert.equal(calls.length, background);
  assert.ok(chart.historyError.hidden, 'a passive cache read is not a failed user selection');
}

async function checkLegendTotals() {
  const cases = [
    ['Exact', point, '100', '$1.00'],
    ['Partial', {amount: '123', display: {credits: '~123', usd: '~$1.23'}}, '123', '$1.23'],
    ['Tiny', {amount: '0.01', display: {credits: '~<0.1', usd: '~<$0.01'}}, '<0.1', '<$0.01'],
    ['Zero', {amount: '0', display: {credits: '0', usd: '$0.00'}}, '0', '$0.00'],
    ['Negative', {amount: '-100', display: {credits: '≈-100', usd: '≈$-1.00'}}, '-100', '$-1.00'],
    ['Unavailable', null, '—', '—'],
  ];
  const series = cases.map(([account, total], i) => ({
    ...first, id: i.toString(16).padStart(8, '0'), account, total, points: [total, null]
  }));
  const response = frame('current', 1, [], series);
  const chart = new context.View(async () => response, () => {});
  chart.setScope('current');
  chart.active(true);
  await chart.refresh();

  for (const [displayUnit, column] of [['credits', 2], ['usd', 3]]) {
    unit = displayUnit;
    chart.draw();
    const cells = chart.selectedLegend.children.map(row => row.children[2]);
    assert.deepEqual(cells.map(cell => cell.children[0]?.textContent ?? cell.textContent),
      cases.map(row => row[column]), displayUnit);
    assert.equal(cells.at(-1).children[1].textContent, 'Total unavailable');
    chart.choose(0);
    assert.deepEqual(chart.tipValues.children.map(row => row.children[2].textContent), cases.map(row => row[column]));
    for (const row of cases) assert.ok(chart.announce.textContent.includes(`${row[0]}: ${row[column]}`));
  }
}

async function checkOverlayRanks() {
  const amounts = [99, 100, 98, 100, 50];
  const value = n => ({amount: String(n), display: {credits: String(n), usd: `$${(n / 100).toFixed(2)}`}});
  const series = Array.from({length: 200}, (_, i) => ({
    ...first, id: i.toString(16).padStart(8, '0'), account: `Account ${i}`,
    points: [i < 5 ? value(amounts[i]) : i % 2 ? null : value(0), value(i === 4 ? 100 : 50)]
  }));
  let response = frame('current', 1, [], series.slice(0, 5));
  const chart = new context.View(async () => response, () => {});
  chart.setScope('current');
  chart.active(true);
  await chart.refresh();

  const bars = bucket => chart.layers.children.map(node => node.attributes)
    .filter(attrs => attrs.class === 'account-timeline-bar' && Number(attrs['data-bucket']) === bucket);
  const fiveWidths = bars(0).map(bar => bar.width);
  response = frame('current', 2, [], series);
  await chart.refresh();
  const ink = i => chart.entries.get(series[i].id).root.children[1].attributes['data-ink'];
  const sparse = bars(0), crowded = bars(1);
  assert.deepEqual(sparse.map(bar => bar.width), fiveWidths, 'missing and zero values take no overlay ranks');
  assert.deepEqual(sparse.map(bar => bar['data-ink']), [1, 3, 0, 2, 4].map(ink),
    'only positive accounts paint, highest first, with stable account colors on a tie');
  const fullHeight = Number(sparse[0].height);
  for (const [i, percent] of [100, 100, 99, 98, 50].entries()) {
    assert.ok(Math.abs(Number(sparse[i].height) - fullHeight * percent / 100) < .001);
    if (i) assert.ok(Number(sparse[i].width) < Number(sparse[i - 1].width), `sparse rank ${i}`);
  }
  assert.equal(crowded.length, 200);
  assert.equal(crowded[0]['data-ink'], ink(4), 'the shortest account yesterday leads today');
  assert.equal(crowded[0].width, sparse[0].width, 'both buckets start with the full bar');
  const target = chart.targets.children[1].attributes;
  const center = Number(target.x) + Number(target.width) / 2;
  for (const [i, bar] of crowded.entries()) {
    const width = Number(bar.width);
    assert.ok(width > 0 && width <= Number(i ? crowded[i - 1].width : target.width), `crowded rank ${i}`);
    assert.ok(Math.abs(Number(bar.x) + width / 2 - center) < .001, `crowded center ${i}`);
  }
}

check().then(checkWaitingProgress).then(checkOverlayRanks).then(checkLegendTotals).then(checkPeriodLoading)
  .catch(error => { console.error(error); process.exitCode = 1; });
