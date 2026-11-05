// Real hidden browser: shared native arithmetic, retained views and open Document PiP.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,command,sessionId,pipSession,checks,layouts,fixture}) => {
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
   assert.match(await evaluate(`miniWatch.view.accounts.children[0].textContent`),/91.6% remaining \(22912\)/);
  assert.equal(await evaluate(`miniWatch.view.accounts.querySelector('progress')===quotaProbe.bar`),true);
  assert.equal(await evaluate(`miniWatch.view.accounts.querySelector('progress').value`),0.91648);
  await evaluate(`location.hash='#/watch'`); await until(`document.querySelector('.watch-account-grid')!==null`);
   assert.equal(await evaluate(`document.querySelector('.watch-quota-summary').textContent`),'Monthly · 91.6% remaining (22912)');
   assert.equal(await evaluate(`document.querySelector('.watch-quota-capacity').textContent`),'Capacity: 25000');
   assert.equal(await evaluate(`document.querySelector('.watch-period-cost')===quotaProbe.cost`),true);
   await command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false},sessionId);
   const aligned = await evaluate(`(() => {const cards=[...document.querySelectorAll('.watch-subscription')];
     return cards.map(card=>({top:card.getBoundingClientRect().top,
       bar:card.querySelector('.watch-quota-track').getBoundingClientRect().top,
       rows:[...card.children].slice(1,5).map(n=>n.className)}));})()`);
   for (const card of aligned) for (const other of aligned.filter(other=>Math.abs(other.top-card.top)<1))
     assert.ok(Math.abs(card.bar-other.bar)<1,'seven-row subgrid aligns primary bars across neighboring cards');
   layouts.push({case:'quota-capacity-alignment',cards:aligned});
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
       assert.match(layout.description,/Used \+ Remaining need not equal Capacity/);
      layouts.push({case:'quota-remaining',scheme,width,scale,...layout});
    }
  }
  await command('Emulation.clearDeviceMetricsOverride',{},sessionId);
  await command('Emulation.clearDeviceMetricsOverride',{},pipSession);
  await evaluate(`document.documentElement.style.zoom='';miniWatch.window.document.documentElement.style.zoom=''`);
  await change('ccost-unit','usd');
   assert.match(await evaluate(`miniWatch.view.accounts.children[0].textContent`),/remaining \(\$229.12\)/);
  await change('ccost-unit','default'); await change('web-theme','default');
  await change('quota-display','used');
  await evaluate(`ReportView.syncUnits(quotaAccounts)`);
  assert.match(await evaluate(`quotaAccounts.textContent`),/Used 2088\/25000 AI credits/);
  await change('quota-display','default');
  assert.equal(await evaluate(`miniWatch.view.accounts.children[0].textContent`),initial.mini);
  assert.equal(await evaluate(`JSON.stringify(liveValue.view.accounts)===quotaProbe.source`),true);
  assert.equal(await evaluate('probeStreams'),initial.streams);
   assert.deepEqual(await evaluate(`({local:localStorage.length,session:sessionStorage.length})`),{local:0,session:0});
   await fixture('quota-idle');
   await until(`liveValue.view.accounts.accounts.length===1 && liveValue.view.accounts.accounts[0].primary.quota.window_active===false`);
   await change('quota-display','remaining');
   assert.match(await evaluate(`miniWatch.view.accounts.children[0].textContent`),/100% remaining \(\?\)/);
   await evaluate(`location.hash='#/watch'`);
   await until(`document.querySelector('.watch-quota-summary')?.textContent.includes('100% remaining')`);
   const idle = await evaluate(`(() => {const root=document.querySelector('.watch-account-grid');
     const bars=[...root.querySelectorAll('progress')];const accounts=document.createElement('section');
     ReportView.overviewAccounts(accounts,liveValue.probe_accounts,'Accounts',true);
     return {labels:[...root.querySelectorAll('.watch-quota-summary')].map(n=>n.textContent),
       capacity:[...root.querySelectorAll('.watch-quota-capacity')].map(n=>n.textContent),
       bars:bars.map(n=>[n.value,n.getAttribute('aria-valuetext'),n.className]),
       reset:[...root.querySelectorAll('.detail')].map(n=>n.textContent),
       accounts:accounts.textContent,accountBars:[...accounts.querySelectorAll('progress')].map(n=>n.value),
       mini:miniWatch.view.accounts.querySelector('progress').value};})()`);
   assert.deepEqual(idle.labels,['5-hour · 100% remaining (?)','Weekly · 100% remaining (?)']);
   assert.deepEqual(idle.capacity,['Capacity: ?','Capacity: ?']);
   assert.ok(idle.bars.every(([value,text,name])=>value===1 && text==='100% remaining' && !name.includes('exhausted')));
   assert.deepEqual(idle.accountBars,[1,1]); assert.equal(idle.mini,1);
   assert.match(idle.accounts,/100% remaining \(\?\)/); assert.ok(idle.reset.includes('Window not started'));
   await change('quota-display','used');
   assert.match(await evaluate(`miniWatch.view.accounts.children[0].textContent`),/0% used \(0\)/);
   await evaluate(`location.hash='#/watch'`);
   await until(`document.querySelector('.watch-quota-summary')?.textContent.includes('0% used (0)')`);
   assert.equal(await evaluate(`document.querySelector('.watch-quota-track progress').value`),0);
   await fixture('quota-ratio');
   await until(`liveValue.view.accounts.accounts[0].primary.quota.remaining_fraction==='0.9'`);
   await until(`document.querySelector('.watch-quota-summary')?.textContent==='5-hour · 10% used (100)'`);
   assert.equal(await evaluate(`document.querySelector('.watch-quota-capacity').textContent`),'Capacity: 1000 (guesstimate)');
   assert.match(await evaluate(`miniWatch.view.accounts.children[0].helpText`),/Capacity: 1000 \(guesstimate\)/);
   await change('quota-display','remaining');
   assert.match(await evaluate(`miniWatch.view.accounts.children[0].textContent`),/90% remaining \(900\)/);
   await change('ccost-unit','usd');
   assert.match(await evaluate(`miniWatch.view.accounts.children[0].textContent`),/90% remaining \(\$9.00\)/);
   await evaluate(`location.hash='#/watch'`);
   await until(`document.querySelector('.watch-quota-capacity')?.textContent==='Capacity: $10.00 (guesstimate)'`);
   assert.equal(await evaluate(`document.querySelector('.watch-quota-summary').textContent`),'5-hour · 90% remaining ($9.00)');
   await evaluate(`(() => {const account=document.createElement('section');ReportView.overviewAccounts(account,liveValue.probe_accounts,'Accounts',true);
     window.ratioAccountText=account.textContent;})()`);
   assert.match(await evaluate('ratioAccountText'),/90% remaining \(\$9.00\)Capacity: \$10.00 \(guesstimate\)/);
   await change('ccost-unit','default');
   await fixture('running'); await until(`liveValue.view.accounts.accounts.length===6`);
   await change('quota-display','default');
   await evaluate(`location.hash='#/watch'`); await until(`document.querySelector('.watch-account-grid')!==null`);
   checks.push('Quota CCost/Capacity: independent native credit allowance and observed Used, immediate Remaining/USD in Accounts/Watch/open PiP, healthy provider-confirmed idle primary/secondary 100% bars with unknown estimates, reset label and Used zero preserved; light/dark narrow/zoom and one SSE');
};
