// Real elapsed time and native CDP pointer input; no clock/selector emulation.
const assert=require('node:assert/strict'),fs=require('node:fs/promises');
module.exports=async ({command,evaluate,until,owner,mini,checks,layouts,output,fixture})=>{
  const mouse=(id,x,y)=>command('Input.dispatchMouseEvent',{type:'mouseMoved',x,y},id);
  const open=async(id,selector)=>{
    await command('Page.bringToFront',{},id);
    await evaluate(id,`document.activeElement?.blur()`);
    // Mini uses the opener's controller, not a second script global in PiP.
    await evaluate(owner,id===mini?`ContextHelp.dismiss(miniWatch.window.document.body)`:
      `ContextHelp.dismiss(document.body)`);
    await mouse(id,1,1);
    const point=await evaluate(id,`(()=>{const n=document.querySelector(${JSON.stringify(selector)});
      if(!n)throw new Error('Missing stationary target: '+${JSON.stringify(selector)});
      n.scrollIntoView({block:'center',inline:'center'});const r=n.getBoundingClientRect();
      return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await mouse(id,point.x,point.y);
    await until(id,`document.getElementById('context-help')?.matches(':popover-open')`);
    return point;
  };
  // Reproduce the old hard cutoff separately in the actual PiP document.
  assert.ok(process.env.COST_GUARD_BASELINE_HELP,'required explicit old-base RED source');
  assert.match(process.env.COST_GUARD_BASELINE_REVISION || '',/^[a-f0-9]{40}$/);
  {
    const source=await fs.readFile(process.env.COST_GUARD_BASELINE_HELP,'utf8');
    const old=source.includes('panel.hidden || !panel.isConnected || now() >= hoverDeadline');
    const fixed=!old&&source.includes('const state = hoverState(pointerTarget);')&&
      source.includes('else if (state === null && now() >= hoverDeadline)')&&
      source.includes('if (state === false) exit(target);')&&source.includes('}, HOVER_CHECK);');
    assert.ok(old||fixed,'Unrecognized baseline watchdog; RED applicability is unknown');
    if(old) {
      await evaluate(mini,`(()=>{${source.replace("panel.id = 'context-help'","panel.id = 'baseline-help'")}
        const b=ContextHelp.button('Original 30-second cutoff','Baseline stationary reading',document);
        b.id='baseline-trigger';document.body.append(b);b.scrollIntoView({block:'center'});})()`);
      await command('Page.bringToFront',{},mini);await mouse(mini,1,1);
      const point=await evaluate(mini,`(()=>{const r=document.getElementById('baseline-trigger').getBoundingClientRect();
        return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
      await mouse(mini,point.x,point.y);
      await until(mini,`document.getElementById('baseline-help')?.matches(':popover-open')`);
      await new Promise(resolve=>setTimeout(resolve,31000));
      assert.equal(await evaluate(mini,`document.getElementById('baseline-help').hidden &&
        document.getElementById('baseline-trigger').matches(':hover')`),true,'RED: actual stationary hover hit the old lease');
      await evaluate(mini,`document.getElementById('baseline-trigger').remove();document.getElementById('baseline-help').remove()`);
      checks.push('RED: default-base help closes actual PiP stationary hover after 30 seconds, while native :hover remains true');
      layouts.push({case:'baseline-red-pip',revision:process.env.COST_GUARD_BASELINE_REVISION});
    } else {
      checks.push('RED_NOT_APPLICABLE: verified base already contains the recognized fixed watchdog; no old-base RED claimed');
      layouts.push({case:'baseline-red-not-applicable',revision:process.env.COST_GUARD_BASELINE_REVISION,
        reason:'recognized fixed watchdog in verified base'});
    }
  }
  await evaluate(owner,`window.stationaryRefresh=setInterval(()=>{
    const c=liveValue.view.active_cards[0],p=c.rows[0].prompt;
    liveValue.view.now_ms+=3000;
    p.display.ccost=String(30+(window.stationaryTicks=(window.stationaryTicks||0)+1)%10);
    if(p.display_units?.credits)p.display_units.credits.ccost=p.display.ccost;
    const a=liveValue.view.accounts.accounts[0];
    a.primary.quota.quota_display.used.percent=(20+stationaryTicks%10)+'%';
    a.primary.quota.quota_display.used.account_percent=a.primary.quota.quota_display.used.percent;
    current.watch.update(liveValue);miniWatch.update(liveValue);
  },3000)`);
  const scenarios=[
    [mini,'.mini-accounts .help-value'],[mini,'.mini-activity'],
    [mini,'td:nth-child(3) .mini-cost-value'],[mini,'td:nth-child(4) .mini-cost-value'],
    [mini,'.mini-context-exceeded'],[mini,'.mini-summary'],
    [owner,'.watch-subscription .metric-value > .help-value'],
    [owner,'.watch-active tbody td:first-child .help-value'],
    [owner,'.watch-active tbody td:nth-child(6) .help-value'],
    [owner,'.watch-active .watch-session-summary > div:nth-child(2) .help-value'],
    [owner,'.watch-active .watch-session-summary > div:first-child .help-value'],
    [owner,'.watch-active th:nth-child(6) button']];
  try {
    for(const [index,[id,selector]] of scenarios.entries()) {
      const point=await open(id,selector);
      await evaluate(id,`window.stationary={started:performance.now(),events:0,samples:[],target:document.querySelector(${JSON.stringify(selector)})};
        window.stationaryInput=()=>stationary.events++;
        document.addEventListener('pointermove',stationaryInput,true);
        window.stationarySample=setInterval(()=>{
          const panel=document.getElementById('context-help'),target=stationary.target;
          const triggerHovered=target.matches(':hover'),panelHovered=panel.matches(':hover');
          const hit=document.elementFromPoint(${point.x},${point.y});
          stationary.samples.push({elapsed:performance.now()-stationary.started,
            open:panel.matches(':popover-open'),triggerHovered,panelHovered,connected:target.isConnected,
            hit:target.contains(hit)?'trigger':panel.contains(hit)?'panel':'other'});
        },1000)`);
      await new Promise(resolve=>setTimeout(resolve,61000));
      const state=await evaluate(id,`clearInterval(stationarySample);document.removeEventListener('pointermove',stationaryInput,true);
        ({elapsed:performance.now()-stationary.started,events:stationary.events,samples:stationary.samples})`);
      assert.ok(state.elapsed>=60000);
      assert.equal(state.events,0,'no pointer input while reading');
      assert.ok(state.samples.length>=55);
      const failed=state.samples.find(value=>!value.open||!value.connected||
        !(value.triggerHovered&&value.hit==='trigger'||value.panelHovered&&value.hit==='panel'));
      if(failed) {
        const error=new Error('Stationary native hover sample failed');
        error.probeCase='stationary-'+(index+1);
        error.observation={case:index+1,document:id===mini?'pip':'full-watch',selector,
          elapsed:Math.round(state.elapsed),pointerEvents:state.events,samples:state.samples.length,
          firstFailure:failed,last:state.samples.at(-1),
          closed:state.samples.filter(value=>!value.open).length,
          unhovered:state.samples.filter(value=>!value.triggerHovered&&!value.panelHovered).length,
          otherHit:state.samples.filter(value=>value.hit==='other').length,
          disconnected:state.samples.filter(value=>!value.connected).length};
        throw error;
      }
      layouts.push({case:'stationary-61s',document:id===mini?'pip':'full-watch',selector,...state});
      if(id===mini) {
        const image=await command('Page.captureScreenshot',{format:'png'},mini);
        await fs.writeFile(output.replace(/\.json$/,`-stationary-${index}.png`),
          Buffer.from(image.data,'base64'));
      }
      await mouse(id,1,1);await until(id,`document.getElementById('context-help').hidden`);
    }
  } finally {
    await evaluate(owner,'clearInterval(stationaryRefresh)');
    const holds=layouts.filter(value=>value.case==='stationary-61s');
    console.log('::notice title=Cost Guard Web stationary::'+JSON.stringify({
      outcome:holds.length===12?'PASS':'PARTIAL',holds:holds.map(value=>({
        document:value.document,selector:value.selector,elapsed:Math.round(value.elapsed),
        samples:value.samples.length,pointerEvents:value.events,
        triggerSamples:value.samples.filter(sample=>sample.triggerHovered).length,
        panelSamples:value.samples.filter(sample=>sample.panelHovered).length}))}));
  }
  for(const theme of ['classic','web'])for(const scheme of ['light','dark']) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},owner);
    await evaluate(owner,`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    await evaluate(owner,'miniWatch.window.resizeTo(360,700)',true);
    await open(mini,'.mini-summary');
    const shape=await evaluate(mini,`(()=>{const p=document.getElementById('context-help'),r=p.getBoundingClientRect();
      return {width:innerWidth,height:innerHeight,documentOverflow:document.documentElement.scrollWidth>innerWidth+1,
        panel:[r.left,r.top,r.right,r.bottom],cssZoom:document.documentElement.currentCSSZoom};})()`);
    assert.equal(shape.documentOverflow,false);
    assert.ok(shape.panel[0]>=0&&shape.panel[1]>=0&&shape.panel[2]<=shape.width+1&&shape.panel[3]<=shape.height+1);
    layouts.push({case:'native-125-percent-narrow',theme,scheme,...shape});
    const image=await command('Page.captureScreenshot',{format:'png'},mini);
    await fs.writeFile(output.replace(/\.json$/,`-${theme}-${scheme}.png`),Buffer.from(image.data,'base64'));
  }
  checks.push('GREEN: twelve actual 61-second stationary native hovers across PiP and Full Watch, with 3-second in-place refresh and real normal exits');
  await mouse(mini,1,1);
  const size=await evaluate(owner,'[miniWatch.window.outerWidth,miniWatch.window.outerHeight]');
  for(const count of [0,1,3,5]) {
    await fixture(`density-${count}-6`);
    await until(owner,`miniWatch.view.promptRows.size===${count}`);
    const state=await evaluate(owner,`(()=>{const w=miniWatch.window,v=miniWatch.view;return {
      rows:v.promptRows.size,columns:v.body.parentNode.tHead.rows[0].cells.length,
      overflow:v.doc.documentElement.scrollWidth>w.innerWidth+1,
      size:[w.outerWidth,w.outerHeight],accounts:v.lines.size};})()`);
    assert.deepEqual(state.size,size,'Live does not resize native PiP');
    assert.equal(state.overflow,false);assert.equal(state.columns,5);assert.equal(state.accounts,6);
    layouts.push({case:'native-density-125-percent',...state});
  }
  await evaluate(owner,'window.retiredHelpDocument=miniWatch.window.document;miniWatch.close()');
  await until(owner,'!miniWatch.window');
  await evaluate(owner,'miniWatch.toggle()',true);
  await until(owner,'!!miniWatch.view && miniWatch.window.document!==retiredHelpDocument');
  assert.equal(await evaluate(owner,`retiredHelpDocument.getElementById('context-help')?.hidden`),true);
  checks.push('Actual PiP 0/1/3/5-row narrow native-125% matrix, stable native size through SSE, and close/reopen retires old help document');
  const targets=await command('Target.getTargets');
  for(const target of targets.targetInfos.filter(value=>value.type==='page')) {
    const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
    if(await evaluate(attached.sessionId,`!!document.querySelector('.mini-watch')`)) {
      await command('Runtime.enable',{},attached.sessionId);
      await command('Page.enable',{},attached.sessionId);
      return attached.sessionId;
    }
  }
  assert.fail('Reopened native PiP target must be attached before later input checks');
};
