// Shipped authenticated HTTP/SSE and real Full/Mini DOM + Chromium AX trees.
const assert = require('node:assert/strict');
module.exports = async ({fixture,evaluate,until,command,sessionId,open,close,checks}) => {
  await fixture('proof-loading');
  await until(`liveValue.view.history_scope==='fixed-source' && liveValue.view.history_state==='loading'`);
  await close(); await open(); // Mini opens midway through the unchanged catalog.
  let pip;
  for (const target of (await command('Target.getTargets')).targetInfos.filter(t=>t.type==='page')) {
    const attached = await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
    if (await evaluate('!!document.querySelector(".mini-watch")',false,attached.sessionId)) pip=attached.sessionId;
  }
  assert.ok(pip);
  await evaluate(`document.querySelector('.watch-earlier').open=true;miniWatch.view.earlierToggle.click()`);
  const ax = async session => (await command('Accessibility.getFullAXTree',{},session)).nodes
    .filter(node=>!node.ignored).map(node=>node.name?.value||'').join('\n');
  const loading = async () => {
    assert.equal(await evaluate(`document.querySelectorAll('.watch-history article').length`),0);
    assert.equal(await evaluate('miniWatch.view.historyRows.size'),0);
    for (const session of [sessionId,pip]) {
      const names = await ax(session); assert.match(names,/Loading earlier sessions….*4\/12 checked/);
      assert.doesNotMatch(names,/Latest sample/);
    }
  };
  await loading();
  const size = await evaluate('({width:miniWatch.window.outerWidth,height:miniWatch.window.outerHeight})');
  await fixture('proof-observed'); await until(`miniWatch.view.historyRows.size===3`);
  assert.equal(await evaluate(`document.querySelectorAll('.watch-history article').length`),5);
  assert.deepEqual(await evaluate('[...miniWatch.view.historyRows.keys()]'),['proof-2','proof-3','proof-4']);
  for (const session of [sessionId,pip]) assert.match(await ax(session),/Latest sample 4/);
  const miniNames=await ax(pip); assert.match(miniNames,/Finished/); assert.doesNotMatch(miniNames,/Latest sample [01]/);
  for (const state of ['refreshing','unavailable']) {
    await fixture('proof-'+state); await until(`liveValue.view.history_state==='${state}'`);
    assert.equal(await evaluate(`document.querySelectorAll('.watch-history article').length`),5);
    for (const session of [sessionId,pip]) assert.match(await ax(session),/Previously verified sessions/);
  }
  assert.deepEqual(await evaluate('({width:miniWatch.window.outerWidth,height:miniWatch.window.outerHeight})'),size,
    'background proof publications never resize the popup');
  await fixture('proof-switch'); await until(`liveValue.view.history_scope==='other-source'`); await loading();
  await close();
  checks.push('Actual Full/Mini DOM and accessibility: initial/halfway loading hides provisional rows, atomic five/three, qualified refresh/failure, source switch, no background popup resize');
};
