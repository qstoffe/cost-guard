// Native synthetic source -> real reports/DTOs -> shipped rendered controllers.
module.exports = async ({evaluate,until,fixture,checks}) => {
  const assert=require('node:assert/strict');
  const cases=await fixture('model-attribution');
  for(const section of ['token-mix','ai-stats']) {
    await evaluate(`location.hash='#/${section}'`);
    await until(`current.section==='${section}' && current.result && !current.loading`);
    const saved=await evaluate('current.result');
    for(const item of cases) {
      const view=section==='token-mix'?item.mix:item.stats;
      await evaluate(`current.period=${JSON.stringify(item.period)};
        current.result={...current.result,view:${JSON.stringify(view)}};
        current.${section==='token-mix'?'tokenMix.update(current.result)':'stats.update(current)'};`);
      const two=['different','mixed-week'].includes(item.name);
      const expected=two?['GPT Astra','GPT-6.1 Sol']:['GPT-6.1 Sol'];
      if(section==='token-mix') {
        const rows=await evaluate(`[...document.querySelector('.token-mix-table').tBodies[0].rows]
          .map(r=>({model:r.cells[1].textContent,prompts:Number(r.cells[2].textContent),calls:Number(r.cells[3].textContent)}))`);
        assert.deepEqual(rows.map(r=>r.model).sort(),expected);
        const sol=rows.find(r=>r.model==='GPT-6.1 Sol');
        assert.equal(sol.calls,item.name==='different'?2:item.name==='logical-prompts'?5:3);
        assert.equal(sol.prompts,item.name==='logical-prompts'?3:item.name==='different'?1:2);
        if(two) assert.equal(rows.find(r=>r.model==='GPT Astra').calls,1);
      } else {
        for(const metric of ['total-cost','total-tokens','average-cost','working-time','token-rate']) {
          const labels=await evaluate(`[...document.querySelectorAll('[data-metric="${metric}"] .ai-stat-model')]
            .map(n=>n.textContent).sort()`);
          assert.deepEqual(labels,expected,item.name+': '+metric);
        }
        const rows=view.ai_stats.find(r=>r.period===item.period).metrics
          .find(m=>m.metric==='total-tokens').podium;
        const sol=rows.find(r=>r.label==='GPT-6.1 Sol');
        assert.match(sol.model_help,/• High/);
        if(item.name!=='different') assert.match(sol.model_help,/• Max/);
        if(item.name==='different') assert.doesNotMatch(sol.model_help,/• Max/);
      }
    }
    await evaluate(`current.result=${JSON.stringify(saved)};
      current.period=${JSON.stringify(section==='token-mix'?'all':'30-days')};
      current.${section==='token-mix'?'tokenMix.update(current.result)':'stats.update(current)'};`);
  }
  checks.push('native V2 Sol High/Sol Max, actual Astra child, Today versus 7 days, unavailable-current-model history and child logical Prompts/Calls rendered in Token Mix and five AI Stats podiums');
};
