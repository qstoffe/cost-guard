// Real Document PiP over the synthetic HTTP/SSE host, no external browser input.
const assert = require('node:assert/strict');

function measure() {
  const {view: v, window: w} = miniWatch, region = v.prompts;
  const head = v.body.parentNode.tHead.rows[0].cells[0];
  const clip = region.getBoundingClientRect(), header = head.getBoundingClientRect();
  const rows = [...v.body.rows].filter(row => row.dataset.id).map(row => {
    const bounds = row.getBoundingClientRect();
    const running = row.getAttribute('aria-label').endsWith(' · Running');
    return {id: row.dataset.id, running, height: bounds.height,
      visible: bounds.top >= header.bottom - 1 && bounds.bottom <= clip.top + region.clientHeight + 1};
  });
  return {
    outer: [w.outerWidth, w.outerHeight], inner: [w.innerWidth, w.innerHeight],
    requested: probeRequests.at(-1), screen: [w.screen.availWidth, w.screen.availHeight],
    height: region.clientHeight, header: header.height, headerOffset: header.top - clip.top,
    available: w.innerHeight - clip.top - parseFloat(w.getComputedStyle(v.doc.body).paddingBottom),
    gutter: region.offsetHeight - region.clientHeight, scrollTop: region.scrollTop,
    scrollHeight: region.scrollHeight, horizontal: region.scrollWidth > region.clientWidth,
    documentOverflow: v.doc.documentElement.scrollWidth > w.innerWidth + 1, rows
  };
}

module.exports = async ({evaluate, until, fixture, open, close, settle, settings, command,
  sessionId, pipSession, evidence}) => {
  const field = 'miniWatchNonRunningRows', endpoint = 'mini-non-running-rows';
  const read = () => evaluate(`(${measure.toString()})()`);
  const widthLayout = () => evaluate(`(${require('./probe_mini_width.cjs').inspect.toString()})(miniWatch.view)`);
  const bounds = () => evaluate('[miniWatch.window.outerWidth,miniWatch.window.outerHeight]');
  const record = (name, {rows, ...layout}) => evidence.layouts.push({case:name, ...layout,
    running:rows.filter(row => row.running).length, nonRunning:rows.filter(row => !row.running).length,
    visible:rows.filter(row => row.visible).map(row => row.id)});
  const publish = async (running, ended, accounts) => {
    await fixture(`history-${ended}-${running}-${accounts}`);
    await until(`liveValue.view.active_cards.length===${running} && liveValue.view.history_cards.length===${ended}`);
  };
  const restore = field => settings(field, {'theme':'theme', 'ccostDisplayUnit':'ccost',
    'miniWatchNonRunningRows':endpoint, 'miniWatchSize':'mini-size'}[field], 'default');

  // Keep the original measured-width relationship under the same fixture, CSS
  // and page zoom; the pre-change source run records a separate native baseline.
  await open();
  const legacy = await evaluate(`(()=>{const m=miniWatch.measure,style=getComputedStyle(m.body);
    const scale=(outerWidth-16)/innerWidth;
    return Math.min(screen.availWidth-16,
      Math.ceil((m.defaultContentWidth()+parseFloat(style.paddingLeft)+parseFloat(style.paddingRight))*scale));})()`);
  const opening = await read();
  assert.ok(Math.abs(opening.requested.width - 0.75 * legacy) <= 1, JSON.stringify({legacy, opening}));
  assert.ok(opening.inner[0] > 0 && opening.outer[0] >= opening.inner[0]);
  assert.ok(opening.outer[0] <= opening.screen[0] + 1);
  assert.equal(await evaluate('miniWatch.feedback.textContent'), '');
  record('opening-relative-width', {...opening, legacy});
  await close();

  await publish(4, 15, 0);
  await open();
  assert.equal(await evaluate('miniWatch.view.nonRunningRows'), 5);
  for (const capacity of [5, 2, 10]) {
    await settings(field, endpoint, capacity);
    // A live preference is allowed to exceed the original height. Reopen to
    // test the full configured band against actual native requested bounds.
    await close(); await open();
    const layout = await read(), {rows} = layout;
    assert.equal(rows.length,19);
    assert.equal(rows.filter(row => row.running).length,4);
    const expected = rows.slice(-(capacity + 4));
    const fullHeight = layout.header + expected.reduce((sum,row) => sum + row.height,0);
    assert.ok(layout.height <= fullHeight + 1, JSON.stringify(layout));
    assert.ok(layout.scrollHeight > layout.height && layout.scrollTop > 0);
    assert.ok(Math.abs(layout.headerOffset) <= 1, JSON.stringify(layout));
    if (layout.height + 1 >= fullHeight) {
      assert.deepEqual(rows.filter(row => row.visible).map(row => row.id),expected.map(row => row.id));
    } else {
      assert.ok(layout.available < fullHeight + layout.gutter + 1, JSON.stringify(layout));
      assert.ok(rows.some(row => row.visible),'a height-clamped native PiP remains navigable');
    }
    record(`capacity-${capacity}`,layout);
  }

  const before = await bounds();
  await evaluate("location.hash='#/settings'");
  await until("!!document.querySelector('#mini-non-running-rows:not([disabled])')");
  const options = await evaluate("[...document.querySelector('#mini-non-running-rows').options].map(o=>o.value)");
  assert.deepEqual(options,['default','2','3','4','5','6','7','8','9','10']);
  for (const value of ['2','10','default']) {
    await evaluate(`(()=>{const select=document.querySelector('#mini-non-running-rows');
      select.value='${value}';select.dispatchEvent(new Event('change'));})()`);
    const capacity = value==='default'?5:Number(value);
    await until(`miniWatch.view.nonRunningRows===${capacity} && !document.querySelector('#mini-non-running-rows').disabled`);
    const saved = await evaluate("api('/api/settings')");
    assert.equal(saved.webSettingsChoices[field], value==='default'?value:capacity);
    assert.deepEqual(await bounds(),before,'changing settings while open cannot resize native PiP');
  }
  await evaluate("location.hash='#/watch'");
  for (const [running, accounts] of [[0,0],[1,1],[12,6],[5,1]]) {
    await publish(running,15,accounts);
    await until(`miniWatch.view.promptRows.size===${15+running}`);
    await settle();
    assert.deepEqual(await bounds(),before,'prompt updates do not resize PiP');
    assert.equal((await read()).rows.filter(row => row.running).length,running);
  }
  for (const [theme, unit] of [['web','usd'],['classic','credits']]) {
    await settings('theme','theme',theme);
    await settings('ccostDisplayUnit','ccost',unit);
    await publish(12,15,6);
    await settle();
    assert.deepEqual(await bounds(),before);
    const header = await widthLayout();
    assert.equal(header.fits,true,JSON.stringify(header));
    assert.equal(header.documentOverflow,false);
  }

  const pip = await pipSession();
  await command('Page.bringToFront',{},pip);
  await evaluate(`miniWatch.window.resizeTo(240,220)`,true);
  await settle();
  const narrow = await read();
  assert.equal(narrow.rows.length,27);
  assert.equal(narrow.documentOverflow,false);
  assert.ok(narrow.scrollHeight > narrow.height);
  assert.ok(narrow.height > narrow.header);
  if (narrow.inner[0] <= 260) assert.equal(narrow.horizontal,true);
  record('native-manual-narrow',narrow);
  const key = async (name, code) => {
    for (const type of ['keyDown','keyUp']) await command('Input.dispatchKeyEvent',
      {type,key:name,code:name,windowsVirtualKeyCode:code},pip);
  };
  await command('Page.bringToFront',{},pip);
  await evaluate(`(()=>{const region=document.querySelector('.mini-prompts');
    region.scrollTop=region.scrollHeight;region.focus({preventScroll:true});})()`,false,pip);
  assert.ok((await read()).scrollTop>0);
  await key('Home',36);
  await until('miniWatch.view.prompts.scrollTop===0');
  assert.equal((await read()).rows[0].visible,true);
  await evaluate('miniWatch.view.prompts.scrollTop=miniWatch.view.prompts.scrollHeight');
  await until('miniWatch.view.prompts.scrollHeight-miniWatch.view.prompts.scrollTop-miniWatch.view.prompts.clientHeight<=1');
  assert.equal((await read()).rows.at(-1).visible,true);
  await evaluate(`window.fitRequests=[];{const w=miniWatch.window;
    for(const name of ['resizeBy','resizeTo']){const native=w[name].bind(w);
      w[name]=(...args)=>{fitRequests.push({name,args});return native(...args);};}}`);
  // Invoke the real View button with transient activation in the PiP realm.
  await evaluate("document.querySelector('.mini-fit-height').click()",true,pip);
  await settle();
  const fitted = await read();
  const fits = await evaluate('fitRequests');
  assert.equal(fits.length,1,JSON.stringify({narrow,fitted,fits}));
  assert.equal(fits[0].args[0],fits[0].name==='resizeBy'?0:narrow.outer[0]);
  assert.equal(fitted.outer[0],narrow.outer[0]);
  assert.ok(fitted.outer[1] >= narrow.outer[1]);
  record('explicit-height-only-fit',fitted);
  await close();

  await command('Page.bringToFront',{},sessionId);
  await settings('miniWatchSize','mini-size','remember-last');
  await open();
  const fallback = await read();
  assert.equal(fallback.requested.width,Math.round(0.75 * Math.min(634,fallback.screen[0] - 16)));
  await evaluate('miniWatch.window.resizeTo(550,410)',true); await settle();
  const manual = await read();
  await close(); await open();
  const remembered = await read();
  assert.equal(remembered.requested.preferInitialWindowPlacement,false);
  assert.ok(Math.abs(remembered.outer[0]-manual.outer[0])<=1,JSON.stringify({manual,remembered}));
  record('remembered-width-reopen',{...remembered, manual:manual.outer});
  await close();
  for (const setting of ['theme','ccostDisplayUnit',field,'miniWatchSize']) await restore(setting);
  // Exercise the browser's minimum independently of the application's normal
  // width formula. A browser-clamped request must not cause an auto-correction.
  await evaluate(`{const m=miniWatch.measure;window.readOpening=m.read.bind(m);
    m.read=controller=>({...readOpening(controller),width:80,height:120});}`);
  try {
    await open();
    const clamped = await read();
    assert.equal(clamped.requested.width,80);
    assert.ok(clamped.inner[0]*evidence.browserZoom>80, JSON.stringify(clamped));
    assert.equal(clamped.documentOverflow,false);
    assert.equal(clamped.rows.length,27);
    await publish(10,15,1); await settle();
    assert.deepEqual(await bounds(),clamped.outer);
    record('browser-minimum-width',clamped);
  } finally {
    await close(); await evaluate('miniWatch.measure.read=readOpening;delete window.readOpening');
  }
  assert.equal(await evaluate('probeStreams'),1);
  evidence.checks.push('Native PiP compact width against measured legacy request; 2/5/10 real row capacity, Settings default/save while open, scrolling/focus, count/theme/unit updates, manual narrow/short resize, explicit height-only Fit and remembered width');
};
