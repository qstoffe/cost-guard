// Canonical synthetic source requests, real host/HTTP/SSE and retained shared cards.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,fixture,until,navigate,checks}) => {
  const values = {credits:{'github-copilot':'1',openai:'2','claude-code':'12'},
    usd:{'github-copilot':'$0.01',openai:'$0.02','claude-code':'$0.12'}};
  for(const phase of ['old','zero','priced','partial','unknown','priced-stale','zero-stale','priced-stale','priced']) {
    await fixture('midnight-'+phase);
    await until(`liveValue?.view?.accounts?.accounts.length===3&&liveValue.view.accounts.accounts.some(item=>item.observation.plan==='Pro Light')`);
    // Fixture acknowledgment publishes before the browser's asynchronous SSE delivery.
    await until(`(()=>{const scopes=liveValue.view.accounts.accounts.map(item=>item.ccost_scopes[0].cost);
      return ${phase.endsWith('stale')}===liveValue.view.quota_stale&&scopes.every(cost=>
        ${phase==='unknown' ? 'cost?.observed_requests>0&&cost?.priced_requests===0' :
          phase==='partial' ? 'cost?.observed_requests===2&&cost?.priced_requests===1' :
          phase==='old'||phase.startsWith('zero') ? 'cost?.observed_requests===0' : 'cost?.observed_requests===1&&cost?.priced_requests===1'});})()`);
    for(const unit of ['credits','usd']) for(const route of ['accounts','watch']) {
      await evaluate(`ReportView.setUnit('${unit}');if(current.accounts)ReportView.syncUnits(current.accounts.root);else ReportView.syncUnits(current.watch.root)`);
      await navigate(route);
      const cards=await evaluate(`(()=>{return [...document.querySelectorAll('#result .watch-subscription')].map(card=>({
          provider:[...liveValue.view.accounts.accounts].find(item=>item.observation.label===card.querySelector('h4').textContent).observation.provider_id,
          today:card.querySelector('h4').nextElementSibling.textContent,icons:card.querySelectorAll('h4 svg').length}));})()`);
      assert.equal(cards.length,3);
      for(const card of cards) {
        const expected=phase==='unknown' ? '—' : phase==='old'||phase.startsWith('zero') ? unit==='usd'?'$0.00':'0' : values[unit][card.provider];
        assert.equal(card.today,'CCost Today: '+expected,phase+'/'+unit+'/'+route+'/'+card.provider);
        assert.equal(card.icons,1);
      }
      if(route==='watch') {
        const expected=phase==='unknown'?'N/A':phase==='old'||phase.startsWith('zero')?unit==='usd'?'$0.00':'0':unit==='usd'?'$0.15':'15';
        assert.equal(await evaluate(`current.watch.daily.querySelector('.metric-value').textContent`),expected);
      }
    }
  }
  checks.push('Canonical Copilot Pro+, OpenAI Pro Light and Claude Agent Opus→Pro Today: empty local day, positive, partial, unpriced and stale-quota zero→positive; Accounts/Full Watch/global USD/Credits via actual HTTP/SSE, no inference');
};
