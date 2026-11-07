// Route parity and responsive, conditional primary alignment over one canonical DTO.
const assert = require('node:assert/strict');
module.exports = async ({command, evaluate, until, sessionId, navigate, checks, layouts}) => {
  await evaluate(`window.capacityOriginal=structuredClone(liveValue.view);window.capacityCase=structuredClone(capacityOriginal)`);
  const settle = () => evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))`);
  const fingerprint = async () => {
    await settle();
    return evaluate(`(() => {
      const cards=[...document.querySelectorAll('#result .watch-subscription')];
      return cards.map(card=>{
        const rect=card.getBoundingClientRect(),bar=card.querySelector('.watch-quota-track'),spacer=card.querySelector('.watch-capacity-spacer');
        return {text:card.textContent,top:rect.top,bar:bar.getBoundingClientRect().top,
          extra:!!card.querySelector(':scope > .watch-monthly-capacity'),spacer:spacer?{
            text:spacer.textContent,hidden:spacer.getAttribute('aria-hidden'),focus:spacer.tabIndex,
            children:spacer.children.length,help:spacer.classList.contains('help-value')}:null,
          progress:[...card.querySelectorAll('progress')].map(p=>({value:p.value,label:p.getAttribute('aria-label'),text:p.getAttribute('aria-valuetext')})),
          lines:[...card.querySelectorAll('.watch-quota-capacity,.watch-monthly-capacity')].map(n=>n.textContent),
          order:[...card.querySelectorAll('.watch-monthly-capacity')].every(n=>n.previousElementSibling.classList.contains('watch-quota-capacity')&&n.nextElementSibling.classList.contains('watch-quota-track'))};
      });
    })()`);
  };
  const help = async () => {
    const count = await evaluate(`document.querySelectorAll('#result .watch-quota-capacity .help-value').length`), result=[];
    for(let index=0;index<count;index++) {
      await evaluate(`document.querySelectorAll('#result .watch-quota-capacity .help-value')[${index}].focus()`);
      await until(`document.querySelector('#context-help')?.matches(':popover-open')`);
      result.push(await evaluate(`document.querySelector('#context-help').textContent`));
      await evaluate(`document.activeElement.blur()`);
    }
    return result;
  };
  for(const width of [360,800,1280,1920]) for(const zoom of [1,1.25]) for(const theme of ['classic','light','dark']) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},sessionId);
    await evaluate(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';document.documentElement.style.zoom='${zoom}'`);
    for(const scenario of ['mixed','single-monthly','all-monthly','period-change']) {
      await evaluate(`(() => {
        capacityCase=structuredClone(capacityOriginal);
        const values=capacityCase.accounts.accounts;
        if('${scenario}'==='mixed')capacityCase.accounts.accounts=values.slice(0,3);
        if('${scenario}'==='single-monthly')capacityCase.accounts.accounts=values.slice(0,1);
        if('${scenario}'==='all-monthly')capacityCase.accounts.accounts=[0,1,2].map(i=>{
          const item=structuredClone(values[0]);item.observation.id='monthly-'+i;return item;});
        if('${scenario}'==='period-change') {
          capacityCase.accounts.accounts=values.slice(0,3);values[1].primary=structuredClone(values[0].primary);
        }
      })()`);
      await navigate('accounts');
      await evaluate(`current.accounts.update(capacityCase)`);
      const accounts=await fingerprint();
      for(const card of accounts) {
        const peers=accounts.filter(peer=>Math.abs(peer.top-card.top)<1),needed=!card.extra&&peers.some(peer=>peer.extra);
        assert.equal(Boolean(card.spacer),needed,`${width}/${zoom}/${theme}/${scenario}: conditional row only beside extra primary capacity`);
        if(card.spacer) assert.deepEqual(card.spacer,{text:'',hidden:'true',focus:-1,children:0,help:false});
        for(const peer of peers) assert.ok(Math.abs(card.bar-peer.bar)<1,'primary progress bars align');
        assert.equal(card.order,true,'real monthly equivalents immediately precede their own bars');
      }
      const accountHelp=await help();
      await navigate('watch');
      await evaluate(`current.watch.update({state:'running',view:capacityCase})`);
      const watch=await fingerprint(),strip=values=>values.map(({top,bar,...facts})=>facts);
      assert.deepEqual(strip(watch),strip(accounts),'identical ordered card text, lines, ARIA, spacer and state on both routes');
      assert.deepEqual(await help(),accountHelp,'identical primary/secondary Capacity explanations');
      assert.equal(await evaluate(`document.documentElement.scrollWidth>innerWidth`),false,'long titles/zoom do not overflow');
      if(scenario==='mixed') {
        assert.match(accounts[0].lines[0],/^Monthly Capacity:/);
        assert.match(accounts[1].lines[0],/^5-hour Capacity:/);
        assert.match(accounts[1].lines[1],/^Monthly Capacity:.*guesstimate/);
        assert.match(accounts[1].lines[2],/^Weekly Capacity:/);
        assert.match(accounts[1].lines[3],/^Monthly Capacity:.*guesstimate/);
        assert.match(accountHelp[1],/30-day guesstimate[\s\S]*not a monthly entitlement[\s\S]*never add/);
      }
      layouts.push({case:'subscription-capacity',width,zoom,theme,scenario,cards:accounts.length,
        spacers:accounts.filter(card=>card.spacer).length,parity:true});
    }
  }
  await evaluate(`document.documentElement.style.zoom='';document.documentElement.dataset.theme='web'`);
  await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},sessionId);
  await navigate('accounts');await evaluate(`current.accounts.update(capacityOriginal)`);await settle();
  checks.push('Shared full-size cards: exact route parity of ordered text, Capacity help, primary/secondary lines, progress ARIA and conditional blank rows; mixed 3+, single/all-monthly and live period changes at 360/800/1280/1920, 100/125% zoom, Classic/Web light/dark; no fabricated secondary tracks or horizontal overflow');
};
