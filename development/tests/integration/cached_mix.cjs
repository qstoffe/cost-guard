const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function main() {
  const context = vm.createContext({AbortController});
  vm.runInContext(fs.readFileSync('src/web/assets/cached-mix.js', 'utf8'), context);
  const Controller = vm.runInContext('CachedMix.Controller', context);
  const requests = [], paints = [];
  const a = 'a'.repeat(32), b = 'b'.repeat(32);
  const view = new Controller((path, {period}, signal) => {
    assert.equal(path, '/api/cache/token-mix');
    return new Promise(resolve => requests.push({period, signal, resolve}));
  }, () => paints.push(view.snapshot().value?.token_mix?.request_count ?? null));
  const hint = (binding, archive_epoch, usage_revision, periods, marks, cleared = false) =>
    ({binding, archive_epoch, usage_revision, end_ms: 100, periods, marks, cleared});
  async function respond(read, binding, count) {
    read.resolve({binding, scope: read.period, start_ms: null, end_ms: 100,
      coverage: 'partial', token_mix: {request_count: count, display: {mix_total_tokens: `${count}`}}});
    await new Promise(setImmediate);
  }

  view.activate('all');
  const previous = requests.at(-1);
  view.activate('today');
  assert.equal(previous.signal.aborted, true);
  await respond(previous, a, 900);
  await respond(requests.at(-1), a, 10);
  assert.equal(paints.at(-1), 10);

  view.committed(hint(a, 0, 1, ['all'], {all: [1, 100]}));
  assert.equal(requests.length, 2);
  view.committed(hint(a, 0, 3, ['all'], {all: [3, 100], today: [2, 100]}), true);
  const missed = requests.at(-1);
  assert.equal(requests.length, 3, 'resync catches a missed relevant commit, even if latest was unrelated');
  view.committed(hint(a, 0, 4, ['today'], {today: [4, 100]}));
  view.committed(hint(a, 0, 5, ['today'], {today: [5, 100]}));
  assert.equal(requests.length, 3);
  await respond(missed, a, 20);
  assert.equal(requests.length, 4, 'coalesce in-flight hints into one requery');
  assert.equal(paints.at(-1), 10);
  await respond(requests.at(-1), a, 50);
  assert.equal(paints.at(-1), 50);

  view.committed(hint(a, 1, null, undefined, {}, true));
  assert.equal(paints.at(-1), null);
  const preRebind = requests.at(-1);
  view.committed(hint(b, 0, 1, ['all'], {all: [1, 100]}));
  assert.equal(preRebind.signal.aborted, true);
  await respond(preRebind, a, 900);
  await respond(requests.at(-1), b, 1);
  assert.equal(paints.at(-1), 1);
  view.health(true);
  assert.equal(paints.at(-1), null);
  assert.equal(paints.includes(900), false);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
