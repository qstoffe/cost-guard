// Actual disposable-profile browser zoom, shipped Accounts and session card DOM.
'use strict';
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,command,browser,targetId,origin}) => {
  const layouts=[],diagnostics=[];
  const settings=browser.toLowerCase().endsWith('msedge.exe')?'edge://settings/appearance':'chrome://settings/appearance';
  const {windowId}=await command('Browser.getWindowForTarget',{targetId});
  for (const zoom of [1,1.25,1.5,2]) {
    await command('Emulation.clearDeviceMetricsOverride');
    await command('Browser.setWindowBounds',{windowId,bounds:{width:1366,height:1000}});
    await command('Page.navigate',{url:settings});
    await until(`typeof chrome.settingsPrivate?.getDefaultZoom==='function'`);
    await evaluate(`new Promise(resolve=>chrome.settingsPrivate.setDefaultZoom(${zoom},resolve))`);
    assert.equal(await evaluate('new Promise(resolve=>chrome.settingsPrivate.getDefaultZoom(resolve))'),zoom);
    await command('Page.navigate',{url:origin+'/#/accounts'});
    await until(`typeof current!=='undefined' && document.querySelector('.live-account-cards .watch-subscription > h4')`);
    const diagnostic=await evaluate(`({width:innerWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.body).zoom})`);
    diagnostics.push({zoom,...diagnostic});
    assert.equal(diagnostic.cssZoom,'1');
    assert.ok(Math.abs(diagnostic.dpr/diagnostics[0].dpr-zoom)<.02);
    assert.ok(Math.abs(diagnostic.width*zoom-diagnostics[0].width)<3);
    await evaluate(`window.accountsReference=document.createElement('div');accountsReference.className='live-account-cards';
      accountsReference.style.cssText='position:fixed;left:0;top:0;visibility:hidden;width:200px;pointer-events:none';
      accountsReference.append(document.querySelector('.live-account-cards .watch-subscription').cloneNode(true));
      document.body.append(accountsReference);location.hash='#/sessions/root'`);
    await until(`current.detail?.quotaUsage?.cards.size===1`);
    await evaluate(`window.quotaNode=current.detail.quotaUsage.grid.firstChild;
      window.quotaValue=structuredClone({scope:current.detail.quotaUsage.scope,
        accounts:[...current.detail.quotaUsage.cards.values()].map(card=>card.value)})`);
    for (const width of [360,520,1280,1920]) {
      await command('Emulation.setDeviceMetricsOverride',{
        width:Math.round(width*zoom),height:1000,deviceScaleFactor:1,mobile:false});
      for (const theme of ['classic','light','dark']) {
        await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]});
        await evaluate(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}'`);
        const facts=await evaluate(`(()=>{
          const root=current.detail.quotaUsage.root,card=quotaNode,heading=card.firstElementChild;
          const expected=getComputedStyle(accountsReference.querySelector('h4')),actual=getComputedStyle(heading);
          const fields=['fontFamily','fontSize','fontWeight','textAlign','backgroundColor','color','padding',
            'borderBottom','borderTopLeftRadius','borderTopRightRadius'];
          const outer=getComputedStyle(root),r=card.getBoundingClientRect(),h=heading.getBoundingClientRect();
          return {viewport:innerWidth,dpr:devicePixelRatio,cssZoom:getComputedStyle(document.body).zoom,
            overflow:document.documentElement.scrollWidth>innerWidth+1,
            parity:fields.every(key=>actual[key]===expected[key]),
            outerBorder:outer.borderWidth,outerPadding:outer.padding,outerBackground:outer.backgroundColor,outerShadow:outer.boxShadow,
            cardWidth:r.width,headerCentered:Math.abs((r.left+r.right-h.left-h.right)/2)<1,
            heading:heading.tagName,title:root.firstElementChild.tagName,
            link:heading.querySelector('a')?.href,rows:card.querySelectorAll('.session-quota-row').length,
            tracks:root.querySelectorAll('progress').length};})()`);
        assert.equal(facts.overflow,false);assert.equal(facts.parity,true,JSON.stringify(facts));
        assert.equal(facts.cssZoom,'1');assert.ok(Math.abs(facts.viewport-width)<2);
        assert.ok(Math.abs(facts.dpr-zoom)<.02);
        assert.equal(facts.outerBorder,'0px');assert.equal(facts.outerPadding,'0px');
        assert.equal(facts.outerBackground,'rgba(0, 0, 0, 0)');assert.equal(facts.outerShadow,'none');
        assert.equal(facts.headerCentered,true);assert.equal(facts.heading,'H3');assert.equal(facts.title,'H2');
        assert.equal(facts.link,'https://github.com/settings/copilot/features');assert.equal(facts.rows,2);assert.equal(facts.tracks,0);
        layouts.push({theme,width,zoom,...facts});
      }
    }
    // Renderer-local focus, no account navigation/external side effects.
    await evaluate(`quotaNode.querySelector('a').focus();window.quotaFocus=document.activeElement;
      current.detail.quotaUsage.update(quotaValue);ReportView.syncUnits(current.detail.root)`);
    assert.equal(await evaluate('document.activeElement===quotaFocus'),true);
    assert.equal(await evaluate(`getComputedStyle(quotaFocus).outlineStyle!=='none'`),true);
    // Synthetic DTO edge-layout exercise, separate from the real HTTP evidence.
    await evaluate(`window.layoutUsage=new AccountCards.SessionUsage();document.body.append(layoutUsage.root);
      window.layoutValue={scope:'synthetic-layout',accounts:Array.from({length:4},(_,index)=>({
        observation:{...quotaValue.accounts[0].observation,id:'layout-'+index,label:'Long account GPT-6 · subscription '+index},
         quotas:Array.from({length:index+1},(_,n)=>({id:'q'+n,label:'weekly GPT-6',percent:n?'?':'~0.001%',contribution:'positive'}))}))};
      layoutUsage.update(layoutValue)`);
    assert.equal(await evaluate(`layoutUsage.cards.size===4 &&
      layoutUsage.root.querySelectorAll('.session-quota-row').length===10 &&
      document.documentElement.scrollWidth<=innerWidth+1`),true);
    await evaluate(`layoutUsage.update({...layoutValue,accounts:[]})`);
    assert.equal(await evaluate(`layoutUsage.root.hidden && !layoutUsage.grid.children.length &&
      layoutUsage.root.getBoundingClientRect().height===0`),true);
    await evaluate('layoutUsage.root.remove();accountsReference.remove()');
  }
  return {layouts,checks:[
    '48 actual native-page-zoom layouts: Classic/Web light/Web dark × 360/520/1280/1920 CSS px × 100/125/150/200%; Accounts computed-header parity, bare section, links/focus and no overflow',
    'synthetic DTO edge layouts: four accounts with one/two/three/four positive quotas, tiny formatted zero and unknown capacity; all-empty hides title/grid without a gap',
    'independent fixed-window native zoom viewport/DPR diagnostics: '+JSON.stringify(diagnostics)]};
};
