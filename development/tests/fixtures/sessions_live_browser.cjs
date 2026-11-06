// Real shipped HTTP/DTO/DOM lifecycle; commands change only the owned synthetic source.
const assert = require('node:assert/strict');
module.exports = async function sessionsLive({evaluate, until, fixture, command}) {
  const checks = [], layouts = [];
  await fixture('live-cold');
  await evaluate("location.hash='#/sessions'");
  await until('current?.catalog?.data?.view.session_usage[0]?.session_id === "root-0121"');
  const row = 'document.querySelector("tr[data-id=root-0121]")';
  assert.equal(await evaluate(`${row}.querySelector('a').getAttribute('href')`),'#/sessions/root-0121');
  assert.match(await evaluate(`${row}.cells[1].textContent`),/\[RUNNING\] Synthetic 0121/);
  assert.deepEqual(await evaluate(`[...${row}.cells].slice(2).map(cell=>cell.textContent)`),Array(4).fill('Loading…'));
  await evaluate(`window.keptRow=${row}; window.keptLink=keptRow.querySelector('a'); keptLink.focus();`);
  await fixture('live-hydrate');
  await until(`${row}.cells[4].textContent === '1'`);
  assert.equal(await evaluate('keptLink.isConnected && document.activeElement===keptLink'),true);
  const initial = await evaluate(`[...${row}.cells].map(cell=>cell.textContent)`);
  assert.notEqual(initial[2],'Loading…'); assert.notEqual(initial[3],'Loading…'); assert.notEqual(initial[5],'Loading…');
  await fixture('live-progress');
  await until(`${row}.cells[4].textContent === '2' && ${row}.cells[2].textContent === 'Multiple models'`);
  assert.equal(await evaluate('keptRow.isConnected && keptLink.isConnected && document.activeElement===keptLink'),true);
  assert.notEqual(await evaluate(`${row}.cells[3].textContent`),initial[3]);
  assert.match(await evaluate(`${row}.cells[1].textContent`),/RUNNING/);
  checks.push('cold canonical running proof; four pending cells hydrate and advance on normal polling; focused link survives');

  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await until('document.querySelector("#context-help")?.textContent.includes("other-provider/gpt-test")');
  assert.match(await evaluate('document.querySelector("#context-help").textContent'),/observed so far[\s\S]*github-copilot\/gpt-test[\s\S]*other-provider\/gpt-test/);
  await evaluate(`window.keptModel=${row}.cells[2].firstChild; window.scrollTo(0,100);
    const range=document.createRange();range.selectNodeContents(keptLink.lastChild);getSelection().removeAllRanges();getSelection().addRange(range);
    window.selectedText=getSelection().toString();window.oldScroll=scrollY;`);
  await fixture('live-finish');
  await until(`!${row}.cells[1].textContent.includes('RUNNING')`);
  assert.equal(await evaluate('keptModel.isConnected && keptRow.cells[2].firstChild===keptModel'),true);
  assert.equal(await evaluate('getSelection().toString()===selectedText && Math.abs(scrollY-oldScroll)<2'),true);
  assert.equal(await evaluate('document.querySelector("#context-help").matches(":popover-open")'),true);
  assert.doesNotMatch(await evaluate('document.querySelector("#context-help").textContent'),/observed so far/);
  const ended=await evaluate(`[...${row}.cells].slice(3).map(cell=>cell.textContent)`);
  await until(`current.catalog.busy === false`);
  await evaluate('current.catalog.load()');
  assert.deepEqual(await evaluate(`[...${row}.cells].slice(3).map(cell=>cell.textContent)`),ended,'idle is not execution time');
  checks.push('keyboard model identities, live help refresh, terminal marker, selection and scroll retained; no idle increments');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  assert.equal(await evaluate('document.querySelector("#context-help").hidden'),true);
  await evaluate('getSelection().removeAllRanges();document.activeElement.blur();window.scrollTo(0,0)');
  const bounds=await evaluate(`(() => {const r=keptModel.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...bounds});
  await until('document.querySelector("#context-help")?.matches(":popover-open")');
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
  await until('document.querySelector("#context-help").hidden');
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[bounds]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('document.querySelector("#context-help")?.matches(":popover-open")');
  assert.equal(await evaluate('document.querySelectorAll("[title],td .help-trigger").length'),0);
  checks.push('shared text-target mouse hover/leave, touch pin and Escape; no native or duplicate help');
  await fixture('fail');
  await until('current.catalog.status.textContent.includes("Source unavailable")');
  assert.doesNotMatch(await evaluate(`${row}.cells[1].textContent`),/RUNNING/);
  assert.deepEqual(await evaluate(`[...${row}.cells].slice(3).map(cell=>cell.textContent)`),ended);
  await fixture('recover'); await fixture('live-resume');
  await until(`${row}.cells[4].textContent === '3' && ${row}.cells[1].textContent.includes('RUNNING')`);
  checks.push('source outage retains qualified metrics; reconnect and later prompt reacquire running and counts');
  for (const theme of ['classic','light','dark']) for (const width of [360,1366,1920]) for (const zoom of [1,1.5]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]});
    await evaluate(`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};document.body.style.zoom=${zoom}`);
    const layout=await evaluate(`(() => {const pan=document.querySelector('.sessions-table-pan');return {
      columns:document.querySelectorAll('.session-catalog-table th').length,rows:current.catalog.body.children.length,
      pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,
      innerVertical:pan.scrollHeight>pan.clientHeight,nowrap:[...keptRow.cells].every(cell=>getComputedStyle(cell).whiteSpace==='nowrap'),
      numericFit:[...keptRow.cells].filter((_,i)=>i!==1).every(cell=>cell.scrollWidth<=cell.clientWidth+1)};})()`);
    assert.equal(layout.columns,6);assert.equal(layout.rows,50);assert.ok(layout.pageWidth<=width+1);
    assert.equal(layout.innerVertical,false);assert.equal(layout.nowrap,true);assert.equal(layout.numericFit,true);
    layouts.push({theme,width,zoom,...layout});
  }
  checks.push('Classic/Web light/dark; 360/1366/1920; 100/150% zoom; six columns/50 rows/document scroll');
  return {checks,layouts};
};
