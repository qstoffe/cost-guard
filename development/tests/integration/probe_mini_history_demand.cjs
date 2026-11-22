// Actual open-Mini filler demand to authenticated leases, no disclosure or extra stream.
const assert = require('node:assert/strict');
const {setTimeout: pause} = require('node:timers/promises');

module.exports = async ({command,evaluate,until,sessionId,targetId,interest,errors,browser}) => {
  const checks = [], transactions = [];
  const accepted = async (tab, offset, visible, history) => {
    const started = performance.now();
    while (performance.now()-started < 5000) {
      const row = interest.slice(offset).find(row => row.tab === tab && row.section === 'watch' &&
        row.visible === visible && row.history === history && row.status === 200 && row.finished);
      if (row) {
        const response = await command('Network.getResponseBody', {requestId:row.requestId}, row.session);
        assert.equal(JSON.parse(response.body).lease_seconds,90);
        transactions.push({visible,history,status:row.status,lease_seconds:90,
          seconds:(performance.now()-started)/1000});
        return performance.now();
      }
      await pause(20);
    }
    throw new Error('Expected accepted key/lifecycle lease before ordinary 30-second renewal');
  };
  await until('!!miniWatch.demand && !!miniWatch.view && miniWatch.view.needsHistory');
  const firstTab = await evaluate('miniWatch.demand.tab'); // Identity is used only in memory.
  await accepted(firstTab,0,true,true);
  const targets = await command('Target.getTargets');
  let pipSession;
  for (const target of targets.targetInfos.filter(item => item.targetId !== targetId && item.type === 'page')) {
    const attached = await command('Target.attachToTarget', {targetId:target.targetId,flatten:true});
    const found = await command('Runtime.evaluate', {expression:'!!document.querySelector(".mini-watch")',
      returnByValue:true}, attached.sessionId);
    if (found.result.value) { pipSession = attached.sessionId; break; }
  }
  assert.ok(pipSession,'actual owned PiP target');
  const cover = await command('Target.createTarget', {url:'about:blank'});
  const covered = await command('Target.attachToTarget', {targetId:cover.targetId,flatten:true});
  await command('Page.bringToFront',{},covered.sessionId);
  await until('document.hidden && !miniWatch.window.document.hidden');
  await evaluate(`window.leaseUpdate=miniWatch.update.bind(miniWatch);miniWatch.update=p=>leaseUpdate(window.leasePublication||p)`);
  const capacity=async count=>evaluate(`(async()=>applySettings(await api('/api/settings/mini-rows',
    {miniWatchRows:${JSON.stringify(count)}})))()`);
  for(const {running,ended,rows,history} of [
    {running:12,ended:2,rows:0,history:false},
    {running:1,ended:2,rows:7,history:true},
    {running:1,ended:10,rows:7,history:false},
    {running:4,ended:0,rows:5,history:true},
  ]) {
    const offset=interest.length;
    await capacity(rows);
    await evaluate(`(()=>{const p=structuredClone(liveValue),base=p.view.active_cards[0];p.view.now_ms++;
      p.view.active_cards=Array.from({length:${running}},(_,i)=>({...base,session_id:'running-'+i}));
      p.view.history_cards=Array.from({length:${ended}},(_,i)=>{
        const card=structuredClone(base);
        card.session_id='ended-'+i;card.focal_id='';
        Object.assign(card.rows[0].prompt,{in_progress:false,execution_unverified:false,completed_at_ms:p.view.now_ms-i});
        return card;
      });
      window.leasePublication=p;miniWatch.update(p);})()`);
    await until(`miniWatch.view.promptRows.size===${running+Math.min(ended,Math.max(0,rows-running))}`);
    assert.equal(await evaluate('miniWatch.view.needsHistory'),history);
    await accepted(firstTab,offset,true,history);
    checks.push(`${running} running + ${ended} non-running at capacity ${rows}: history interest ${history}`);
  }
  await capacity('default');
  await evaluate(`miniWatch.update=window.leaseUpdate;delete window.leasePublication;delete window.leaseUpdate;miniWatch.update(liveValue)`);
  let offset = interest.length;
  await evaluate('miniWatch.close();true');
  await accepted(firstTab,offset,false,false);
  await until('!miniWatch.window');
  await command('Page.bringToFront',{},sessionId);
  await command('Target.closeTarget',{targetId:cover.targetId});
  offset = interest.length;
  await evaluate('miniWatch.toggle()',true);
  await until('!!miniWatch.demand && miniWatch.view.needsHistory');
  const secondTab = await evaluate('miniWatch.demand.tab');
  assert.notEqual(secondTab,firstTab,'reopen owns a new document lease');
  await accepted(secondTab,offset,true,true);
  assert.equal(await evaluate('probeStreams'),1,'Mini never creates another EventSource');
  offset = interest.length;
  await evaluate('miniWatch.close();true');
  await accepted(secondTab,offset,false,false);
  assert.deepEqual(errors,[]);
  checks.push('Hidden opener/visible PiP automatically fills history; accepted close withdrawal, new open-Mini lease and single EventSource');
  return {outcome:'PASS',browser,checks,transactions,
    limitations:['Owned hidden browser keyboard and authenticated leases, not physical input, remembered geometry or OS proof.']};
};
