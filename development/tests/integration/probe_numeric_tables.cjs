// Canonical fixture exports through actual Full/Mini PiP, Sessions and detail DOM.
const assert = require('node:assert/strict');
module.exports = async ({command,evaluate,until,owner,mini,checks,layouts}) => {
  const full = '.watch-active tbody td:nth-child(6) .help-value';
  const prompt = '.mini-prompts tbody td:nth-child(3) .mini-cost-value';
  const total = '.mini-prompts tbody td:nth-child(4) .mini-cost-value';
  for (const unit of ['credits','usd']) {
    for (const mode of ['mixed','zero','absent','mixed']) {
      await evaluate(owner,`(() => {
        document.activeElement?.blur();miniWatch.window.document.activeElement?.blur();
        ReportView.setUnit('${unit}',current.watch.root);ReportView.setUnit('${unit}',miniWatch.view.root);
        const p={...liveValue,view:structuredClone(liveValue.probe_ccost_unavailable['${mode}'])};
        p.source_observed_at_ms=p.view.now_ms=Date.now();
        // Distinct synthetic sessions isolate each source fixture's state.
        for(const c of [...p.view.active_cards,...p.view.history_cards]) {
          c.observed_at_ms=Date.now();c.session_id+='-numeric-${mode}';
        }
        current.watch.update(p);miniWatch.update(p);
      })()`);
      for (const [id,selector] of [[owner,full],[mini,prompt],[mini,total]]) {
        const text=await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).textContent`);
        // The whole-session fixture includes one supported zero-cost compaction.
        // Mini intentionally uses its priced subtotal, not prompt unknownness.
        if(mode==='absent') assert.equal(text,unit==='usd'?'$0.00':'0');
        else if(mode==='zero') assert.equal(text,unit==='usd'?'$0.00':'0');
        else {
          assert.match(text,unit==='usd'?/^\$\d/:/^[<\d]/);
          assert.doesNotMatch(text,/\?|Partial /);
        }
        layouts.push({unit,mode,surface:id===mini?'Mini':'Full',selector,text});
      }
      if(mode==='mixed') {
        for (const [id,selector] of [[owner,full],[mini,prompt],[mini,total]]) {
          await command('Page.bringToFront',{},id);
          await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
          await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
          await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
          const help=await evaluate(id,`document.querySelector('#context-help').textContent`);
          assert.doesNotMatch(help,/\?\s*(?:\$|[<\d])/);
          await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
        }
      }
    }
  }
  // Same identity, successful-but-unpriced publications, and genuine corrections.
  for (const unit of ['credits','usd']) {
    await evaluate(owner,`(() => {
      document.activeElement?.blur();miniWatch.window.document.activeElement?.blur();
      ReportView.setUnit('${unit}',document.body);ReportView.setUnit('${unit}',miniWatch.view.root);
      window.zeroPending={...liveValue,view:structuredClone(liveValue.probe_ccost_unavailable.absent)};
      for(const c of zeroPending.view.active_cards) {
        c.session_id='zero-retention-${unit}';
        c.session_summary.context={...c.session_summary.context,context_scope:'zero-source-${unit}'};
      }
      current.watch.update(zeroPending);miniWatch.update(zeroPending);
    })()`);
    for(const [raw,complete,expected] of [[null,false,0],['125',false,125],['0',false,125],
      [null,false,125],['100',true,100],['0',true,0]]) {
      await evaluate(owner,`(() => {
        const p=structuredClone(zeroPending),c=p.view.active_cards[0],r=c.rows[0].prompt;
        r.ccost=${JSON.stringify(raw)};r.unresolved_cost=${!complete};
        r.display.ccost=${JSON.stringify(raw ?? '0')};
        r.display_units={credits:{ccost:${JSON.stringify(raw ?? '0')}},
          usd:{ccost:${JSON.stringify('$'+(Number(raw)/100).toFixed(2))}}};
        current.watch.update(p);miniWatch.update(p);
      })()`);
      const wanted=unit==='usd'?'$'+(expected/100).toFixed(2):String(expected);
      for(const [id,selector] of [[owner,full],[mini,prompt]]) {
        assert.equal(await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).textContent`),wanted);
        if(id===mini) assert.equal(await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).getAttribute('aria-label')`),
          'Prompt reference CCost: '+wanted);
      }
    }
    await evaluate(owner,`(() => {
      const p=structuredClone(zeroPending),r=p.view.active_cards[0].rows[0].prompt;
      r.event_id+='-new';r.ccost=null;r.unresolved_cost=true;r.display.ccost='0';
      r.display_units={credits:{ccost:'0'},usd:{ccost:'$0.00'}};
      p.view.active_cards[0].focal_id=r.event_id;current.watch.update(p);miniWatch.update(p);
    })()`);
    assert.equal(await evaluate(mini,`document.querySelector(${JSON.stringify(prompt)}).textContent`),unit==='usd'?'$0.00':'0');
  }
  checks.push('Unknown → positive partial → observed unresolved zero/retry retains → lower correction → verified zero; new prompt isolation and Mini accessible cost label in both units');
  await evaluate(owner,`miniWatch.close();window.numericSessions=new SessionsCatalog.View(()=>Promise.resolve());
    numericSessions.data={view:{timezone_id:'UTC'}};
    window.numericDetail=new SessionDetail.View(()=>Promise.resolve(),'root');document.body.append(numericSessions.root,numericDetail.root)`);
  for(const unit of ['credits','usd']) {
    for(const mode of ['mixed','absent','zero','mixed']) {
      await evaluate(owner,`ReportView.setUnit('${unit}',document.body);
        numericSessions.data.source={identity:'fixture-${mode}',generation:'v2'};
        numericSessions.rows(liveValue.probe_ccost_unavailable['${mode}'].probe_sessions);numericSessions.pan.hidden=false;
        numericDetail.update({revision:'${unit}-${mode}',state:'observed',result:{observed_at_ms:Date.now(),
          source:{identity:'fixture-${mode}',generation:'v2'},
          view:liveValue.probe_ccost_unavailable['${mode}'].probe_detail}})`);
      const cells=await evaluate(owner,`['.sessions-catalog tbody td:nth-child(5)',
        '.session-detail tbody td:nth-child(4)','.session-detail tfoot td:nth-child(4)']
        .map(selector=>document.querySelector(selector).textContent)`);
      for(const text of cells) {
        if(mode==='absent') assert.equal(text,unit==='usd'?'$0.00':'0');
        else assert.match(text,unit==='usd'?/^\$\d/:/^[<\d]/);
        assert.doesNotMatch(text,/\?|Partial /);
      }
      layouts.push({unit,mode,surface:'Sessions/detail/footer',cells});
    }
  }
  checks.push('Both units: canonical partial, unavailable, zero and refresh-back values in Full Watch, Mini/PiP, Sessions, detail/footer and cost-help amounts; no numeric prefix or replacement decoration');
  await evaluate(owner,`window.numericStats=new AIStatsView.View(()=>{});
    window.numericStatsState={period:'today',result:null};document.body.replaceChildren(numericStats.root)`);
  for(const unit of ['credits','usd']) {
    await evaluate(owner,`ReportView.setUnit('${unit}',document.body);numericStats.update(numericStatsState)`);
    assert.equal(await evaluate(owner,`numericStats.cards.get('total-cost').value.textContent`),
      unit==='usd'?'$0.00':'0 CCost');
    await evaluate(owner,`(() => {
      const names=['hourly-rate','total-cost','total-tokens','token-rate','working-time','average-cost',
        'expensive-session','longest-session','busiest-day','night-owl','streak','parallel'];
      const metrics=names.map(metric=>({metric,value:'125',exact_value:'125',reasons:[],podium:[],
        display:{value:'125 CCost',trait:'Fixture',token_help:'125 tokens',response_help:'No response sample',
          calendar_rate:'125 CCost/h',workday_rate:'125 CCost/h',active_rate:'125 CCost/h',rate_help:'Fixture rates'},
        display_units:{usd:{value:'$1.25',calendar_rate:'$1.25/h',workday_rate:'$1.25/h',active_rate:'$1.25/h'}}}));
      numericStatsState={period:'today',result:{source:{identity:'stats-${unit}',generation:'v2'},view:{
        kind:'ai-stats',timezone_id:'UTC',ai_stats_policy:'fun-3-responses',ai_stats_work:{scopes:{today:{ready:true}}},
        ai_stats:[{period:'today',start_ms:1000,metrics}]}};
      numericStats.update(numericStatsState);
    })()`);
    for(const [raw,complete,expected] of [['0',false,125],['100',true,100],['0',true,0]]) {
      await evaluate(owner,`(() => {
        const metric=numericStatsState.result.view.ai_stats[0].metrics.find(m=>m.metric==='total-cost');
        metric.value='${raw}';metric.reasons=${complete?'[]':"['pricing_gap']"};
        metric.display.value='${raw} CCost';metric.display_units.usd.value='$${(Number(raw)/100).toFixed(2)}';
        numericStats.update(numericStatsState);
      })()`);
      assert.equal(await evaluate(owner,`numericStats.cards.get('total-cost').value.textContent`),
        unit==='usd'?'$'+(expected/100).toFixed(2):expected+' CCost');
    }
    await evaluate(owner,`numericStatsState.period='all';numericStatsState.result=null;numericStats.update(numericStatsState)`);
    assert.equal(await evaluate(owner,`numericStats.cards.get('total-cost').value.textContent`),
      unit==='usd'?'$0.00':'0 CCost','pending period cannot inherit another period');
    assert.equal(await evaluate(owner,`numericStats.cards.get('total-tokens').card.textContent`),'Loading…');
  }
  checks.push('AI Stats actual DOM: cold numeric CCost only, both units, incomplete zero retains, qualified decrease/zero replaces, period isolation; noncost pending remains Loading');
};
