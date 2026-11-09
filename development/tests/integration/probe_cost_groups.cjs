// Synthetic grouped wire evidence through real Watch/Mini DOM and shipped help.
const assert = require('node:assert/strict');
module.exports = async function costGroups({command,evaluate,until,owner,mini,checks,layouts}) {
  await evaluate(owner,`document.activeElement?.blur();document.querySelector('.watch-earlier').open=true`);
  for (const table of ['watch-active','watch-history']) {
    const facts = await evaluate(owner,`(() => {
      const c=document.querySelector('.${table} tbody tr'),p=liveValue.view.${table==='watch-active'?'active_cards':'history_cards'}[0].rows[0].prompt;
      return {parts:p.cost_detail.parts.map(g=>({role:g.role,agents:g.agent_count,calls:g.calls})),
        mixHelp:!!c.children[7].querySelector('.help-value'),calls:p.display.calls_help};
    })()`);
    assert.deepEqual(facts.parts,[{role:'main',agents:0,calls:2},{role:'subagents',agents:2,calls:2}]);
    assert.equal(facts.mixHelp,false);
    assert.match(facts.calls,/Subagents — Child Model · Low \(2 agents\): 2\nTotal Calls: 4/);
    await evaluate(owner,`document.querySelector('.${table} tbody td:nth-child(7) .help-value').focus()`);
    await until(owner,`document.querySelector('#context-help')?.matches(':popover-open')`);
    assert.match(await evaluate(owner,`document.querySelector('#context-help').textContent`),/Total Calls: 4/);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},owner);
  }
  await command('Page.bringToFront',{},owner);
  await evaluate(owner,`document.activeElement?.blur();document.querySelector('.watch-active tbody td:nth-child(6) .help-value').scrollIntoView({block:'center',inline:'center'})`);
  const point=await evaluate(owner,`(() => {const r=document.querySelector('.watch-active tbody td:nth-child(6) .help-value').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},owner);
  await until(owner,`document.querySelector('#context-help')?.matches(':popover-open')`);
  assert.equal(await evaluate(owner,`(() => {
    const target=document.querySelector('.watch-active tbody td:nth-child(6) .help-value'),p=structuredClone(liveValue);
    for(let i=0;i<10;i++){p.view.active_cards[0].rows[0].watch_duration_ms++;current.watch.update(p);}
    return target===document.querySelector('.watch-active tbody td:nth-child(6) .help-value')&&target.isConnected;
  })()`),true);
  assert.equal(await evaluate(owner,`document.querySelector('#context-help').matches(':popover-open')`),true,
    'active metric updates must not tear down hovered cost evidence');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},owner);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},owner);
  const sameModel=await evaluate(owner,`(() => {
    document.activeElement?.blur();const p=structuredClone(liveValue);
    for(const card of [...p.view.active_cards,...p.view.history_cards]) for(const row of card.rows) {
      row.prompt=structuredClone(liveValue.probe_same_model);
    }
    current.watch.update(p);
    return [...document.querySelectorAll('.watch-card tbody td:nth-child(4)')].map(cell=>({
      label:cell.textContent,help:!!cell.querySelector('.help-value'),aria:cell.children[0].getAttribute('aria-label')}));
  })()`);
  assert.ok(sameModel.length>=2);
  for(const cell of sameModel) {assert.equal(cell.help,true);assert.equal(cell.label,'Model*');assert.match(cell.aria,/Linked subagents participated \(2\)/);}
  await evaluate(owner,`document.querySelector('.watch-active tbody td:nth-child(4) .help-value').focus()`);
  await until(owner,`document.querySelector('#context-help')?.matches(':popover-open')`);
  assert.match(await evaluate(owner,`document.querySelector('#context-help').textContent`),/Main prompt — Main Model · High[\s\S]*Subagents — Main Model · Low/);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},owner);
  const stable=await evaluate(owner,`(() => {
    const real=Date.now,base=real(),p=structuredClone(liveValue),history=structuredClone(p.view.history_cards);
    let offset=0;Date.now=()=>base+offset;
    const amounts=[];
    try {
      for(offset=0;offset<=241000;offset+=1000) {
        p.view.now_ms=liveValue.view.now_ms+offset;
        for(const card of p.view.active_cards) {card.session_summary.state='checking';card.rows[0].prompt.calls++;}
        current.watch.earlier.open=offset%2000===0;
        if(offset===120000)p.view.history_cards=[];
        if(offset===121000)p.view.history_cards=history;
        current.watch.update(p);miniWatch.update(p);
        if(offset%60000===0||offset===241000) amounts.push({at:offset,
          full:[...current.watch.cards.values()].map(c=>({amount:c.costLabel.textContent,note:c.costStatus.textContent})),
          mini:[...miniWatch.view.root.querySelectorAll('tbody .mini-cost-value')].map(n=>n.textContent)});
      }
      const unknown=structuredClone(p);unknown.view.active_cards=unknown.view.active_cards.slice(0,1);
      unknown.view.active_cards[0].session_id='unknown-total';
      unknown.view.active_cards[0].session_summary={cost:null,context:null,state:'loading'};
      current.watch.update(unknown);miniWatch.update(unknown);
      const loading={full:[...current.watch.cards.values()].find(c=>c.value.session_id==='unknown-total').costLabel.textContent,
        mini:miniWatch.view.body.querySelector('tr[data-id="unknown-total"] .mini-cost-value').textContent};
      return {amounts,loading};
    } finally {Date.now=real;document.activeElement?.blur();current.watch.earlier.open=true;current.watch.update(liveValue);miniWatch.update(liveValue);}
  })()`);
  for(const sample of stable.amounts) {
    for(const total of sample.full) {assert.equal(total.amount,'4583');assert.equal(total.note,'');}
    assert.ok(sample.mini.length>0,'paired Mini cost targets must actually be present');
    for(const total of sample.mini) assert.equal(total,'33 (4583)');
  }
  assert.deepEqual(stable.loading,{full:'Loading…',mini:'33 (Loading…)'});
  layouts.push({case:'241-second-stable-totals',...stable});
  for(const width of [1280,360]) for(const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
    await evaluate(owner,`(() => {
      document.activeElement?.blur();document.documentElement.style.zoom='${zoom}';
      const p=structuredClone(liveValue);for(const card of [...p.view.active_cards,...p.view.history_cards])
        for(const row of card.rows)row.prompt=structuredClone(p.probe_cost_groups);
      current.watch.update(p);current.watch.earlier.open=true;
    })()`);
    for(const table of ['watch-active','watch-history']) {
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},owner);
      await evaluate(owner,`document.querySelector('.${table} tbody td:nth-child(6) .help-value').focus()`);
      await until(owner,`document.querySelector('#context-help')?.matches(':popover-open')`);
      const bounds=await evaluate(owner,`(() => {
        const n=document.querySelector('#context-help'),r=n.getBoundingClientRect();n.scrollTop=n.scrollHeight;
        return {text:n.textContent,left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:innerWidth,height:innerHeight,
          scroll:n.scrollHeight>n.clientHeight&&n.scrollTop>0};
      })()`);
      assert.match(bounds.text,/6 additional role\/model\/effort groups not shown[\s\S]*Known subtotal: 150[\s\S]*Total CCost: 750/);
      assert.ok(bounds.scroll&&bounds.left>=0&&bounds.top>=0&&bounds.right<=width&&bounds.bottom<=900);
      const {text,...geometry}=bounds;layouts.push({case:'bounded-30-cost-groups',table,zoom,...geometry});
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},owner);
      await evaluate(owner,`document.activeElement?.blur()`);
    }
  }
  await evaluate(owner,`document.documentElement.style.zoom='';current.watch.update(liveValue)`);
  await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
  checks.push('Backend-aggregated two-agent cost/Calls groups in both real Full Watch tables; no Token Mix cell help; single-model linked work opens recorded effort help and retains accessible star; 241 virtual seconds of other-prompt publications/disclosure/eviction/re-entry and unknown Loading parity in real Full/Mini DOM');
  checks.push('Advancing active row publications retain an open hovered cost target; 30 backend-projected groups preserve omitted cost evidence and real scroll/clamped bounds in both tables at 1280/360 widths and 100%/150% zoom');
};
