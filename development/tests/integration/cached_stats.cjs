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
  assert.ok(!renders.some(value => ['obsolete', 'purged', 'wrong period', 'expired session'].includes(value)));
})().catch(error => { console.error(error); process.exitCode = 1; });
