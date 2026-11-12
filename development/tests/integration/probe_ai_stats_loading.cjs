// Real DOM contract through the retained view; controlled publications are synthetic.
module.exports = async ({evaluate,checks}) => {
  const assert=require('node:assert/strict');
  const result=await evaluate(`(() => {
    const parent=document.createElement('div');document.body.append(parent);
    const view=new AIStatsView.View(()=>{}), original=structuredClone(current.result);
    const state={period:'30-days',result:null};view.update(state);view.attach(parent);
    const cards=[...parent.querySelectorAll('.ai-stat')];
    const pending=()=>cards.length===12 && cards.every(c=>c.textContent==='Loading…' && c.childNodes.length===1 &&
      c.children.length===0 && c.getAttribute('role')==='status' && c.getAttribute('aria-live')==='off');
    const cold=pending(), before=cards.map(c=>({width:c.getBoundingClientRect().width,height:c.getBoundingClientRect().height}));
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
    const nodes=cards.map(c=>c.firstChild);view.update(state);
    const retained=cards.every((c,i)=>c.firstChild===nodes[i]);
    state.period='all';state.result={...original,view:{...original.view,
      ai_stats_work:{scopes:{all:{ready:false}}}}};view.update(state);const switched=pending();
     let failed=true, cases=0;
     const invalid=structuredClone(original);invalid.view.ai_stats_policy='fun-2-tokens';
     const malformed=structuredClone(original);malformed.view.ai_stats[0].metrics=[];
     for(const result of [null,partial,invalid,malformed])
       for(const failedAttempt of [false,true]) for(const interrupted of [false,true])
         for(const loading of [false,true]) for(const phase of ['queued','deferred','parked','backoff','source_starting']) {
           Object.assign(state,{period:'30-days',result,failed:failedAttempt,interrupted,loading,phase});
           view.update(state);failed &&= pending();cases++;
         }
    state.failed=false;state.result=original;state.period='30-days';view.update(state);
    const stable=cards.every((c,i)=>c===parent.querySelectorAll('.ai-stat')[i] && c.getBoundingClientRect().width===before[i].width &&
      c.getBoundingClientRect().height===before[i].height);
     parent.remove();return {cold,sliced,quietPoll,ready,retained,switched,failed,stable,unitIndependent,order,cases};
  })()`);
   for(const [key,value] of Object.entries(result)) if(!['order','cases'].includes(key)) assert.equal(value,true,key);
   assert.equal(result.cases,160);
  assert.deepEqual(result.order.map(t=>t.replace(/^[^A-Za-z]+/,'')),[
    'AI Hourly Rate','Total AI Cost','Total Tokens','Token Consumption Rate','AI Working Time','Average Cost per Session']);
  checks.push('twelve stable shells: plain Loading-only cold/partial/period switch; no repeated poll mutations; atomic ready; truthful terminal failure; token unit independence; six ordered Overview cards');
};
