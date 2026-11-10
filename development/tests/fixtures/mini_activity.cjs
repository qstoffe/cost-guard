// Fixed absolute instants through the real Mini Controller/render/row/help owners.
const assert = require('node:assert/strict');
module.exports = function activity(vm, context, controller, view, input, helpText, clock) {
  const saved = structuredClone(input), savedNow = clock.get(), base = saved.view.active_cards[0];
  const hour = 3600000, day = 24 * hour, now = Date.parse('2026-11-10T00:00:00Z');
  const zone = value => vm.runInContext(`ReportView.setTimezone(${JSON.stringify(value)})`, context);
  const card = (id, at, flags = {}, full) => {
    const value = structuredClone(base), local = full || new Date(at).toISOString().slice(0, 16).replace('T', ' ') + ' +0000';
    Object.assign(value, {session_id:id, focal_id:id});
    Object.assign(value.rows[0].prompt, {event_id:id, at_ms:at - day, completed_at_ms:at,
      in_progress:false, execution_unverified:false, aborted:false, has_error:false, completed_successfully:true}, flags);
    Object.assign(value.rows[0].prompt.display, {clock:'02:30', finished_clock:'02:30', start_date_time:local, finished_date_time:local});
    return value;
  };
  const show = (active, history = []) => {
    input.view = {...saved.view, active_cards:active, history_cards:history, history_state:'observed', history_epoch:1};
    controller.update(input);
  };
  const time = id => view.promptRows.get(id).children[0].textContent;
  zone('UTC'); clock.set(now);
  for (const [age, expected] of [
    [12 * hour - 1, '02:30'], [12 * hour, '12h ago'], [13 * hour + 55 * 60000, '13h ago'],
    [day - 1, '23h ago'], [day, '1d ago'], [2 * day - 1, '1d ago'], [2 * day, '2d ago'],
    [30 * day - 1, '29d ago'], [30 * day, '1m ago'], [60 * day - 1, '1m ago'], [60 * day, '2m ago'],
    [360 * day, '12m ago'], [365 * day - 1, '12m ago'], [365 * day, '1y ago'],
    [730 * day - 1, '1y ago'], [730 * day, '2y ago']]) {
    const value = card('boundary', now - age); show([value]);
    assert.equal(time('boundary'), expected, `elapsed ${age}ms`);
    assert.equal(helpText(view.promptRows.get('boundary').children[0].children[0]), value.rows[0].prompt.display.finished_date_time);
    if (expected.includes('ago')) assert.match(time('boundary'), /^\d+[hdmy] ago$/);
  }
  // Same configured date wins even after 20 hours. Crossing midnight retains the
  // clock until exactly twelve absolute hours, not twelve local clock hours.
  clock.set(Date.parse('2026-11-10T23:00:00Z'));
  show([card('today', Date.parse('2026-11-10T02:00:00Z'))]); assert.equal(time('today'), '02:30');
  clock.set(Date.parse('2026-11-11T00:00:00Z'));
  show([card('midnight', Date.parse('2026-11-10T23:59:00Z'))]); assert.equal(time('midnight'), '02:30');
  // Browser UTC date is Nov 10; configured Stockholm date is already Nov 11.
  zone('Europe/Stockholm'); clock.set(Date.parse('2026-11-10T23:30:00Z'));
  show([card('zone', Date.parse('2026-11-10T10:30:00Z'), {}, '2026-11-10 11:30 +0100')]);
  assert.equal(time('zone'), '13h ago');
  show([card('zone', Date.parse('2026-11-10T23:00:00Z'), {}, '2026-11-11 00:00 +0100')]);
  assert.equal(time('zone'), '02:30');
  clock.set(Date.parse('2026-11-10T22:30:00Z'));
  show([card('zone', Date.parse('2026-11-09T23:30:00Z'), {}, '2026-11-10 00:30 +0100')]);
  assert.equal(time('zone'), '02:30', 'same configured date overrides 23 elapsed hours across UTC midnight');
  // Fall-back repeated 02:30 differs by one elapsed hour; spring-forward loses
  // one local hour. Exact help retains both offsets independently of age tokens.
  for (const [current, instants, expected] of [
    ['2026-10-26T00:00:00Z', [['2026-10-25T00:30:00Z','2026-10-25 02:30 +0200'],
      ['2026-10-25T01:30:00Z','2026-10-25 02:30 +0100']], ['23h ago','22h ago']],
    ['2026-03-30T00:00:00Z', [['2026-03-29T00:30:00Z','2026-03-29 01:30 +0100'],
      ['2026-03-29T01:30:00Z','2026-03-29 03:30 +0200']], ['23h ago','22h ago']]]) {
    clock.set(Date.parse(current));
    show(instants.map(([at, full], index) => card('dst' + index, Date.parse(at), {}, full)));
    instants.forEach(([,full], index) => {
      assert.equal(time('dst' + index), expected[index]);
      assert.equal(helpText(view.promptRows.get('dst' + index).children[0].children[0]), full);
    });
  }
  zone('UTC'); clock.set(now);
  for (const at of [null, undefined, NaN, -1, Infinity, '1000']) {
    show([card('unknown', now, {completed_at_ms:at})]);
    assert.equal(time('unknown'), '—'); assert.equal(view.promptRows.get('unknown').activityHelp, 'Unknown finish time');
  }
  show([card('future', now + day)]); assert.equal(time('future'), '02:30');
  const old = Array.from({length:5}, (_, i) => ({...card('old' + i, now - (800 - i * 100) * day), focal_id:''}));
  show([], old);
  assert.equal(view.promptRows.size, 5, 'all five historical slots retain 100+ day and multi-year sessions');
  assert.deepEqual(view.body.children.filter(row => row.dataset.id).map(row => row.dataset.id), old.map(c => c.session_id));
  assert.equal(time('old0'), '2y ago');
  const retained = view.promptRows.get('old4');
  const run = card('old4', now, {in_progress:true, completed_successfully:false, at_ms:now - 13 * hour, completed_at_ms:null},
    '2026-11-09 11:00 +0000');
  show([run], old); assert.equal(view.promptRows.get('old4'), retained); assert.equal(time('old4'), '▶ 13h ago');
  for (const [flags, css, token] of [[{execution_unverified:true}, '', '13h ago'],
    [{in_progress:false, completed_successfully:true}, 'mini-success', '1d ago'],
    [{in_progress:false, aborted:true}, 'mini-error', '1d ago'], [{in_progress:false, has_error:true}, 'mini-error', '1d ago']]) {
    const changed = structuredClone(run); Object.assign(changed.rows[0].prompt, {completed_at_ms:now - day}, flags);
    show([changed], old); assert.equal(time('old4'), token); assert.equal(retained.className, css);
  }
  // The sole existing five-second presentation callback updates a keyed row with
  // no publication, timer, demand/membership change or native resize request.
  const at = now - 12 * hour; clock.set(now - 1); show([card('tick', at)]);
  const row = view.promptRows.get('tick'), target = row.children[0].children[0], timers = [...controller.window.timers];
  const payload = JSON.stringify(input); assert.equal(time('tick'), '02:30'); assert.equal(timers.length, 1);
  helpText(target); clock.set(now); timers[0]();
  assert.equal(time('tick'), '12h ago'); assert.equal(view.promptRows.get('tick'), row);
  assert.equal(row.children[0].children[0], target); assert.equal(helpText(target), '2026-11-09 12:00 +0000');
  assert.equal(JSON.stringify(input), payload); assert.deepEqual([...controller.window.timers], timers);
  input.view = saved.view; clock.set(savedNow); zone(null); controller.update(input);
};
