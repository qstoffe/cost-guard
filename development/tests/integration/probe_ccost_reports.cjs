// Check the shared report renderer too: its sortable headers are distinct from
// the interactive Sessions catalog and Session Detail.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, owner, heading, checks}) => {
  await evaluate(owner, `(() => {
    const root = document.createElement('section'); root.id = 'frozen-cost-report'; document.body.append(root);
    const source = liveValue.probe_ccost_unavailable.mixed;
    const rows = [12, 2].map(cost => ({session_id:'s'+cost,title:'Session '+cost,ccost:cost,display:{ccost:String(cost)}}));
    const account = structuredClone(source.accounts.accounts[0]);
    account.ccost_scopes = ['today','this month'].map(name => ({...account.ccost_scopes[0],name}));
    const view = {...source.probe_detail, kind:'normal', session_usage:rows, accounts_quotas:{accounts:[account]}};
    ReportView.setUnit('credits'); ReportView.render(root,{observed_at_ms:1,source:{},view},{section:'accounts',pages:{}});
    root.querySelector('details').open = true;
  })()`);
  const root = '#frozen-cost-report';
  const sessions = `${root} [aria-label="Sessions"]`;
  const prompts = `${root} [aria-label^="Prompts ·"]`;
  const column = `${sessions} th:nth-child(3) button`;
  await heading(owner,`${root} .help-copy span`,'CCost',/not your bill/);
  await heading(owner,column,'CCost',/entire session[\s\S]*Sort this column/);
  await heading(owner,`${root} h3 + a + p span`,'Full-session CCost',/entire session/);
  for (const [index,label,scope] of [[2,'CCost',/this prompt/],[6,'~Ictx CCost',/first request/],[7,'~Extra CCost',/output.*later requests/]])
    await heading(owner,`${prompts} th:nth-child(${index}) button`,label,scope);
  for (const [index,scope] of ['today','this month'].entries()) {
    await heading(owner,`${root} .account-card > :nth-child(${index+1} of p.metric-value) > span:first-child`,
      `CCost ${scope}:`,new RegExp('account.*' + scope));
  }
  const values = () => evaluate(owner,`[...document.querySelectorAll('${sessions} tbody td:nth-child(3)')].map(n=>n.textContent)`);
  assert.deepEqual(await values(),['12','2']);
  for (const order of [['2','12'],['12','2']]) {
    await evaluate(owner,`document.querySelector('${column}').click()`);
    assert.deepEqual(await values(),order);
  }
  await evaluate(owner,`document.querySelector('${root}').remove()`);
  checks.push('Frozen report reading guide, session/prompt/component headings and account scope labels, with reversible numeric sort.');

  await evaluate(owner, `(() => {
    const chart = new AccountTimelineView.View(()=>{},()=>{});
    document.body.append(chart.root);
    const start = Date.UTC(2026,10,1), end = start + 86400000;
    const amount = {amount:'100',display:{credits:'100',usd:'$1.00'}};
    chart.cache.set(chart.period,{view:{period:chart.period,timezone_id:'UTC',start_ms:start,end_ms:end,
      buckets:[[start,end]],series:[{id:'00000001',account:'Monthly plan',points:[amount],total:amount,
        provider_monthly_total:true,observed_total:amount,peak:'100',ticks:[amount]}]}});
    chart.draw();
  })()`);
  await heading(owner,'.account-timeline h2 button','CCost',/account and period/);
  await heading(owner,'.account-timeline-range > span:first-child','Observed OpenCode daily CCost',/daily.*provider/i);
  checks.push('Accounts chart heading and conditional observed-month label retain distinct scope from provider totals.');
};
