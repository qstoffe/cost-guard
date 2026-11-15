// Native windows with deliberately held API resolution/styles; no desktop UI.
const assert=require('node:assert/strict');
module.exports=async({evaluate,until,fixture,command,sessionId,checks})=>{
  await evaluate(`window.raceNative=documentPictureInPicture.requestWindow.bind(documentPictureInPicture);
    window.raceStyles=miniWatch.measure.styleDocument.bind(miniWatch.measure);
    window.raceErrors=[];window.addEventListener('unhandledrejection',e=>raceErrors.push(String(e.reason)));
    window.raceIdentity=miniWatch.instance;`);
  const off=async()=>{
    await until('!miniWatch.pending&&!miniWatch.window');
    assert.equal(await evaluate(`miniWatch.button.getAttribute('aria-pressed')`),'false');
    assert.equal(await evaluate('miniWatch.feedback.textContent'),'');
  };
  for(const action of ['off','on-off-on','native-x','identity']) {
    await evaluate(`documentPictureInPicture.requestWindow=async options=>{
      const w=await raceNative(options);window.raceWindow=w;
      await new Promise(resolve=>window.raceResolve=resolve);return w;
    };window.raceWindow=null;window.racePromise=miniWatch.toggle();undefined`,true);
    await until('!!window.raceWindow');
    assert.equal(await evaluate(`miniWatch.button.getAttribute('aria-pressed')`),'false');
    if(action==='native-x')await evaluate('raceWindow.close()');
    else if(action==='identity')await evaluate(`miniWatch.settings(null,'race-host')`);
    else {
      await evaluate('miniWatch.toggle()',true);
      if(action==='on-off-on')await evaluate('miniWatch.toggle()',true);
    }
    await evaluate('raceResolve();racePromise');
    if(action==='on-off-on'){
      assert.equal(await evaluate('!!miniWatch.view&&!raceWindow.closed'),true);
      await evaluate('miniWatch.close()');
    }
    await off();
    assert.equal(await evaluate('raceWindow.closed'),true);
    await evaluate('miniWatch.settings(null,raceIdentity)');
  }
  for(const action of ['off','native-x','theme-route','css-error']) {
    await evaluate(`documentPictureInPicture.requestWindow=async options=>{
      const w=await raceNative(options),append=w.document.head.append.bind(w.document.head);
      window.raceWindow=w;window.raceLinks=[];
      w.document.head.append=(...nodes)=>nodes.forEach(node=>{
        if(node.rel==='stylesheet')raceLinks.push(node);else append(node);
      });window.raceAppend=append;return w;
    };
    miniWatch.measure.styleDocument=doc=>{raceStyles(doc);return false;};
    window.racePromise=miniWatch.toggle();undefined`,true);
    await until('!!miniWatch.window&&raceLinks.length===2');
    assert.equal(await evaluate('miniWatch.window.document.body.textContent'),'Loading Mini Watch…');
    assert.equal(await evaluate('miniWatch.feedback.textContent'),'');
    if(action==='off')await evaluate('miniWatch.toggle()',true);
    else if(action==='native-x')await evaluate('raceWindow.close()');
    else if(action==='css-error'){
      await evaluate(`raceLinks[0].href=new URL('/missing-probe-styles.css',location.href).href;
        raceLinks.forEach(link=>raceAppend(link));`);
    } else {
      await evaluate(`location.hash='#/accounts';document.documentElement.dataset.theme='web';miniWatch.settings();`);
      await evaluate('raceLinks.forEach(link=>raceAppend(link));racePromise');
      assert.equal(await evaluate(`miniWatch.view.doc.documentElement.dataset.theme`),'web');
      await evaluate(`location.hash='#/watch'`);await until(`current.section==='watch'`);
      await evaluate('miniWatch.close()');
    }
    await evaluate('racePromise');
    await until('!miniWatch.pending&&!miniWatch.window');
    if(action==='css-error'){
      assert.match(await evaluate('miniWatch.feedback.textContent'),/Could not open/);
      assert.equal(await evaluate('miniWatch.button.title'),'');
      assert.equal(await evaluate(`miniWatch.feedback.className`),'sr-only');
      await evaluate('miniWatch.close()');
    }else await off();
  }
  await evaluate(`documentPictureInPicture.requestWindow=raceNative;miniWatch.measure.styleDocument=raceStyles;`);
  // No publication is still a usable, non-invented loading/empty view.
  await evaluate('miniWatch.publication=null;miniWatch.observations.view=null;miniWatch.toggle()',true);
  assert.equal(await evaluate('!!miniWatch.view'),true);
  assert.match(await evaluate('miniWatch.view.body.textContent'),/Loading/);
  await evaluate('miniWatch.close()');
  // requestWindow consumes transient activation. This next call has no gesture.
  await evaluate('miniWatch.toggle()');
  assert.equal(await evaluate('miniWatch.window'),null);
  assert.match(await evaluate('miniWatch.feedback.textContent'),/Could not open/);
  assert.equal(await evaluate('miniWatch.button.title'),'');
  await evaluate('miniWatch.close()');
  assert.deepEqual(await evaluate('raceErrors'),[]);
  assert.equal(await evaluate('probeStreams'),1,'no second Live stream through any native race');
  const targetsBefore=(await command('Target.getTargets')).targetInfos.filter(t=>t.type==='page').map(t=>t.targetId);
  // Reload the real parent while an owned PiP is still waiting for styles.
  await evaluate(`documentPictureInPicture.requestWindow=async options=>{
    const w=await raceNative(options),append=w.document.head.append.bind(w.document.head);
    w.document.head.append=(...nodes)=>nodes.filter(n=>n.rel!=='stylesheet').forEach(n=>append(n));return w;
  };miniWatch.measure.styleDocument=doc=>{raceStyles(doc);return false;};
  window.racePromise=miniWatch.toggle();undefined`,true);
  await until('!!miniWatch.window&&!!miniWatch.pending&&!miniWatch.view');
  // Genuine response-header policy denial, not a mocked requestWindow rejection.
  await fixture('deny-pip');await command('Page.reload',{},sessionId);
  await until(`typeof miniWatch!=='undefined'&&miniWatch.reason.includes('policy')`);
  assert.deepEqual((await command('Target.getTargets')).targetInfos.filter(t=>t.type==='page').map(t=>t.targetId).sort(),
    targetsBefore.sort(),'parent pagehide cannot leave an orphan native PiP');
  assert.equal(await evaluate(`miniWatch.button.getAttribute('aria-disabled')`),'true');
  assert.equal(await evaluate(`miniWatch.button.disabled`),false,'policy-disabled control remains keyboard discoverable');
  assert.equal(await evaluate('miniWatch.button.title'),'');
  assert.equal(await evaluate('miniWatch.feedback.textContent'),'');
  assert.equal(await evaluate(`document.permissionsPolicy?.allowsFeature('picture-in-picture') ??
    document.featurePolicy.allowsFeature('picture-in-picture')`),false);
  await evaluate('miniWatch.button.click()',true);
  assert.equal(await evaluate('miniWatch.window'),null,'actual header policy prevents a native request');
  assert.equal(await evaluate('miniWatch.feedback.textContent'),'Could not open Mini Watch. Try again.');
  checks.push('Native delayed-resolution On/Off/On, native X, host identity, held/failed CSS, theme/route return, parent reload while opening, missing publication, one stream/no unhandled rejection, native user-activation rejection, actual Permissions-Policy disablement and focusable error description');
};
