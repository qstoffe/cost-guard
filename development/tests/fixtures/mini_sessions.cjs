// Presentation selection over canonical server identities/times; no browser valuation.
const assert = require('node:assert/strict');
module.exports = function sessionTable(vm, context, controller, view, input, helpText) {
  const saved = structuredClone(input.view), base = saved.active_cards[0];
  const card = (id, at, running=false) => ({...structuredClone(base),session_id:id,title:'Same display title',focal_id:running?id:'',
    rows:[{...structuredClone(base.rows[0]),live_context:{display:{watch_next_context_tokens:'17'}},
       prompt:{...structuredClone(base.rows[0].prompt),preview:'',event_id:id,at_ms:at,in_progress:running,
        completed_successfully:!running,completed_at_ms:running?null:at,
        display:{ccost:'49',clock:'12:34',start_date_time:'2026-10-25 02:30 +0200',
          finished_clock:'23:47',finished_date_time:'2026-10-25 02:30 +0100'}}}],
    session_summary:{...structuredClone(base.session_summary),context:{display:{watch_next_context_tokens:'900'}}}});
  const show = (active,history,state='observed',epoch=0) => {
    input.view={...saved,active_cards:active,history_cards:history,history_state:state,history_epoch:epoch};controller.update(input);
  };
  const rows = () => view.body.children.filter(row=>row.dataset.id);
  const ids = () => rows().map(row=>row.dataset.id);
  const history = Array.from({length:5},(_,i)=>card('h'+i,100+i));
  assert.equal(view.root.querySelectorAll('table').length,1);
  assert.equal(view.earlierToggle,undefined);assert.equal(view.historyBody,undefined);
  const headers=view.body.parentNode.querySelectorAll('th');
  assert.deepEqual(headers.map(n=>n.textContent),['Activity','Session','CCost','Total','Ctx']);
  assert.match(helpText(headers[0].children[0]),/Start time for a running prompt; finish time for a completed prompt\/session\./);
  assert.equal(helpText(headers[1].children[0]),'The name of the session.');
  assert.match(helpText(headers[2].children[0]),/represented prompt’s reference cost/);
  assert.equal(helpText(headers[3].children[0]),'The entire session’s reference cost, including attributed linked subagents.');
  assert.match(helpText(headers[4].children[0]),/last valid session-level estimate/);
  for(const count of [0,1,3,4,5,6,10]) {
    const active=Array.from({length:count},(_,i)=>card('a'+i,200+i,true));show(active,history);
    assert.equal(rows().length,Math.max(5,count));
    assert.deepEqual(ids(),[...history.slice(Math.min(5,count)).map(c=>c.session_id),...active.map(c=>c.session_id)]);
    assert.equal(new Set(ids()).size,rows().length);assert.equal(view.needsHistory,count<5);
    for(const row of rows()) assert.equal(row.children[0].textContent,row.dataset.id.startsWith('a')?'▶ 12:34':'23:47');
  }
  show([],history);const retained=view.promptRows.get('h4'),time=retained.children[0].children[0];
  assert.ok(rows().every(row=>row.className===''),'successful cold history is neutral');
  assert.match(retained.attributes['aria-label'],/Completed/,'neutral history retains its outcome');
  assert.equal(retained.children[4].textContent,'900','historical context uses session summary, not stale prompt');
  assert.equal(time.textContent,'23:47');assert.equal(helpText(time),'2026-10-25 02:30 +0100');
  const resumed=card('h4',300,true);show([resumed],history);
  assert.equal(view.promptRows.get('h4'),retained,'history promotes in the same keyed row');assert.equal(ids().at(-1),'h4');
   assert.equal(retained.children[4].textContent,'17');assert.equal(time.textContent,'▶ 12:34');
   assert.equal(time.children[0].attributes['aria-hidden'],'true');assert.equal(time.children[0].tabIndex,undefined);
   assert.deepEqual(time.children[0].events,{});assert.equal(time.tabIndex,0);
  assert.equal(helpText(time),'2026-10-25 02:30 +0200');
  const concurrent=Array.from({length:10},(_,i)=>{const value=card('h4',301+i,true);value.focal_id=value.rows[0].prompt.event_id='p'+i;
    value.rows[0].prompt.prompt_number=100+i;value.rows[0].prompt.display_units={};value.rows[0].prompt.display.ccost=String(i);return value;});
  show(concurrent,history);assert.equal(rows().length,5);assert.equal(view.promptRows.get('h4'),retained);
  assert.match(retained.attributes['aria-label'],/Prompt 109 · Running/);
  assert.equal(helpText(retained.children[1].children[0].children[0]),'Same display title\nPrompt #109');
  const cost=retained.children[2].children[0];
  assert.match(helpText(cost),/Duration: 10m/);assert.equal(retained.children[2].textContent,'9');
  assert.equal(retained.children[3].textContent,'4583');
  {
    assert.match(helpText(cost),/Duration: 10m/);
    const panel=view.doc.body.children.at(-1);
    assert.equal(panel.children.length,3);
    assert.equal(panel.children[1].className,'context-help-running-duration');
    assert.equal(panel.children[1].textContent,'Duration: 10m');
  }
  assert.equal(retained.className,'mini-running');
  const tied=structuredClone(concurrent.at(-1));tied.focal_id=tied.rows[0].prompt.event_id='z';tied.rows[0].prompt.prompt_number=200;
  show([tied,concurrent.at(-1)],history);assert.match(retained.attributes['aria-label'],/Prompt 200 · Running/,'stable event-ID tie break');
  const unverified=card('h4',999,true);unverified.rows[0].prompt.execution_unverified=true;
   show([...concurrent,unverified],history);assert.equal(time.textContent,'▶ 12:34');
  assert.match(retained.attributes['aria-label'],/Running/,'genuinely running wins over unverified candidate');
   show([unverified],history);assert.match(retained.attributes['aria-label'],/Unverified/);assert.equal(retained.className,'');
   assert.equal(time.textContent,'12:34');
  helpText(cost);
  assert.equal(view.doc.body.children.at(-1).children.length,0,'unverified Duration is plain text');
  const ended=Array.from({length:5},(_,i)=>{const c=card('h4',400+i);c.focal_id=c.rows[0].prompt.event_id='end'+i;return c;});
  show(ended,history);assert.equal(ids().filter(id=>id==='h4').length,1);assert.equal(view.promptRows.get('h4'),retained);
   assert.equal(retained.className,'mini-success');assert.equal(ids().at(-1),'h4');
   assert.equal(time.textContent,'23:47');
  const handedOff={...ended.at(-1),focal_id:''};
  show([],[...history.slice(0,4),handedOff]);
   assert.equal(view.promptRows.get('h4'),retained);assert.equal(retained.className,'','grace expires in the same row');
   assert.equal(time.textContent,'23:47');
   for(const outcome of [{aborted:true,completed_successfully:false},{has_error:true,completed_successfully:false}]) {
     show([resumed],history);assert.equal(time.textContent,'▶ 12:34');
     const failed=structuredClone(handedOff);Object.assign(failed.rows[0].prompt,outcome);
    show([{...failed,focal_id:failed.rows[0].prompt.event_id}],history);
     assert.equal(retained.className,'mini-error');
     assert.equal(time.textContent,'23:47');
    show([],[...history.slice(0,4),failed]);assert.equal(retained.className,'','old failure is neutral');
     assert.match(retained.attributes['aria-label'],/Aborted|Error/);
     assert.equal(time.textContent,'23:47');
  }
   show([resumed],history);assert.equal(retained.className,'mini-running','a consecutive prompt resumes the same row');
   assert.equal(time.textContent,'▶ 12:34');
   for(const terminal of [{aborted:true},{has_error:true},{completed_successfully:true}]) {
     const corrected=structuredClone(resumed);Object.assign(corrected.rows[0].prompt,terminal);
     show([corrected],history);assert.equal(time.textContent,'12:34','terminal evidence forbids a play cue even with a contradictory running flag');
   }
   const unknownStart=structuredClone(resumed);unknownStart.rows[0].prompt.at_ms=null;
   show([unknownStart],history);assert.equal(time.textContent,'▶ —');assert.equal(helpText(time),'Unknown start time');
   const stale=structuredClone(input);stale.view.now_ms=saved.now_ms-1;
   show(ended,history);controller.update(stale);controller.render();
   assert.equal(time.textContent,'23:47','older SSE publication cannot revive the running cue');
   for(let repeat=0;repeat<3;repeat++) {controller.update(input);controller.render();assert.equal(time.textContent,'23:47');}
   const source=input.view.source_label;
   input.view={...input.view,source_label:'corrected-source',active_cards:[],history_cards:[{...resumed,focal_id:''}]};controller.update(input);
   assert.equal(time.textContent,'—','historical-only running-shaped data has no play cue or invented finish');
   input.view.source_label=source;show([card('replacement',500,true)],[]);
   assert.equal(view.promptRows.has('h4'),false);assert.equal(rows()[0].children[0].textContent,'▶ 12:34');
   show([],[card('replacement',600)]);assert.equal(rows()[0].children[0].textContent,'23:47','replacement session clears its own cue');
  const olderGrace=card('grace',50);olderGrace.focal_id='grace';show([olderGrace],history);
  assert.deepEqual(ids(),history.map(c=>c.session_id),'older grace cannot displace a newer history winner');
  const unknown=card('unknown',0);unknown.rows[0].prompt.completed_at_ms=null;
  show([],[unknown,...history.slice(1)]);assert.equal(ids()[0],'unknown');
  assert.equal(rows()[0].children[0].textContent,'—');assert.equal(helpText(rows()[0].children[0].children[0]),'Unknown finish time');
  for(const state of ['loading','unavailable']) {
    show([resumed],history,state);assert.deepEqual(ids(),['h4']);
    assert.match(view.body.textContent,state==='loading'?/Loading earlier sessions…/:/Unable to load earlier sessions/);
    assert.equal(view.needsHistory,true);
  }
  show([],history,'refreshing',1);assert.deepEqual(ids(),history.map(c=>c.session_id));
  assert.equal(rows().length,5);assert.doesNotMatch(view.body.textContent,/checking for changes/);
  show([],[]);assert.equal(rows().length,0);assert.equal(view.body.children[0].children[0].colSpan,5);
  show([],history.slice(0,2));assert.equal(rows().length,2,'no duplicate/fake data rows');
  for(const [amount,total] of [['N/A','562'],['49','Loading…'],['?49','562'],['0','0']]) {
    const value=card('only',10);value.rows[0].prompt.display_units={};value.rows[0].prompt.display.ccost=amount;
    value.session_summary.cost=total==='Loading…'?null:{display:{account_ccost:total}};value.session_summary.state='loading';show([],[value]);
    assert.equal(rows()[0].children[2].textContent,amount);
    assert.equal(rows()[0].children[3].textContent,total);
    assert.equal(rows()[0].children[2].children[0].attributes['aria-label'],'Prompt reference CCost: '+amount);
    assert.equal(rows()[0].children[3].children[0].attributes['aria-label'],'Whole-session reference CCost: '+total);
    const target=rows()[0].children[3].children[0];
    assert.equal(target.className,'mini-cost-value help-value');assert.equal(target.tabIndex,0);
    assert.equal(target.attributes.title,undefined);assert.ok(target.events.focus&&target.events.pointerenter);
     assert.match(rows()[0].totalCostHelp,total==='Loading…'
       ? /Whole-session reference CCost/ : /CCost cannot be calculated.*N\/A does not mean zero/);
  }
  // Source-corrected whole-session subtotals never replace the representative cost.
  const partial=card('subtotal',500,true),summary=partial.session_summary;
  partial.rows[0].prompt.display_units={};
  summary.cost={known_ccost:'562',complete:false,observed_requests:3,priced_requests:2,
    display:{known_ccost:'?562',account_ccost:'562'},display_units:{
      credits:{known_ccost:'?562',account_ccost:'562'},usd:{known_ccost:'?$5.62',account_ccost:'$5.62'}}};
  const canonical=JSON.stringify(partial);
  for(const stage of ['running','grace','history']) {
    partial.rows[0].prompt.in_progress=stage==='running';partial.rows[0].prompt.completed_at_ms=600;
    for(const [unit,expected] of [['credits','562'],['usd','$5.62']]) {
      vm.runInContext(`ReportView.setUnit('${unit}')`,context);
      show(stage==='history'?[]:[partial],stage==='history'?[partial]:[]);
      const row=rows()[0];assert.equal(row.children[3].textContent,expected);
      assert.equal(row.children[2].textContent,'49');
    }
  }
  partial.rows[0].prompt.in_progress=true;partial.rows[0].prompt.completed_at_ms=null;
  assert.equal(JSON.stringify(partial),canonical,'display never rewrites canonical cost/completeness');
  vm.runInContext('ReportView.setUnit("credits")',context);
  for(const [cost,state,expected] of [
    [{display:{account_ccost:'563'},observed_requests:3,priced_requests:2},'refreshing','563'],
    [{display:{account_ccost:'—'},observed_requests:3,priced_requests:0},'observed','N/A'],
    [{display:{account_ccost:'0'},observed_requests:0,priced_requests:0},'observed','0'],
    [null,'unavailable','N/A'],[null,'loading','Loading…']]) {
    summary.cost=cost;summary.state=state;show([partial],[]);
    assert.equal(rows()[0].children[3].textContent,expected);
  }
  // Full Watch keeps its independent per-prompt rows and certified five history cards.
  show(saved.active_cards,history);context.fullInput=input;context.fullParent=view.el('div');context.fullState={connection:'Live connected.'};
  vm.runInContext('ReportView.renderLive(fullParent,fullInput,fullState)',context);
  assert.equal(context.fullState.watch.history.children.length,5);
  input.view=saved;controller.update(input);
};
