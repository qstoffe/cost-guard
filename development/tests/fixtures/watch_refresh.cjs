// Source-qualified history proof, not a timer or a recent-overlay demand flag.
module.exports = (vm, context) => {
  const assert = require('node:assert/strict');
  const saved = structuredClone(context.input);
  const history = saved.view.history_cards;
  const render = () => vm.runInContext('refreshWatch.update(refreshInput)', context);
  context.refreshInput = saved;
  vm.runInContext('globalThis.refreshWatch = new WatchView.View({connection:"Live connected."})', context);
  Object.assign(saved.view, {history_state:'observed', history_epoch:1, recent_finished_cards:[history[0]]});
  render();
  const view = context.refreshWatch, nodes = [...view.history.children];
  view.earlier.open = true;
  const card = [...view.cards.values()].find(value => value.root === nodes[0]);
  card.tools.node.open = true;
  const row = card.body.children[0];
  for (let epoch=1;epoch<4;epoch++) for (const state of ['loading','refreshing','retrying','observed','unavailable']) {
    Object.assign(saved.view, {history_state:state, history_epoch:epoch});
    render();
    assert.deepEqual([...view.history.children],nodes,'no status node mounted between populated history cards');
    assert.equal(view.history.children.length,history.length);
    assert.doesNotMatch(view.history.textContent,/Loading earlier|Refreshing|Retrying/);
    assert.equal(card.body.children[0],row);
    assert.equal(card.tools.node.open,true);
    assert.equal(view.earlier.open,true);
  }
  const promoted = structuredClone(history[0]);promoted.session_id='new-qualified-root';
  saved.view.history_cards=[promoted];saved.view.recent_finished_cards=[];
  saved.view.history_state='observed';render();
  assert.equal(view.history.children.length,1);
  assert.equal(view.history.children[0].dataset.session,'new-qualified-root');
  // A new source has no eligible history/epoch. Empty proof persists through retries.
  Object.assign(saved.view,{history_cards:[],history_scope:'new-source',history_epoch:0,history_state:'loading'});
  render();assert.equal(view.history.textContent,'Loading earlier sessions…');
  saved.view.history_state='unavailable';render();
  assert.equal(view.history.textContent,'Unable to load earlier sessions');
  saved.view.history_state='observed';saved.view.history_epoch=1;render();
  for(const state of ['loading','refreshing','retrying']) {
    saved.view.history_state=state;render();assert.equal(view.history.textContent,'No earlier sessions');
  }
  // Footer fields retain independently; source/model/epoch invalidation stays real.
  const inputCard=saved.view.active_cards[0], summary=inputCard.session_summary;
  summary.state='observed';summary.context={watch_next_context_tokens:0,context_state:'ready-current',
    context_scope:'source',context_epoch:'epoch',context_provider:'p',context_model:'m',
    display:{watch_next_context_tokens:'0'}};
  render();
  const active=[...view.cards.values()].find(value=>value.value.session_id===inputCard.session_id);
  const cost=active.costLabel.textContent;
  for(const state of ['loading','pending','refreshing','retrying']) {
    summary.state=state;summary.cost=null;
    summary.context={...summary.context,watch_next_context_tokens:null,display:{}};
    render();assert.equal(active.contextValue.textContent,'0');assert.equal(active.costLabel.textContent,cost);
    assert.doesNotMatch(active.summary.textContent,/Loading/);
  }
  summary.context={...summary.context,context_epoch:'compacted',context_state:'invalidated'};
  render();assert.equal(active.contextValue.textContent,'N/A');
  for(const field of ['context_scope','context_epoch','context_provider','context_model']) {
    summary.context={watch_next_context_tokens:47_000,context_state:'ready-current',
      context_scope:'source',context_epoch:'epoch',context_provider:'p',context_model:'m',
      display:{watch_next_context_tokens:'47k'}};
    render();assert.equal(active.contextValue.textContent,'47k');
    summary.context={...summary.context,[field]:'changed',context_state:'pending',
      watch_next_context_tokens:null,display:{}};
    render();assert.equal(active.contextValue.textContent,'N/A',field+' cannot borrow old context');
  }
};
