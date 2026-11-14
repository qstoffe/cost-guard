// Shipped Full/Mini DOM and real Chromium input over source-derived fixture exports.
const assert = require('node:assert/strict');
module.exports = async function({command,evaluate,until,owner,mini,checks,layouts}) {
  const full = '.watch-active tbody td:nth-child(6) .help-value';
  const prompt = '.mini-prompts > table .mini-cost-value > span:first-child';
  const total = '.mini-prompts > table .mini-cost-value > span:nth-child(3)';
  async function apply(mode) {
    await evaluate(owner,`(() => {document.activeElement?.blur();miniWatch.window.document.activeElement?.blur();
      const p={...liveValue,view:structuredClone(liveValue.probe_ccost_unavailable[${JSON.stringify(mode)}])};
      p.source_observed_at_ms=p.view.now_ms=Date.now();for(const c of [...p.view.active_cards,...p.view.history_cards])c.observed_at_ms=Date.now();
      current.watch.update(p);miniWatch.update(p);window.ccostPublication=p;})()`);
    await until(mini,`document.querySelector('.mini-cost-value')`);
  }
  async function focus(id,selector) {
    await command('Page.bringToFront',{},id);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
    await evaluate(id,`document.activeElement?.blur();document.querySelector(${JSON.stringify(selector)}).focus()`);
    await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
    return evaluate(id,`document.querySelector('#context-help').textContent`);
  }
  await evaluate(owner,`ReportView.setUnit('credits',current.watch.root);ReportView.setUnit('credits',miniWatch.view.root)`);
  await apply('absent');
  for(const [id,selector] of [[owner,full],[mini,prompt],[mini,total],[owner,'.watch-active .watch-session-summary > div:last-child .help-value'],[mini,'.mini-daily .help-value']]) {
    const text=await focus(id,selector);
    assert.match(text,/Claude Sonnet 4 has no listed reference price in the available GitHub Copilot/);
    assert.match(text,/N\/A does not mean zero/);
    const target=await evaluate(id,`(() => {const n=document.querySelector(${JSON.stringify(selector)}),r=n.getBoundingClientRect();return {text:n.textContent,width:r.width,parent:n.parentNode.getBoundingClientRect().width,title:n.hasAttribute('title'),tab:n.tabIndex};})()`);
    assert.equal(target.text,'N/A');assert.equal(target.title,false);assert.equal(target.tab,0);
    assert.ok(target.width<target.parent);layouts.push({case:'unavailable-cost-target',selector,...target});
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
    await evaluate(owner,id===owner ? `ReportView.syncUnits(document.body)` : `ReportView.syncUnits(miniWatch.view.root)`);
    assert.equal(await evaluate(id,`document.querySelector('#context-help').matches(':popover-open')`),false);
  }
  for(const [mode,expected] of [['identity',/could not be matched/],['rate',/required reference rate.*output/],
      ['usage',/usage information is missing.*cached input, cache write, output/],['catalog',/price data cannot currently be checked/]]) {
    await apply(mode);
    const text=await focus(owner,full);assert.match(text,expected);assert.doesNotMatch(text,/has no listed/);
  }
   await apply('mixed');
   assert.match(await evaluate(mini,`document.querySelector(${JSON.stringify(prompt)}).textContent`),/^[<\d]/);
  await apply('zero');assert.equal(await evaluate(mini,`document.querySelector(${JSON.stringify(prompt)}).textContent`),'0');
  await apply('known');assert.notEqual(await evaluate(mini,`document.querySelector(${JSON.stringify(prompt)}).textContent`),'N/A');
  await apply('prompt-only');
  assert.equal(await evaluate(mini,`document.querySelector(${JSON.stringify(prompt)}).textContent`),'N/A');
   assert.match(await evaluate(mini,`document.querySelector(${JSON.stringify(total)}).textContent`),/^[<\d]/);
  assert.match(await focus(mini,prompt),/Claude Sonnet 4/);
  assert.doesNotMatch(await focus(mini,total),/has no listed/);
  await apply('session-only');
  assert.notEqual(await evaluate(mini,`document.querySelector(${JSON.stringify(prompt)}).textContent`),'N/A');
  assert.equal(await evaluate(mini,`document.querySelector(${JSON.stringify(total)}).textContent`),'N/A');
  assert.match(await focus(mini,total),/available model pricing and usage information/);
  assert.doesNotMatch(await focus(mini,prompt),/cannot be calculated/);
  await apply('pending');assert.match(await evaluate(mini,`document.querySelector(${JSON.stringify(total)}).textContent`),/Loading/);
  await apply('absent');
  await focus(mini,total);
  const refresh=await evaluate(owner,`(() => {const row=miniWatch.view.body.children[0],n=row.querySelector('.mini-cost-value > span:nth-child(3)');
    const p=structuredClone(ccostPublication);p.view.active_cards[0].session_summary.cost=liveValue.probe_ccost_unavailable.catalog.active_cards[0].session_summary.cost;
    miniWatch.update(p);return {same:n===row.querySelector('.mini-cost-value > span:nth-child(3)'),focused:miniWatch.window.document.activeElement===n,
      text:miniWatch.window.document.querySelector('#context-help').textContent};})()`);
  assert.equal(refresh.same,true);assert.equal(refresh.focused,true);assert.match(refresh.text,/price data cannot currently be checked/);
   await evaluate(owner,`ReportView.setUnit('usd',current.watch.root);ReportView.setUnit('usd',miniWatch.view.root)`);
   assert.match(await evaluate(mini,`document.querySelector('#context-help').textContent`),/price data cannot currently be checked/);
   await focus(mini,'.mini-daily .help-value');
   const dailyKnown=await evaluate(owner,`(() => {const n=miniWatch.view.dailyAmount,p=structuredClone(ccostPublication);
     p.view.daily_usage=liveValue.probe_ccost_unavailable.known.daily_usage;miniWatch.update(p);
     return {same:n===miniWatch.view.dailyAmount,focused:miniWatch.window.document.activeElement===n,
       open:miniWatch.window.document.querySelector('#context-help').matches(':popover-open'),tab:n.tabIndex,
       help:n.classList.contains('help-value'),text:n.textContent};})()`);
   assert.equal(dailyKnown.same,true);assert.equal(dailyKnown.focused,true);assert.equal(dailyKnown.open,false);
   assert.equal(dailyKnown.tab,-1);assert.equal(dailyKnown.help,false);assert.notEqual(dailyKnown.text,'N/A');
   await apply('absent');
   // Real pointer hover and touch target the amount, not the surrounding cell.
  await evaluate(mini,`document.activeElement.blur()`);
  const point=await evaluate(mini,`(() => {const n=document.querySelector(${JSON.stringify(prompt)});n.scrollIntoView();const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},mini);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},mini);
  await until(mini,`document.querySelector('#context-help')?.matches(':popover-open')`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},mini);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},mini);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},mini);
   await until(mini,`document.querySelector('#context-help')?.matches(':popover-open')`);
   assert.match(await evaluate(mini,`document.querySelector('#context-help').textContent`),/Claude Sonnet 4/);
   // Sessions belongs to the opener. End the PiP phase before keyboard checks there.
   await evaluate(owner,`miniWatch.close()`,true);
   await command('Page.bringToFront',{},owner);
   // Headless PiP does not restore the opener's native focus. Use CDP focus,
   // without claiming physical window-focus restoration or changing app events.
   await command('Emulation.setFocusEmulationEnabled',{enabled:true},owner);
   await evaluate(owner,`(() => {document.activeElement?.blur();window.ccostSessions=new SessionsCatalog.View(()=>Promise.resolve());
    ccostSessions.rows(liveValue.probe_ccost_unavailable.absent.probe_sessions);ccostSessions.pan.hidden=false;
    window.ccostDetail=new SessionDetail.View(()=>Promise.resolve(),'root');
    ccostDetail.update({revision:'absent',state:'observed',result:{observed_at_ms:Date.now(),view:liveValue.probe_ccost_unavailable.absent.probe_detail}});
    document.body.append(ccostSessions.root,ccostDetail.root);})()`);
  for(const selector of ['.sessions-catalog tbody td:nth-child(4) .help-value','.session-detail tbody td:nth-child(4) .help-value',
      '.session-detail tfoot td:nth-child(4) .help-value']) {
    assert.match(await focus(owner,selector),/Claude Sonnet 4 has no listed/);
    assert.equal(await evaluate(owner,`document.querySelector(${JSON.stringify(selector)}).textContent`),'N/A');
  }
   const catalogTarget='.sessions-catalog tbody td:nth-child(4) .help-value';
   await focus(owner,catalogTarget);
   const catalogRefresh=await evaluate(owner,`(() => {const n=document.querySelector(${JSON.stringify(catalogTarget)});
     ccostSessions.rows(liveValue.probe_ccost_unavailable.catalog.probe_sessions);
     return {same:n===document.querySelector(${JSON.stringify(catalogTarget)}),focused:document.activeElement===n,
       open:document.querySelector('#context-help').matches(':popover-open'),text:document.querySelector('#context-help').textContent};})()`);
   assert.equal(catalogRefresh.same,true);assert.equal(catalogRefresh.focused,true);assert.equal(catalogRefresh.open,true);
   assert.match(catalogRefresh.text,/price data cannot currently be checked/);
  await evaluate(owner,`document.activeElement.blur();ccostDetail.update({revision:'catalog',state:'history_retained',result:{observed_at_ms:Date.now(),view:liveValue.probe_ccost_unavailable.catalog.probe_detail}})`);
  assert.match(await focus(owner,'.session-detail tbody td:nth-child(4) .help-value'),/price data cannot currently be checked/);
   await evaluate(owner,`document.activeElement.blur();ccostSessions.root.remove();ccostDetail.root.remove()`);
   await command('Emulation.setFocusEmulationEnabled',{enabled:false},owner);
  checks.push('Canonical absent/identity/rate/usage/catalog/partial/zero/known/pending snapshots; direct Full and separate Mini prompt/session/day N/A targets; real keyboard/Escape/hover/touch and Document PiP; retained reason refresh and unit/focus identity');
  checks.push('Independent one-N/A Mini pairs; production Sessions catalog/detail/footer text targets, retained history correction and accurate reason refresh');
};
