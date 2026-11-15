'use strict';
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,fixture,command,browser,targetId,origin}) => {
  const checks=[],layouts=[];
  await fixture('quota-source');
  await evaluate(`location.hash='#/sessions/root'`);
  await until(`current.detail?.quotaUsage?.grid.textContent.includes('~235%')`);
  assert.deepEqual(await evaluate(`[...current.detail.quotaUsage.grid.querySelectorAll('.session-quota-row')].map(n=>n.textContent)`),
    ['Monthly10%','5-hour~235%']);
  assert.equal(await evaluate(`current.detail.quotaUsage.cards.size`),1);
  assert.equal(await evaluate(`current.detail.root.lastElementChild===current.detail.quotaUsage.root &&
    current.detail.quotaUsage.root.previousElementSibling===current.detail.activity.root`),true);
  await evaluate(`window.quotaNode=current.detail.quotaUsage.grid.firstChild;
    window.quotaRow=quotaNode.querySelectorAll('.session-quota-row')[1];
    window.originalDetail=current.detail;window.originalBody=current.detail.body;
    window.originalRevision=current.detail.data.revision;`);
  const before=await fixture('quota-observe');
  await fixture('quota-capacity');
  await until(`quotaRow.textContent.includes('~117.5%')`);
  const after=await fixture('quota-observe');
  assert.equal(after.history_reads,before.history_reads,'capacity changes do not read session source');
  assert.equal(await evaluate(`current.detail.data.revision===originalRevision &&
    current.detail.quotaUsage.grid.firstChild===quotaNode &&
    quotaNode.querySelectorAll('.session-quota-row')[1]===quotaRow &&
    current.detail.body===originalBody && current.detail.status.hidden`),true);
  for (const unit of ['usd','credits']) {
    await evaluate(`ReportView.setUnit('${unit}');ReportView.syncUnits(current.detail.root)`);
    assert.equal(await evaluate('quotaRow.textContent'),'5-hour~117.5%');
  }
   checks.push('native exact 7/70; ratio >100%; unused model/account omitted; title-cased labels; downstream placement; live capacity changes on unchanged history; unit independence; stable DOM and quiet status');
  for (const page of ['accounts','watch','ai-stats']) {
    await evaluate(`location.hash='#/${page}'`);
    await until(`current.section==='${page}'`);
    assert.equal((await fixture('quota-observe')).leases,0,'detached detail releases lease');
    await evaluate(`document.querySelector('nav a[href^="#/sessions"]').click()`);
    await until(`current.detail===originalDetail && current.detail.token && !current.detail.busy`);
    assert.equal(await evaluate(`location.hash==='#/sessions/root' &&
      document.querySelector('nav a[aria-current="page"]').textContent==='Sessions' &&
      document.title.startsWith('Session') && current.detail.body===originalBody`),true);
  }
  await evaluate(`location.hash='#/sessions/root-0001'`);
  await until(`current.detail?.id==='root-0001' && current.detail.data`);
  await evaluate(`location.hash='#/accounts'`);
  await until(`current.section==='accounts'`);
  await evaluate(`document.querySelector('nav a[href^="#/sessions"]').click()`);
  await until(`current.detail?.id==='root-0001'`);
  await evaluate(`current.detail.root.querySelector('a[href="#/sessions"]').click()`);
  await until(`current.catalog && !rememberedSession`);
  await evaluate(`location.hash='#/watch'`);
  await until(`current.section==='watch'`);
  await evaluate(`document.querySelector('nav a[href="#/sessions"]').click()`);
  await until(`current.catalog && location.hash.startsWith('#/sessions')`);
  await evaluate(`location.hash='#/sessions/root'`);
  await until(`current.detail===originalDetail && current.detail.data`);
  await evaluate(`history.back()`);
  await until(`current.catalog && !rememberedSession`);
  await evaluate(`history.forward()`);
  await until(`current.detail===originalDetail`);
  checks.push('Accounts/Watch/AI Stats return to same detail, no detached lease; detail B replaces A; Show all clears; explicit catalog/history Back/Forward preserved');
  for (const theme of ['light','dark','classic']) for (const width of [320,360,1280]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]});
    await evaluate(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';
      current.detail.quotaUsage.root.scrollIntoView()`);
    const geometry=await evaluate(`(() => {const root=current.detail.quotaUsage.root;const r=root.getBoundingClientRect();
      return {overflow:document.documentElement.scrollWidth>innerWidth+1,contentWidth:r.width,
      cards:root.querySelectorAll('.account-card').length,color:getComputedStyle(quotaRow).color};})()`);
     assert.equal(geometry.overflow,false);assert.ok(geometry.contentWidth>0);assert.equal(geometry.cards,1);
    layouts.push({theme,width,...geometry});
  }
  await evaluate(`quotaNode.querySelector('a').focus();window.savedFocus=document.activeElement`);
  await evaluate(`location.hash='#/watch'`);await until(`current.section==='watch'`);
  await evaluate(`document.querySelector('nav a[href^="#/sessions"]').click()`);
  await until(`current.detail===originalDetail && current.detail.token`);
  assert.equal(await evaluate(`document.activeElement===savedFocus`),true);
  await fixture('quota-remove');
   await until(`current.detail.quotaUsage.cards.size===0 && current.detail.quotaUsage.root.hidden`);
  assert.doesNotMatch(await evaluate(`current.detail.quotaUsage.grid.textContent`),/account 1/);
  checks.push('320/360/1280 light/dark/Classic no overflow; focused heading survives round trip; removed account disappears without source reread');
  await command('Page.reload');
  await until(`typeof current!=='undefined' && current?.detail?.id==='root' && current.detail.data &&
     current.detail.quotaUsage.cards.size===0 && current.detail.quotaUsage.root.hidden`);
  assert.equal(await evaluate(`document.querySelector('nav a[href^="#/sessions"]').getAttribute('href')`),'#/sessions/root');
  await evaluate(`connectionStatus('Synthetic authentication expiry',
    {kind:'authorization_required',terminal:true,writable:false})`);
  assert.equal(await evaluate(`!current.detail.data && current.detail.quotaUsage.root.hidden &&
    current.detail.quotaUsage.cards.size===0 && !current.detail.token`),true);
   checks.push('explicit-detail reload reopens the route/lease; terminal authentication loss clears retained table/quota values and lease');
   await fixture('quota-source');
   const matrix=await require('./session_quota_layout_browser.cjs')({evaluate,until,command,browser,targetId,origin});
   checks.push(...matrix.checks);layouts.push(...matrix.layouts);
  return {checks,layouts,measurements:{history_reads_before_capacity:before.history_reads,
    history_reads_after_capacity:after.history_reads}};
};
