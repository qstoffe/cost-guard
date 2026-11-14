// Synthetic canonical-shaped publications in a real headless Document PiP.
const assert=require('node:assert/strict');
module.exports=async function({evaluate,command,sessionId,pip,layouts,checks}) {
  await evaluate(`window.colorBase=structuredClone(liveValue);window.colorUpdate=miniWatch.update.bind(miniWatch);
    miniWatch.update=()=>{};window.colorPublish=(phase,severity='none',guidance='ready',state='ready-current')=>{
      const p=structuredClone(colorBase),v=p.view,c=v.active_cards[0],r=c.rows[0],ctx=c.session_summary.context;
      v.now_ms=Date.now();c.observed_at_ms=v.now_ms;c.session_id='color-session';c.title='Color fixture';
      c.focal_id=r.prompt.event_id=phase==='new'?'next-prompt':'color-prompt';
      Object.assign(r.prompt,{in_progress:['running','new','unverified'].includes(phase),
        execution_unverified:phase==='unverified',completed_successfully:phase==='finished'||phase==='earlier',
        aborted:phase==='error',has_error:phase==='error',completed_at_ms:v.now_ms-1000});
      Object.assign(ctx,{context_scope:'color-source',context_epoch:'color-epoch',context_state:state,
        watch_next_context_tokens:state==='ready-current'?230000:null,
        display:{watch_next_context_tokens:state==='ready-current'?'230k':'N/A'},
        warning:{severity,guidance_state:guidance,multiplier:'2.4',
          text:'[Price threshold >200k exceeded]',display:{warning_cost:'(2.4x more expensive)'}}});
      r.live_context=structuredClone(ctx);
      v.active_cards=phase==='earlier'?[]:[c];v.history_cards=phase==='earlier'?[c]:[];
      if(phase==='earlier')c.focal_id='';
      v.history_state='observed';v.history_epoch=1;
      const before=JSON.stringify(p);colorUpdate(p);
      return before===JSON.stringify(p);
    };`);
  const publish=async(...args)=>assert.equal(await evaluate(`colorPublish(...${JSON.stringify(args)})`),true,'source wire is immutable');
  const read=()=>evaluate(`(()=>{const w=miniWatch.window,v=miniWatch.view,r=v.promptRows.get('color-session'),style=n=>w.getComputedStyle(n);
    const token=name=>{const n=v.doc.createElement('span');n.style.color='var('+name+')';v.root.append(n);
      const color=style(n).color;n.remove();return color;};
    return {running:token('--watch-running'),normal:token('--ink'),error:token('--error'),success:token('--watch-success'),
      cls:r.className,values:[...r.cells].map(c=>[c,...c.querySelectorAll('*')].map(n=>style(n).color)),
      text:[...r.cells].map(c=>c.textContent),help:r.contextHelp,tab:r.cells[4].tabIndex,
      exceeded:r.cells[4].classList.contains('mini-context-exceeded'),same:r===window.colorRow,
      headers:[...v.doc.querySelectorAll('th')].map(n=>style(n).color)};})()`);
  const help='Price threshold >200k exceeded · 2.4x more expensive';
  for(const theme of ['classic','web'])for(const scheme of ['light','dark']) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},sessionId);
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    await publish('running');await evaluate(`window.colorRow=miniWatch.view.promptRows.get('color-session')`);
    const initial=await read(),headers=initial.headers;
    for(const phase of ['running','finished','earlier','new','unverified','error']) {
      for(const [severity,guidance,state,eligible] of [
        ['none','ready','ready-current',false],['approaching','ready','ready-current',false],
        ['exceeded','ready','ready-current',true],['exceeded','pending','ready-current',false],
        ['exceeded','refreshing','ready-current',false],['exceeded','unavailable','ready-current',false],
        ['exceeded','ready','pending',false],['exceeded','ready','invalidated',false]]) {
        await publish(phase,severity,guidance,state);
        const value=await read(),running=phase==='running'||phase==='new';
        const other=running?value.running:phase==='finished'?value.success:phase==='error'?value.error:value.normal;
        assert.equal(value.same,true);assert.equal(value.values.length,5);
        value.values.forEach((colors,index)=>assert.ok(colors.every(c=>c===(index===4&&!running?(eligible?value.error:value.normal):other)),
          `${theme}/${scheme}/${phase}/${severity}/${guidance}/${state}: cell ${index} ${JSON.stringify(value)}`));
        assert.equal(value.exceeded,eligible);assert.equal(value.help,eligible?help:'');assert.equal(value.tab,eligible?0:-1);
        assert.equal(value.cls==='mini-running',running);assert.deepEqual(value.headers,headers);
        assert.deepEqual(value.text.slice(1,4),initial.text.slice(1,4),'session and both cost scopes are unchanged');
        if(state==='ready-current')assert.equal(value.text[4],'230k');
        if(state==='invalidated')assert.equal(value.text[4],'N/A');
        await evaluate('miniWatch.render();miniWatch.syncTheme()');
        assert.deepEqual((await read()).values,value.values,'refresh does not retain obsolete foreground');
      }
    }
    await publish('running','none','ready','invalidated');
    await publish('new','none','pending','pending');
    const unknown=await read();assert.equal(unknown.text[4],'N/A');
    assert.ok(unknown.values.flat().every(color=>color===unknown.running),'unseeded pending Ctx is yellow too');
    assert.equal(unknown.help,'');assert.equal(unknown.tab,-1);
    // Same warning remains accessible through native keyboard, hover and touch in both categories.
    for(const phase of ['running','earlier']) {
      await publish(phase,'exceeded');const before=await read();
      const panel=`miniWatch.view.doc.getElementById('context-help')`;
      await command('Page.bringToFront',{},pip);
      const key=async key=>{for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',
        {type,key,code:key,windowsVirtualKeyCode:key==='Tab'?9:27},pip);};
      const dismiss=async()=>{await key('Escape');await evaluate('colorRow.cells[4].blur()');
        await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);};
      const point=await evaluate(`(()=>{const r=colorRow.cells[4].getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      await dismiss();await key('Tab');await evaluate('colorRow.cells[3].firstChild.focus()');await key('Tab');
      assert.equal(await evaluate(`${panel}?.matches(':popover-open')`),true);
      assert.equal(await evaluate(`${panel}.textContent`),help);
      await dismiss();
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
      await evaluate('new Promise(resolve=>setTimeout(resolve,700))');
      assert.equal(await evaluate(`${panel}.textContent`),help);assert.equal(await evaluate(`${panel}.matches(':popover-open')`),true);
      await dismiss();
      for(const type of ['touchStart','touchEnd'])await command('Input.dispatchTouchEvent',
        {type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},pip);
      assert.equal(await evaluate(`${panel}.matches(':popover-open')`),true);
      assert.equal(await evaluate(`${panel}.textContent`),help);
      assert.deepEqual((await read()).text,before.text);await dismiss();
    }
    layouts.push({case:`context-precedence-${theme}-${scheme}`,sample:await read()});
  }
  await evaluate('miniWatch.update=colorUpdate;miniWatch.update(liveValue);delete window.colorPublish;delete window.colorBase;delete window.colorRow;delete window.colorUpdate');
  checks.push('192 native PiP publication cases: all five cell/descendant computed foregrounds; normal/approaching/exceeded/pending/refreshing/unavailable/invalidated context, Running/finished/Earlier/new Running/unverified/error; Classic/Web light/dark; immutable source, keyed identity, help semantics, refresh, header isolation and keyboard/hover/touch warning help');
};
