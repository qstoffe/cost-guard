// Session-qualified state survives missing prompt permission and DOM remounts.
const assert = require('node:assert/strict');
module.exports = function(controller, view, input, helpText) {
  const saved=structuredClone(input.view), base=saved.active_cards[0];let now=saved.now_ms;
  const card=(id,prompt,tokens,state='ready-current',epoch='epoch')=>{
    const value=structuredClone(base);
    Object.assign(value,{session_id:id,focal_id:prompt,context_handoff:null,state:'observed'});
    Object.assign(value.rows[0].prompt,{event_id:prompt,in_progress:true,execution_unverified:false});
    value.rows[0].live_context={watch_next_context_tokens:tokens,display:{
      watch_next_context_tokens:tokens==null?'N/A':`${tokens/1000}k`,watch_delta_context_tokens:'N/A'}};
    value.session_summary.context={context_scope:'source:'+id,context_epoch:epoch,context_state:state,
      watch_next_context_tokens:tokens,display:{watch_next_context_tokens:tokens==null?'N/A':`${tokens/1000}k`}};
    return value;
  };
  const prior=card('A','p1',230000), pending=card('A','p2',null,'pending');
  const show=(cards,extra={})=>{input.view={...saved,now_ms:++now,active_cards:cards,history_cards:[],...extra};controller.update(input);};
  const cell=id=>view.promptRows.get(id).children[4];
  show([prior]);assert.equal(cell('A').textContent,'230k');
  for(const state of ['observed','partial','retrying','loading','observed']) {
    const early=structuredClone(pending);early.state=state;
    show([early,card('B','new',null,'pending')]);controller.render();
    assert.equal(cell('A').textContent,'230k');assert.equal(cell('B').textContent,'N/A');
    assert.match(helpText(cell('A')),/previous same-session estimate; current prompt pending refresh/);
    assert.match(helpText(cell('A')),/Δ Ctx: N\/A/);
  }
  show([pending],{history_scope:'unrelated history owner',history_epoch:72});
  assert.equal(cell('A').textContent,'230k','history proof lifetime is not context identity');
  view.drawSessions(null);controller.render();assert.equal(cell('A').textContent,'230k','DOM row is not context owner');
  show([card('A','p2',235000)]);assert.equal(cell('A').textContent,'235k');
  assert.doesNotMatch(helpText(cell('A')),/previous same-session/);
  show([card('A','p3',null,'pending')]);assert.equal(cell('A').textContent,'235k');
  show([card('A','p3',235000)]);assert.doesNotMatch(helpText(cell('A')),/previous same-session/);
  show([card('A','p4',null,'pending')]);assert.equal(cell('A').textContent,'235k');
  show([card('A','p4',null,'invalidated')]);assert.equal(cell('A').textContent,'N/A');
  show([pending]);assert.equal(cell('A').textContent,'N/A','explicit invalidation cannot revive');
  show([prior]);show([card('A','p2',null,'pending','compacted')]);assert.equal(cell('A').textContent,'N/A');
  show([prior]);show([pending],{source_label:'another source'});assert.equal(cell('A').textContent,'N/A');
  show([prior]);show([],{history_state:'observed'});show([pending]);assert.equal(cell('A').textContent,'N/A','removed session cannot leak retained context');
  const newSource=structuredClone(pending);newSource.session_summary.context.context_scope='replacement-source';
  show([prior]);show([newSource]);assert.equal(cell('A').textContent,'N/A','source instance replacement invalidates immediately');
  const unverified=structuredClone(pending);unverified.rows[0].prompt.execution_unverified=true;
  show([prior]);show([unverified]);assert.equal(cell('A').textContent,'230k','execution uncertainty alone is pending');
  const summary=card('A','p2',230000,'pending');show([summary]);
  view.drawSessions(null);controller.render();assert.equal(cell('A').textContent,'230k','fresh row uses qualified summary');
  show([prior]);const older=structuredClone(input.view);show([card('A','p2',235000)]);
  controller.update({state:'running',view:older});assert.equal(cell('A').textContent,'235k','late HTTP cannot rewind');
  controller.settings({miniWatchPlacement:'remember-last'},'changed-host');show([pending]);assert.equal(cell('A').textContent,'N/A');
  controller.settings({miniWatchPlacement:'remember-last'},'fixture-host');input.view=saved;controller.update(input);
};
