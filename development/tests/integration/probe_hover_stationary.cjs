// Real elapsed time and native CDP pointer input; no clock/selector emulation.
const assert=require('node:assert/strict'),fs=require('node:fs/promises');
module.exports=async ({command,evaluate,until,owner,mini,checks,layouts,output})=>{
  const mouse=(id,x,y)=>command('Input.dispatchMouseEvent',{type:'mouseMoved',x,y},id);
  const open=async(id,selector)=>{
    await command('Page.bringToFront',{},id);
    await evaluate(id,`document.activeElement?.blur();ContextHelp.dismiss(document.body)`);
    await mouse(id,1,1);
    const point=await evaluate(id,`(()=>{const n=document.querySelector(${JSON.stringify(selector)});
      if(!n)throw new Error('Missing stationary target: '+${JSON.stringify(selector)});
      n.scrollIntoView({block:'center',inline:'center'});const r=n.getBoundingClientRect();
      return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await mouse(id,point.x,point.y);
    await until(id,`document.getElementById('context-help')?.matches(':popover-open')`);
  };
  // Reproduce the old hard cutoff separately in the actual PiP document.
  if(process.env.COST_GUARD_BASELINE_HELP) {
    const source=await fs.readFile(process.env.COST_GUARD_BASELINE_HELP,'utf8');
    if(source.includes('panel.hidden || !panel.isConnected || now() >= hoverDeadline')) {
      await evaluate(mini,`(()=>{${source.replace("panel.id = 'context-help'","panel.id = 'baseline-help'")}
        const b=ContextHelp.button('Original 30-second cutoff','Baseline stationary reading',document);
        b.id='baseline-trigger';document.body.append(b);})()`);
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
    }
  }
  await evaluate(owner,`window.stationaryRefresh=setInterval(()=>{
    const c=liveValue.view.active_cards[0],p=c.rows[0].prompt;
    p.display.ccost=String(30+(window.stationaryTicks=(window.stationaryTicks||0)+1)%10);
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
      await open(id,selector);
      await evaluate(id,`window.stationary={started:performance.now(),events:0,samples:[],target:document.querySelector(${JSON.stringify(selector)})};
        window.stationaryInput=()=>stationary.events++;
        document.addEventListener('pointermove',stationaryInput,true);
        window.stationarySample=setInterval(()=>stationary.samples.push({
          elapsed:performance.now()-stationary.started,open:document.getElementById('context-help').matches(':popover-open'),
          hovered:stationary.target.matches(':hover'),connected:stationary.target.isConnected}),1000)`);
      await new Promise(resolve=>setTimeout(resolve,61000));
      const state=await evaluate(id,`clearInterval(stationarySample);document.removeEventListener('pointermove',stationaryInput,true);
        ({elapsed:performance.now()-stationary.started,events:stationary.events,samples:stationary.samples})`);
      assert.ok(state.elapsed>=60000);
      assert.equal(state.events,0,'no pointer input while reading');
      assert.ok(state.samples.length>=55);
      assert.ok(state.samples.every(value=>value.open&&value.hovered&&value.connected),JSON.stringify({selector,...state}));
      layouts.push({case:'stationary-61s',document:id===mini?'pip':'full-watch',selector,...state});
      if(id===mini) {
        const image=await command('Page.captureScreenshot',{format:'png'},mini);
        await fs.writeFile(output.replace(/\.json$/,`-stationary-${index}.png`),
          Buffer.from(image.data,'base64'));
      }
      await mouse(id,1,1);await until(id,`document.getElementById('context-help').hidden`);
    }
  } finally {await evaluate(owner,'clearInterval(stationaryRefresh)');}
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
};
