// Real shipped HTTP/DOM, explicit clicks and passive Live with all scalar work held.
const assert = require('node:assert/strict');
module.exports = async ({evaluate,until,fixture,command}) => {
  await evaluate("location.hash='#/sessions?period=today&sort=activity&direction=-1'");
  await until('current?.catalog?.data?.total===46 && !current.catalog.operation && !current.catalog.busy');
  const baseline=await fixture('warm-observe'), timings=[];
  await evaluate(`(()=>{window.warmReplies=[];window.warmBanners=[];window.warmFlickers=[];
    const api=current.catalog.api;
    current.catalog.api=async(...args)=>{
      const start=performance.now(),data=await api(...args);
      if(!args[1]?.action)warmReplies.push({ms:performance.now()-start,request:args[1],
        pending:data.pending_sort,progress:data.progress,epoch:data.epoch});
      return data;
    };
    const update=current.catalog.update.bind(current.catalog);
    current.catalog.update=data=>{update(data);if(current.catalog.data?.sort==='activity' &&
      current.catalog.data.direction===-1 && current.catalog.offset===0 &&
      [...current.catalog.body.rows].some(row=>row.dataset.id==='root-0001'))warmFlickers.push(data.epoch);};
    new MutationObserver(()=>{if(!current.catalog.status.hidden)warmBanners.push(current.catalog.status.textContent);})
      .observe(current.catalog.status,{attributes:true,childList:true,subtree:true});})()`);
  for(let turn=0;turn<3;turn++) {
    await fixture('warm-stream-'+turn);
    for(const sort of ['ccost','ccost','duration','activity','name','model','ccost','prompts','duration','ctx']) {
      for(let toggle=0;toggle<2;toggle++) {
        const start=Date.now();
        await evaluate(`current.catalog.headers.find(h=>h.key==='${sort}').th.querySelector('button').click()`);
        await until(`current.catalog.data.sort==='${sort}' && !current.catalog.operation && !current.catalog.busy`);
        timings.push({sort,ms:Date.now()-start});
        assert.equal(await evaluate('current.catalog.data.pending_sort'),false);
        assert.equal(await evaluate('current.catalog.body.rows[0].dataset.id'),'root-0000');
        assert.equal(await evaluate('current.catalog.data.total'),46);
      }
    }
  }
  assert.deepEqual(await evaluate('warmBanners'),[]);
  const after=await fixture('warm-observe');
  assert.equal(after.history_reads,baseline.history_reads,'sorts must perform no source reads');
  assert.equal(after.metrics.attempts,baseline.metrics.attempts,'sorts must admit no scalar work');
  const route=async(period,sort='activity',direction=-1)=>{
    await evaluate(`location.hash='#/sessions?period=${period}&sort=${sort}&direction=${direction}'`);
    await until(`current.catalog.data.period==='${period}' && current.catalog.data.sort==='${sort}' &&
      current.catalog.data.direction===${direction} && !current.catalog.operation && !current.catalog.busy`);
  };
  await route('today');
  await fixture('warm-pending');
  await until('current.catalog.data.page_reused && current.catalog.data.progress.revalidating > 0');
  assert.deepEqual(await evaluate('warmFlickers'),[]);
  assert.equal(await evaluate('current.catalog.body.rows[0].dataset.id'),'root-0000');
  assert.equal(await evaluate('current.catalog.status.hidden'),true);
  await fixture('warm-fill');
  await evaluate('current.catalog.load()');
  await until('!current.catalog.data.pending_sort');
  await evaluate('current.catalog.next.focus();current.catalog.next.click()');
  await until('current.catalog.data.offset===25 && !current.catalog.operation && !current.catalog.busy');
  const old=`document.querySelector('tr[data-id="root-0001"]')`;
  assert.equal(await evaluate(`${old}.activity.textContent`),'2026-11-16 00:05*');
  assert.equal(await evaluate(`${old}.value.running`),false);
  const expected='2026-11-16 00:05\nCompletion unverified. Showing recorded prompt start, not finish.';
  await evaluate(`${old}.activity.focus({preventScroll:true})`);
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  assert.equal(await evaluate('document.getElementById("context-help").textContent'),expected);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'});
  await evaluate(`${old}.activity.blur()`);
  const point=await evaluate(`(()=>{${old}.activity.scrollIntoView({block:'center'});
    const r=${old}.activity.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  assert.equal(await evaluate('document.getElementById("context-help").textContent'),expected);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'});
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1});
  await command('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  assert.equal(await evaluate('document.getElementById("context-help").textContent'),expected);
  const pinned=await evaluate('[...current.catalog.body.rows].map(row=>row.dataset.id)');
  await fixture('warm-stream-99');
  await evaluate('current.catalog.load()');
  assert.deepEqual(await evaluate('[...current.catalog.body.rows].map(row=>row.dataset.id)'),pinned);
  await route('7-days');
  assert.equal(await evaluate('current.catalog.data.total'),48);
  await route('all');
  assert.equal(await evaluate('current.catalog.data.total'),48);
  await route('today');
  // Superseded responses cannot restore a header/order from abandoned clicks.
  await evaluate(`(async()=>{for(const sort of ['duration','ccost','name','activity']){
    current.catalog.headers.find(h=>h.key===sort).th.querySelector('button').click();
    await new Promise(resolve=>setTimeout(resolve,10));}})()`);
  await until('!current.catalog.busy && !current.catalog.operation');
  assert.equal(await evaluate('current.catalog.data.sort'),await evaluate('current.catalog.sort'));
  await route('today');
  await fixture('warm-finish');
  await evaluate('current.catalog.load()');
  await until('current.catalog.data.pending_sort');
  await evaluate(`current.catalog.headers.find(h=>h.key==='duration').th.querySelector('button').click()`);
  await until('!current.catalog.status.hidden');
  assert.match(await evaluate('current.catalog.status.textContent'),/Sorting sessions by Duration/);
  await fixture('warm-fill');
  await until('!current.catalog.operation && !current.catalog.busy && !current.catalog.data.pending_sort');
  assert.equal(await evaluate('current.catalog.body.querySelectorAll(".session-running").length'),0);
  assert.deepEqual(await evaluate('warmFlickers'),[]);
  const final=await fixture('warm-observe');
  assert.equal(final.reads['root-0002'],1);
  return {checks:['60 warm header clicks: all seven columns/both directions, no banner/read/scalar admission',
    '48 candidates/46 Today matches; quiet verified order retains old start-only row on page two',
    'exact single-star local timestamp and hover/focus/touch help; frozen page-two membership',
    '7-days/All time, rapid supersession; real finish waits with legitimate banner then retires Running'],
    measurements:{timings,http:await evaluate('warmReplies'),baseline,after,final}};
};
