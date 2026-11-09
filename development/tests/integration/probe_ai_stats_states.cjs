// Actual hover colors and canonical Python-projected evidence states in Chromium.
const assert = require('node:assert/strict');

function colors(index) {
  const button = document.querySelectorAll('.ai-stats-periods button')[index];
  const label = button.querySelector('.help-label') || button;
  const style = getComputedStyle(button), inner = getComputedStyle(label);
  const luminance = color => color.match(/[\d.]+/g).slice(0,3).map(Number).map(n => {
    const value = n / 255; return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
  }).reduce((total, value, i) => total + value * [.2126,.7152,.0722][i], 0);
  const contrast = (a,b) => (Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
  return {button:style.color, background:style.backgroundColor, label:inner.color,
    labelBackground:inner.backgroundColor, selected:button.getAttribute('aria-pressed'),
    buttonContrast:contrast(style.color,style.backgroundColor), labelContrast:contrast(inner.color,style.backgroundColor)};
}

module.exports = async function({command,evaluate,until,fixture,tab,contrasts,states,checks}) {
  await evaluate(`selectStats(current,'all')`);
  await until(`!current.loading && current.result?.view.ai_stats.some(row=>row.period==='all')`);
  const original = await evaluate(`current.result`);
  const move = (x,y) => command('Input.dispatchMouseEvent',{type:'mouseMoved',x,y},tab);
  for (const theme of ['classic','light','dark']) for (const width of [360,520,1280])
    for (const [scale,font,zoom] of [['normal','15px','1'],['text-200','30px','1'],['zoom-125','15px','1.25']]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};
        document.documentElement.style.fontSize=${JSON.stringify(font)}; document.documentElement.style.zoom=${JSON.stringify(zoom)};`);
      for (let index=0;index<5;index++) for (const selected of [true,false]) {
        await evaluate(`selectStats(current,${JSON.stringify(['today','7-days','30-days','month','all'][selected?index:(index+1)%5])});
          document.activeElement.blur(); document.querySelectorAll('.ai-stats-periods button')[${index}].scrollIntoView({block:'center'});`);
        const immediate=await evaluate(`(${colors.toString()})(${index})`);
        assert.ok(immediate.buttonContrast>=4.5,'selection must not cross-fade through unreadable colors');
        await evaluate(`Promise.all(document.getAnimations().map(animation=>animation.finished.catch(()=>{})))`);
        const point=await evaluate(`(() => {const b=document.querySelectorAll('.ai-stats-periods button')[${index}],
          r=b.getBoundingClientRect(), l=(b.querySelector('.help-label')||b).getBoundingClientRect();
          return {label:{x:l.x+l.width/2,y:l.y+l.height/2},padding:{x:r.x+2,y:r.y+2}};})()`);
        for (const position of ['before','label','padding','after','pressed']) {
          const p=point[position==='pressed'?'label':position]; await move(p?.x||1,p?.y||1);
          if(position==='pressed') await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p},tab);
          await evaluate(`Promise.all(document.getAnimations().map(animation=>animation.finished.catch(()=>{})))`);
          const sample=await evaluate(`(${colors.toString()})(${index})`);
          contrasts.push({theme,width,scale,index,position,...sample});
          assert.equal(sample.selected,String(selected));
          assert.ok(sample.labelContrast>=4.5,JSON.stringify(contrasts.at(-1)));
          assert.ok(sample.buttonContrast>=4.5,JSON.stringify(contrasts.at(-1)));
          assert.equal(sample.label,sample.button,'help label inherits the same control foreground');
          if(position==='pressed') await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p},tab);
        }
      }
    }
  checks.push('all five selected/unselected controls: actual label/padding hover, press and departure, Classic/light/dark, 360/520/1280, 200% text and 125% CSS zoom; computed contrast >=4.5');
  await evaluate(`document.documentElement.style.fontSize=''; document.documentElement.style.zoom='';
    selectStats(current,'all'); window.__statsCalls=0; window.__statsApi=api;
    api=async (...args)=>{if(args[0]==='/api/reports')__statsCalls++;return __statsApi(...args);};`);
  await command('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false},tab);
  const escape=async()=>{await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'},tab);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'},tab);};
  for (const index of [3,4]) {
    await escape(); await move(1,1);
    await evaluate(`document.activeElement.blur(); document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
      document.querySelectorAll('.ai-stats-periods button')[${index}].focus();`);
    await until(`!document.getElementById('context-help').hidden`);
    assert.match(await evaluate(`document.getElementById('context-help').textContent`),index===3?/calendar month/:/whole robot saga/);
    await escape(); await until(`document.getElementById('context-help').hidden`);
  }
  await evaluate(`document.activeElement.blur(); document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));`);
  const point=await evaluate(`(() => {const b=document.querySelectorAll('.ai-stats-periods button')[4];b.scrollIntoView();
    const r=b.querySelector('.help-label').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await move(point.x,point.y); await until(`!document.getElementById('context-help').hidden`);
  assert.equal(await evaluate(`__statsCalls`),0,'hover and focus never acquire history');
  await escape(); await move(1,1);
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},tab);
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},tab);
  await until(`!document.getElementById('context-help').hidden`);
  assert.match(await evaluate(`document.getElementById('context-help').textContent`),/whole robot saga/i);
  await escape(); await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
  assert.equal(await evaluate(`document.querySelectorAll('.ai-stats-periods [title]').length`),0);
  await evaluate(`api=__statsApi`);
  checks.push('selected month/all keyboard scope help and Escape; actual selected-label hover/touch help; no duplicate native title or history acquisition');

  const cases=await fixture('stats-evidence');
  for(const item of cases) for(const theme of ['classic','light','dark']) for(const unit of ['credits','usd']) {
    await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};
      current.result=${JSON.stringify(item.result)};current.period=current.result.view.ai_stats[0].period;current.stats.update(current);
      ReportView.setUnit(${JSON.stringify(unit)},output);`);
    const rendered=await evaluate(`[...document.querySelectorAll('.ai-stat')].map(card=>({
      value:card.querySelector('.ai-stat-value').textContent,trait:card.querySelector('.ai-stat-trait').textContent,
      state:!!card.querySelector('.ai-stat-state')}))`);
    const expected=item.result.view.ai_stats[0].metrics;
    assert.equal(rendered.length,10);
    rendered.forEach((card,index)=>{
      if (index !== 0) assert.equal(card.value,expected[index].display_units?.[unit]?.value || expected[index].display.value);
      assert.equal(card.trait,expected[index].display.trait);
      assert.equal(card.state,false);
      assert.doesNotMatch(JSON.stringify(card),/Unavailable|Partial|Provisional|No data|N\/A|Unknown|Observed|≥|NaN|Infinity|vault/i);
    });
    const rates=await evaluate(`[...document.querySelectorAll('.ai-stat-rate')].map(row=>({
      label:row.getAttribute('aria-label'),value:row.querySelector('.ai-stat-rate-value').textContent}))`);
    assert.deepEqual(rates.map(row=>row.label),['Calendar average','Workday average','Active AI average']);
    assert.deepEqual(rates.map(row=>row.value),['calendar_rate','workday_rate','active_rate'].map(key=>
      expected[0].display_units?.[unit]?.[key] || expected[0].display[key]));
    if (item.name==='three-rates') assert.deepEqual(rates.map(row=>row.value),unit==='credits' ?
      ['5 CCost/h','21 CCost/h','30 CCost/h'] : ['$0.05/h','$0.21/h','$0.30/h']);
    if (item.name==='faster-robot') assert.equal(rates[2].value,unit==='credits'?'120 CCost/h':'$1.20/h');
    if (item.name==='no-workdays') assert.equal(rates[1].value,'No workdays');
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stat-state,.ai-stats-status').length`),0);
    const forbidden=/Unavailable|Partial|Provisional|No data|N\/A|Unknown|Observed|≥|Some executions|Historical source coverage|not a verified overall winner|missing reference-price evidence|snapshot interval|The evidence is still in the vault|estimated|approximate|lower bound/i;
    assert.doesNotMatch(await evaluate(`output.textContent`),forbidden);
    assert.equal(await evaluate(`document.getElementById('report-updating')`),null);
    for (const affected of theme==='classic' && unit==='credits' ? expected.map((_,i)=>i) : [0]) {
      await evaluate(`document.activeElement.blur(); document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
        document.querySelectorAll('.ai-stat h4 button')[${affected}].focus();`);
      await until(`!document.getElementById('context-help').hidden`);
      assert.doesNotMatch(await evaluate(`document.getElementById('context-help').textContent`),forbidden);
      await escape();
    }
    const ax=await command('Accessibility.getFullAXTree',{},tab);
    assert.doesNotMatch(ax.nodes.filter(node=>!node.ignored).map(node=>[node.name?.value,node.description?.value].join(' ')).join('\n'),forbidden);
    states.push({case:item.name,theme,unit,rendered,rates});
  }
  await evaluate(`current.result=${JSON.stringify(cases.find(item=>item.name==='source-gap').result)}; current.period='all'; current.stats.update(current);
    document.activeElement.blur(); document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));
    window.__focusedStat=document.querySelector('.ai-stat h4 button'); __focusedStat.focus();`);
  await until(`!document.getElementById('context-help').hidden`);
  await evaluate(`current.result=${JSON.stringify(cases.find(item=>item.name==='unknown-duration').result)};
    current.stats.update(current); ReportView.setUnit('credits',output);`);
  assert.equal(await evaluate(`document.activeElement===__focusedStat`),true);
   assert.match(await evaluate(`document.getElementById('context-help').textContent`),/hourly appetite when it's actually working/);
  await escape();
  await evaluate(`current.result=${JSON.stringify(original)};current.period='30-days';current.stats.update(current);`);
  checks.push('twelve canonical evidence cases: ten cards with three Python-prepared rates, example/faster robot/no-workdays, both units/three themes; no state/reason DOM, focused heading retained');
};
