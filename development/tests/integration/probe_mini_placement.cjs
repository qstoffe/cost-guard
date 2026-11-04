// Actual hidden Document PiP bounds/cache, not physical Windows/DPI or manual dragging.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
module.exports = async ({evaluate,until,command,sessionId,targetId,restart,checks,layouts,output,screenshots}) => {
  const bounds = async () => {
    const targets = await command('Target.getTargets');
    for (const target of targets.targetInfos.filter(item => item.type === 'page' && item.targetId !== targetId)) {
      const {sessionId: pip} = await command('Target.attachToTarget', {targetId:target.targetId,flatten:true});
      const found = await command('Runtime.evaluate', {expression:'!!document.querySelector(".mini-watch")',returnByValue:true},pip);
      if (found.result.value) return command('Browser.getWindowForTarget', {targetId:target.targetId});
    }
    throw new Error('Owned PiP target unavailable');
  };
  const measure = async name => {
    const value = await bounds(); layouts.push({case:'placement-'+name,...value.bounds}); return value;
  };
  const same = (actual,expected) => {
    for (const key of ['left','top','width','height']) assert.ok(Math.abs(actual[key]-expected[key]) <= 2,
      `${key}: ${JSON.stringify({actual,expected})}`);
  };
  const close = async native => {
    await evaluate(native ? 'miniWatch.window.close()' : 'miniWatch.close()');
    await until('!miniWatch.window');
  };
  const open = async () => {
    await evaluate('miniWatch.toggle()',true); await until('!!miniWatch.window');
  };
  const change = async (field,value) => {
    await evaluate(`(async () => applySettings(await api('/api/settings/${field === 'miniWatchPlacement' ? 'mini-placement' : field === 'ccostDisplayUnit' ? 'ccost' : 'theme'}', {${field}:'${value}'})))()`);
  };
  const initial = (await measure('first-standard')).bounds;
  // Use the owned hidden browser's native bounds seam: both dimensions AND position.
  const alter = async name => {
    const {windowId} = await bounds();
    // Stay inside the browser's PiP work-area maximum at emulated 150%.
    await command('Browser.setWindowBounds', {windowId,bounds:{width:500,height:340}});
    try {
      await until('Math.abs(miniWatch.window.outerWidth-500)<=2 && Math.abs(miniWatch.window.outerHeight-340)<=2');
      await command('Browser.setWindowBounds', {windowId,bounds:{left:80,top:90}});
      await until('Math.abs(miniWatch.window.screenX-80)<=2 && Math.abs(miniWatch.window.screenY-90)<=2');
    } catch (error) {
      layouts.push({case:'placement-resize-failure',...await command('Browser.getWindowBounds',{windowId}),
        dom:await evaluate('({x:miniWatch.window.screenX,y:miniWatch.window.screenY,w:miniWatch.window.outerWidth,h:miniWatch.window.outerHeight})')});
      throw error;
    }
    const current = (await measure(name)).bounds;
    same(current,{left:80,top:90,width:500,height:340}); return current;
  };
  for (const native of [false,true]) {
    const moved = await alter(native ? 'before-native-close' : 'before-app-close');
    await close(native); await open(); same((await measure('remember-reopen')).bounds,moved);
  }
  const beforeSwitch = (await bounds()).bounds;
  await change('miniWatchPlacement','standard');
  same((await measure('unchanged-on-mode-switch')).bounds,beforeSwitch);
  await close(false); await open(); same((await measure('standard-reset')).bounds,initial);
  await alter('standard-moved'); await close(true); await open(); same((await measure('standard-every-open')).bounds,initial);
  await change('miniWatchPlacement','remember-last');
  const last = await alter('remember-after-switch'); await close(false); await open(); same((await bounds()).bounds,last);
  checks.push('Actual hidden PiP with width/height present: Remember last reuses position and size after app/native close; Standard resets both each open; mode switch applies next open');

  await evaluate("location.hash='#/settings'"); await until("document.getElementById('mini-placement')?.disabled === false");
  const controls = await evaluate(`[...document.querySelectorAll('.web-settings select')].map(select=>({id:select.id,value:select.value,options:[...select.options].map(option=>option.text)}))`);
  assert.equal(controls.length,3);
  assert.deepEqual(controls.map(item=>item.value),['default','default','remember-last']);
  assert.deepEqual(controls.map(item=>item.options),[
    ['Default (Classic)','Classic','Web'],['Default (Credits)','Credits','USD'],
    ['Default (Remember last)','Remember last','Standard placement']]);
  const settingsImage = await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sessionId);
  const settingsPath = output.replace(/\.json$/,'')+'-settings.png';
  await fs.writeFile(settingsPath,Buffer.from(settingsImage.data,'base64')); screenshots.push(path.basename(settingsPath));
  await change('theme','classic'); await change('ccostDisplayUnit','credits');
  const instance = await evaluate('hostInstance');
  await close(false);
  await command('Page.reload',{},sessionId);
  await until("typeof miniWatch !== 'undefined' && hostState.kind === 'connected'");
  assert.equal(await evaluate('hostInstance'),instance);
  await open(); same((await measure('opener-reload-standard')).bounds,initial);
  const reloaded = await alter('reloaded-moved'); await close(true); await open(); same((await bounds()).bounds,reloaded);
  await close(false);

  // A real Python process/server restart, same profile and persisted disposable config.
  const launch = await restart();
  await command('Page.navigate',{url:launch.url},sessionId);
  await until("typeof miniWatch !== 'undefined' && hostState.kind === 'connected' && liveValue?.view?.running?.count === 2");
  assert.notEqual(await evaluate('hostInstance'),instance);
  const saved = await evaluate("api('/api/settings')");
  assert.deepEqual(saved.webSettingsChoices,{theme:'classic',ccostDisplayUnit:'credits',miniWatchPlacement:'remember-last'});
  await open(); same((await measure('new-process-first-open')).bounds,initial);
  const newMoved = await alter('new-process-moved'); await close(false); await open(); same((await bounds()).bounds,newMoved);
  await change('theme','default'); await change('ccostDisplayUnit','default'); await change('miniWatchPlacement','default');
  const inheriting = await evaluate("api('/api/settings')");
  assert.deepEqual(inheriting.webSettingsChoices,{theme:'default',ccostDisplayUnit:'default',miniWatchPlacement:'default'});
  assert.deepEqual(await evaluate('({local:localStorage.length,session:sessionStorage.length})'),{local:0,session:0});
  checks.push('Three native selects preserve Default/explicit choices; real Python host restart keeps file-backed mode but first open resets native bounds; opener reload also starts standard, then remembers; no browser storage');
  // Restore the original initial state for the established layout/SSE probe.
  await close(false); await change('miniWatchPlacement','standard'); await open();
  await change('miniWatchPlacement','default'); await evaluate("location.hash='#/watch'");
  await until("document.body.dataset.section === 'watch'");
};
