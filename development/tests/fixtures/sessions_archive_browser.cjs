// Time the shipped DOM, not the API reply. Fixture clocks never time interactions.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, command, fixture}) => {
  const timings = {};
  const catalog = 'current?.catalog';
  const ready = `${catalog}?.data?.cache_first && !current.catalog.operation && current.catalog.body.rows.length===25`;
  const ids = '[...current.catalog.body.rows].map(row=>row.dataset.id)';
  const measure = async (label, act, done, budget) => {
    const start = performance.now();
    await act();
    await until(done, budget + 1500);
    timings[label] = Math.round(performance.now() - start);
    assert.ok(timings[label] <= budget, `${label}: ${timings[label]} ms > ${budget} ms`);
  };
  const range = (start, step) => Array.from({length:25}, (_,i) => 'root-'+String(start+i*step).padStart(4,'0'));
  await measure('enter-all', () => evaluate("location.hash='#/sessions?period=all&sort=activity&direction=-1'"),
    `${ready} && current.catalog.data.total===10000`, 2000);
  for (const [key, increasing] of Object.entries({
    activity:true, name:true, model:false, ccost:true, prompts:false, duration:true, ctx:false
  })) {
    const button = `current.catalog.headers.find(h=>h.key==='${key}').th.querySelector('button')`;
    for (const direction of [1, -1]) {
      await measure(`${key}:${direction}`, () => evaluate(`${button}.click()`),
        `${ready} && current.catalog.data.sort==='${key}' && current.catalog.data.direction===${direction}`, 2000);
      const ascending = increasing === (direction === 1);
      assert.deepEqual(await evaluate(ids), range(ascending ? 0 : 9999, ascending ? 1 : -1));
    }
  }
  await measure('today', () => evaluate("current.catalog.periodButtons.find(p=>p.key==='today').button.click()"),
    `${ready} && current.catalog.data.period==='today' && current.catalog.data.total<10000`, 2000);
  await measure('all', () => evaluate("current.catalog.periodButtons.find(p=>p.key==='all').button.click()"),
    `${ready} && current.catalog.data.total===10000`, 2000);
  await evaluate("current.catalog.headers.find(h=>h.key==='name').th.querySelector('button').click()");
  await until(`${ready} && current.catalog.data.sort==='name' && current.catalog.data.direction===1`);
  const page = n => `${ready} && current.catalog.data.offset===${n}`;
  await measure('next', () => evaluate('current.catalog.next.click()'), page(25), 2000);
  assert.deepEqual(await evaluate(ids), range(25, 1));
  await measure('previous', () => evaluate('current.catalog.previous.click()'), page(0), 2000);
  assert.deepEqual(await evaluate(ids), range(0, 1));
  assert.equal((await fixture('stats')).reads, 0, 'cache-only sorting, paging and filtering');

  await evaluate('current.catalog.next.click()');
  await until(page(25));
  const shown = i => `${page(25)} && document.querySelector('tr[data-id="root-${i}"]')?.innerText.includes('Name ${i} corrected')`;
  await measure('source-correction-to-page-2', () => fixture('correct'), shown('0025'), 5000);
  const network = offline => command('Network.emulateNetworkConditions',
    {offline,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await command('Network.enable', {});
  // Wait for two actual missed reads, not just a toggle too brief for the
  // application to notice. Measure inside the tab, not at the next CDP poll.
  await evaluate(`window.missedPages=0;
    const fetchBeforeOutage=window.fetch;
    window.fetch=async (...args)=>{
      try{return await fetchBeforeOutage(...args)}
      catch(error){if(args[0]==='/api/sessions' && !navigator.onLine) missedPages++; throw error}
    };`);
  await network(true);
  await until('!navigator.onLine');
  await fixture('correct-offline');
  await until('missedPages >= 2');
  assert.equal(await evaluate(shown('0026')), false);
  await evaluate(`window.reconnectMark={};
    addEventListener('online',async ()=>{
      const response=await fetch('/api/live');
      if(response.ok && (await response.json()).instance_id) reconnectMark.usable=performance.now();
    },{once:true});
    new MutationObserver((_, observer)=>{
      if(${shown('0026')}) {reconnectMark.shown=performance.now();observer.disconnect()}
    }).observe(current.catalog.body,{childList:true,subtree:true,characterData:true});`);
  await network(false);
  await until('reconnectMark.usable && reconnectMark.shown', 35000);
  timings['reconnect-to-page-2'] = await evaluate('Math.max(0,Math.round(reconnectMark.shown-reconnectMark.usable))');
  assert.ok(timings['reconnect-to-page-2'] <= 5000, JSON.stringify(timings));
  assert.deepEqual(await evaluate(ids), range(25, 1));
  assert.equal(await evaluate('current.catalog.data.period+":"+current.catalog.data.sort+":"+current.catalog.data.direction'), 'all:name:1');
  return timings;
};
