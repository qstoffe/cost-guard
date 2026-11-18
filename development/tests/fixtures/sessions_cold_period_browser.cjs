// Compare actual clicks, rendered pending state and ordinary acknowledgement.
const assert = require('node:assert/strict');

module.exports = async ({evaluate, until, fixture}) => {
  await evaluate("location.hash='#/sessions'");
  await until(`current?.catalog?.data?.period === 'today' &&
    current.catalog.data.order_state === 'verified' && !current.catalog.operation`, 20000);
  const before = await fixture('stats');
  assert.ok(!before.catalog_reads['root-0100'], 'no 7-day preload');
  await evaluate(`(() => {
    const view = current.catalog;
    window.periodRun = {replies: [], started: performance.now()};
    const request = view.api;
    view.api = async (...args) => {
      const reply = await request(...args);
      if (!args[1]?.action && args[1]?.period === '7-days') {
        periodRun.replies.push({navigation: args[1].navigation, applied: args[1].applied,
          pending: reply.pending_sort, completed: reply.progress.completed, total: reply.progress.total,
          ms: performance.now() - periodRun.started});
      }
      return reply;
    };
    view.periodButtons.find(item => item.key === '7-days').button.click();
  })()`);
  await until(`current.catalog.operation?.pending && !current.catalog.status.hidden`);
  assert.match(await evaluate('current.catalog.status.textContent'), /Loading sessions in 7 days/);
  assert.equal(await evaluate('current.catalog.data.period'), 'today', 'do not apply the pending answer');
  const responsiveness = await evaluate(`(async () => {
    const started = performance.now();
    const live = await api('/api/live');
    const watchMs = performance.now() - started;
    const opened = await api('/api/detail', {action: 'open', session_id: 'root-0290', mode: 'live'});
    try {
      for (let attempt = 0; attempt < 40; attempt++) {
        const page = await api('/api/detail', {action: 'begin', token: opened.token, offset: 0});
        if (!page.pending && page.result) return {watchMs, detailMs: performance.now() - started - watchMs,
          watched: live.values?.live?.view != null, detailRows: page.total};
        await new Promise(resolve => setTimeout(resolve, 150));
      }
      throw new Error('Detail did not get a responsive acquisition turn');
    } finally { await api('/api/detail', {action: 'close', token: opened.token}); }
  })()`);
  assert.equal(responsiveness.watched, true);
  assert.ok(responsiveness.detailRows > 0);
  await until(`current.catalog.data.period === '7-days' && !current.catalog.operation`, 110000);
  assert.deepEqual(await evaluate(`[
    current.catalog.data.order_state, current.catalog.data.total, current.catalog.body.rows.length,
    current.catalog.body.rows[0].dataset.id]`), ['verified', 300, 25, 'root-0000']);
  await until('periodRun.replies.some(reply => reply.applied && !reply.navigation)', 12000);
  const replies = await evaluate('periodRun.replies');
  const indexing = replies.filter(reply => reply.navigation);
  assert.equal(indexing.at(-1).completed, 302);
  assert.ok(indexing.every((reply, i) => reply.total === 302 && (!i || reply.completed >= indexing[i-1].completed)));
  const cold = await fixture('stats');
  assert.equal(cold.acknowledged, true);
  assert.equal(Object.keys(cold.catalog_reads).length, 302);
  for (const period of ['today', '7-days']) {
    await evaluate(`current.catalog.periodButtons.find(item => item.key === '${period}').button.click()`);
    await until(`current.catalog.data.period === '${period}' && !current.catalog.operation`);
  }
  const warm = await fixture('stats');
  assert.deepEqual({...warm.catalog_reads, 'root-0000': 0}, {...cold.catalog_reads, 'root-0000': 0},
    'a warm revisit must not reread stable roots; the running root may refresh independently');
  return {checks: ['cold click retains Today during real progress, then shows verified 300 members / 25 rows',
    'ordinary poll acknowledges the epoch', 'other Live/Detail HTTP remains responsive',
    'Today → 7 days repeat performs no stable history reads'],
    measurements: {readyMs: indexing.at(-1).ms, acknowledgedMs: replies.find(reply => reply.applied && !reply.navigation).ms,
      coldPolls: indexing.length, responsiveness, before: before.metrics, cold: cold.metrics, warm: warm.metrics}};
};
