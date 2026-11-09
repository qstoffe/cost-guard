// Actual shared cards and open PiP: server-prepared raw help, native CDP input, no inference.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,command,sessionId,pipSession,checks,fixture,route,change}) => {
  await fixture('quota-estimates');
  await until(`liveValue.view.accounts.accounts[0].primary.cost.known_ccost==='613'`);
  const source = await evaluate(`({raw:JSON.stringify(liveValue.view.accounts),streams:probeStreams,reports:probeReports})`);
  for (const theme of ['classic','web']) for (const scheme of ['light','dark']) {
    await change('web-theme',theme);
    for (const target of [sessionId,pipSession]) await command('Emulation.setEmulatedMedia',
      {features:[{name:'prefers-color-scheme',value:scheme}]},target);
    for (const mode of ['used','remaining']) for (const unit of ['credits','usd']) {
      await change('quota-display',mode); await change('ccost-unit',unit);
      const amount = unit==='usd' ? (mode==='used'?'$6.13':'$60.00') : (mode==='used'?'613':'6000');
      for (const section of ['accounts','watch']) {
        await route(section);
        const data = await evaluate(`(() => {const root=document.querySelector('.watch-subscription');return {
          text:root.textContent,mini:miniWatch.view.accounts.children[0].textContent,
          help:miniWatch.view.accounts.children[0].helpText,raw:JSON.stringify(liveValue.view.accounts),
          streams:probeStreams,reports:probeReports,bars:[...root.querySelectorAll('progress')].map(b=>b.value)};})()`);
        assert.ok(data.text.includes(`Monthly · ${mode==='used'?'10%':'90%'} ${mode} (${amount})`));
        assert.ok(data.mini.includes(`${mode} (${amount})`));
        assert.ok(data.text.includes(`Monthly Capacity: ~${unit==='usd'?'$60.00':'6000'}`));
        assert.ok(data.text.includes(`5-hour Capacity: ~${unit==='usd'?'$6.00':'600'}`));
        assert.ok(data.text.includes(`Remaining: ${unit==='usd'?'$6.00':'600'}/day`));
        assert.ok(data.text.includes(`Remaining: ${unit==='usd'?'$20.00':'2000'}/workday`));
        assert.match(data.help,/6130 Credits/);
        if(mode==='remaining') assert.match(data.help,/5517 Credits/); else assert.doesNotMatch(data.help,/5517 Credits/);
        assert.equal(data.raw,source.raw);assert.equal(data.streams,source.streams);assert.equal(data.reports,source.reports);
        assert.deepEqual(data.bars,mode==='used'?[.1,.1]:[.9,.9]);
      }
    }
  }
  await change('quota-display','remaining'); await change('ccost-unit','credits'); await route('watch');
  // Keyboard focus and refresh stay on the same intrinsic parenthetical target.
  for (const [selector,raw] of [['.watch-primary-details p:nth-child(2) span','613'],['.watch-primary-details p:nth-child(3) span','1839']]) {
    await evaluate(`document.querySelector('${selector}').focus()`);
    await until(`document.querySelector('[role=tooltip]')?.textContent.includes('${raw} Credits')`);
    assert.equal(await evaluate(`document.activeElement.hasAttribute('aria-describedby')`),true);
  }
  await evaluate(`document.querySelector('.watch-subscription > .watch-quota-summary > .help-value').focus()`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
  await until(`document.querySelector('[role=tooltip]')?.textContent.includes('5517 Credits')`);
  assert.equal(await evaluate(`document.activeElement.className`),'watch-period-cost help-value');
  await evaluate(`window.estimateFocus=document.activeElement;ReportView.setUnit('usd',document.getElementById('result'))`);
  await until(`document.querySelector('[role=tooltip]')?.textContent.includes('5517 Credits ($55.17)')`);
  assert.equal(await evaluate(`document.activeElement===estimateFocus`),true);
  await fixture('quota-estimates-update');
  await until(`document.querySelector('[role=tooltip]')?.textContent.includes('5877 Credits ($58.77)')`);
  assert.equal(await evaluate(`document.activeElement===estimateFocus`),true);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},sessionId);
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},sessionId);
  assert.equal(await evaluate(`document.querySelector('[role=tooltip]')?.matches(':popover-open')`),false);
  // Hover the secondary Capacity with real browser input, not a synthetic focus event.
  const point = await evaluate(`(() => {document.activeElement.blur();const n=document.querySelector('.watch-secondary-quota .watch-quota-capacity span');
    n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},sessionId);
  await until(`document.querySelector('[role=tooltip]')?.matches(':popover-open') && document.querySelector('[role=tooltip]').textContent.startsWith('Estimated full-window reference CCost')`);
  assert.doesNotMatch(await evaluate(`document.querySelector('[role=tooltip]').textContent`),/613 Credits|rounding|÷/);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},sessionId);
  // Touch the compact line; it uses the same raw primary estimate and its own document controller.
  const touch = await evaluate(`(() => {const d=miniWatch.window.document,n=miniWatch.view.accounts.children[0].children[0].children[0];
    n.scrollIntoView();const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch]},pipSession);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},pipSession);
  await until(`miniWatch.window.document.querySelector('[role=tooltip]')?.textContent.includes('5877 Credits')`);
  assert.match(await evaluate(`miniWatch.window.document.querySelector('[role=tooltip]').textContent`),/6530 Credits/);
  await change('web-theme','default');await change('ccost-unit','credits');
  checks.push('Estimate rounding: Accounts/Watch/open Mini, primary/secondary/monthly/independent pace, Classic/Web light/dark × Used/Remaining × Credits/USD; raw source, native fractions and fetch counts unchanged. Actual keyboard, delayed hover, touch, Escape and same-target Live/raw-help refresh verified.');
};
