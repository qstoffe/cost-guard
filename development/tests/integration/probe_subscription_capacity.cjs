// Shared-card semantic slots and actual ordinal progress coordinates, not text-height guesses.
const assert = require('node:assert/strict'), fs = require('node:fs/promises');
module.exports = async ({command, evaluate, until, sessionId, navigate, checks, layouts, output, baseline = false, browserZoom = 1}) => {
  await evaluate(`window.capacityOriginal=structuredClone(liveValue.view);window.capacityCase=structuredClone(capacityOriginal);
    window.capacityUpdate=AccountCards.View.prototype.update;
    AccountCards.View.prototype.update=function(){return capacityUpdate.call(this,capacityCase)};
    window.capacityBuild=scenario=>{
      const originals=capacityOriginal.accounts.accounts;
      const templates=[originals[0].primary,originals[1].primary,originals[1].secondary[0]];
      const quota=(type,unknown)=>{
        const slot=structuredClone(templates[type]),q=slot.quota;
        q.ccost_reference.monthly_applicable=type!==0;
        if(unknown){q.ccost_reference={...q.ccost_reference,capacity:null,monthly_capacity:null,basis:'unknown'};
          q.display.capacity_help='Reference CCost capacity is unknown.';
          q.display.monthly_capacity_help='No compatible same-window reference CCost Capacity.';
          for(const tokens of [q.display,...Object.values(q.display_units||{})]){
            tokens.ccost_capacity='?';tokens.monthly_capacity=type===0?'':'N/A';}}
        return slot;
      };
      const unknown=['unknown','unknown-again'].includes(scenario);
      capacityCase=structuredClone(capacityOriginal);
      capacityCase.accounts.accounts=[0,1,2,3,4].map((count,index)=>{
        const item=structuredClone(originals[index%originals.length]);
        item.observation.id='capacity-'+index;
        if(index===2)item.observation.label='An intentionally long account title that wraps across several lines';
        item.primary=quota(scenario==='all-monthly'||scenario==='single-monthly'?0:index%3,unknown||index===2);
        item.secondary=Array.from({length:count},(_,level)=>quota(scenario==='all-monthly'?0:(index+level)%3,unknown||index===2));
        if(index===3)item.primary.display.watch_reset='Reset details with a deliberately longer explanation that wraps';
        return item;
      });
      if(scenario==='single-monthly')capacityCase.accounts.accounts=capacityCase.accounts.accounts.slice(0,1);
      if(scenario==='period-change')capacityCase.accounts.accounts[1].primary=quota(0,false);
      if(scenario==='reorder')capacityCase.accounts.accounts.reverse();
      if(scenario==='missing'){
        const slot=capacityCase.accounts.accounts[2].primary;slot.used_fraction=null;
        slot.quota.quota_display.used.percent='—';slot.quota.quota_display.remaining.percent='—';
      }
      if(scenario==='unlimited'){
        const q=capacityCase.accounts.accounts[2].primary.quota;q.unlimited=true;
        q.ccost_reference={...q.ccost_reference,capacity:null,monthly_capacity:null,basis:'unlimited'};
      }
      if(scenario==='stale')capacityCase.quota_stale=true;
    };`);
  const settle = () => evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))`);
  const fingerprint = async () => {
    await settle();
    return evaluate(`(() => [...document.querySelectorAll('#result .watch-subscription')].map(card=>{
      const rect=card.getBoundingClientRect();
      return {text:card.textContent,top:rect.top,height:rect.height,
        tracks:[...card.querySelectorAll('.watch-quota-track')].map(n=>({y:n.getBoundingClientRect().top,
          progress:n.querySelector('progress')?.getBoundingClientRect().top??null})),
        dividers:[...card.querySelectorAll('.watch-quota-divider')].map(n=>n.getBoundingClientRect().top),
        spacers:[...card.querySelectorAll('.watch-capacity-spacer')].map(n=>({text:n.textContent,
          hidden:n.getAttribute('aria-hidden'),focus:n.tabIndex,children:n.children.length,help:n.classList.contains('help-value')})),
        progress:[...card.querySelectorAll('progress')].map(p=>({value:p.value,label:p.getAttribute('aria-label'),text:p.getAttribute('aria-valuetext')})),
        lines:[...card.querySelectorAll('.watch-quota-capacity,.watch-monthly-capacity')].map(n=>n.textContent)};
    }))()`);
  };
  const help = async (all = false) => {
    const selector='#result .watch-quota-summary > .help-value:first-child,#result .watch-quota-capacity .help-value,#result .watch-monthly-capacity .help-value';
    const count = await evaluate(`document.querySelectorAll('${selector}').length`), result=[];
    const indices=all?Array.from({length:count},(_,index)=>index):
      [...new Set([0,1,2,count-3,count-2,count-1])].filter(index=>index>=0&&index<count);
    for(const index of indices) {
      await evaluate(`document.querySelectorAll('${selector}')[${index}].focus()`);
      await until(`document.querySelector('#context-help')?.matches(':popover-open')`);
      const {text,kind}=await evaluate(`({text:document.querySelector('#context-help').textContent,kind:document.activeElement.parentElement.className})`);
      assert.doesNotMatch(text,/rolling ·|account scope|Native Used:[\s\S]*Capacity:/);
      if(kind.includes('summary'))assert.doesNotMatch(text,/Capacity|CCost|÷|pricing/);
      else assert.doesNotMatch(text,/Native Used:|Native Remaining:/);
      result.push(text);
      await evaluate(`document.activeElement.blur()`);
    }
    return result;
  };
  const scenarios=baseline?['mixed']:['mixed','single-monthly','all-monthly','period-change','unknown','recovered','unknown-again','reorder','missing','unlimited','stale'];
  for(const width of baseline?[1920]:[360,800,1280,1920]) for(const zoom of baseline?[1]:[1,1.25]) for(const theme of baseline?['light']:['classic','classic-dark','light','dark']) {
    // Device emulation dimensions are pre-page-zoom; keep the actual CSS viewport
    // at the requested matrix width when the disposable profile uses native zoom.
    await command('Emulation.setDeviceMetricsOverride',{width:Math.round(width*browserZoom),height:1400,deviceScaleFactor:1,mobile:false},sessionId);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme.endsWith('dark')?'dark':'light'}]},sessionId);
    await evaluate(`document.documentElement.dataset.theme='${theme.startsWith('classic')?'classic':'web'}';document.documentElement.style.zoom='${zoom}'`);
    for(const scenario of scenarios) {
      await evaluate(`capacityBuild('${scenario}')`);
      await navigate('accounts');await evaluate(`current.accounts.update(capacityCase);window.scrollTo(0,0)`);
      const accounts=await fingerprint();
      const expected=await evaluate(`capacityCase.accounts.accounts.map(item=>[item.primary,...item.secondary].map(slot=>({
        monthly:slot.quota.ccost_reference.monthly_applicable,unlimited:slot.quota.unlimited,
        unknown:capacityCase.quota_stale||slot.quota.ccost_reference.capacity==null})))`);
      if(width===1920&&zoom===1&&theme==='light'&&scenario==='mixed'&&output){
        const image=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:true},sessionId);
        await fs.writeFile(output.replace(/\.json$/,'')+'-capacity.png',Buffer.from(image.data,'base64'));
      }
      if(!baseline)for(const [index,card] of accounts.entries()) {
        const peers=accounts.filter(peer=>Math.abs(peer.top-card.top)<1);
        assert.equal(card.tracks.length,expected[index].length,'no phantom quota tracks');
        assert.equal(card.dividers.length,expected[index].length-1,'one divider before each real additional quota');
        const wantedSpacers=expected[index].filter((slot,level)=>!slot.monthly&&accounts.some((peer,i)=>
          peers.includes(peer)&&expected[i][level]?.monthly)).length;
        assert.equal(card.spacers.length,wantedSpacers,`${width}/${zoom}/${theme}/${scenario}: only same-row semantic spacers`);
        for(const spacer of card.spacers)assert.deepEqual(spacer,{text:'',hidden:'true',focus:-1,children:0,help:false});
        card.tracks.forEach((track,level)=>{
          for(const peer of peers.filter(peer=>peer.tracks[level])){
            assert.ok(Math.abs(track.y-peer.tracks[level].y)<1,'same ordinal tracks align');
            if(track.progress!=null&&peer.tracks[level].progress!=null)
              assert.ok(Math.abs(track.progress-peer.tracks[level].progress)<1,'actual progress rectangles align');
          }
        });
        card.dividers.forEach((y,level)=>{
          for(const peer of peers.filter(peer=>peer.dividers[level]!=null))assert.ok(Math.abs(y-peer.dividers[level])<1,'divider slots align');
        });
        assert.equal(card.lines.length,expected[index].reduce((sum,slot)=>sum+1+Number(slot.monthly),0));
        assert.ok(card.lines.every(line=>!/: (N\/A|—|\s*$|~\?)/.test(line)),'unknown values are question marks, not suppressed');
        let line=0;
        for(const slot of expected[index]){
          if(slot.unknown)assert.ok(card.lines[line].endsWith(': '+(slot.unlimited?'Unlimited':'?')));
          if(slot.monthly&&slot.unknown)assert.ok(card.lines[line+1].endsWith(': ?'));
          line+=1+Number(slot.monthly);
        }
      }
      const allHelp=width===1920&&zoom===1&&theme==='light';
      const accountHelp=baseline?[]:await help(allHelp);
      if(!baseline){
        await navigate('watch');await evaluate(`current.watch.update({state:'running',view:capacityCase})`);
        const watch=await fingerprint(),strip=values=>values.map(({top,height,tracks,dividers,...facts})=>facts);
        assert.deepEqual(strip(watch),strip(accounts),'same shared text, slots, progress ARIA and state on both routes');
        watch.forEach(card=>card.tracks.forEach((track,level)=>{
          for(const peer of watch.filter(peer=>Math.abs(peer.top-card.top)<1&&peer.tracks[level]))
            assert.ok(Math.abs(track.y-peer.tracks[level].y)<1,'Full Watch ordinal tracks align');
        }));
        assert.deepEqual(await help(allHelp),accountHelp,'same Usage/Capacity/Monthly explanations');
        assert.equal(await evaluate(`document.documentElement.scrollWidth>innerWidth`),false,'no horizontal overflow');
      }
      const viewport=await evaluate(`({width:innerWidth,dpr:devicePixelRatio,scale:visualViewport.scale})`);
      assert.equal(viewport.width,width,'matrix width is the actual CSS viewport at native browser zoom');
      layouts.push({case:'subscription-capacity',width,zoom,theme,scenario,viewport,cards:accounts.map(({top,height,tracks,dividers,spacers,lines})=>
        ({top,height,tracks,dividers,spacers:spacers.length,lines}))});
    }
  }
  if(!baseline){
    // Same mounted card, including an open Capacity help target, through value and period changes.
    await navigate('accounts');await evaluate(`capacityBuild('mixed');current.accounts.update(capacityCase);
      window.capacityCard=document.querySelectorAll('.watch-subscription')[1];
      window.capacityBar=capacityCard.querySelector('progress');window.capacityHelp=capacityCard.querySelector('.watch-quota-capacity span');
      capacityHelp.focus();`);
    for(const scenario of ['unknown','recovered','unknown-again','period-change','mixed']){
      await evaluate(`capacityBuild('${scenario}');current.accounts.update(capacityCase)`);await settle();
      assert.deepEqual(await evaluate(`({bar:capacityBar===capacityCard.querySelector('progress'),focus:document.activeElement===capacityHelp,
        help:document.querySelector('#context-help').matches(':popover-open')})`),{bar:true,focus:true,help:true});
    }
  }
  await evaluate(`document.documentElement.style.zoom='';document.documentElement.dataset.theme='web'`);
  await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},sessionId);
  await navigate('accounts');await evaluate(`AccountCards.View.prototype.update=capacityUpdate;delete window.capacityUpdate;
    current.accounts.update(capacityOriginal)`);await settle();
  checks.push(baseline?'Before-change mixed known/unknown screenshot and ordinal DOM coordinates captured':
    'Permanent unknown Capacity rows, 0–4 secondary quotas, actual ordinal progress/divider coordinates and route parity; mixed/single/all-monthly/period/value/order/missing/unlimited/stale transitions at 360/800/1280/1920, 100/125% CSS zoom, Classic/Web light/dark; stable progress/focus/open help');
};
