// Safe live Duration fragments in the actual Document PiP help lifecycle.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,command,pip,ownerSession,checks}) => {
  const key = async key => { for (const type of ['keyDown','keyUp'])
    await command('Input.dispatchKeyEvent',{type,key,code:key,windowsVirtualKeyCode:key==='Tab'?9:27},pip); };
  const panel = `miniWatch.view.doc.getElementById('context-help')`;
  await evaluate(`window.durationPublication=structuredClone(liveValue);
    {const v=durationPublication.view,c=v.active_cards[0],r=c.rows[0];
    v.active_cards=[c];v.history_cards=[];v.history_state='observed';v.history_epoch=1;
    c.state='observed';c.session_id='duration-synthetic';c.focal_id=r.prompt.event_id='duration-prompt';
    Object.assign(r.prompt,{in_progress:true,execution_unverified:false,has_error:false,aborted:false});
    r.display_units={};r.display.watch_duration_ms='11s';r.model='<img src=x onerror=alert(1)>';
    c.session_summary.cost={known_ccost:'562',complete:false,observed_requests:3,priced_requests:2,
      display:{known_ccost:'?562',account_ccost:'562'},display_units:{
        credits:{known_ccost:'?562',account_ccost:'562'},usd:{known_ccost:'?$5.62',account_ccost:'$5.62'}}};
    window.durationUpdate=miniWatch.update.bind(miniWatch);miniWatch.update=()=>durationUpdate(durationPublication);
    miniWatch.update(durationPublication);window.durationRow=miniWatch.view.promptRows.get(c.session_id);}`);
  await command('Page.bringToFront',{},pip);
  for (const theme of ['classic','web']) for (const scheme of ['light','dark']) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},ownerSession);
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    for (const unit of ['credits','usd']) {
      const column=2;
      await key('Escape');await key('Tab');
      await evaluate(`ReportView.setUnit('${unit}');miniWatch.update(durationPublication);durationRow.cells[${column}].firstChild.focus()`);
      assert.equal(await evaluate('durationRow.cells[3].textContent'),unit==='usd'?'$5.62':'562');
      await until(`${panel}?.matches(':popover-open')`);
      const before=await evaluate(`(()=>{const p=${panel},s=p.querySelector('.context-help-running-duration'),w=miniWatch.window;
        window.durationSpan=s;return {line:s?.textContent,count:p.querySelectorAll('span').length,
        text:p.textContent,images:p.querySelectorAll('img').length,color:w.getComputedStyle(s).color,
        running:w.getComputedStyle(durationRow).color,normal:w.getComputedStyle(p).color};})()`);
      assert.equal(before.line,'Duration: 11s');assert.equal(before.count,1);assert.equal(before.images,0);
      assert.ok(before.text.includes('Main model: <img src=x onerror=alert(1)>'));
      assert.equal(before.color,before.running);assert.notEqual(before.color,before.normal);
      // CCost still owns delayed hover and immediate touch, not just keyboard help.
      await key('Escape');await evaluate('durationRow.cells[2].firstChild.blur()');
      const point=await evaluate(`(()=>{const r=durationRow.cells[2].firstChild.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
      assert.equal(await evaluate(`${panel}.matches(':popover-open')`),false);
      await until(`${panel}.matches(':popover-open')`);
      assert.equal(await evaluate(`${panel}.querySelector('span').textContent`),'Duration: 11s');
      await key('Escape');await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
      for(const type of ['touchStart','touchEnd'])await command('Input.dispatchTouchEvent',{
        type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},pip);
      await until(`${panel}.matches(':popover-open')`);
      await evaluate('durationRow.cells[2].firstChild.focus()');
      await evaluate(`{const selection=miniWatch.view.doc.getSelection();selection.selectAllChildren(durationSpan);
        durationPublication.view.active_cards[0].rows[0].display.watch_duration_ms='12s';miniWatch.update(durationPublication);}`);
      assert.equal(await evaluate(`${panel}.querySelector('span')===durationSpan && durationSpan.textContent==='Duration: 12s'`),true);
      assert.equal(await evaluate(`miniWatch.view.doc.activeElement===durationRow.cells[${column}].firstChild`),true);
      assert.equal(await evaluate(`miniWatch.view.doc.getSelection().toString()`),'Duration: 12s');
      await evaluate(`miniWatch.view.doc.getSelection().removeAllRanges()`);
      // Already-open help loses the cue for every non-running/untrusted outcome.
      for (const phase of ['completed','aborted','failed','unverified','historical','replacement']) {
        await evaluate(`{const v=durationPublication.view,c=(v.active_cards[0]||v.history_cards[0]),r=c.rows[0];
          v.active_cards=[c];v.history_cards=[];c.focal_id=r.prompt.event_id;
          Object.assign(r.prompt,{in_progress:true,execution_unverified:false,has_error:false,aborted:false});
          if('${phase}'==='completed')r.prompt.in_progress=false;
          if('${phase}'==='aborted')r.prompt.aborted=true;
          if('${phase}'==='failed')r.prompt.has_error=true;
          if('${phase}'==='unverified')r.prompt.execution_unverified=true;
          if('${phase}'==='historical'){v.active_cards=[];v.history_cards=[c];c.focal_id='';r.prompt.in_progress=false;}
          if('${phase}'==='replacement'){c.focal_id=r.prompt.event_id='replacement';r.prompt.in_progress=false;}
          miniWatch.update(durationPublication);}`);
        const state=await evaluate(`({open:${panel}.matches(':popover-open'),spans:${panel}.querySelectorAll('span').length,
          text:${panel}.textContent,focus:miniWatch.view.doc.activeElement===durationRow.cells[${column}].firstChild})`);
        assert.equal(state.open && !state.spans && state.text.includes('Duration: 12s'),true,phase+' '+JSON.stringify(state));
      }
      await evaluate(`{const c=durationPublication.view.active_cards[0],r=c.rows[0];
        r.prompt.in_progress=true;r.display.watch_duration_ms='11s';miniWatch.update(durationPublication);}`);
      await key('Escape');await evaluate('durationRow.cells[2].firstChild.blur()');
      const heading=`miniWatch.view.body.parentNode.tHead.rows[0].cells[3].firstChild`;
      for(const method of ['focus','hover','touch']) {
        await key('Escape');await evaluate('miniWatch.view.doc.activeElement.blur()');
        await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
        const point=await evaluate(`(()=>{const r=${heading}.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
        if(method==='focus') { await key('Tab');await evaluate(`${heading}.focus()`); }
        if(method==='hover')await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
        if(method==='touch')for(const type of ['touchStart','touchEnd'])await command('Input.dispatchTouchEvent',{
          type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},pip);
        await until(`${panel}.matches(':popover-open')`).catch(async error=>{
          const state=await evaluate(`({method:'${method}',theme:'${theme}',scheme:'${scheme}',unit:'${unit}',
            focus:miniWatch.view.doc.activeElement?.tagName,heading:${heading}.outerHTML,
            hovered:${heading}.matches(':hover'),windowFocus:miniWatch.view.doc.hasFocus(),
            panel:${panel}.outerHTML})`);
          throw new Error(error.message+' '+JSON.stringify(state));
        });
        assert.equal(await evaluate(`${panel}.textContent`),'The entire session’s reference cost, including attributed linked subagents.');
      }
      await key('Escape');await key('Tab');
      await evaluate('durationRow.cells[2].firstChild.focus()');await key('Tab');
      assert.equal(await evaluate('miniWatch.view.doc.activeElement===durationRow.cells[4]'),true,'Tab skips plain Total');
      await key('Escape');await evaluate('miniWatch.view.doc.activeElement.blur()');
      const total=await evaluate(`(()=>{const n=durationRow.cells[3].firstChild,r=n.getBoundingClientRect();return {
        x:r.x+r.width/2,y:r.y+r.height/2,tab:n.tabIndex,help:n.classList.contains('help-value'),
        title:n.hasAttribute('title'),role:n.getAttribute('role'),dead:'totalCostHelp' in durationRow};})()`);
      assert.equal(total.tab,-1);assert.equal(total.help,false);assert.equal(total.title,false);
      assert.equal(total.role,null);assert.equal(total.dead,false);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:total.x,y:total.y},pip);
      // A negative hover assertion spans more than the shared 600ms help delay.
      await evaluate('new Promise(resolve=>miniWatch.window.setTimeout(resolve,700))');
      assert.equal(await evaluate(`${panel}.matches(':popover-open')`),false);
      await evaluate('durationRow.cells[3].firstChild.focus()');
      for(const type of ['mousePressed','mouseReleased'])await command('Input.dispatchMouseEvent',{
        type,button:'left',clickCount:1,x:total.x,y:total.y},pip);
      for(const type of ['touchStart','touchEnd'])await command('Input.dispatchTouchEvent',{
        type,touchPoints:type==='touchStart'?[{x:total.x,y:total.y,id:1,radiusX:1,radiusY:1,force:1}]:[]},pip);
      assert.equal(await evaluate(`${panel}.matches(':popover-open')`),false);
      assert.equal(await evaluate('miniWatch.view.doc.activeElement===durationRow.cells[3].firstChild'),false);
      await evaluate(`{const n=durationRow.cells[3].firstChild,s=miniWatch.view.doc.getSelection();s.selectAllChildren(n);}`);
      assert.equal(await evaluate('miniWatch.view.doc.getSelection().toString()===durationRow.cells[3].textContent'),true);
      await evaluate('miniWatch.view.doc.getSelection().removeAllRanges()');
      assert.deepEqual(await evaluate(`(()=>{const c=durationPublication.view.active_cards[0].session_summary.cost;
        return [c.known_ccost,c.complete,c.observed_requests,c.priced_requests];})()`),['562',false,3,2]);
    }
  }
  // Corrected evidence and source availability update the same plain Total, even
  // when the native window is narrow. The CCost value remains independently priced.
  await evaluate('miniWatch.window.resizeTo(280,550)',true);
  for(const [state,cost,expected] of [
    ['refreshing',{display:{account_ccost:'563'},observed_requests:3,priced_requests:2},'563'],
    ['observed',{display:{account_ccost:'—'},observed_requests:3,priced_requests:0},'N/A'],
    ['observed',{display:{account_ccost:'0'},observed_requests:0,priced_requests:0},'0'],
    ['unavailable',null,'N/A'],['loading',null,'Loading…']]) {
    await evaluate(`{const s=durationPublication.view.active_cards[0].session_summary;
      s.state=${JSON.stringify(state)};s.cost=${JSON.stringify(cost)};miniWatch.update(durationPublication);}`);
    assert.equal(await evaluate('durationRow.cells[3].textContent'),expected);
    assert.equal(await evaluate('durationRow.cells[3].firstChild.className'),'mini-cost-value');
  }
  await key('Escape');await evaluate(`miniWatch.update=durationUpdate;delete window.durationUpdate;ReportView.setUnit('credits');miniWatch.update(liveValue)`);
  checks.push('CCost keyboard/delayed-hover/touch help retains yellow running Duration, ticking span/focus/selection, literal model text and completion/abort/error/unverified/history/replacement transitions; Total is plain/selectable, skipped by Tab and has no focus/click/touch help or dead prompt details; exact Total heading help; Classic/Web light/dark and Credits/USD');
};
