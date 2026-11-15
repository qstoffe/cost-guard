// Synthetic source groups through actual Running Watch and retained Mini history.
const assert = require('node:assert/strict');
module.exports = async function costGroups({command,evaluate,until,owner,mini,checks,layouts}) {
  assert.equal(await evaluate(owner,`document.querySelector('.watch-earlier,.watch-history')`),null);
  assert.equal(await evaluate(mini,`!!document.querySelector('.mini-prompts tr[data-id="past"]')`),true);
  const targets = [[owner,'.watch-active tbody td:nth-child(6) .help-value'],
    [mini,'.mini-prompts tr[data-id="past"] td:nth-child(3) .help-value']];
  for(const [id,selector] of targets) {
    for(const unit of ['credits','usd']) {
      await evaluate(owner,`ReportView.setUnit('${unit}',current.watch.root);miniWatch.render()`);
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
      await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
      await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
      const text=await evaluate(id,`document.querySelector('#context-help').textContent`);
      assert.match(text,/^Prompt #\d+\nSession Models:\n• fixture\/main-model — High — \(.+\)\n\nSub Agents:\n• fixture\/child-model — Low — \(.+\)(?:\n\nDuration: .+)?$/);
      assert.ok(text.includes(unit==='usd'?'($0.25)':'(25 Credits)'));
      assert.doesNotMatch(text,/Partial cost coverage|Subtotal:|Calls:|CCost:|Model \d|Sub Agent \d/);
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
      await evaluate(id,`document.activeElement?.blur()`);
    }
  }
  await evaluate(owner,`ReportView.setUnit('credits',current.watch.root);miniWatch.render()`);
  // A real stationary pointer must survive repeated prompt publications.
  await command('Page.bringToFront',{},owner);
  await evaluate(owner,`document.querySelector('.watch-active tbody td:nth-child(6) .help-value').scrollIntoView({block:'center',inline:'center'})`);
  const point=await evaluate(owner,`(()=>{const r=document.querySelector('.watch-active tbody td:nth-child(6) .help-value').getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},owner);
  await until(owner,`document.querySelector('#context-help')?.matches(':popover-open')`);
  assert.equal(await evaluate(owner,`(()=>{
    const target=document.querySelector('.watch-active tbody td:nth-child(6) .help-value'),p=structuredClone(liveValue);
    for(let i=0;i<10;i++){p.view.active_cards[0].rows[0].watch_duration_ms++;current.watch.update(p);}
    return target===document.querySelector('.watch-active tbody td:nth-child(6) .help-value')&&target.isConnected;
  })()`),true);
  assert.equal(await evaluate(owner,`document.querySelector('#context-help').matches(':popover-open')`),true);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},owner);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},owner);
  const stable=await evaluate(owner,`(()=>{
    document.activeElement?.blur();const real=Date.now,base=real(),p=structuredClone(liveValue);
    const prior=Object.fromEntries(['observations','publication','epoch','receivedAt','sourceScope'].map(key=>[key,miniWatch[key]]));
    miniWatch.observations=new prior.observations.constructor();let offset=0;Date.now=()=>base+offset;
    const amounts=[];
    try {
      for(offset=0;offset<=241000;offset+=1000) {
        p.view.now_ms=liveValue.view.now_ms+offset;
        for(const card of p.view.active_cards){card.session_summary.state='checking';card.rows[0].prompt.calls++;}
        current.watch.update(p);miniWatch.update(p);
        if(offset%60000===0||offset===241000)amounts.push({
          full:[...current.watch.cards.values()].map(c=>c.costLabel.textContent),
          mini:[...miniWatch.view.body.querySelectorAll('tr[data-id]')].map(n=>[n.children[2].textContent,n.children[3].textContent])});
      }
      return amounts;
    } finally {Date.now=real;Object.assign(miniWatch,prior);current.watch.update(liveValue);miniWatch.update(liveValue);}
  })()`);
  for(const sample of stable) {
    assert.ok(sample.full.length&&sample.mini.length);
    for(const amount of sample.full)assert.equal(amount,'4583');
    for(const amounts of sample.mini)assert.deepEqual(amounts,['33','4583']);
  }
  layouts.push({case:'241-second-retained-totals',samples:stable.length});
  // All 30 distinct effort groups are displayed, not the diagnostic 24-part cap.
  for(const width of [1280,360]) for(const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:550,deviceScaleFactor:1,mobile:false},owner);
    await evaluate(owner,`miniWatch.window.resizeTo(${width===360?360:560},550)`,true);
    await evaluate(mini,`document.documentElement.style.zoom='${zoom}'`);
    await evaluate(owner,`(()=>{
      document.activeElement?.blur();document.documentElement.style.zoom='${zoom}';
      const p=structuredClone(liveValue);
      for(const card of [...p.view.active_cards,...p.view.history_cards])
        for(const row of card.rows)row.prompt=structuredClone(p.probe_cost_groups);
      current.watch.update(p);miniWatch.update(p);
    })()`);
    for(const [id,selector] of targets) {
      await command('Page.bringToFront',{},id);
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
      await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
      await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
      const bounds=await evaluate(id,`(()=>{
        const n=document.querySelector('#context-help'),r=n.getBoundingClientRect();n.scrollTop=n.scrollHeight;
        return{text:n.textContent,left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:innerWidth,height:innerHeight,
          scroll:n.scrollHeight>n.clientHeight&&n.scrollTop>0};
      })()`);
      assert.equal(bounds.text.match(/• (?:fixture|second)\/model-\d — Effort \d+ — \(25 Credits\)/g)?.length,30);
      const [main,agents]=bounds.text.split('\n\nSub Agents:\n');
      assert.equal(main.match(/• /g)?.length,2);
      assert.equal(agents.match(/• /g)?.length,28);
      assert.match(main,/• fixture\/model-0 — Effort 0 — \(25 Credits\)/);
      assert.match(main,/• second\/model-1 — Effort 1 — \(25 Credits\)/);
      assert.doesNotMatch(bounds.text,/not shown|Known subtotal|Total CCost|Partial cost coverage/);
      const {text,...geometry}=bounds;
      assert.ok(bounds.scroll&&bounds.left>=0&&bounds.top>=0&&bounds.right<=bounds.width&&bounds.bottom<=bounds.height,JSON.stringify(geometry));
      layouts.push({case:'30-cost-groups',surface:id===owner?'Running':'Mini Earlier',zoom,...geometry});
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
      await evaluate(id,`document.activeElement?.blur()`);
    }
  }
  await evaluate(owner,`document.documentElement.style.zoom='';current.watch.update(liveValue);miniWatch.update(liveValue)`);
  await evaluate(mini,`document.documentElement.style.zoom=''`);
  await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
  checks.push('Full Earlier intentionally absent; actual Running and retained Mini Earlier compact groups, both units, no boilerplate');
  checks.push('Stationary hovered Running target survives advancing updates; Full/Mini totals retain 241 virtual seconds; all 30 distinct effort groups scroll/clamp at narrow/150% layouts');
};
