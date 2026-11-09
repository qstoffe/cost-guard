// Rendered text geometry for the shared Overview/Fun Facts cards, not accounting.
const assert = require('node:assert/strict');

function inspect() {
  const issues = [], details = [], rows = new Map();
  const rect = node => node.getBoundingClientRect();
  const contains = (outer, inner) => inner.top >= outer.top - 1 && inner.bottom <= outer.bottom + 1 &&
    inner.left >= outer.left - 1 && inner.right <= outer.right + 1;
  const cards = [...document.querySelectorAll('.ai-stat')];
  cards.forEach((card, index) => {
    const bounds = rect(card), fields = [...card.children];
    const rowKey = card.parentElement.parentElement.querySelector('h3').textContent + ':' + Math.round(bounds.top);
    const heights = rows.get(rowKey) || []; heights.push(bounds.height); rows.set(rowKey, heights);
    fields.forEach((field, position) => {
      const box = rect(field);
      if (!contains(bounds, box)) issues.push({index, field:position, kind:'field-outside-card'});
      if (position && box.top < rect(fields[position - 1]).bottom - 1)
        issues.push({index, field:position, kind:'overlapping-rows'});
      const walker = document.createTreeWalker(field, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        if (!walker.currentNode.textContent.trim()) continue;
        const range = document.createRange(); range.selectNodeContents(walker.currentNode);
        for (const line of range.getClientRects()) {
          if (!contains(box, line)) issues.push({index, field:position, kind:'text-outside-field',
            fieldHeight:box.height, textHeight:line.height});
          // A fitting card alone cannot detect an inner overflow:hidden clip.
          for (let ancestor = walker.currentNode.parentElement; ancestor && card.contains(ancestor); ancestor = ancestor.parentElement) {
            const style = getComputedStyle(ancestor), clip = rect(ancestor);
            if (style.overflowY !== 'visible' && (line.top < clip.top - 1 || line.bottom > clip.bottom + 1))
              issues.push({index, field:position, kind:'vertical-clip'});
            if (style.overflowX !== 'visible' && (line.left < clip.left - 1 || line.right > clip.right + 1))
              issues.push({index, field:position, kind:'horizontal-clip'});
          }
        }
      }
    });
    const detail = card.querySelector('.ai-stat-detail'), style = getComputedStyle(detail);
    details.push({index, height:rect(detail).height, lineHeight:style.lineHeight, overflow:style.overflow,
      rows:getComputedStyle(card).gridTemplateRows, link:!!detail.querySelector('a')});
  });
  return {count:cards.length, issues, details,
    equalRows:[...rows.values()].every(heights => Math.max(...heights) - Math.min(...heights) < 1),
    pageOverflow:document.documentElement.scrollWidth > innerWidth};
}

module.exports = async function({command, evaluate, until, tab, textLayouts, checks}) {
  const measure = async label => {
    const layout = await evaluate(`(${inspect.toString()})()`);
    textLayouts.push({label,...layout});
    assert.deepEqual(layout.issues, [], label + ': text/link regions must fit: ' + JSON.stringify(layout));
    assert.equal(layout.pageOverflow, false, label + ': page overflow');
    assert.equal(layout.equalRows, true, label + ': sibling heights');
  };
  await measure('canonical populated session links and date');
  // Exercise existing display/DOM seams with intentionally synthetic edge strings.
  await evaluate(`window.__statsOriginal=current.result; window.__statsPeriod=current.period;
    window.__statsStress=structuredClone(current.result);
    for (const row of __statsStress.view.ai_stats) {
      row.metrics.forEach((metric,index)=>{
        metric.display.trait='A long readable trait with descenders gjpqy and accents Åé — '.repeat(3);
        metric.status=['complete','unknown','partial'][index%3];
        metric.display.value=index%2 ? 'N/A' : '12345678901234567890';
        metric.display_units={credits:{...metric.display,value:index%2 ? 'N/A' : '12345678901234567890 credits'},
          usd:{...metric.display,value:index%2 ? 'N/A' : '$123456789012345678.90'}};
        if(metric.metric==='hourly-rate') for(const unit of ['credits','usd'])
          for(const key of ['calendar_rate','workday_rate','robot_day'])
            metric.display_units[unit][key]=(unit==='usd'?'$':'')+'123456789012345678.90'+
              (unit==='credits'?' CCost':'')+(key==='robot_day'?'/8h day':'/h');
        metric.detail=metric.metric==='busiest-day' ? 'September 30, 2026' : '';
        if(metric.session_id) metric.session_title=index%2 ? 'Short gjpqy' : 'LongSessionWithNoBreaks'.repeat(8)+' — gjpqy Åé';
      });
      row.matched={metric:'speed-gap',display:{value:'120×',trait:'A long matched-run trait '.repeat(5)},
        detail:'Matched first inputs on September 30, 2026 — '+ 'detail'.repeat(30)};
    }
    current.result=__statsStress; current.stats.update(current);`);
  for (const theme of ['classic','light','dark']) for (const width of [360,520,1280]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
    for (const scale of [1,1.25,1.5,2]) {
      await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};
        document.documentElement.style.fontSize=${JSON.stringify(15*scale+'px')};
        document.body.style.fontFamily=${JSON.stringify(scale===1.5?'Georgia, serif':'Arial, sans-serif')};`);
      for (const unit of ['credits','usd']) {
        await evaluate(`ReportView.setUnit('${unit}',output)`);
        await measure(theme + '/' + width + '/' + scale + '/' + unit);
      }
    }
  }
  await evaluate(`document.documentElement.style.fontSize=''; document.body.style.fontFamily='';
    current.result=__statsOriginal; current.period=__statsPeriod; current.stats.update(current);
    ReportView.setUnit('credits',output);`);
  await evaluate(`window.__statsLink=document.querySelector('.ai-stat-detail a');
    __statsLink.closest('.ai-stat').querySelector('h4 button').focus();`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},tab);
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},tab);
  assert.equal(await evaluate(`document.activeElement===__statsLink`),true);
  const link = await evaluate(`(() => {
    current.stats.update(current);
    __statsLink.scrollIntoView({block:'center'});
    const r=__statsLink.getClientRects()[0], style=getComputedStyle(__statsLink);
    return {x:r.x+r.width/2,y:r.y+r.height/2,href:__statsLink.hash,
      focused:document.activeElement===__statsLink && __statsLink.matches(':focus-visible'),
      outline:style.outlineStyle, outlineWidth:parseFloat(style.outlineWidth),
      unclipped:[...function*(){for(let a=__statsLink.parentElement;a && a!==document.body;a=a.parentElement)yield a;}()]
        .every(a=>getComputedStyle(a).overflowY==='visible')}; })()`);
  assert.equal(link.focused,true); assert.equal(link.unclipped,true);
  assert.notEqual(link.outline,'none'); assert.ok(link.outlineWidth>0);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:link.x,y:link.y},tab);
  assert.equal(await evaluate(`__statsLink.matches(':hover') && document.elementFromPoint(${link.x},${link.y})===__statsLink`),true);
  await command('Input.dispatchMouseEvent',{type:'mousePressed',x:link.x,y:link.y,button:'left',clickCount:1},tab);
  await command('Input.dispatchMouseEvent',{type:'mouseReleased',x:link.x,y:link.y,button:'left',clickCount:1},tab);
  await until(`location.hash===${JSON.stringify(link.href)}`);
  await evaluate(`location.hash='#/ai-stats'`);
  await until(`current.section==='ai-stats' && current.result && !current.loading`);
  await evaluate(`document.querySelector('.ai-stat-detail a').focus()`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'},tab);
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13},tab);
  await until(`location.hash===${JSON.stringify(link.href)}`);
  await evaluate(`location.hash='#/ai-stats'`);
  await until(`current.section==='ai-stats' && current.result && !current.loading`);
  checks.push('session link Tab focus, visible unclipped outline, retained focus/node on update, pointer hover/hit/click and Enter keep the canonical session target');
  for (const period of ['today','7-days','30-days','month','all']) {
    await evaluate(`selectStats(current,'${period}')`);
    await until(`!current.loading && current.result?.view.ai_stats.some(row=>row.period==='${period}')`);
    await measure('canonical period ' + period);
  }
  // Both optional labels use the same five non-overlapping tracks and final link.
  for (const metric of ['speed-gap','original-thinker']) {
    await evaluate(`current.result=__statsStress; current.period=__statsStress.view.ai_stats[0].period;
      __statsStress.view.ai_stats[0].matched.metric='${metric}'; current.stats.update(current);`);
    await measure('optional matched card ' + metric);
    assert.equal(await evaluate(`document.querySelectorAll('.ai-stat').length`),11);
    assert.equal(await evaluate(`current.stats.extra.lastChild.hash`),'#/comparisons');
  }
  await evaluate(`selectStats(current,__statsPeriod)`);
  assert.equal(await evaluate(`document.querySelectorAll('.ai-stat').length`),10);
  checks.push('actual text ranges, clipping ancestors and separate rows; long/short/unbroken titles, dates, large values, unknown/partial/empty, optional facts, five periods, units, fonts, 100/125/150/200% text scaling');
};

module.exports.inspect = inspect;
