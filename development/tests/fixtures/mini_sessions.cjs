// Mini session-table regression cases over immutable server display tokens, not valuation.
const assert = require('node:assert/strict');
module.exports = function sessionTables(vm, context, controller, view, input, helpText) {
  const saved = structuredClone(input.view), active = saved.active_cards[0];
  const summary = active.session_summary;
  // Startup and Mini opened halfway through the same fixed catalog: neither
  // client may treat a supplied provisional candidate as a verified winner.
  for (const cards of [[], [active]]) {
    input.view = {...saved, history_state:'loading', history_cards:cards};
    controller.update(input);
    assert.equal(view.historyBody.textContent, 'Loading earlier sessions…');
    context.historyInput = input; context.historyParent = view.el('div');
    vm.runInContext('ReportView.renderLive(historyParent, historyInput, {connection:"Live connected."})', context);
    assert.match(context.historyParent.textContent, /Loading earlier sessions…/);
  }
  input.view = saved; controller.update(input);
  assert.equal(view.earlier.hidden, true);
  assert.equal(view.earlierToggle.attributes['aria-expanded'], 'false');
  assert.equal(view.earlierToggle.attributes['aria-controls'], view.earlier.id);
  assert.equal(view.earlier.attributes['aria-labelledby'], view.earlierToggle.id);
  assert.deepEqual(view.body.parentNode.querySelectorAll('th').map(cell => cell.textContent),
    ['Session', 'CCost (Total)', 'Duration', 'Ctx']);
  assert.deepEqual(view.historyBody.parentNode.querySelectorAll('th').map(cell => cell.textContent),
    ['Finished', 'Session', 'CCost (Total)', 'Ctx']);
  assert.match(view.historyBody.parentNode.attributes['aria-label'], /latest valid session context \(Ctx\)/);
  const activityHeader = view.historyBody.parentNode.querySelectorAll('th')[0];
  assert.match(helpText(activityHeader.children[0]), /latest supported finish[\s\S]*full local date and offset/);
  const contextHeader = view.historyBody.parentNode.querySelectorAll('th')[3];
  assert.match(helpText(contextHeader.children[0]), /Last valid estimate of the next request’s context[\s\S]*Not historical prompt context or a sum[\s\S]*N\/A means unavailable/);
  assert.equal(contextHeader.title, undefined);
  for (const body of [view.body, view.historyBody]) {
    const header = body.parentNode.querySelectorAll('th')[body === view.body ? 0 : 1];
    assert.equal(header.textContent, 'Session');
    assert.equal(header.querySelectorAll('button').length, 1);
    const session = header.children[0];
    assert.equal(helpText(session), 'The name of the session.');
    assert.doesNotMatch(helpText(session), /CCost/);
    const costHeader = body.parentNode.querySelectorAll('th')[body === view.body ? 1 : 2];
    assert.match(helpText(costHeader.children[0]), /First: .*prompt’s reference CCost[\s\S]*In parentheses: the entire session’s reference CCost[\s\S]*Not provider billing[\s\S]*N\/A[\s\S]*partial pricing/);
  }
  const cost = (row, historical = false) => row.children[historical ? 2 : 1].children[0].textContent;
  assert.deepEqual(view.body.children.map(row => cost(row)), ['2 (4583)', '3 (4583)']);
  const title = view.body.children[0].children[0].children[0].children[0];
  assert.equal(title.tabIndex, 0); assert.equal(title.title, undefined);
  assert.equal(helpText(title), 'Concurrent\nPrompt #23 in this session');
  const activeCost = view.body.children[0].children[1].children[0];
  assert.equal(activeCost.tabIndex, 0);
  assert.match(helpText(activeCost), /Prompt #23\nMain model:[\s\S]*Effort:[\s\S]*Duration: 10m/);
  assert.match(helpText(view.body.children[1].children[1].children[0]), /Prompt #24[\s\S]*Duration: 20m/);
  assert.equal(view.body.children[0].children[0].textContent, 'Concurrent', 'Session contains no cost');
  const history = index => ({...active, session_id:'history-'+index, title:'Earlier '+index, focal_id:'',
    session_summary:{...summary, context:{display:{watch_next_context_tokens:String(900+index)}}},
    rows:[{...active.rows[0], live_context:{display:{watch_next_context_tokens:'17'}},
      prompt:{...active.rows[0].prompt, in_progress:false, completed_at_ms:index ? 1000+index : null,
        display:{...active.rows[0].prompt.display, finished_clock:'23:47', finished_date_time:'2026-11-05 23:47 +0100'}}}]});
  input.view = {...saved, history_cards:[0,1,2,3,4].map(history)};
  controller.update(input); view.earlierToggle.fire('click');
  assert.equal(view.earlier.hidden, false);
  assert.equal(view.earlierToggle.attributes['aria-expanded'], 'true');
  assert.deepEqual(view.historyBody.children.map(row => row.dataset.id), ['history-2','history-3','history-4']);
  assert.deepEqual(view.historyBody.children.map(row => row.children[3].textContent), ['902','903','904']);
  assert.ok(view.historyBody.children.every(row => row.children.length === 4 && cost(row, true) === '2 (4583)'));
  assert.equal(view.earlier.parentNode, view.prompts, 'both tables use one region');
  const row = view.historyBody.children[0];
  assert.equal(row.querySelectorAll('button').length,0,'history values have no duplicate cues');
  assert.match(row.attributes['aria-label'], /Earlier session · Earlier 2/);
  const detail = row.children[2].children[0];
  const historicalTitle = row.children[1].children[0].children[0];
  assert.equal(historicalTitle.tabIndex, 0);
  assert.equal(helpText(historicalTitle), 'Earlier 2\nPrompt #23 in this session');
  assert.equal(detail.tabIndex, 0); assert.equal(detail.title, undefined);
  const historicalItem = input.view.history_cards[2].rows[0], originalItem = structuredClone(historicalItem);
  Object.assign(historicalItem, {model:'Example Model', effort:'high', display:{watch_duration_ms:'4m 12s'}});
  Object.assign(historicalItem.prompt, {prompt_number:7, calls:12, linked_agent_count:2, has_additional_model:true,
    unresolved_cost:true, aborted:true, abort_reason:'quota_limit',
    cost_detail:{model_count:2, calls_complete:false, parts:[{role:'main',provider_id:'example',model_id:'model'}]}});
  controller.update(input);
  assert.match(helpText(detail), /Prompt #7\nMain model: Example Model \[example\/model\]\nEffort: high\nDuration: 4m 12s\nCalls: 12/);
  assert.equal(helpText(historicalTitle), 'Earlier 2\nPrompt #7 in this session');
  assert.equal(row.children[1].children[0].children[0], historicalTitle);
  assert.match(helpText(detail), /Linked subagents: 2[\s\S]*Multiple models[\s\S]*Partial pricing[\s\S]*attribution incomplete[\s\S]*Aborted · quota limit/);
  assert.doesNotMatch(helpText(detail), /preview|raw prompt/i);
  Object.assign(historicalItem, {model:'N/A', effort:'N/A', display:{}});
  Object.assign(historicalItem.prompt, {prompt_number:null, calls:null, linked_agent_count:0, has_additional_model:false,
    unresolved_cost:false, aborted:false, abort_reason:'', cost_detail:null});
  controller.update(input);
  assert.equal(row.children[2].children[0], detail, 'detail target is stable across corrections');
  assert.equal(helpText(detail), 'Prompt number unavailable\nMain model: N/A\nEffort: N/A\nDuration: N/A');
  assert.equal(helpText(historicalTitle), 'Earlier 2\nPrompt number unavailable');
  Object.assign(historicalItem, originalItem); controller.update(input);
  for (let index=0;index<20;index++) {input.view.now_ms++; controller.update(input);}
  assert.equal(view.historyBody.children[0],row,'publication preserves row/focus identity');
  assert.equal(view.earlier.hidden,false,'SSE never resets disclosure');
  const time = row.children[0].children[0], running = view.body.children.map(node => node.textContent);
  assert.equal(time.tabIndex,0); assert.equal(time.title,undefined);
  assert.equal(time.textContent,'23:47'); assert.equal(helpText(time),'2026-11-05 23:47 +0100');
  for (const [clock, full] of [['00:08','2026-11-06 00:08 +0100'],
    ['02:30','2026-10-25 02:30 +0200'], ['02:30','2026-10-25 02:30 +0100']]) {
    Object.assign(input.view.history_cards[2].rows[0].prompt.display,{finished_clock:clock,finished_date_time:full});
    controller.update(input);
    assert.equal(view.historyBody.children[0],row); assert.equal(row.children[0].children[0],time);
    assert.equal(time.textContent,clock); assert.equal(helpText(time),full,'server timezone/offset tokens win over browser Date');
  }
  const retry = structuredClone(input.view.history_cards[2]); retry.state='retrying';
  input.view.history_cards[2]=retry; input.view.history_state='refreshing'; input.view.history_epoch=1; controller.update(input);
  assert.equal(time.textContent,'02:30','failed source retry retains the authentic finish');
  assert.match(view.historyBody.textContent,/Previously verified sessions/);
  input.view.history_state='observed'; controller.update(input);
  assert.deepEqual(view.body.children.map(node => node.textContent),running,'historical-only updates leave running semantics unchanged');
  view.earlierToggle.fire('click'); controller.update(input);
  assert.equal(view.earlier.hidden,true);
  view.earlierToggle.fire('click'); assert.equal(view.historyBody.children[0],row,'toggle never reacquires or rebuilds');
  const certified = structuredClone(input.view);
  const winnerIds = certified.history_cards.map(card => card.session_id);
  context.stagedParent = view.el('div'); context.stagedState = {connection:'Live connected.'};
  for (const ready of [false, true]) {
    input.view = structuredClone(certified);
    for (const card of input.view.history_cards) {
      card.session_summary = {...card.session_summary, state:ready?'observed':'loading',
        cost:ready?summary.cost:null,
        context:{...summary.context, warning:{...summary.context.warning,
          guidance_state:ready?'ready':'pending', multiplier:ready?'2.4':null,
          display:{warning_cost:ready?'(2.4x more expensive)':'(Price comparison pending)'}}}};
    }
    controller.update(input); context.stagedInput=input;
    vm.runInContext('ReportView.renderLive(stagedParent, stagedInput, stagedState)', context);
    const full = context.stagedState.watch;
    assert.deepEqual(full.history.children.map(card=>card.dataset.session),winnerIds);
    assert.deepEqual(view.historyBody.children.map(row=>row.dataset.id),winnerIds.slice(-3));
    for (const card of full.cards.values()) {
      if (!winnerIds.includes(card.value.session_id)) continue;
      assert.equal(card.summary.dataset.guidance,ready?'ready':'pending');
      assert.equal(card.costLabel.textContent,ready?'4583':'Loading…');
      assert.equal(card.contextValue.textContent,'120k');
      assert.equal(card.title.textContent,card.value.title);
      assert.equal(card.body.children[0].children[0].textContent,
        card.value.rows[0].prompt.display.finished_clock);
    }
    assert.ok(view.historyBody.children.every(row=>cost(row,true)==='2 ('+(ready?'4583':'Loading…')+')'));
    assert.ok(view.historyBody.children.every(row=>row.children[3].textContent==='120k'));
    assert.equal(view.historyBody.children[0],row,'enrichment preserves the certified Mini row');
    assert.equal(input.view.history_epoch,certified.history_epoch,'field updates never invent a proof epoch');
  }
  input.view=certified; controller.update(input);
  vm.runInContext('ReportView.setUnit("usd")',context); controller.settings();
  assert.ok(view.body.children.every(row => cost(row).endsWith(' ($45.82)')));
  assert.ok(view.historyBody.children.every(row => cost(row, true)==='$0.01 ($45.82)'));
  vm.runInContext('ReportView.setUnit("credits")',context); controller.settings();
  for (const [value,expected] of [
    [{...summary,cost:null,state:'loading'},'Loading…'],
    [{...summary,cost:null,state:'unavailable'},'N/A'],
    [{...summary,cost:{observed_requests:2,priced_requests:0,complete:false}},'N/A'],
    [{...summary,state:'partial',cost:{observed_requests:2,priced_requests:1,complete:false,display:{known_ccost:'?12'}}},'?12'],
    [{...summary,cost:{observed_requests:0,priced_requests:0,complete:true,display:{known_ccost:'0'}}},'0'],
    [{...summary,state:'refreshing'},'4583'], [{...summary,state:'unavailable'},'4583']]) {
    input.view.active_cards = saved.active_cards.map(card=>({...card,session_summary:value}));
    input.view.history_cards = [history(0)].map(card=>({...card,session_summary:value})); controller.update(input);
    assert.ok(view.body.children.every(row=>cost(row).endsWith(' ('+expected+')')));
    assert.equal(cost(view.historyBody.children[0], true), '2 ('+expected+')');
    assert.equal(view.body.children[0].children[0].textContent, 'Concurrent', 'source captions never change Session row height');
    if (['partial','unavailable'].includes(value.state)) assert.match(helpText(view.body.children[0].children[1].children[0]), /Source evidence:/);
  }
  const resumed = {...history(3),focal_id:active.focal_id};
  input.view = {...saved, active_cards:[...saved.active_cards,resumed],history_cards:[history(3),history(4)]};
  controller.update(input);
  assert.deepEqual(view.historyBody.children.map(row=>row.dataset.id),['history-4'],'no active/grace duplicate');
  input.view = {...input.view,active_cards:saved.active_cards,history_cards:[history(3),history(4)]};
  controller.update(input); assert.equal(view.historyBody.children.length,2,'eligible re-entry');
  input.view = {...input.view,history_cards:[history(0)]}; controller.update(input);
  assert.equal(view.historyBody.children.length,1,'unknown finish fallback keeps server order');
  assert.equal(view.historyBody.children[0].children[0].textContent,'—','null timestamp overrides misleading display tokens');
  assert.equal(helpText(view.historyBody.children[0].children[0].children[0]),'Unknown finish time');
  input.view.history_cards[0].rows=[]; controller.update(input);
  assert.equal(view.historyBody.children[0].children[0].textContent,'—','missing representative is unknown');
  assert.equal(helpText(view.historyBody.children[0].children[0].children[0]),'Unknown finish time');
  input.view = {...input.view,history_cards:[],history_state:'unavailable'}; controller.update(input);
  assert.equal(view.historyBody.textContent,'Unable to verify latest sessions','server owns retention and invalidation');
  assert.equal(view.observationHelp,undefined);
  input.view.history_state='observed'; controller.update(input);
  assert.equal(view.historyBody.textContent,'No earlier sessions','canonical empty clears retained history');
  assert.equal(view.historyBody.children[0].children[0].colSpan,4);
  input.view.history_state='loading'; controller.update(input);
  assert.equal(view.historyBody.textContent,'Loading earlier sessions…');
  assert.equal(view.historyBody.children[0].children[0].colSpan,4);
  input.view.history_state='unavailable'; controller.update(input);
  assert.equal(view.historyBody.textContent,'Unable to verify latest sessions');
  assert.equal(view.historyBody.children[0].children[0].colSpan,4);
  input.view = {...saved,active_cards:saved.active_cards.map(card=>({...card,title:''}))}; controller.update(input);
  assert.equal(view.body.children[0].children[0].children[0].children[0].textContent,active.session_id);
  assert.equal(view.body.children[0].children[0].querySelectorAll('button').length,0);
  for (const [promptCost,total,expected] of [['N/A','562','N/A (562)'], ['49','Loading…','49 (Loading…)'],
      ['?49','?562','?49 (?562)'], ['0','0','0 (0)']]) {
    const card = structuredClone(active);
    card.rows[0].prompt.display_units = {}; card.rows[0].prompt.display = {ccost:promptCost};
    card.session_summary = {...summary,cost:{display:{known_ccost:total}},state:'observed'};
    input.view = {...saved,active_cards:[card],history_cards:[{...card,session_id:'distinct-earlier',focal_id:''}]};
    controller.update(input);
    assert.equal(cost(view.body.children[0]),expected);
    assert.equal(cost(view.historyBody.children[0],true),expected,'independent prompt/whole-session formats');
    assert.match(view.historyBody.children[0].children[2].children[0].attributes['aria-label'],/Prompt reference CCost: .*; whole-session reference CCost:/);
  }
  view.earlierToggle.fire('click'); input.view=saved; controller.update(input);
};
