// Real hidden browser: shared native arithmetic, retained views and open Document PiP.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,command,sessionId,pipSession,checks,layouts}) => {
  const change = async (id,value) => {
    await evaluate(`location.hash='#/settings'`);
    await until(`document.getElementById('${id}')?.disabled===false`);
    await evaluate(`(() => {const select=document.getElementById('${id}');select.focus();select.value='${value}';select.dispatchEvent(new Event('change'));})()`);
    await until(`document.getElementById('${id}').disabled===false && document.getElementById('${id}').value==='${value}'`);
    assert.equal(await evaluate(`document.activeElement.id`),id);
  };
  const initial = await evaluate(`(() => {window.quotaProbe={source:JSON.stringify(liveValue.view.accounts),
    bar:miniWatch.view.accounts.querySelector('progress'),cost:views.get('#/watch')?.watch?.accounts.querySelector('.watch-period-cost')};
    return {streams:probeStreams,mini:miniWatch.view.accounts.children[0].textContent};})()`);
  assert.match(initial.mini,/8.4% used \(1814\)/);
  await change('quota-display','remaining');
  assert.match(await evaluate(`miniWatch.view.accounts.children[0].textContent`),/91.6% remaining \(CCost used: 1814\)/);
  assert.equal(await evaluate(`miniWatch.view.accounts.querySelector('progress')===quotaProbe.bar`),true);
  assert.equal(await evaluate(`miniWatch.view.accounts.querySelector('progress').value`),0.91648);
  await evaluate(`location.hash='#/watch'`); await until(`document.querySelector('.watch-account-grid')!==null`);
  assert.match(await evaluate(`document.querySelector('.watch-quota-summary').textContent`),/91.6% remaining \(CCost used: 1814\).*22912\/25000/);
  assert.equal(await evaluate(`document.querySelector('.watch-period-cost')===quotaProbe.cost`),true);
  const exhausted = await evaluate(`(() => {const bar=[...document.querySelectorAll('.watch-quota-track progress')].find(bar=>bar.getAttribute('aria-label')==='Weekly remaining');
    return {value:bar.value,text:bar.getAttribute('aria-valuetext'),color:getComputedStyle(bar).color};})()`);
  assert.equal(exhausted.value,0); assert.match(exhausted.text,/exhausted/);
  await evaluate(`(() => {window.quotaAccounts=document.createElement('section');
    ReportView.overviewAccounts(quotaAccounts,liveValue.probe_accounts,'Accounts',true);
    document.getElementById('result').replaceChildren(quotaAccounts);})()`);
  assert.match(await evaluate(`quotaAccounts.textContent`),/Remaining 22912\/25000 AI credits/);
  assert.equal(await evaluate(`quotaAccounts.querySelector('progress').value`),0.91648);
  for (const scheme of ['light','dark']) {
    await change('web-theme','web');
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},sessionId);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},pipSession);
    for (const width of [360,560]) for (const scale of [1,1.25]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:800,deviceScaleFactor:scale,mobile:false},sessionId);
      await command('Emulation.setDeviceMetricsOverride',{width,height:450,deviceScaleFactor:scale,mobile:false},pipSession);
      await evaluate(`document.documentElement.style.zoom='${scale}';miniWatch.window.document.documentElement.style.zoom='${scale}'`);
      const layout = await evaluate(`(() => {const w=miniWatch.window,d=w.document;return {width:innerWidth,
        watchOverflow:(() => {document.getElementById('result').replaceChildren(views.get('#/watch').watch.root);return document.documentElement.scrollWidth>innerWidth;})(),
        pageOverflow:(() => {document.getElementById('result').replaceChildren(quotaAccounts);return document.documentElement.scrollWidth>innerWidth;})(),
        miniWidth:w.innerWidth,
        miniOverflow:d.documentElement.scrollWidth>w.innerWidth,mini:miniWatch.view.accounts.children[0].textContent,
        description:miniWatch.view.accounts.children[0].helpText,
        accessible:[...quotaAccounts.querySelectorAll('progress')].every(bar=>bar.getAttribute('aria-label')&&bar.getAttribute('aria-valuetext'))};})()`);
      assert.equal(layout.pageOverflow,false); assert.equal(layout.watchOverflow,false);
      assert.equal(layout.miniOverflow,false); assert.equal(layout.accessible,true);
      assert.match(layout.description,/separate from native quota, not remaining CCost/);
      layouts.push({case:'quota-remaining',scheme,width,scale,...layout});
    }
  }
  await command('Emulation.clearDeviceMetricsOverride',{},sessionId);
  await command('Emulation.clearDeviceMetricsOverride',{},pipSession);
  await evaluate(`document.documentElement.style.zoom='';miniWatch.window.document.documentElement.style.zoom=''`);
  await change('ccost-unit','usd');
  assert.match(await evaluate(`miniWatch.view.accounts.children[0].textContent`),/CCost used: \$18.14/);
  await change('ccost-unit','default'); await change('web-theme','default');
  await change('quota-display','used');
  await evaluate(`ReportView.syncUnits(quotaAccounts)`);
  assert.match(await evaluate(`quotaAccounts.textContent`),/Used 2088\/25000 AI credits/);
  await change('quota-display','default');
  assert.equal(await evaluate(`miniWatch.view.accounts.children[0].textContent`),initial.mini);
  assert.equal(await evaluate(`JSON.stringify(liveValue.view.accounts)===quotaProbe.source`),true);
  assert.equal(await evaluate('probeStreams'),initial.streams);
  assert.deepEqual(await evaluate(`({local:localStorage.length,session:sessionStorage.length})`),{local:0,session:0});
  await evaluate(`location.hash='#/watch'`); await until(`document.querySelector('.watch-account-grid')!==null`);
  checks.push('Quota orientation: authenticated fourth select, same-period Accounts/Watch/open PiP, exhausted empty bar, independent USD/CCost, retained nodes, light/dark narrow/zoom, unchanged source and one SSE');
};
