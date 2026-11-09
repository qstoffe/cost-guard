// Actual anchor hit-testing, keyboard/touch/new-tab behavior and theme geometry.
const assert = require('node:assert/strict');
module.exports = async ({command,evaluate,sessionId,navigate,checks,layouts,openEvents,browserZoom=1}) => {
  await navigate('accounts');
  await evaluate(`window.linkOriginal=structuredClone(liveValue.view);window.linkTheme=document.documentElement.dataset.theme;
    window.linkCase=structuredClone(linkOriginal);linkCase.accounts.accounts=linkCase.accounts.accounts.slice(0,2);
    linkCase.accounts.accounts[0].observation.label='GitHub Copilot — long account heading with wrapping at narrow widths';
    linkCase.accounts.accounts[1].observation.provider_id='unknown';
    linkCase.accounts.accounts[1].observation.label='Unknown provider';
    ReportView.setQuotaMode('used');
    window.linkUpdate=AccountCards.View.prototype.update;
    AccountCards.View.prototype.update=function(){return linkUpdate.call(this,linkCase)};`);
  for (const width of [360,1280]) for (const zoom of [1,1.25]) for (const theme of ['classic','light','dark']) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'},
      {name:'prefers-reduced-motion',value:'reduce'}]},sessionId);
    await evaluate(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';document.documentElement.style.zoom='${zoom}'`);
    for (const exhausted of [false,true]) for (const route of ['accounts','watch']) {
      await navigate(route);
      await evaluate(`linkCase.accounts.accounts[0].primary.quota.quota_display.used.exhausted=${exhausted};
        if(current.accounts)current.accounts.update(linkCase);else current.watch.update({state:'running',view:linkCase});
        window.linkCard=document.querySelector('#result .watch-subscription');window.linkTarget=linkCard.querySelector('h4 a');
        linkTarget.scrollIntoView({block:'center'});`);
      const point = await evaluate(`(()=>{const r=linkTarget.getClientRects()[0];return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},sessionId);
      const facts = await evaluate(`(()=>{const a=getComputedStyle(linkTarget),h=getComputedStyle(linkTarget.parentNode);return {
        hover:linkTarget.matches(':hover'),decoration:a.textDecorationLine,cursor:a.cursor,color:a.color,headingColor:h.color,
        exhausted:linkCard.dataset.exhausted,overflow:document.documentElement.scrollWidth>innerWidth,
        unknown:document.querySelectorAll('#result .watch-subscription')[1].querySelector('h4 a')===null,
        href:linkTarget.href,target:linkTarget.target,rel:linkTarget.rel};})()`);
      assert.equal(facts.hover,true); assert.equal(facts.decoration,'underline'); assert.equal(facts.cursor,'pointer');
      assert.equal(facts.color,facts.headingColor); assert.equal(facts.exhausted,String(exhausted));
      assert.equal(facts.overflow,false); assert.equal(facts.unknown,true);
      assert.equal(facts.href,'https://github.com/settings/copilot/features');
      assert.equal(facts.target,'_blank'); assert.equal(facts.rel,'noopener noreferrer');
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},sessionId);
      assert.equal(await evaluate(`getComputedStyle(linkTarget).textDecorationLine`),'none');
      await evaluate('linkTarget.focus()');
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
      await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9,modifiers:8},sessionId);
      await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9,modifiers:8},sessionId);
      const focus = await evaluate(`({focused:document.activeElement===linkTarget,visible:linkTarget.matches(':focus-visible'),
        outline:getComputedStyle(linkTarget).outlineStyle,width:getComputedStyle(linkTarget).outlineWidth})`);
      assert.equal(focus.focused,true); assert.equal(focus.visible,true); assert.equal(focus.outline,'solid');
      assert.ok(parseFloat(focus.width)*zoom*browserZoom>=1.8,
        'focus outline remains visibly at least two rendered pixels under CSS/browser zoom: '+JSON.stringify(focus));
      await evaluate('linkTarget.blur()');
      layouts.push({case:'account-links',width,zoom,browserZoom,theme,route,exhausted,hover:true,keyboard:true,overflow:false});
    }
  }
  await navigate('accounts');
  await evaluate(`current.accounts.update(linkCase);document.documentElement.style.zoom='';
    window.linkTarget=document.querySelector('#result .watch-subscription h4 a');linkTarget.scrollIntoView({block:'center'});
    window.linkStreams=probeStreams;window.linkRequests=probeURLs.length;window.linkLocation=location.href;
    window.linkConnection=liveConnection;window.linkCSRF=csrf;`);
  const ax = await command('Accessibility.getFullAXTree',{},sessionId);
  assert.ok(ax.nodes.some(node=>node.role?.value==='link'&&node.name?.value===
    'GitHub Copilot — long account heading with wrapping at narrow widths — provider usage or settings (opens in a new tab)'));
  const targetsBefore = (await command('Target.getTargets')).targetInfos.map(target=>target.targetId);
  const padding = await evaluate(`(()=>{const r=linkTarget.parentNode.getBoundingClientRect();return {x:r.left+2,y:r.top+r.height/2}})()`);
  assert.equal(await evaluate(`document.elementFromPoint(${padding.x},${padding.y}).tagName`),'H4');
  for (const type of ['mousePressed','mouseReleased'])
    await command('Input.dispatchMouseEvent',{type,...padding,button:'left',clickCount:1},sessionId);
  assert.deepEqual((await command('Target.getTargets')).targetInfos.map(target=>target.targetId).sort(),[...targetsBefore].sort());
  for (const mode of ['pointer','touch']) {
    const point = await evaluate(`(()=>{const r=linkTarget.getClientRects()[0];return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
    const opened = openEvents.length;
    if (mode==='pointer') {
      for (const type of ['mousePressed','mouseReleased'])
        await command('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1},sessionId);
    } else {
      await command('Emulation.setTouchEmulationEnabled',{enabled:true},sessionId);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},sessionId);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},sessionId);
    }
    const targets = (await command('Target.getTargets')).targetInfos.filter(target=>!targetsBefore.includes(target.targetId));
    assert.equal(targets.length,1,mode+' opens one new tab');
    assert.equal(openEvents.length,opened+1); assert.equal(openEvents.at(-1).url,'https://github.com/settings/copilot/features');
    await command('Target.closeTarget',{targetId:targets[0].targetId});
  }
  const retained = await evaluate(`({location:location.href===linkLocation,streams:probeStreams===linkStreams,
    connection:liveConnection===linkConnection,auth:csrf===linkCSRF,requests:probeURLs.slice(linkRequests)})`);
  assert.deepEqual({...retained,requests:[]},{location:true,streams:true,connection:true,auth:true,requests:[]});
  // The existing ten-second snapshot health probe and visibility-interest pulse
  // may overlap a popup. Both only read/present the same host-owned publication.
  assert.ok(retained.requests.every(url=>['/api/interest','/api/live'].includes(url)),JSON.stringify(retained.requests));
  await command('Emulation.setTouchEmulationEnabled',{enabled:false},sessionId);
  await evaluate(`AccountCards.View.prototype.update=linkUpdate;delete window.linkUpdate;
    document.documentElement.dataset.theme=linkTheme;current.accounts.update(linkOriginal)`);
  checks.push('Account links: Watch/Accounts normal/exhausted Classic/Web light/dark at 360/1280 and 100/125% zoom; hover/leave, native Tab focus, AX purpose, plain unknown, header padding inert, pointer/touch each open one new tab; same Live connection/CSRF/route, only ordinary snapshot/interest heartbeats permitted');
};
