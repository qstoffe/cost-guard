// Actual shipped Watch DOM/layout under transient and sustained source states.
const assert = require('node:assert/strict');
module.exports = async function quiet({evaluate,layouts,checks}) {
  const result = await evaluate(`(() => {
    const view=current.watch, p=structuredClone(liveValue), cards=[...p.view.active_cards,...p.view.history_cards];
    view.update(p);
    const snapshot=()=>[...view.cards.values()].map(c=>({text:c.root.textContent,height:c.root.getBoundingClientRect().height,
      summary:c.summary.textContent,cost:c.costLabel.textContent,message:c.message.textContent,hidden:c.message.hidden}));
    const before=snapshot();
    for(const c of cards) {c.state='retrying';c.session_summary.state='refreshing';}
    p.state='retrying';
    const cycles=[];
    for(let i=0;i<5;i++) {view.update(p);cycles.push(snapshot());}
    for(const c of view.cards.values()) {c.retrySince=Date.now()-30001;c.summarySince=Date.now()-30001;}
    view.retrySince=Date.now()-30001;view.update(p);const sustained=snapshot(),source=view.empty.textContent;
    for(const c of cards) {c.state='unavailable';c.session_summary.state='unavailable';}
    view.update(p);const unavailable=snapshot();
    view.update(liveValue);return {before,cycles,sustained,source,unavailable,recovered:snapshot()};
  })()`);
  for (const cycle of result.cycles) cycle.forEach((card,i)=>{
    assert.equal(card.height,result.before[i].height); assert.equal(card.cost,result.before[i].cost);
    assert.equal(card.message,''); assert.equal(card.hidden,true);
    assert.doesNotMatch(card.summary,/refreshing|retrying|retained total/i);
  });
  assert.match(result.source,/Source updates delayed.*not current/);
  for(const card of result.sustained) {assert.match(card.message,/Prompt updates delayed.*not current/); assert.match(card.summary,/session total updates delayed.*not current/);}
  for(const card of result.unavailable) assert.match(card.message,/Source unavailable.*not current/);
  result.recovered.forEach((card,i)=>assert.equal(card.height,result.before[i].height));
  layouts.push({case:'quiet-watch-refresh',...result});
  checks.push('Five real DOM refresh/revaluation cycles retain prompt/session figures and exact card heights without retry/refresh labels in active/earlier cards; virtual sustained delay, unavailable source and recovery remain explicit');
};
