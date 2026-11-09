// Actual PiP keyboard-to-authenticated-lease proof, independent of remembered geometry.
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
  await until('!!miniWatch.demand && !!miniWatch.view && miniWatch.view.earlier.hidden');
  const firstTab = await evaluate('miniWatch.demand.tab'); // Identity is used only in memory.
  let acknowledged = await accepted(firstTab,0,true,false);
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
  for (const [key,code,keyCode,text] of [['Enter','Enter',13,'\r'],[' ','Space',32,' ']]) {
    for (const expanded of [true,false]) {
      assert.ok(performance.now()-acknowledged < 5000,'fresh acknowledged lease excludes periodic renewal');
      await command('Runtime.evaluate', {expression:'document.querySelector(".mini-earlier-toggle").focus()'}, pipSession);
      const offset = interest.length;
      await command('Input.dispatchKeyEvent', {type:'keyDown',key,code,windowsVirtualKeyCode:keyCode,
        text,unmodifiedText:text},pipSession);
      await command('Input.dispatchKeyEvent', {type:'keyUp',key,code,windowsVirtualKeyCode:keyCode},pipSession);
      await until(`!miniWatch.view.earlier.hidden === ${expanded}`);
       assert.equal(await evaluate('miniWatch.view.earlierToggle.getAttribute("aria-expanded")'),String(expanded));
       assert.equal(await evaluate('miniWatch.view.earlierToggle.getAttribute("aria-pressed")'),String(expanded));
       assert.equal(await evaluate('miniWatch.view.prompts.dataset.expanded'),String(expanded));
      acknowledged = await accepted(firstTab,offset,true,expanded);
      checks.push(`${code} ${expanded?'expands':'collapses'} actual PiP and promptly updates accepted history demand`);
    }
  }
  let offset = interest.length;
  await evaluate('miniWatch.close();true');
  await accepted(firstTab,offset,false,false);
  await until('!miniWatch.window');
  await command('Page.bringToFront',{},sessionId);
  await command('Target.closeTarget',{targetId:cover.targetId});
  offset = interest.length;
  await evaluate('miniWatch.toggle()',true);
  await until('!!miniWatch.demand && miniWatch.view.earlier.hidden');
  const secondTab = await evaluate('miniWatch.demand.tab');
  assert.notEqual(secondTab,firstTab,'reopen owns a new document lease');
  await accepted(secondTab,offset,true,false);
  assert.equal(await evaluate('probeStreams'),1,'Mini never creates another EventSource');
  offset = interest.length;
  await evaluate('miniWatch.close();true');
  await accepted(secondTab,offset,false,false);
  assert.deepEqual(errors,[]);
  checks.push('Hidden opener/visible PiP, accepted close withdrawal, new collapsed reopen lease and single EventSource');
  return {outcome:'PASS',browser,checks,transactions,
    limitations:['Owned hidden browser keyboard and authenticated leases, not physical input, remembered geometry or OS proof.']};
};
