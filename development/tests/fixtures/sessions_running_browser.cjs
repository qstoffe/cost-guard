// Shipped HTTP, source-normalized prompt facts and real headless keyboard/touch DOM.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks = [];
  await fixture('running-source-26');
  const route = async (sort, direction) => {
    await evaluate(`location.hash='#/sessions?period=all&sort=${sort}&direction=${direction}'`);
    await until(`current.catalog?.data?.sort==='${sort}' && current.catalog.data.direction===${direction} &&
      current.catalog.data.total===126 && !current.catalog.operation && !current.catalog.busy`);
  };
  const ids = () => evaluate('[...current.catalog.body.rows].map(row=>row.dataset.id)');
  for (const sort of ['activity','name','model','ccost','prompts','duration','ctx']) {
    for (const direction of [1,-1]) {
      await route(sort,direction);
      assert.deepEqual(await ids(), Array.from({length:25},(_,i)=>`root-${String(25-i).padStart(4,'0')}`));
      assert.equal(await evaluate('current.catalog.body.rows[0].activity.textContent.endsWith("*")'),true);
      assert.equal(await evaluate(`current.catalog.headers.find(header=>header.key==='${sort}').th.getAttribute('aria-sort')`),
        direction === 1 ? 'ascending' : 'descending');
    }
  }
  checks.push('all seven sorts, both directions: 26 running roots precede 100 finished; start-desc order, independent regular ARIA direction');
  await evaluate('current.catalog.next.click()');
  await until('current.catalog.data.offset===25 && !current.catalog.operation && !current.catalog.busy');
  assert.equal((await ids())[0],'root-0000');
  assert.equal(await evaluate('current.catalog.body.rows[0].value.running'),true);
  assert.equal(await evaluate('current.catalog.body.rows[1].value.running'),false);
  assert.equal(await evaluate('current.catalog.body.rows[1].activity.textContent.includes("*")'),false);
  await evaluate('current.catalog.previous.click()');
  await until('current.catalog.data.offset===0 && !current.catalog.operation && !current.catalog.busy');
  const original = await evaluate(`({ids:[...current.catalog.body.rows].map(row=>row.dataset.id),
    clock:current.catalog.body.rows[0].activity.textContent,raw:current.catalog.body.rows[0].value.last_activity_ms})`);
  await fixture('running-churn');
  await evaluate('current.catalog.load()');
  assert.deepEqual(await ids(),original.ids);
  assert.equal(await evaluate('current.catalog.body.rows[0].activity.textContent'),original.clock);
  const expectedHelp = original.clock.slice(0,-1)+'\n* Running sessions appear first, regardless of sorting.';
  await evaluate('current.catalog.body.rows[0].activity.focus({preventScroll:true})');
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  assert.equal(await evaluate('document.getElementById("context-help").textContent'),expectedHelp);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'});
  await command('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
  const point = await evaluate(`(()=>{const r=current.catalog.body.rows[0].activity.getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  assert.equal(await evaluate('document.getElementById("context-help").textContent'),expectedHelp);
  checks.push('page-two running overflow; one activity-only star; source metadata/part churn keeps start and order; exact focus/touch tooltip');
  await evaluate('window.evictedRunning=current.catalog.body.rows[0];evictedRunning.activity.focus({preventScroll:true})');
  await fixture('running-finish');
  await evaluate('current.catalog.load()');
  await until('!current.catalog.body.querySelector(\'[data-id="root-0025"]\')');
  assert.equal(await evaluate('evictedRunning.isConnected'),false);
  assert.equal(await evaluate('document.activeElement===current.catalog.pan'),true);
  assert.equal(await evaluate('current.catalog.body.rows.length'),25);
  assert.deepEqual(await ids(),await evaluate('current.catalog.data.view.session_usage.map(row=>row.session_id)'));
  assert.equal(await evaluate('document.getElementById("context-help").hidden'),true);
  await route('activity',-1);
  await evaluate('current.catalog.next.click()');
  await until('current.catalog.data.offset===25 && !current.catalog.operation && !current.catalog.busy');
  assert.equal((await ids())[0],'root-0025');
   assert.equal(await evaluate('current.catalog.body.rows[0].value.running'),false);
   assert.equal(await evaluate('current.catalog.body.rows[0].activity.textContent'),'2026-11-15 01:59');
   assert.equal(await evaluate(`(()=>{const node=current.catalog.body.rows[0].activity;
     return !node.hasAttribute('tabindex') && !node.hasAttribute('aria-describedby') &&
       !node.classList.contains('help-value') && !node.hasAttribute('title');})()`),true);
   checks.push('supported abort removes star and reinserts terminal row after the remaining running group');
   // Source-shaped cell transitions over a stable real row. Keep the tooltip
   // open across the catalog→Running→finished transitions.
   await command('Emulation.setTouchEmulationEnabled',{enabled:false});
   await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab'});
   await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab'});
   await evaluate(`window.activityView=new SessionsCatalog.View(api);
     document.querySelector('main').append(activityView.root);
     activityView.update({...structuredClone(current.catalog.data), navigation:null});
     window.activityRow=activityView.body.rows[0];window.activityNode=activityRow.activity;
     window.publishActivity=(fields,zone='Europe/Stockholm')=>{
       const catalog=activityView,data=structuredClone(catalog.data);
       data.view.timezone_id=zone;Object.assign(data.view.session_usage[0],fields);
       catalog.update(data);
     };
     publishActivity({activity_state:'pending',last_activity_ms:null,prompt_started_ms:null,catalog_activity_ms:null});`);
   assert.equal(await evaluate('activityNode.textContent'),'');
   assert.equal(await evaluate(`activityNode.querySelector('.metric-spinner')?.getAttribute('aria-label')`),'Loading last activity');
   assert.equal(await evaluate('activityNode.tabIndex'),-1);
   await evaluate(`publishActivity({catalog_activity_ms:Date.parse('2026-03-29T01:30Z')})`);
   assert.equal(await evaluate('activityNode.textContent'),'2026-03-29 03:30*');
   await evaluate('activityNode.focus({preventScroll:true})');
   await until('document.getElementById("context-help")?.matches(":popover-open")');
   assert.match(await evaluate('document.getElementById("context-help").textContent'),/Preliminary activity/);
   await evaluate(`publishActivity({running:true,prompt_started_ms:Date.parse('2026-10-25T01:30Z')})`);
   assert.equal(await evaluate('activityNode.textContent'),'2026-10-25 02:30*');
   assert.equal(await evaluate('document.getElementById("context-help").textContent'),
     '2026-10-25 02:30\n* Running sessions appear first, regardless of sorting.');
   await evaluate(`publishActivity({running:false,catalog_activity_ms:null,activity_state:'ready',
     last_activity_ms:Date.parse('2026-10-25T01:31Z')})`);
   assert.equal(await evaluate('activityNode.textContent'),'2026-10-25 02:31');
   assert.equal(await evaluate(`activityRow===activityView.body.rows[0] && activityNode===activityRow.activity &&
     document.getElementById('context-help').hidden && !activityNode.hasAttribute('aria-describedby') &&
     !activityNode.hasAttribute('tabindex') && !activityNode.classList.contains('help-value')`),true);
   await evaluate('activityNode.click()');
   assert.equal(await evaluate('document.getElementById("context-help").hidden'),true);
   await evaluate('activityView.root.remove()');
   checks.push('open help follows pending → catalog → Running with one star → verified ordinary with no help target');
  const labels = await evaluate(`[
    ReportView.activityHelp(Date.parse('2026-03-29T01:30Z'),'Europe/Stockholm'),
    ReportView.activityHelp(Date.parse('2026-10-25T00:30Z'),'Europe/Stockholm'),
    ReportView.activityHelp(Date.parse('2026-10-25T01:30Z'),'Europe/Stockholm'),
    ReportView.activityHelp(Date.parse('2026-11-15T23:30Z'),'Europe/Stockholm'),
    ReportView.activityHelp(1,null), ReportView.activityHelp(0,'UTC'),
    ReportView.activityHelp(1,'Invalid/Timezone')]`);
  assert.deepEqual(labels,['2026-03-29 03:30','2026-10-25 02:30','2026-10-25 02:30',
    '2026-11-16 00:30',...Array(3).fill('Activity time unavailable.')]);
  checks.push('DST gap/fold and local midnight exactness; invalid clock/configuration never substitutes browser timezone');
  return {checks};
};
