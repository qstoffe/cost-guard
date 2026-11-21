// Drive the real opener controller with explicit clocks and pending replies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function main() {
  let now = 1000, nextTimer = 0;
  const pending = [], rendered = [], timers = new Map();
  const context = vm.createContext({
    Date: {now: () => now}, AbortController,
    setTimeout: (fn, ms) => { timers.set(++nextTimer, {fn, ms}); return nextTimer; },
    clearTimeout: id => timers.delete(id)
  });
  vm.runInContext(fs.readFileSync('src/web/assets/cached-watch.js', 'utf8'), context);
  const Controller = vm.runInContext('CachedWatch.Controller', context);
  const controller = new Controller((path, value, signal) => {
    assert.equal(path, '/api/cache/watch');
    assert.equal(value, undefined);
    return new Promise(resolve => pending.push({resolve, signal}));
  }, publication => rendered.push(publication));
  const hint = (binding, archive_epoch, generation) => ({binding, archive_epoch, generation});
  const snapshot = (binding, epoch, generation, title) => ({
    ...hint(binding, epoch, generation), freshness: 'current', observed_ms: 1000, expires_ms: 2000,
    view: {cards_state: 'observed', earlier_cards: [],
      active_cards: [{title, rows: [{prompt: {in_progress: true}}]}]}
  });
  function advanceRead() {
    const matches = [...timers].filter(([, timer]) => timer.ms === 30);
    assert.equal(matches.length, 1);
    const [[id, timer]] = matches;
    timers.delete(id); timer.fn();
    return pending.at(-1);
  }
  async function reply(read, data) {
    read.resolve(data);
    // Let the controller's cross-realm promise continuation finish.
    await new Promise(setImmediate);
  }
  const title = () => rendered.at(-1)?.view.active_cards[0]?.title;

  controller.cacheHint(hint('A', 0, 1));
  const obsolete = advanceRead();
  controller.cacheHint(hint('A', 0, 2));
  controller.cacheHint(hint('A', 0, 3));
  assert.equal(pending.length, 1);
  await reply(obsolete, snapshot('A', 0, 1, 'old generation'));
  assert.equal(rendered.length, 0);
  await reply(advanceRead(), snapshot('A', 0, 3, 'latest'));
  assert.equal(title(), 'latest');

  controller.cacheHint(hint('A', 0, 3), true);
  assert.equal(timers.size, 1, 'unchanged resync schedules no read or redraw');
  controller.cacheHint(hint('A', 0, 4));
  const preClear = advanceRead();
  controller.cacheHint(hint('A', 1, 0));
  assert.equal(preClear.signal.aborted, true);
  assert.equal(rendered.at(-1), null);
  await reply(preClear, snapshot('A', 0, 4, 'purged'));
  assert.equal(rendered.at(-1), null);
  await reply(advanceRead(), snapshot('A', 1, 1, 'new epoch'));
  assert.equal(title(), 'new epoch');

  controller.cacheHint(hint('A', 1, 2));
  const previousSource = advanceRead();
  controller.cacheHint(hint(null));
  await reply(previousSource, snapshot('A', 1, 2, 'old binding'));
  assert.equal(rendered.at(-1), null);
  controller.cacheHint(hint('B', 0, 1));
  await reply(advanceRead(), snapshot('B', 0, 1, 'current binding'));
  assert.equal(title(), 'current binding');

  controller.health(false, true);
  assert.equal(rendered.at(-1).state, 'as-of');
  const uncertainRead = advanceRead();
  controller.health(false, false);
  await reply(uncertainRead, snapshot('B', 0, 1, 'current binding'));
  assert.equal(rendered.at(-1).state, 'as-of', 'a response from before recovery cannot restore Running');
  await reply(advanceRead(), snapshot('B', 0, 1, 'current binding'));
  assert.equal(rendered.at(-1).state, 'running');

  now = 2000; // Opener timers have not run; Mini still sees an expired publication.
  const held = controller.publication();
  assert.equal(held.state, 'as-of');
  assert.equal(held.view.active_cards.length, 0);
  assert.equal(held.view.earlier_cards[0].rows[0].prompt.execution_unverified, true);
  assert.equal(held.view.earlier_cards[0].rows[0].prompt.in_progress, false);
  controller.health(true, false);
  assert.equal(rendered.at(-1), null);
  assert.equal(timers.size, 0);
}

main().catch(error => { console.error(error); process.exitCode = 1; });
