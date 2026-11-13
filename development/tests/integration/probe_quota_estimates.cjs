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
      const amount = unit==='usd' ? (mode==='used'?'$6.13':'$55.00') : (mode==='used'?'613':'5500');
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
        assert.ok(data.text.includes(`Remaining: ${unit==='usd'?'$18.00':'1800'}/workday`));
        assert.ok(data.help.startsWith(`Capacity: ~${unit==='usd'?'$61.30':'6130 Credits'}\nNext reset: `));
        if(mode==='remaining') assert.ok(data.help.includes(`Remaining: ~${unit==='usd'?'$55.17':'5517 Credits'}`));
        else assert.doesNotMatch(data.help,/Remaining:/);
        assert.doesNotMatch(data.help,/Unrounded|estimate|Provider-reported fraction used|Observed same-window|Guesstimate|÷/i);
        assert.match(data.help,/\nNext reset: Reset (?:in [^,\n]+, \d{2}:\d{2} (?:today|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|at \d{2}:\d{2}, \d{4}-\d{2}-\d{2})(?:\n|$)/);
        assert.equal(data.raw,source.raw);assert.equal(data.streams,source.streams);assert.equal(data.reports,source.reports);
        assert.deepEqual(data.bars,mode==='used'?[.1,.1]:[.9,.9]);
        // Exercise the exact intrinsic targets, comparing server-owned raw help in both units.
        const targets=await evaluate(`[...document.querySelectorAll('.watch-subscription .watch-quota-summary > .help-value:first-child,.watch-subscription .watch-quota-capacity > .help-value,.watch-subscription .watch-monthly-capacity > .help-value')].map(n=>n.parentElement.className)`);
        for(let index=0;index<targets.length;index++) {
          await evaluate(`document.querySelectorAll('.watch-subscription .watch-quota-summary > .help-value:first-child,.watch-subscription .watch-quota-capacity > .help-value,.watch-subscription .watch-monthly-capacity > .help-value')[${index}].focus()`);
          await until(`document.querySelector('[role=tooltip]')?.matches(':popover-open')`);
          const text=await evaluate(`document.querySelector('[role=tooltip]').textContent`);
          if(targets[index].includes('summary')) {
            assert.match(text,/^Used: [^\n]+\nRemaining: [^\n]+\nReset /);
            assert.doesNotMatch(text,/Capacity|CCost|÷|rolling|scope|pricing/);
          } else {
            assert.match(text,/^(Monthly )?Capacity: ~/);
            assert.doesNotMatch(text,/Unrounded|estimate|Provider-reported|Observed|Guesstimate|÷|×/i);
            assert.doesNotMatch(text,/Native Used:|Native Remaining:|rolling|scope/);
            const key=targets[index].includes('monthly')?'monthly_capacity_help':'capacity_help';
            const ordinal=targets.slice(0,index).filter(value=>value.includes('summary')).length-1;
            const expected=await evaluate(`ReportView.display([liveValue.view.accounts.accounts[0].primary,...liveValue.view.accounts.accounts[0].secondary][${ordinal}].quota,'${key}')`);
            assert.equal(text,expected);
          }
        }
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
  await until(`document.querySelector('[role=tooltip]')?.textContent==='Remaining: ~$55.17'`);
  assert.equal(await evaluate(`document.activeElement===estimateFocus`),true);
  await evaluate(`window.capacityFocus=document.querySelector('.watch-quota-capacity span');capacityFocus.focus()`);
  await until(`document.querySelector('[role=tooltip]')?.textContent==='Capacity: ~$61.30'`);
  await fixture('quota-estimates-update');
  await until(`document.querySelector('[role=tooltip]')?.textContent==='Capacity: ~$65.30'`);
  assert.equal(await evaluate(`document.activeElement===capacityFocus`),true);
  await evaluate(`estimateFocus.focus()`);
  await until(`document.querySelector('[role=tooltip]')?.textContent==='Remaining: ~$58.77'`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},sessionId);
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},sessionId);
  assert.equal(await evaluate(`document.querySelector('[role=tooltip]')?.matches(':popover-open')`),false);
  // Hover the secondary Capacity with real browser input, not a synthetic focus event.
  const point = await evaluate(`(() => {document.activeElement.blur();const n=document.querySelector('.watch-secondary-quota .watch-quota-capacity span');
    n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},sessionId);
  await until(`document.querySelector('[role=tooltip]')?.matches(':popover-open') && document.querySelector('[role=tooltip]').textContent.startsWith('Capacity: ~$')`);
  assert.match(await evaluate(`document.querySelector('[role=tooltip]').textContent`),/^Capacity: ~\$\d+\.\d{2}$/);
  assert.doesNotMatch(await evaluate(`document.querySelector('[role=tooltip]').textContent`),/Native Used:|Native Remaining:|rolling|scope/);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},sessionId);
  // Touch each shared target; no whole-card popup or cross-topic help.
  for(const [selector,pattern] of [['.watch-quota-summary > .help-value:first-child',/^Used: [^\n]+\nRemaining:/],
      ['.watch-quota-capacity > .help-value',/^Capacity: ~\$65.30$/],
      ['.watch-secondary-quota .watch-monthly-capacity > .help-value',/^Monthly Capacity: ~\$\d+\.\d{2}$/]]) {
    const point=await evaluate(`(() => {document.activeElement.blur();const n=document.querySelector('${selector}');
      n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},sessionId);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},sessionId);
    await until(`document.querySelector('[role=tooltip]')?.matches(':popover-open')`);
    assert.match(await evaluate(`document.querySelector('[role=tooltip]').textContent`),pattern);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},sessionId);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},sessionId);
  }
  // Touch the compact line; it uses the same raw primary estimate and its own document controller.
  const touch = await evaluate(`(() => {const d=miniWatch.window.document,n=miniWatch.view.accounts.children[0].children[0].children[0];
    n.scrollIntoView();const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch]},pipSession);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},pipSession);
  await until(`miniWatch.window.document.querySelector('[role=tooltip]')?.textContent.includes('Remaining: ~$58.77')`);
  assert.match(await evaluate(`miniWatch.window.document.querySelector('[role=tooltip]').textContent`),/^Capacity: ~\$65.30\nNext reset: /);
  await evaluate(`window.quotaMiniTarget=miniWatch.view.accounts.children[0].children[0].children[0]`);
  await change('ccost-unit','credits');
  await until(`miniWatch.window.document.querySelector('[role=tooltip]')?.matches(':popover-open') &&
    miniWatch.window.document.querySelector('[role=tooltip]').textContent.includes('Remaining: ~5877 Credits')`);
  await fixture('quota-estimates');
  await until(`miniWatch.window.document.querySelector('[role=tooltip]')?.textContent.includes('Remaining: ~5517 Credits')`);
  assert.equal(await evaluate(`quotaMiniTarget===miniWatch.view.accounts.children[0].children[0].children[0]`),true);
  assert.equal(await evaluate(`miniWatch.window.document.querySelectorAll('[role=tooltip]').length`),1);
  assert.match(await evaluate(`miniWatch.window.document.querySelector('[role=tooltip]').textContent`),/^Capacity: ~6130 Credits\nNext reset: /);
  await change('web-theme','default');await change('ccost-unit','credits');
  checks.push('Estimate rounding: Accounts/Watch/open Mini, primary/secondary/monthly/independent pace, Classic/Web light/dark × Used/Remaining × Credits/USD; raw source, native fractions and fetch counts unchanged. Actual keyboard, delayed hover, touch, Escape and same-target Live/raw-help refresh verified.');
};
