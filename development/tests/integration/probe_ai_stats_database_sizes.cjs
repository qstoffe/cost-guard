const assert = require('node:assert/strict');

module.exports = async function({command, evaluate, until, fixture, tab, checks}) {
  const card = '.ai-stat-databases', values = `[...document.querySelectorAll('${card} dd')].map(node=>node.textContent)`;
  await until(`${values}.join('/')==='128 B/92 KB'`);
  assert.deepEqual(await evaluate(`(() => {
    const card=document.querySelector('${card}');
    return {count:document.querySelectorAll('${card}').length, title:card.querySelector('h4').textContent,
      group:card.closest('section').querySelector('h3').textContent, last:card===card.parentNode.lastElementChild,
      labels:[...card.querySelectorAll('dt')].map(node=>node.textContent)};
  })()`), {count:1, title:'Database Sizes', group:'Fun Facts', last:true, labels:['OpenCode DB','CostGuard Cache DB']});
  await evaluate(`window.__sizeCard=document.querySelector('${card}'); window.__sizeReads=0;
    window.__sizeFetch=fetch; fetch=(url,...args)=>{
      if(url==='/api/database-sizes') __sizeReads++;
      return __sizeFetch(url,...args);
    };`);
  for (const period of ['today','7-days','month','all','30-days']) {
    await evaluate(`selectStats(current,'${period}')`);
    await until(`!current.loading && current.result?.view.ai_stats.some(row=>row.period==='${period}')`);
    assert.equal(await evaluate(`__sizeCard===document.querySelector('${card}') && __sizeReads===0`),true);
    assert.deepEqual(await evaluate(values),['128 B','92 KB']);
  }
  await fixture('stats-resize-cache');
  await evaluate(`location.hash='#/accounts'`); await until(`current.section==='accounts'`);
  await evaluate(`location.hash='#/ai-stats'`); await until(`${values}.join('/')==='128 B/2.5 MB'`);
  assert.equal(await evaluate(`__sizeReads`),1);

  const sizeCases = [[0,999,['0 B','999 B']], [1000,999_000,['1 KB','999 KB']],
    [1_000_000,1_000_000_000,['1 MB','1 GB']], [null,92_000,['Size unavailable','92 KB']],
    [285_000_000,'not a byte count',['285 MB','Size unavailable']]];
  for (const [opencode,cache,expected] of sizeCases) {
    await evaluate(`(async()=>{
      const original=fetch; fetch=async()=>Response.json({opencode_bytes:${JSON.stringify(opencode)},cache_bytes:${JSON.stringify(cache)}});
      try { await current.stats.refreshDatabaseSizes(); } finally { fetch=original; }
    })()`);
    assert.deepEqual(await evaluate(values),expected);
    assert.equal(await evaluate(`AIStatsView.valid(current.result) && document.querySelectorAll('.ai-stat[data-metric]').length===13`),true);
  }
  await evaluate(`(async()=>{
    const original=fetch; fetch=async()=>{throw new Error('optional metadata read failed');};
    try { await current.stats.refreshDatabaseSizes(); } finally { fetch=original; }
  })()`);
  assert.deepEqual(await evaluate(values),['Size unavailable','Size unavailable']);
  assert.equal(await evaluate(`AIStatsView.valid(current.result) && !current.failed && !current.loading`),true);
  await evaluate(`fetch=__sizeFetch; current.stats.refreshDatabaseSizes()`);
  await until(`${values}.join('/')==='128 B/2.5 MB'`);
  await command('Page.bringToFront',{},tab);
  const move = (x,y) => command('Input.dispatchMouseEvent',{type:'mouseMoved',x,y},tab);
  const escape = async () => {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);
    await until(`document.getElementById('context-help').hidden`);
  };
  for (const mode of ['hover','focus','touch']) {
    if (mode === 'touch') await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
    for (const [index,text] of [[0,/session-based statistics.*deleted session/],[1,/at least 30 days.*at least 60 minutes/]]) {
      const button = `document.querySelectorAll('${card} dt button')[${index}]`;
      await evaluate(`document.activeElement.blur(); ${button}.scrollIntoView({block:'center'});
        new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
      if (mode === 'focus') {
        await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true})); ${button}.focus()`);
      } else {
        const point = await evaluate(`(() => {
          const r=${button}.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2};
        })()`);
        assert.equal(await evaluate(`${button}.contains(document.elementFromPoint(${point.x},${point.y}))`),true);
        if (mode === 'hover') await move(point.x,point.y);
        else {
          await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},tab);
          await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},tab);
        }
      }
      await until(`${button}.getAttribute('aria-describedby')==='context-help' && document.getElementById('context-help')?.hidden===false`);
      const body = await evaluate(`document.getElementById('context-help').textContent`);
      assert.match(body,text,mode); assert.match(body,/excluding auxiliary files/,mode);
      await escape();
      if (mode === 'hover') await move(1,1);
    }
    if (mode === 'touch') await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
  }
  checks.push('Database Sizes: one compact card, two labels and distinct hover/focus/touch help; B/KB/MB/GB, isolated failures, five stable periods, real re-entry refresh');
};
