const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function main() {
  const context = vm.createContext({AbortController});
  vm.runInContext(fs.readFileSync('src/web/assets/cached-mix.js', 'utf8'), context);
  const Controller = vm.runInContext('CachedMix.Controller', context);
  const requests = [], paints = [];
  const a = 'a'.repeat(32), b = 'b'.repeat(32);
  const view = new Controller((path, input, signal) => {
    assert.ok(['/api/cache/token-mix', '/api/cache/token-mix/groups'].includes(path));
    return new Promise((resolve, reject) => requests.push({path, ...input, signal, resolve, reject}));
  }, () => paints.push(view.snapshot().value?.token_mix?.request_count ?? null));
  const hint = (binding, archive_epoch, usage_revision, periods, marks, cleared = false) =>
    ({binding, archive_epoch, usage_revision, end_ms: 100, periods, marks, cleared});
  async function respond(read, binding, count, revision = 'revision') {
    read.resolve({binding, scope: read.period, start_ms: null, end_ms: 100,
      coverage: 'partial', token_mix: {request_count: count, display: {mix_total_tokens: `${count}`}},
      groups: {revision}});
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
  view.committed(hint(a, 0, 5, ['today'], {today: [5, 100, 'new-model-metadata']}));
  assert.equal(requests.length, 5, 'group-only publication with the same usage revision and clock is not lost');
  await respond(requests.at(-1), a, 50);

  view.committed(hint(a, 1, null, undefined, {}, true));
  assert.equal(paints.at(-1), null);
  const preRebind = requests.at(-1);
  view.committed(hint(b, 0, 1, ['all'], {all: [1, 100]}));
  assert.equal(preRebind.signal.aborted, true);
  await respond(preRebind, a, 900);
  await respond(requests.at(-1), b, 1);
  assert.equal(paints.at(-1), 1);

  const descending = ['tokens', 'desc'];
  view.orders.model = descending;
  const oldPage = view.page('model', 'anchor', descending, new AbortController().signal);
  const pageRead = requests.at(-1);
  assert.equal(pageRead.after, 'anchor');
  assert.equal(pageRead.direction, 'desc');
  view.activate('7-days');
  assert.equal(requests.at(-1).orders.model, descending);
  await respond(requests.at(-1), b, 7);
  pageRead.resolve({binding: b, scope: 'today', kind: 'model', revision: 'revision', order: descending, rows: []});
  assert.equal(await oldPage, null, 'old period page must not paint after navigation');
  const beforeHidden = requests.length;
  view.activate(null);
  view.committed(hint(b, 0, 2, ['7-days'], {'7-days': [2, 100]}));
  assert.equal(requests.length, beforeHidden, 'no hidden-page SQL reads');
  assert.equal(view.snapshot().value.scope, '7-days', 'anchor stays compatible while hidden');
  view.activate('7-days');
  await respond(requests.at(-1), b, 8);
  assert.equal(paints.at(-1), 8, 'visible tab picks up the later cached snapshot');
  const revoked = view.page('model', '', descending, new AbortController().signal);
  requests.at(-1).reject(new Error('authentication_required'));
  assert.equal(await revoked, null);
  assert.equal(view.snapshot().error, 'authentication_required');
  assert.equal(paints.at(-1), null, 'paging authorization loss withdraws the current snapshot');

  view.health(true);
  assert.equal(paints.at(-1), null);
  assert.equal(paints.includes(900), false);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
