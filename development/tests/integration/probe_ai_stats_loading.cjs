// Real DOM contract through the retained view; controlled publications are synthetic.
module.exports = async ({evaluate,checks}) => {
  const assert=require('node:assert/strict');
  const result=await evaluate(`(() => {
    const parent=document.createElement('div');document.body.append(parent);
    const view=new AIStatsView.View(()=>{}), original=structuredClone(current.result);
    const state={period:'30-days',result:null};view.update(state);view.attach(parent);
    const cards=[...parent.querySelectorAll('.ai-stat')];
    const pending=()=>${require('../fixtures/stats_pending.cjs')('.ai-stat','parent')};
     const cold=pending(), coldState=cards.map(c=>({metric:c.dataset.metric,text:c.textContent,
       values:[...c.querySelectorAll('.ai-stat-rate-value,.ai-stat-value:not(.ai-stat-rates)')].map(n=>n.textContent),
       children:c.childNodes.length})),
       before=cards.map(c=>({width:c.getBoundingClientRect().width,height:c.getBoundingClientRect().height}));
    const partial=structuredClone(original);partial.view.ai_stats_work.scopes['30-days'].ready=false;
    state.result=partial;view.update(state);const sliced=pending();
    const textNodes=cards.map(c=>c.firstChild);view.update(state);
    const quietPoll=cards.every((c,i)=>c.firstChild===textNodes[i]);
    state.result=original;view.update(state);
    const ready=cards.every(c=>c.querySelector('h4') && c.querySelector('.ai-stat-trait'));
    const order=[...parent.querySelector('.ai-stats-grid').querySelectorAll('h4')].map(n=>n.textContent);
    const tokenCards=cards.filter(c=>['total-tokens','token-rate'].includes(c.dataset.metric));
     const tokens=tokenCards.map(c=>c.textContent);ReportView.setUnit('usd',parent);
     const unitIndependent=tokenCards.every((c,i)=>c.textContent===tokens[i]);ReportView.setUnit('credits',parent);
     const knownCosts=Object.fromEntries(cards.filter(c=>['hourly-rate','total-cost','subagent-cost','average-cost','expensive-session'].includes(c.dataset.metric))
       .map(c=>[c.dataset.metric,[...c.querySelectorAll('.ai-stat-rate-value,.ai-stat-value:not(.ai-stat-rates)')].map(n=>n.textContent)]));
     state.result=partial;view.update(state);
     const qualifiedRetention=${require('../fixtures/stats_pending.cjs')('.ai-stat','parent','knownCosts')};
     state.result=original;view.update(state);
    const nodes=cards.map(c=>c.firstChild);view.update(state);
    const retained=cards.every((c,i)=>c.firstChild===nodes[i]);
    state.period='all';state.result={...original,view:{...original.view,
      ai_stats_work:{scopes:{all:{ready:false}}}}};view.update(state);const switched=pending();
     let failed=true, cases=0;
     const invalid=structuredClone(original);invalid.view.ai_stats_policy='fun-2-tokens';
     const malformed=structuredClone(original);malformed.view.ai_stats[0].metrics=[];
     state.period='30-days';state.result=original;view.update(state);
     for(const result of [null,partial,invalid,malformed])
       for(const failedAttempt of [false,true]) for(const interrupted of [false,true])
         for(const loading of [false,true]) for(const phase of ['queued','deferred','parked','backoff','source_starting']) {
           Object.assign(state,{period:'30-days',result,failed:failedAttempt,interrupted,loading,phase});
            view.update(state);failed &&= ${require('../fixtures/stats_pending.cjs')('.ai-stat','parent','knownCosts')};cases++;
         }
    state.failed=false;state.result=original;state.period='30-days';view.update(state);
    const stable=cards.every((c,i)=>c===parent.querySelectorAll('.ai-stat')[i] && c.getBoundingClientRect().width===before[i].width &&
      c.getBoundingClientRect().height===before[i].height);
      parent.remove();return {cold,sliced,quietPoll,ready,retained,switched,failed,stable,unitIndependent,qualifiedRetention,order,cases,coldState};
  })()`);
   for(const [key,value] of Object.entries(result)) if(!['order','cases','coldState'].includes(key))
     assert.equal(value,true,key+': '+JSON.stringify(result.coldState));
   assert.equal(result.cases,160);
  assert.deepEqual(result.order.map(t=>t.replace(/^[^A-Za-z]+/,'')),[
     'AI Hourly Rate','Total AI Cost','Subagent Cost','Total Tokens','Token Consumption Rate','AI Working Time','Average Cost per Session']);
   checks.push('thirteen stable shells: cold/new-scope N/A, exact same-scope retained CCost and Loading-only noncost cards; quiet polls, ready commit, truthful failure, token unit independence');
};
