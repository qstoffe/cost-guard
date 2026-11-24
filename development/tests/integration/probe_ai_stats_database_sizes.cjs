const assert = require('node:assert/strict');

module.exports = async function({command, evaluate, until, fixture, tab, checks}) {
  const card = '.ai-stat-databases';
  const texts = selector => `[...document.querySelectorAll('${card} ${selector}')].map(node=>node.textContent)`;
  const values = texts('.ai-stat-value'), counts = texts('dd button'), caption = `${texts('.ai-stat-trait')}[0]`;
  await until(`${counts}.join('/')==='2 main sessions/1 main session'`);
  const initial = await evaluate(values);
  initial.forEach(text => assert.match(text,/^[\d,.]+ KB$/));
  assert.deepEqual(await evaluate(`(() => {
    const card=document.querySelector('${card}');
    return {count:document.querySelectorAll('${card}').length, title:card.querySelector('h4 button').textContent,
      group:card.closest('section').querySelector('h3').textContent,
      labels:[...card.querySelectorAll('dt')].map(node=>node.textContent)};
  })()`), {count:1, title:'Database Sizes', group:'Overview', labels:['OpenCode DB','CostGuard Cache DB']});
  await evaluate(`window.__sizeCard=document.querySelector('${card}'); window.__sizeReads=0;
    window.__sizeFetch=fetch; fetch=(url,...args)=>{
      if(url==='/api/database-sizes') __sizeReads++;
      return __sizeFetch(url,...args);
    };`);
  for (const period of ['today','7-days','month','all','30-days']) {
    await evaluate(`selectStats(current,'${period}')`);
    await until(`!current.loading && current.result?.view.ai_stats.some(row=>row.period==='${period}')`);
    assert.equal(await evaluate(`__sizeCard===document.querySelector('${card}') && __sizeReads===0`),true);
    assert.deepEqual(await evaluate(values),initial);
    assert.deepEqual(await evaluate(counts),['2 main sessions','1 main session']);
  }
  await fixture('stats-resize-cache');
  await evaluate(`location.hash='#/accounts'`); await until(`current.section==='accounts'`);
  await evaluate(`location.hash='#/ai-stats'`); await until(`${values}[1]?.endsWith(' MB')`);
  assert.equal(await evaluate(`__sizeReads`),1);

  const sizeCases = [[0,999,['0 B','999 B'],/needs two/], [1000,999_000,['1 KB','999 KB'],/whole luggage/],
    [1_000_000_000,1_000_000,['1 GB','1 MB'],/traveling light/], [500,500,['500 B','500 B'],/about the same/],
    [500,800,['500 B','800 B'],/bigger/], [null,92_000,['Size unavailable','92 KB'],/needs two/],
    [285_000_000,'not a byte count',['285 MB','Size unavailable'],/needs two/]];
  for (const [opencode,cache,expected,comparison] of sizeCases) {
    await evaluate(`(async()=>{
      const original=fetch; fetch=async()=>Response.json({opencode_bytes:${JSON.stringify(opencode)},cache_bytes:${JSON.stringify(cache)},cache_main_sessions:0});
      try { await current.stats.refreshDatabaseSizes(); } finally { fetch=original; }
    })()`);
    assert.deepEqual(await evaluate(values),expected);
    assert.deepEqual(await evaluate(counts),['Main sessions unavailable','0 main sessions']);
    assert.match(await evaluate(caption),comparison);
    assert.equal(await evaluate(`AIStatsView.valid(current.result) && document.querySelectorAll('.ai-stat[data-metric]').length===13`),true);
  }
  await evaluate(`(async()=>{
    const original=fetch; fetch=async()=>{throw new Error('optional metadata read failed');};
    try { await current.stats.refreshDatabaseSizes(); } finally { fetch=original; }
  })()`);
  assert.deepEqual(await evaluate(values),['285 MB','Size unavailable'],'failed refresh retains measured facts');
  assert.equal(await evaluate(`AIStatsView.valid(current.result) && !current.failed && !current.loading`),true);
  await evaluate(`fetch=__sizeFetch; current.stats.refreshDatabaseSizes()`);
  await until(`${counts}.join('/')==='2 main sessions/1 main session'`);
  await command('Page.bringToFront',{},tab);
  const move = (x,y) => command('Input.dispatchMouseEvent',{type:'mouseMoved',x,y},tab);
  const escape = async () => {
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);
    await until(`document.getElementById('context-help').hidden`);
  };
  for (const mode of ['hover','focus','touch']) {
    if (mode === 'touch') await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
    for (const [index,text] of [[0,/saved Web history.*main SQLite files only.*not side files/],
      [1,/2 subagent sessions in OpenCode DB/],[2,/Subagent sessions unavailable in CostGuard Cache DB/]]) {
      const button = `document.querySelectorAll('${card} button')[${index}]`;
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
      assert.match(body,text,mode);
      await escape();
      if (mode === 'hover') await move(1,1);
    }
    if (mode === 'touch') await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
  }
  checks.push('Database Sizes: one Overview card with store-specific counts and hover/focus/touch help; five stable periods, comparable and neutral captions, real re-entry refresh and isolated failures');
};
