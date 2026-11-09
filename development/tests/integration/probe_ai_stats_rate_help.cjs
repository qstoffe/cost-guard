// Real title-help paragraphs, live copy changes and optional input at narrow/zoomed sizes.
const assert = require('node:assert/strict');

module.exports = async function({command,evaluate,until,fixture,tab,checks}) {
  const original=await evaluate(`current.result`), period=await evaluate(`current.period`);
  const cases=await fixture('stats-evidence');
  const escape=async()=>{
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);
  };
  const text=()=>evaluate(`document.getElementById('context-help').textContent`);
  const focus=async()=>{
    await evaluate(`document.activeElement.blur(); document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
      document.querySelector('.ai-stat h4 button').focus();`);
    await until(`!document.getElementById('context-help').hidden`);
  };
  const select=async name=>{
    const result=cases.find(item=>item.name===name).result;
    await evaluate(`current.result=${JSON.stringify(result)}; current.period=current.result.view.ai_stats[0].period;
      current.stats.update(current);`);
  };
  const paragraphs=copy=>{
    const parts=copy.split('\n\n'); assert.equal(parts.length,3);
    parts.forEach((part,index)=>{
      assert.ok(part.startsWith(['24h:','Workday:','Robot 8h shift:'][index]));
      assert.equal(part.trim(),part); assert.doesNotMatch(part,/\n/);
      assert.ok(part.split(/\s+/).length<=22);
    });
    assert.doesNotMatch(copy,/[÷×=$]|CCost|active hours|\\n/);
  };
  for(const theme of ['classic','light','dark']) for(const width of [360,1280])
    for(const [font,zoom] of [['15px','1'],['30px','1'],['15px','1.25']]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};
        document.documentElement.style.fontSize=${JSON.stringify(font)}; document.documentElement.style.zoom=${JSON.stringify(zoom)};`);
      for(const [name,punchline] of [['complete',/parking spot/],['three-rates',/charging dock/],
          ['faster-robot',/shredded/],['empty',/hasn't started/],['unknown-duration',/charging dock/],
          ['no-workdays',/No scheduled workdays/]]) {
        await escape(); await select(name); await focus();
        const copy=await text(); paragraphs(copy); assert.match(copy,punchline);
        for(const unit of ['credits','usd']) {
          await evaluate(`ReportView.setUnit('${unit}',output)`);
          assert.equal(await text(),copy,'currency never changes the joke tier');
          const geometry=await evaluate(`(() => {
            const panel=document.getElementById('context-help'), box=panel.getBoundingClientRect();
            const node=panel.firstChild, paragraphs=panel.textContent.split('\\n\\n'); let offset=0;
            const ranges=paragraphs.map(part=>{const r=document.createRange();r.setStart(node,offset);
              r.setEnd(node,offset+part.length);offset+=part.length+2;const b=r.getBoundingClientRect();
              return {top:b.top,bottom:b.bottom};});
            return {visible:!panel.hidden,role:panel.getAttribute('role'),space:getComputedStyle(panel).whiteSpace,
              fits:box.left>=-1&&box.right<=innerWidth+1&&box.top>=-1&&box.bottom<=innerHeight+1,
              scroll:panel.scrollHeight>panel.clientHeight+1||panel.scrollWidth>panel.clientWidth+1,
              gaps:ranges.slice(1).map((r,i)=>r.top-ranges[i].bottom),
              focused:document.activeElement===document.querySelector('.ai-stat h4 button')};})()`);
          assert.equal(geometry.role,'tooltip'); assert.equal(geometry.space,'pre-line');
          assert.ok(geometry.visible&&geometry.fits&&geometry.focused,JSON.stringify(geometry));
          assert.equal(geometry.scroll,false); assert.ok(geometry.gaps.every(gap=>gap>5));
        }
      }
    }
  await evaluate(`document.documentElement.style.fontSize=''; document.documentElement.style.zoom='';`);
  await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},tab);
  await escape(); await select('complete'); await focus();
  await evaluate(`window.__rateFocus=document.activeElement; window.__rateCards=[...document.querySelectorAll('.ai-stat')];`);
  await select('faster-robot');
  assert.match(await text(),/shredded/);
  assert.equal(await evaluate(`document.activeElement===__rateFocus&&__rateCards.every((c,i)=>c===document.querySelectorAll('.ai-stat')[i])`),true);
  await escape(); await select('three-rates');
  assert.equal(await evaluate(`document.getElementById('context-help').hidden`),true,'refresh does not reopen dismissed help');
  await evaluate(`current.result=${JSON.stringify(original)}; current.period=${JSON.stringify(period)}; current.stats.update(current);`);
  for(const id of ['today','7-days','30-days','month','all']) {
    await evaluate(`selectStats(current,'${id}')`);
    await focus(); paragraphs(await text()); await escape();
  }
  await evaluate(`document.activeElement.blur(); document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
    document.querySelector('.ai-stat h4 button').scrollIntoView({block:'center'});`);
  const point=await evaluate(`(() => {const r=document.querySelector('.ai-stat h4 button').getBoundingClientRect();
    return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},tab);
  await until(`!document.getElementById('context-help').hidden`); paragraphs(await text()); await escape();
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:1,y:1},tab);
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},tab);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},tab);
  await until(`!document.getElementById('context-help').hidden`); paragraphs(await text()); await escape();
  await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
  await evaluate(`current.result=${JSON.stringify(original)}; current.period=${JSON.stringify(period)}; current.stats.update(current);`);
  checks.push('rate title: three actual visually separated short paragraphs, six scenarios × three themes × two widths × three scales × both units; no tooltip scrolling/clipping; retained focused live tier/period updates, Escape suppression, real hover and emulated touch');
};
