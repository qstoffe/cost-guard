// Source authorization, not time/string parsing, decides Mini display continuity.
const assert = require('node:assert/strict');
module.exports = function(controller, view, input, helpText) {
  const saved = structuredClone(input.view), base = saved.active_cards[0];
  let now = saved.now_ms;
  const card = (id, prompt, tokens, text, handoff=null) => {
    const value = structuredClone(base);
    Object.assign(value,{session_id:id,focal_id:prompt,context_handoff:handoff,state:'observed'});
    Object.assign(value.rows[0].prompt,{event_id:prompt,in_progress:true,execution_unverified:false});
    value.rows[0].live_context = {watch_next_context_tokens:tokens,display:{watch_next_context_tokens:text,
      watch_delta_context_tokens:tokens==null?'N/A':'+3k'}};
    return value;
  };
  const prior = card('A','p1',172000,'172k');
  const pending = card('A','p2',null,'N/A',{previous_id:'p1',previous_tokens:172000});
  const show = (cards, extra={}) => {input.view={...saved,now_ms:++now,active_cards:cards,history_cards:[],...extra};controller.update(input);};
  const cell = id => view.promptRows.get(id).children[4];
  show([prior]);assert.equal(cell('A').textContent,'172k');
  for(let i=0;i<4;i++) {
    show([pending,card('B','p2',null,'N/A')]);controller.render();
    assert.equal(cell('A').textContent,'172k');assert.equal(cell('B').textContent,'N/A');
    assert.match(helpText(cell('A')),/previous same-session estimate; current prompt pending refresh/);
    assert.match(helpText(cell('A')),/Δ Ctx: N\/A/);
  }
  const fresh=card('A','p2',175000,'175k');show([fresh]);
  assert.equal(cell('A').textContent,'175k');assert.doesNotMatch(helpText(cell('A')),/previous same-session/);
  // Fresh evidence with the same number must still advance the prompt identity.
  show([card('A','p3',null,'N/A',{previous_id:'p2',previous_tokens:175000})]);assert.equal(cell('A').textContent,'175k');
  show([card('A','p3',175000,'175k')]);assert.doesNotMatch(helpText(cell('A')),/previous same-session/);
  show([card('A','p4',null,'N/A',{previous_id:'p3',previous_tokens:175000})]);assert.equal(cell('A').textContent,'175k');
  show([card('A','p4',null,'N/A')]);assert.equal(cell('A').textContent,'N/A','authoritative invalidation clears retention');
  show([pending]);assert.equal(cell('A').textContent,'N/A','invalidated value cannot revive');
  show([prior]);show([]);show([pending]);assert.equal(cell('A').textContent,'N/A','removal/reappearance is fresh');
  show([prior]);show([pending],{source_label:'another source'});assert.equal(cell('A').textContent,'N/A');
  show([prior]);show([pending],{history_scope:'another source epoch'});assert.equal(cell('A').textContent,'N/A');
  show([prior]);const unverified=structuredClone(pending);unverified.rows[0].prompt.execution_unverified=true;
  show([unverified]);assert.equal(cell('A').textContent,'N/A');
  show([prior]);const corrected=structuredClone(pending);corrected.context_handoff.previous_tokens=171000;
  show([corrected]);assert.equal(cell('A').textContent,'N/A','source correction rejects an obsolete visible value');
  const history=card('A','p1',172000,'172k');history.focal_id='';history.rows[0].prompt.in_progress=false;
  history.session_summary.context={watch_next_context_tokens:172000,display:{watch_next_context_tokens:'172k'}};
  show([],{history_cards:[history],history_state:'observed'});show([pending]);assert.equal(cell('A').textContent,'172k','validated continuing history may resume');
  history.session_summary.context.watch_next_context_tokens=999000;
  history.session_summary.context.display.watch_next_context_tokens='999k';
  show([],{history_cards:[history],history_state:'observed'});show([pending]);assert.equal(cell('A').textContent,'N/A','unrelated session summary cannot seed a prompt');
  const zero=card('A','zero',0,'0');show([zero]);show([card('A','next',null,'N/A',{previous_id:'zero',previous_tokens:0})]);
  assert.equal(cell('A').textContent,'0');
  show([prior]);const newer=structuredClone(input.view);show([fresh]);
  controller.update({state:'running',view:newer});assert.equal(cell('A').textContent,'175k','late HTTP snapshot cannot rewind');
  controller.settings({miniWatchPlacement:'remember-last'},'changed-host');show([pending]);assert.equal(cell('A').textContent,'N/A');
  controller.settings({miniWatchPlacement:'remember-last'},'fixture-host');
  input.view=saved;controller.update(input);
};
