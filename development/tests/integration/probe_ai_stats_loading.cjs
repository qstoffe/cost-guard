// Real DOM contract through the retained view; controlled publications are synthetic.
module.exports = async ({evaluate,checks}) => {
  const assert=require('node:assert/strict');
  const result=await evaluate(`(() => {
    const parent=document.createElement('div');document.body.append(parent);
    const view=new AIStatsView.View(()=>{}), original=structuredClone(current.result);
    const state={period:'30-days',result:null};view.update(state);view.attach(parent);
     const cards=[...parent.querySelectorAll('.ai-stat[data-metric]')];
     const pending=()=>${require('../fixtures/stats_pending.cjs')('.ai-stat[data-metric]','parent')};
     const cold=pending(), coldState=cards.map(c=>({metric:c.dataset.metric,text:c.textContent,
        values:[...c.querySelectorAll('.ai-stat-value')].map(n=>n.textContent),
       children:c.childNodes.length})),
       before=cards.map(c=>({width:c.getBoundingClientRect().width,height:c.getBoundingClientRect().height}));
    const partial=structuredClone(original);partial.view.ai_stats_work.scopes['30-days'].ready=false;
    state.result=partial;view.update(state);const sliced=pending();
    const indicators=cards.map(c=>c.querySelector('.metric-spinner'));view.update(state);
    const quietPoll=cards.every((c,i)=>indicators[i] && c.querySelector('.metric-spinner')===indicators[i]);
    state.result=original;view.update(state);
    const ready=cards.every(c=>c.querySelector('h4') && c.querySelector('.ai-stat-trait'));
    const order=[...parent.querySelector('.ai-stats-grid').querySelectorAll('h4')].map(n=>n.textContent);
    const tokenCards=cards.filter(c=>['total-tokens','token-rate'].includes(c.dataset.metric));
     const tokens=tokenCards.map(c=>c.textContent);ReportView.setUnit('usd',parent);
     const unitIndependent=tokenCards.every((c,i)=>c.textContent===tokens[i]);ReportView.setUnit('credits',parent);
     const knownCosts=Object.fromEntries(cards.filter(c=>['hourly-rate','total-cost','subagent-cost','average-cost','expensive-session'].includes(c.dataset.metric))
        .map(c=>[c.dataset.metric,[...c.querySelectorAll('.ai-stat-value')].map(n=>n.textContent)]));
     state.result=partial;view.update(state);
      const qualifiedRetention=${require('../fixtures/stats_pending.cjs')('.ai-stat[data-metric]','parent','knownCosts')};
     state.result=original;view.update(state);
    const nodes=cards.map(c=>c.firstChild);view.update(state);
    const retained=cards.every((c,i)=>c.firstChild===nodes[i]);
    state.period='all';state.result={...original,view:{...original.view,
      ai_stats_work:{scopes:{all:{ready:false}}}}};view.update(state);const switched=pending();
      let failed=true, cases=0, firstFailure=null;
     const invalid=structuredClone(original);invalid.view.ai_stats_policy='fun-2-tokens';
     const malformed=structuredClone(original);malformed.view.ai_stats[0].metrics=[];
     state.period='30-days';state.result=original;view.update(state);
     for(const result of [null,partial,invalid,malformed])
       for(const failedAttempt of [false,true]) for(const interrupted of [false,true])
         for(const loading of [false,true]) for(const phase of ['queued','deferred','parked','backoff','source_starting']) {
           Object.assign(state,{period:'30-days',result,failed:failedAttempt,interrupted,loading,phase});
             view.update(state);
              const retainedCase=${require('../fixtures/stats_pending.cjs')('.ai-stat[data-metric]','parent','knownCosts')};
             if(!retainedCase && !firstFailure) firstFailure={cases,scope:view.readyScope,
               values:cards.map(c=>[c.dataset.metric,c.textContent]),knownCosts};
             failed &&=retainedCase;cases++;
         }
    state.failed=false;state.result=original;state.period='30-days';view.update(state);
      const stable=cards.every((c,i)=>c===parent.querySelectorAll('.ai-stat[data-metric]')[i] && c.getBoundingClientRect().width===before[i].width &&
       c.getBoundingClientRect().height===before[i].height);
     const unsupported=structuredClone(original);
     for(const row of unsupported.view.ai_stats) for(const metric of row.metrics) {
       for(const display of [metric.display,...Object.values(metric.display_units||{})])
          display.value='N/A';
       metric.detail='Not Applicable';metric.display.trait='N/A';metric.podium=[];
       if(metric.metric==='token-rate')metric.value='0';
     }
     const neutralView=new AIStatsView.View(()=>{});
     neutralView.update({period:'30-days',result:unsupported});
     const neutral=!/N\\/A|Not Applicable/i.test(neutralView.root.textContent) &&
         [...neutralView.root.querySelectorAll('[data-metric] .ai-stat-value')].every(n=>n.textContent==='—');
      const hourly=parent.querySelector('[data-metric="hourly-rate"]');
      const standardHourly=hourly.querySelector('.ai-stat-value').tagName==='P' &&
        hourly.querySelectorAll('.ai-stat-value').length===1 && !hourly.querySelector('.ai-stat-rate');
     state.result=null;state.statsIdentity='invalidated';state.interrupted=false;view.update(state);
     const invalidated=pending();
      parent.remove();return {cold,sliced,quietPoll,ready,retained,switched,failed,stable,unitIndependent,qualifiedRetention,neutral,invalidated,standardHourly,order,cases,coldState,firstFailure};
  })()`);
   for(const [key,value] of Object.entries(result)) if(!['order','cases','coldState','firstFailure'].includes(key))
      assert.equal(value,true,key+': '+JSON.stringify(result.firstFailure||result.coldState));
   assert.equal(result.cases,160);
  assert.deepEqual(result.order.map(t=>t.replace(/^[^A-Za-z]+/,'')),[
      'AI Hourly Rate','Total AI Cost','Subagent Cost','Total Tokens','Token Consumption Rate','AI Working Time','Average Cost per Session','Database Sizes']);
    checks.push('thirteen stable shells: cold/new-scope Loading, whole same-scope retained cards, no N/A; quiet polls, ready commit, truthful failure, token unit independence');
};
