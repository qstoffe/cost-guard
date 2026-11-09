// Actual shipped Watch DOM/layout under transient and sustained source states.
const assert = require('node:assert/strict');
module.exports = async function quiet({evaluate,layouts,checks}) {
  const result = await evaluate(`(() => {
    const view=current.watch, p=structuredClone(liveValue), cards=[...p.view.active_cards,...p.view.history_cards];
    const clock=Date.now,start=clock();let now=start;Date.now=()=>now;
    for(const c of cards) {c.state='observed';c.observed_at_ms=start;}
    p.source_observed_at_ms=start;view.update(p);
    const snapshot=()=>[...view.cards.values()].map(c=>({text:c.root.textContent,height:c.root.getBoundingClientRect().height,
      summary:c.summary.textContent,cost:c.costLabel.textContent,message:c.message.textContent,hidden:c.message.hidden}));
    const before=snapshot();
    for(const c of cards) {c.state='partial';c.session_summary.state='partial';}
    const cycles=[];
    view.update(p);
    for(const ms of [1000,5000,10000,30000,59999]) {now=start+ms;p.view.now_ms++;view.update(p);cycles.push(snapshot());}
    now=start+60000;view.update(p);const sustained=snapshot();
    p.state='retrying';view.update(p);now+=60000;view.update(p);const source=view.empty.textContent;
    for(const c of cards) {c.state='unavailable';c.session_summary.state='unavailable';}
    view.update(p);const unavailable=snapshot();
    const recovered=structuredClone(liveValue);recovered.source_observed_at_ms=now+1;
    for(const c of [...recovered.view.active_cards,...recovered.view.history_cards])c.observed_at_ms=now+1;
    view.update(recovered);Date.now=clock;return {before,cycles,sustained,source,unavailable,recovered:snapshot()};
  })()`);
  for (const cycle of result.cycles) cycle.forEach((card,i)=>{
    assert.equal(card.height,result.before[i].height); assert.equal(card.cost,result.before[i].cost);
    assert.equal(card.message,''); assert.equal(card.hidden,true);
    assert.doesNotMatch(card.summary,/refreshing|retrying|retained total/i);
  });
  // App-owned source retry feedback is not duplicated in card/day notices.
  assert.equal(result.source,'');
  for(const card of result.sustained) {assert.equal(card.message,''); assert.doesNotMatch(card.summary,/partial source evidence/);}
  for(const card of result.unavailable) assert.equal(card.message,'');
  result.recovered.forEach((card,i)=>assert.equal(card.height,result.before[i].height));
  layouts.push({case:'quiet-watch-refresh',...result});
  checks.push('Five real DOM refresh/revaluation cycles retain prompt/session figures and exact card heights; sustained delay, unavailable source and recovery remain silent after useful content');
};
