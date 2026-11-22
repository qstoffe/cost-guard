'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const sandbox = {AbortController, clearTimeout, setTimeout};
vm.runInNewContext(`${fs.readFileSync('src/web/assets/cached-stats.js', 'utf8')}\nthis.Controller = CachedStats.Controller;`, sandbox);

(async () => {
  const requests = [], renders = [];
  const a = 'a'.repeat(32), b = 'b'.repeat(32);
  let now = 10, expiry;
  const timing = {now: () => now, set: run => { expiry = run; return 1; }, cancel: () => { expiry = null; }};
  const controller = new sandbox.Controller((path, body, signal) => {
    assert.equal(path, '/api/cache/ai-stats');
    return new Promise(resolve => requests.push({period: body.period, signal, resolve}));
  }, () => renders.push(controller.snapshot().value?.display.working), timing);
  const result = (period, binding, archive_epoch, working, valid_until_ms = null) => ({
    period, binding, archive_epoch, coverage: 'unknown', display: {working}, valid_until_ms
  });
  const finish = async (i, value) => {
    requests[i].resolve(value);
    await new Promise(setImmediate); // Drain the foreign VM's promise continuation.
  };

  controller.activate('all');
  controller.committed({binding: a, marks: {all: [1, 3]}});
  await finish(0, result('all', a, 0, 'obsolete'));
  assert.equal(requests.length, 2);
  await finish(1, result('all', a, 0, '1m'));
  assert.equal(controller.snapshot().value.display.working, '1m');
  controller.committed({binding: a, marks: {all: [1, 3], today: [2, 4]}}, true);
  assert.equal(requests.length, 2, 'unselected commits must not re-read');

  controller.activate('today');
  controller.activate('all');
  assert.ok(requests[2].signal.aborted);
  await finish(2, result('today', a, 0, 'wrong period'));
  await finish(3, result('all', a, 0, '1m'));
  controller.committed({binding: a, archive_epoch: 0, marks: {all: [3, 5]}});
  controller.committed({binding: a, archive_epoch: 1, cleared: true, marks: {}});
  assert.ok(requests[4].signal.aborted);
  assert.equal(controller.snapshot().value, null);
  await finish(4, result('all', a, 0, 'purged'));
  await finish(5, result('all', a, 1, undefined));

  controller.activate(null);
  controller.committed({binding: b, archive_epoch: 0, marks: {today: [1, 6]}}, true);
  assert.equal(requests.length, 6, 'hidden tabs must not re-read');
  controller.activate('today');
  await finish(6, result('today', b, 0, '3m', 20));
  assert.equal(controller.snapshot().value.display.working, '3m');
  now = 20; expiry();
  assert.equal(controller.snapshot().value, null);
  assert.equal(requests[7].period, 'today');
  controller.health(true);
  await finish(7, result('today', b, 0, 'expired session'));
  assert.equal(controller.snapshot().value, null);
  controller.health(false);
  await finish(8, result('today', b, 0, 'crossed midnight in flight', 20));
  assert.equal(requests.length, 10, 'an in-flight rollover immediately gets one local re-read');
  assert.equal(requests[9].period, 'today');
  await finish(9, result('today', b, 0, 'server still on old day', 20));
  assert.equal(requests.length, 10, 'clock skew does not turn renewal into polling');
  assert.equal(controller.snapshot().value, null);
  controller.committed({binding: b, archive_epoch: 0, marks: {today: [2, 20]}});
  await finish(10, result('today', b, 0, 'new day', 30));
  assert.equal(controller.snapshot().value.display.working, 'new day');
  const discarded = ['obsolete', 'purged', 'wrong period', 'expired session', 'crossed midnight in flight',
    'server still on old day'];
  assert.ok(!renders.some(value => discarded.includes(value)));

  const measured = (title, sessions_generation) => ({
    ...result('today', b, 0, 'new day', 30), sessions_generation,
    measured_root_time: {longest_root: 'leader'}, longest_session: {session_id: 'leader', title}
  });
  controller.committed({binding: b, archive_epoch: 0, marks: {today: [3, 20]}});
  await finish(11, measured('First title', 3));
  controller.sessionCommit({binding: b, generation: 4, detail_roots: ['peer']});
  controller.sessionCommit({binding: b, generation: 5, detail_roots: ['other']});
  assert.equal(requests.length, 12, 'contiguous unrelated commits must not fetch Stats');
  controller.sessionCommit({binding: b, generation: 6, detail_roots: ['leader']});
  assert.equal(requests.length, 13);
  controller.sessionCommit({binding: b, generation: 7, detail_roots: ['leader']});
  await finish(12, measured('Obsolete title', 6));
  assert.equal(controller.snapshot().value.longest_session.title, 'First title');
  await finish(13, measured('Current title', 7));
  assert.equal(controller.snapshot().value.longest_session.title, 'Current title');
  controller.sessionCommit({binding: b, generation: 5, detail_roots: ['leader']});
  assert.equal(requests.length, 14, 'an older notification must not fetch Stats');
})().catch(error => { console.error(error); process.exitCode = 1; });
