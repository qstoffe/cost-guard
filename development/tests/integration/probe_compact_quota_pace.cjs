// Shipped Watch and native Document PiP, with separate browser input journeys.
const assert = require('node:assert/strict');

module.exports = async ({command,evaluate,until,key,owner,mini,checks,fixture,input}) => {
  assert.ok(['keyboard','mouse','touch'].includes(input));
  const setUnit = unit => evaluate(owner,`ReportView.setUnit('${unit}',current.watch.root); miniWatch.render()`);
  const selector = '.mini-accounts > li:first-child .help-value';
  const panel = `document.querySelector('#context-help')`;
  const open = `${panel}?.matches(':popover-open')`;
  const publish = async (name,cost) => {
    await fixture(name);
    await until(owner,`liveValue.view.accounts.accounts[0].primary.cost.known_ccost==='${cost}'`);
  };
  const expected = () => evaluate(owner,String.raw`(() => {
    const p=liveValue.view.accounts.accounts[0].primary, pace=p.quota.ccost_pace;
    return 'Capacity: '+ReportView.display(p.quota,'capacity_amount')+'\nNext reset: '+ReportView.display(p,'mini_reset')+
      '\n\nCCost Remaining/day: '+ReportView.display(pace,'ccost_per_day')+
      '\nCCost Remaining/workday: '+ReportView.display(pace,'ccost_per_workday');
  })()`);
  const assertOpen = async (id,text) => {
    await until(id,`${open} && ${panel}.textContent===${JSON.stringify(text)}`);
    const facts = await evaluate(id,`(() => {const p=${panel}, r=p.getBoundingClientRect();return {
      panels:document.querySelectorAll('[role=tooltip]').length,
      whiteSpace:getComputedStyle(p).whiteSpace, fits:r.left>=0 && r.top>=0 && r.right<=innerWidth &&
        r.bottom<=innerHeight && p.scrollHeight<=p.clientHeight};})()`);
    assert.deepEqual(facts,{panels:1,whiteSpace:'pre-line',fits:true});
  };

  await command('Emulation.setDeviceMetricsOverride',{width:360,height:720,deviceScaleFactor:1,mobile:false},owner);
  await command('Emulation.setDeviceMetricsOverride',{width:290,height:360,deviceScaleFactor:1,mobile:false},mini);
  for (const id of [owner,mini]) {
    await command('Page.bringToFront',{},id);
    await setUnit('credits');
    await publish('quota-estimates','613');
    const credits = await expected();
    assert.match(credits,/^Capacity: ~6130 Credits\nNext reset: [^\n]+\n\nCCost Remaining\/day: 600\nCCost Remaining\/workday: 1800$/);
    await evaluate(id,`(() => {
      window.paceLabel=document.querySelector('${selector}');
      window.paceRow=paceLabel.closest('li'); window.paceBar=paceRow.querySelector('progress');
      paceLabel.scrollIntoView({block:'nearest'});
    })()`);
    assert.deepEqual(await evaluate(id,`({stops:paceRow.querySelectorAll('[tabindex="0"]').length,
      tab:paceLabel.tabIndex,buttons:paceRow.querySelectorAll('button').length})`),{stops:1,tab:0,buttons:0});
    if (input==='keyboard') {
      await evaluate(id,`paceRow.parentElement.focus()`);
      await key(id,'Tab');
      assert.equal(await evaluate(id,`document.activeElement===paceLabel`),true);
    } else {
      const point = await evaluate(id,`(() => {const r=paceLabel.getBoundingClientRect();
        return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
      if (input==='mouse') await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},id);
      else {
        await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
        await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},id);
        await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
      }
    }
    await assertOpen(id,credits);
    await setUnit('usd');
    const usd = await expected();
    assert.match(usd,/^Capacity: ~\$61\.30\nNext reset: [^\n]+\n\nCCost Remaining\/day: \$6\.00\nCCost Remaining\/workday: \$18\.00$/);
    await assertOpen(id,usd);
    for (const theme of ['classic','web']) for (const scheme of ['light','dark']) {
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},id);
      await evaluate(owner,`document.documentElement.dataset.theme='${theme}';miniWatch.syncTheme()`);
      await setUnit('credits');
      await assertOpen(id,credits);
      await setUnit('usd');
      await assertOpen(id,usd);
    }
    await publish('quota-compact-reset','653');
    const reset = await expected();
    assert.notEqual(reset.split('\n')[1],usd.split('\n')[1]);
    assert.notEqual(reset.split('\n\n')[1],usd.split('\n\n')[1]);
    await assertOpen(id,reset);
    assert.equal(await evaluate(id,`paceLabel===document.querySelector('${selector}') &&
      paceRow===paceLabel.closest('li') && paceRow.querySelector('progress')===paceBar && paceBar.value===.15 &&
      !/CCost Remaining/.test(paceRow.textContent) && paceLabel.getAttribute('aria-describedby')==='context-help'`),true);
    if (input==='keyboard') assert.equal(await evaluate(id,`document.activeElement===paceLabel`),true);
    if (input==='mouse') assert.equal(await evaluate(id,`paceLabel.matches(':hover')`),true);
    await key(id,'Escape');
    assert.equal(await evaluate(id,open),false);
    checks.push(`${id===owner?'Watch':'native Document PiP'}: ${input}, responsive fit, Classic/Web light/dark, Credits/USD and open same-node help after Live reset.`);
  }
};
