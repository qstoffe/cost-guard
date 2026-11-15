// Accounts-only tooltip ownership under native headless browser input.
const assert=require('node:assert/strict');
module.exports=async({command,evaluate,until,sessionId,navigate,checks})=>{
  await navigate('accounts');
  await evaluate(`window.helpOriginal=structuredClone(liveValue.view);
    window.helpView=new AccountCards.View();helpView.attach(document.getElementById('result'));
    window.helpCase=structuredClone(helpOriginal);
    helpCase.accounts.accounts=helpCase.accounts.accounts.slice(0,1);
    window.helpItem=helpCase.accounts.accounts[0];
    helpItem.secondary=Array.from({length:4},()=>structuredClone(helpItem.primary));
    helpItem.today_note='Partial pricing / attribution. Account attribution uncertain.';
    window.helpPhase=(phase)=>{
      helpCase.quota_stale=phase==='stale';
      for(const slot of [helpItem.primary,...helpItem.secondary]){
        const q=slot.quota,known=['ratio','native'].includes(phase);
        q.unlimited=phase==='unlimited';
        q.ccost_reference={...q.ccost_reference,basis:known?phase:'unknown',
          capacity:known?'125':null,monthly_capacity:known?'900':null,monthly_applicable:true};
        for(const [unit,tokens] of Object.entries(q.display_units)){
          tokens.ccost_capacity=known?(phase==='ratio'?'~':'')+(unit==='usd'?'$1.25':'125'):'?';
          tokens.monthly_capacity=known?'~'+(unit==='usd'?'$9.00':'900'):'N/A';
          const amount=unit==='usd'?'$1.25':'125 Credits',monthly=unit==='usd'?'$9.00':'900 Credits';
          tokens.capacity_help=known?'Capacity: '+(phase==='ratio'?'~':'')+amount+'\\nPartial pricing / attribution.\\nAccount attribution uncertain.':
            'Capacity: ?\\n'+(phase==='expired'?'Quota source is stale, unavailable or expired; refresh the native quota.':'No verified active recurring quota window.');
          tokens.monthly_capacity_help=known?'Monthly Capacity: ~'+monthly+'\\nPartial pricing / attribution.':
            'Monthly Capacity: N/A\\nNo verified active recurring quota window.';
        }
      }
      helpView.update(helpCase);
    };`);
  for(const unit of ['credits','usd'])for(const mode of ['used','remaining']){
    await evaluate(`ReportView.setUnit('${unit}');ReportView.setQuotaMode('${mode}');
      helpPhase('unknown');window.helpBar=helpView.root.querySelector('progress')`);
    for(const phase of ['unknown','ratio','native','unknown','expired','stale','ratio','unlimited']){
      const raw=await evaluate(`helpPhase('${phase}');JSON.stringify(helpCase)`);
      const facts=await evaluate(`({
        summaries:[...helpView.root.querySelectorAll('.watch-quota-summary')].map(n=>({
          text:n.textContent,targets:n.querySelectorAll('.help-value,[tabindex],[aria-describedby],[title]').length})),
        native:!helpView.root.querySelector('.watch-quota-capacity .help-value'),
        bar:helpView.root.querySelector('progress')===helpBar})`);
      assert.equal(facts.summaries.length,5);
      assert.ok(facts.summaries.every(n=>n.targets===0));
      assert.equal(facts.native,['native','unlimited'].includes(phase));
      // Unlimited legitimately changes the track shape; other values retain bars.
      if(phase!=='unlimited')assert.equal(facts.bar,true);
      for(const [selector,expected] of [
        ['.watch-subscription > .metric-value .help-value',"This account's reference cost for the local calendar day."],
        ...(['native','unlimited'].includes(phase)?[]:[
          ['.watch-quota-capacity .help-value',phase==='ratio'?
            'Capacity: ~'+(unit==='usd'?'$1.25':'125 Credits'):
            phase==='stale'?'Reference CCost unavailable for a stale or unavailable observation.':
            phase==='expired'?'Capacity: ?\nQuota source is stale, unavailable or expired; refresh the native quota.':
            'Capacity: ?\nNo verified active recurring quota window.']]),
        ['.watch-monthly-capacity .help-value',phase==='ratio'||phase==='native'?
          'Monthly Capacity: ~'+(unit==='usd'?'$9.00':'900 Credits'):
          phase==='stale'?'Reference CCost unavailable for a stale or unavailable observation.':
          'Monthly Capacity: N/A\nNo verified active recurring quota window.']
      ]){
        await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},sessionId);
        await evaluate(`helpView.root.querySelector('${selector}').focus()`);
        await until(`document.querySelector('#context-help')?.matches(':popover-open')`);
        assert.equal(await evaluate(`document.querySelector('#context-help').textContent`),expected);
      }
      assert.equal(await evaluate(`JSON.stringify(helpCase)`),raw,'help never mutates canonical/source metadata');
    }
    // An open ratio popup must disappear synchronously when native evidence arrives.
    await evaluate(`helpPhase('ratio');window.oldHelp=helpView.root.querySelector('.watch-quota-capacity .help-value');
      oldHelp.focus();helpPhase('native')`);
    assert.deepEqual(await evaluate(`({connected:oldHelp.isConnected,aria:oldHelp.getAttribute('aria-describedby'),
      open:document.querySelector('#context-help').matches(':popover-open'),
      focus:helpView.root.querySelector('.watch-quota-capacity span').tabIndex})`),
      {connected:false,aria:null,open:false,focus:-1});
  }
  // Trusted pointer/touch cannot turn plain summary/period/native text into help.
  for(const selector of ['.watch-quota-summary > span:first-child','.watch-period-cost','.watch-quota-capacity span']){
    const point=await evaluate(`(()=>{document.activeElement.blur();const n=helpView.root.querySelector('${selector}');
      n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},sessionId);
    await evaluate(`new Promise(resolve=>setTimeout(resolve,ContextHelp.HOVER_DELAY+100))`);
    assert.equal(await evaluate(`document.querySelector('#context-help').matches(':popover-open')`),false);
    await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},sessionId);
    await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},sessionId);
    assert.equal(await evaluate(`document.querySelector('#context-help').matches(':popover-open')`),false);
  }
  await navigate('watch');
  assert.equal(await evaluate(`document.querySelectorAll('#result .watch-subscription').length`),0);
  await navigate('accounts');await evaluate(`current.accounts.attach(document.getElementById('result'))`);
  checks.push('Exact Today/estimated/monthly/unknown help; 0–4 secondary levels, Credits/USD × Used/Remaining, inactive/expired/stale/native/unlimited transitions, source immutability, native owner/ARIA removal, trusted hover/touch absence, compact Watch unchanged');
};
