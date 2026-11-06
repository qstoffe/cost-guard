// Mini session-table regression cases over immutable server display tokens, not valuation.
const assert = require('node:assert/strict');
module.exports = function sessionTables(vm, context, controller, view, input, helpText) {
  const saved = structuredClone(input.view), active = saved.active_cards[0];
  const summary = active.session_summary;
  assert.equal(view.earlier.hidden, true);
  assert.equal(view.earlierToggle.attributes['aria-expanded'], 'false');
  assert.equal(view.earlierToggle.attributes['aria-controls'], view.earlier.id);
  assert.equal(view.earlier.attributes['aria-labelledby'], view.earlierToggle.id);
  assert.deepEqual(view.body.parentNode.querySelectorAll('th').map(cell => cell.textContent),
    ['Session (Total CCost)', '#', 'CCost', 'Duration', 'Ctx']);
  assert.deepEqual(view.historyBody.parentNode.querySelectorAll('th').map(cell => cell.textContent),
    ['Activity', 'Session (Total CCost)', 'Ctx']);
  assert.match(view.historyBody.parentNode.attributes['aria-label'], /latest valid session context \(Ctx\)/);
  const activityHeader = view.historyBody.parentNode.querySelectorAll('th')[0];
  assert.match(helpText(activityHeader.children[0]), /latest supported finish[\s\S]*full local date and offset/);
  const contextHeader = view.historyBody.parentNode.querySelectorAll('th')[2];
  assert.match(helpText(contextHeader.children[0]), /Last valid estimate of the next request’s context[\s\S]*Not historical prompt context or a sum[\s\S]*N\/A means unavailable/);
  assert.equal(contextHeader.title, undefined);
  for (const body of [view.body, view.historyBody]) {
    const header = body.parentNode.querySelectorAll('th')[body === view.body ? 0 : 1];
    assert.deepEqual(header.children[0].children.map(node => node.textContent), ['Session', ' (Total CCost)']);
    assert.equal(header.querySelectorAll('button').length, 2, 'separate text-sized targets, no help in the grid gap');
    const [session, total] = header.children[0].children;
    assert.equal(helpText(session), 'The name of the session.');
    assert.match(helpText(total), /Reference cost of the entire session[\s\S]*earlier prompts and linked subagents/);
    assert.doesNotMatch(helpText(session), /CCost/);
  }
  const cost = row => row.children[row.children.length === 3 ? 1 : 0].children[0].children[1].textContent;
  assert.deepEqual(view.body.children.map(cost), [' (4583)', ' (4583)']);
  assert.notEqual(view.body.children[0].children[2].textContent, '4583');
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
  assert.deepEqual(view.historyBody.children.map(row => row.children[2].textContent), ['902','903','904']);
  assert.ok(view.historyBody.children.every(row => row.children.length === 3 && cost(row) === ' (4583)'));
  assert.equal(view.earlier.parentNode, view.prompts, 'both tables use one region');
  const row = view.historyBody.children[0];
  assert.equal(row.querySelectorAll('button').length,0,'history values have no duplicate cues');
  assert.match(row.attributes['aria-label'], /Earlier session · Earlier 2/);
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
  retry.rows[0].prompt.display.finished_clock='12:34'; input.view.history_cards[2]=retry; controller.update(input);
  assert.equal(time.textContent,'02:30','failed source retry retains the authentic finish');
  assert.deepEqual(view.body.children.map(node => node.textContent),running,'historical-only updates leave running semantics unchanged');
  view.earlierToggle.fire('click'); controller.update(input);
  assert.equal(view.earlier.hidden,true);
  view.earlierToggle.fire('click'); assert.equal(view.historyBody.children[0],row,'toggle never reacquires or rebuilds');
  vm.runInContext('ReportView.setUnit("usd")',context); controller.settings();
  assert.ok([...view.body.children,...view.historyBody.children].every(row => cost(row)===' ($45.82)'));
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
    assert.ok([...view.body.children,...view.historyBody.children].every(row=>cost(row)===' ('+expected+')'));
    const note=view.body.children[0].children[0].children[0].children[2].textContent;
    assert.equal(Boolean(note),['partial','unavailable'].includes(value.state),'confirmed retained/partial evidence stays visible, routine refresh stays quiet');
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
  assert.equal(view.historyBody.children[0].dataset.id,'history-0','failed read retains real history');
  assert.equal(view.observationHelp,undefined);
  input.view.history_state='observed'; controller.update(input);
  assert.equal(view.historyBody.textContent,'No earlier sessions','canonical empty clears retained history');
  assert.equal(view.historyBody.children[0].children[0].colSpan,3);
  input.view.history_state='loading'; controller.update(input);
  assert.equal(view.historyBody.textContent,'Loading earlier sessions…');
  assert.equal(view.historyBody.children[0].children[0].colSpan,3);
  input.view.history_state='unavailable'; controller.update(input);
  assert.equal(view.historyBody.textContent,'Earlier sessions unavailable');
  assert.equal(view.historyBody.children[0].children[0].colSpan,3);
  input.view = {...saved,active_cards:saved.active_cards.map(card=>({...card,title:''}))}; controller.update(input);
  assert.equal(view.body.children[0].children[0].children[0].children[0].textContent,active.session_id);
  assert.equal(view.body.children[0].children[0].querySelectorAll('button').length,0);
  view.earlierToggle.fire('click'); input.view=saved; controller.update(input);
};
