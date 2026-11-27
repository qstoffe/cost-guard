// A held real chunk distinguishes the initial follow from a later jump over the reader.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, command, checks}) => {
  await evaluate(`{
    const request = window.fetch;
    window.fetch = async (url, options) => {
      if (url === '/api/detail' && JSON.parse(options.body).action === 'chunk') {
        window.fetch = request;
        await new Promise(resolve => window.releaseHistoryChunk = resolve);
      }
      return request(url, options);
    };
    location.hash = '#/sessions/root-0000';
  }`);
  await until('window.releaseHistoryChunk && current.detail?.body.rows.length > 10');
  const pan = 'document.querySelector(\'[role="region"][aria-label="Session prompt history"]\')';
  const geometry = () => evaluate(`(() => {
    const pan = ${pan}, table = pan.querySelector('table'), rows = [...table.tBodies[0].rows];
    const bounds = pan.getBoundingClientRect(), top = Math.max(bounds.top, table.tHead.getBoundingClientRect().bottom);
    const bottom = Math.min(bounds.top + pan.clientHeight, table.tFoot.getBoundingClientRect().top);
    const visible = rows.filter(row => {
      const r = row.getBoundingClientRect();
      return Math.min(r.bottom,bottom) - Math.max(r.top,top) > 1;
    }).map(row => row.dataset.id);
    return {count:rows.length, visible, first:rows[0]?.dataset.id, last:rows.at(-1)?.dataset.id,
      top:pan.scrollTop, remaining:pan.scrollHeight-pan.clientHeight-pan.scrollTop, height:pan.clientHeight,
      tableHeight:table.getBoundingClientRect().height, page:scrollY};
  })()`);
  function expectPinned(facts) {
    assert.ok(facts.top > 0 && Math.abs(facts.remaining) <= 1, `not pinned: ${facts.top}, ${facts.remaining}`);
    assert.equal(facts.visible.length, 10);
    assert.equal(facts.visible.at(-1), facts.last);
  }
  const partial = await geometry();
  expectPinned(partial);
  assert.ok(partial.count < 1001);
  await evaluate(`${pan}.scrollTop = 0; releaseHistoryChunk()`);
  await until('current.detail?.body.rows.length === 1001 && !current.detail.busy');
  const complete = await geometry();
  assert.equal(complete.top, 0);
  assert.equal(complete.visible[0], partial.first);
  assert.equal(complete.visible.length, 10);

  await evaluate(`location.hash = '#/sessions/root-0001'`);
  await until(`current.detail?.id === 'root-0001' && current.detail.body.rows.length === 1 && !current.detail.busy`);
  await evaluate(`{
    const request = window.fetch;
    window.fetch = async (url, options) => {
      if (url === '/api/detail' && JSON.parse(options.body).action === 'begin') {
        window.fetch = request;
        await new Promise(resolve => window.releaseWarmRead = resolve);
      }
      return request(url,options);
    };
    location.hash = '#/sessions/root-0000';
  }`);
  await until(`window.releaseWarmRead && current.detail?.id === 'root-0000' && current.detail.body.rows.length === 1001`);
  expectPinned(await geometry());
  await evaluate('releaseWarmRead()');
  await until('!current.detail.busy');
  checks.push('partial read opens pinned; reading oldest survives final chunk; returning from another session reopens cached history pinned');

  // Isolate renderer publications from background acquisition. Keep real row IDs and styling.
  await command('Emulation.setDeviceMetricsOverride', {width:360,height:500,deviceScaleFactor:1,mobile:false});
  await evaluate(`{
    const view = current.detail, source = view.data, block = source.result.view.prompt_blocks[0];
    view.poll = async () => {};
    window.publishHistory = n => view.update({...source, total:n, result:{...source.result, view:{
      ...source.result.view, prompt_blocks:[{...block, rows:block.rows.slice(0,n)}]}}});
  }`);
  let previousHeight = 0;
  for (const count of [0, 1, 10]) {
    await evaluate(`publishHistory(${count})`);
    const facts = await geometry();
    assert.equal(facts.count, count);
    assert.equal(facts.visible.length, count);
    assert.ok(facts.height > previousHeight && Math.abs(facts.height - facts.tableHeight) <= 1,
      `expected natural table height at ${count}: ${facts.height} vs ${facts.tableHeight}`);
    previousHeight = facts.height;
  }
  await evaluate(`publishHistory(20); window.scrollTo(0,80); ${pan}.scrollLeft = ${pan}.scrollWidth`);
  const pinned = await geometry();
  expectPinned(pinned);
  assert.ok(pinned.page > 0);
  const horizontal = await evaluate(`(() => {const p=${pan}, last=p.querySelector('th:last-child button').getBoundingClientRect();
    const start=p.getBoundingClientRect().left + p.clientLeft;
    return {left:p.scrollLeft, lastLeft:last.left, lastRight:last.right, start, end:start+p.clientWidth,
      pageWidth:document.documentElement.scrollWidth, viewport:innerWidth};
  })()`);
  assert.ok(horizontal.left > 0 && horizontal.lastLeft >= horizontal.start - 1 && horizontal.lastRight <= horizontal.end + 1 &&
    horizontal.pageWidth <= horizontal.viewport + 1, `last column reachable inside narrow page: ${JSON.stringify(horizontal)}`);
  const away = await evaluate(`(() => {const p=${pan}; p.scrollTop = 70; const top=p.scrollTop;
    publishHistory(21); return top;})()`);
  const reading = await geometry();
  assert.equal(reading.count, 21);
  assert.ok(away > 0 && reading.remaining > 1);
  assert.equal(reading.top, away);
  assert.equal(reading.page, pinned.page);
  await evaluate(`${pan}.scrollTop = ${pan}.scrollHeight; publishHistory(22)`);
  const following = await geometry();
  expectPinned(following);
  assert.equal(following.count, 22);
  assert.notEqual(following.last, reading.last);
  assert.equal(following.page, pinned.page);
  checks.push('natural 0/1/10 rows; 10 visible of 20 at 360px; horizontal access; immediate append away and after returning to bottom preserves document offset');
};
