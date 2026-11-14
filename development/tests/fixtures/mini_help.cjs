// Mini-only value help: selected prompt identity, source tokens and canonical warnings.
const assert = require('node:assert/strict');
module.exports = function miniHelp(controller, view, input, helpText) {
  const saved = structuredClone(input.view), base = structuredClone(saved.active_cards[0]);
  base.session_id = 'help-a'; base.title = 'Example Session'; base.focal_id = 'prompt-21';
  const item = base.rows[0], prompt = item.prompt;
  Object.assign(prompt, {event_id:'prompt-21',prompt_number:21,preview:'Implement pagination for this table'});
  item.live_context = {display:{watch_next_context_tokens:'128k',watch_delta_context_tokens:'+4k'}};
  base.session_summary.context = {display:{watch_next_context_tokens:'900k'}};
  const show = (active=[base], history=[]) => {
    input.view = {...saved,active_cards:active,history_cards:history,history_state:'observed',history_epoch:1};
    controller.update(input); return view.promptRows.get('help-a');
  };
  const row = show(), title = row.children[1].children[0].children[0], ctx = row.children[4];
  assert.equal(helpText(title), 'Example Session\nPrompt #21: Implement pagination for…');
  assert.equal(row.contextHelp,'');assert.equal(ctx.tabIndex,-1);
  const visible = row.textContent;
  for (const [preview, expected] of [
    ['Short hint','Short hint'], ['1234567890123456789012345','1234567890123456789012345'],
    ['12345678901234567890123456','1234567890123456789012345…'],
    ['  two\n\twords\u0000 here  ','two words here'],
    ['a'.repeat(24)+'e\u0301 tail','a'.repeat(24)+'e\u0301…'],
    ['a'.repeat(24)+'👨‍👩‍👧‍👦 tail','a'.repeat(24)+'👨‍👩‍👧‍👦…'],
    ['a'.repeat(24)+'👍🏽 tail','a'.repeat(24)+'👍🏽…'],
    ['a'.repeat(24)+'… tail','a'.repeat(24)+'…'],
    ['a'.repeat(22)+'... tail','a'.repeat(22)+'…'],
    ['<img src=x onerror=alert(1)>','<img src=x onerror=alert(…']]) {
    prompt.preview = preview; show();
    assert.equal(helpText(title),'Example Session\nPrompt #21: '+expected);
    assert.equal(title.children.length,0,'preview remains text-only contextual help, not markup');
    assert.equal(row.textContent,visible,'tooltips do not change the compact row');
  }
  for (const preview of ['', ' \n ', null, undefined, 42]) {
    prompt.preview = preview; show();
    assert.equal(helpText(title),'Example Session\nPrompt #21');
  }
  prompt.preview = 'Available hint'; prompt.prompt_number = null; show();
  assert.equal(helpText(title),'Example Session\nPrompt number unavailable\nPrompt: Available hint');
  prompt.preview = ''; base.title = ''; show();
  assert.equal(helpText(title),'help-a\nPrompt number unavailable','unnamed sessions retain stable identity');
  base.title = 'Example Session';
  const history = structuredClone(base); history.focal_id = '';
  history.rows[0].prompt = {...prompt,in_progress:false,completed_at_ms:1000,preview:'Historical hint',prompt_number:20};
  history.rows[0].live_context = {display:{watch_next_context_tokens:'17k',watch_delta_context_tokens:'+12k'}};
  show([], [history]);
  assert.equal(view.promptRows.get('help-a'),row);
  assert.equal(ctx.textContent,'900k');
  assert.equal(row.contextHelp,'');
  assert.equal(helpText(title),'Example Session\nPrompt #20: Historical hint');
  history.rows[0].live_context = null; show([], [history]);
  assert.equal(row.contextHelp,'');
  history.rows = []; show([], [history]);
  assert.equal(helpText(title),'Example Session\nPrompt number unavailable');
  assert.equal(row.contextHelp,'');
  prompt.prompt_number = 21; prompt.preview = 'Original hint'; show();
  for (const delta of ['0','+4k','-12k','N/A','~source-token']) {
    item.live_context.display.watch_delta_context_tokens = delta; show();
    assert.equal(row.contextHelp,'');
    assert.equal(ctx.textContent,'128k');
  }
  item.live_context = null; show();
  assert.equal(row.contextHelp,'');
  item.live_context = {display:{watch_next_context_tokens:'0k',watch_delta_context_tokens:'0'}};
  for (const [severity, state, contextState, multiplier] of [
    ['none','ready','ready-current',null],['approaching','ready','ready-current','2.4'],
    ['exceeded','ready','ready-current','2.4'],['exceeded','ready','ready-current',null],
    ['exceeded','pending','ready-current',null],['exceeded','refreshing','ready-current','2.4'],
    ['exceeded','unavailable','ready-current',null],['exceeded','ready','pending','2.4'],
    ['exceeded','ready','invalidated','2.4']]) {
    Object.assign(base.session_summary.context,{context_state:contextState,context_scope:'help',
      watch_next_context_tokens:230000,warning:{severity,multiplier,
      text:'[Price threshold >200k exceeded]',guidance_state:state,display:{warning_cost:'(2.4x more expensive)'}}}); show();
    const exceeded=severity==='exceeded'&&state==='ready'&&contextState==='ready-current';
    assert.equal(row.contextHelp,exceeded?'Price threshold >200k exceeded'+(multiplier?' · 2.4x more expensive':''):'');
    assert.equal(ctx.tabIndex,exceeded?0:-1);
    assert.equal(ctx.className.includes('mini-context-exceeded'),exceeded);
    if(exceeded)assert.equal(helpText(ctx),row.contextHelp);
    assert.equal(ctx.dataset.guidance,state);
  }
  base.session_summary.context={display:{watch_next_context_tokens:'900k'}};
  const other = structuredClone(base); other.session_id = 'help-b'; other.title = 'Other session';
  const next = structuredClone(base); next.focal_id = next.rows[0].prompt.event_id = 'prompt-22';
  next.title = 'Renamed session'; Object.assign(next.rows[0].prompt,{at_ms:prompt.at_ms+1,prompt_number:22,preview:'Replacement hint'});
  next.rows[0].live_context.display = {watch_next_context_tokens:'256k',watch_delta_context_tokens:'-4k'};
  next.session_summary.context.warning = null;
  show([base,next,other],[history]);
  assert.equal(view.promptRows.get('help-a'),row);
  assert.equal(helpText(title),'Renamed session\nPrompt #22: Replacement hint');
  assert.equal(row.contextHelp,'');
  assert.equal(view.promptRows.get('help-b').contextHelp,'');
  assert.equal(row.children.length,5); assert.equal(row.querySelectorAll('button').length,0);
  assert.equal(title.tabIndex,0); assert.equal(ctx.tabIndex,-1);
  input.view = saved; controller.update(input);
};
