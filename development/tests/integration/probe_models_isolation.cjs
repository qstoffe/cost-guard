// Source-shaped browser regression: shipped authenticated host, native input, live DOM.
const assert = require('node:assert/strict');
async function probeIsolation({command, evaluate, until, id, mode, fixture, requests, baseline = false}) {
  const observations = [], checks = [];
  const read = expression => evaluate(id, expression);
  const wait = expression => until(id, expression);
  const mouse = async selector => {
    const point = await read(`(()=>{const n=document.querySelector(${JSON.stringify(selector)});n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
    await command('Input.dispatchMouseEvent', {type:'mouseMoved', ...point}, id);
    await command('Input.dispatchMouseEvent', {type:'mousePressed', button:'left', clickCount:1, ...point}, id);
    await command('Input.dispatchMouseEvent', {type:'mouseReleased', button:'left', clickCount:1, ...point}, id);
  };
  const key = async (key, code, windowsVirtualKeyCode) => {
    await command('Input.dispatchKeyEvent', {type:'keyDown',key,code,windowsVirtualKeyCode}, id);
    await command('Input.dispatchKeyEvent', {type:'keyUp',key,code,windowsVirtualKeyCode}, id);
  };
  const capture = async label => {
    const value = await read(`(()=>{const n=document.querySelector('[data-model-control="refresh"]'),s=getComputedStyle(n);return {
      focus:n.matches(':focus'),visible:n.matches(':focus-visible'),active:n.matches(':active'),
      outline:s.outline,shadow:s.boxShadow,border:s.borderColor,
      benchmarkRoot:probeBenchmark===current.benchmark.root,benchmarkRows:probeRows.every((n,i)=>n===current.benchmark.body.rows[i]),
      detached:probeDetached,priceRows:probePriceRows.every((n,i)=>n===document.querySelector('.overview-model-table').tBodies[0].rows[i])};})()`);
    observations.push({label,...value});
    return value;
  };
  await read(`window.probeBenchmark=current.benchmark.root;window.probeRows=[...current.benchmark.body.rows];
    window.probePriceRows=[...document.querySelector('.overview-model-table').tBodies[0].rows];window.probeDetached=0;
    window.probeObserver=new MutationObserver(records=>{for(const r of records)for(const n of r.removedNodes)
      if(n===probeBenchmark||n.contains?.(probeBenchmark))probeDetached++;});
    probeObserver.observe(document.getElementById('result'),{childList:true,subtree:true});`);
  // First exercise the native same-element keyboard -> mouse transition. Browser
  // heuristics can retain :focus-visible even when focus never changes on click.
  await read(`document.querySelector('.model-section-heading a').focus()`);
  await key('Tab','Tab',9);
  observations.push({label:'keyboard-before-pointer',...await read(`(()=>{const n=document.activeElement;return {control:n.dataset.modelControl,visible:n.matches(':focus-visible'),outline:getComputedStyle(n).outline};})()`)});
  await mode('hold');
  await mouse('[data-model-control="refresh"]');
  await wait('current.loading');
  await new Promise(resolve=>setTimeout(resolve,5200));
  await mode('release'); await wait('!current.loading');
  const unchanged = await capture('unchanged-price-after-5s');
  assert.equal(requests.filter(r=>r.route==='/api/models/benchmark/refresh').length,0,'price refresh never forces Harbor');
  if (!baseline) {
    assert.equal(unchanged.detached,0,'price publication must never detach benchmark');
    assert.equal(unchanged.benchmarkRows,true,'unchanged benchmark row identities');
    assert.equal(unchanged.priceRows,true,'same price data preserves rows');
    assert.equal(unchanged.outline.includes('none') || unchanged.outline.includes('0px'),true,'no pointer focus halo');
  }
  await mode('changed');
  await mouse('[data-model-control="refresh"]'); await wait('!current.loading');
  const changed = await capture('changed-price');
  if (!baseline) { assert.equal(changed.detached,0); assert.equal(changed.benchmarkRows,true); }
  // Real protected endpoint, not a fake View update: status and a new observation
  // with equal rows must not destroy either table.
  await read(`window.probePrice=document.querySelector('.overview-model-table');window.probeToolbar=document.querySelector('.model-price-controls');
    window.probePriceRows=[...probePrice.tBodies[0].rows];window.probeRows=[...current.benchmark.body.rows];`);
  await mouse('[data-benchmark-control="refresh"]');
  await wait('!current.benchmark.manual && !current.benchmark.data.refreshing && !current.benchmark.loading');
  const benchmark = await capture('benchmark-status-and-unchanged-data');
  if (!baseline) {
    assert.equal(benchmark.benchmarkRows,true,'status/date-only benchmark preserves rows');
    assert.equal(await read(`probePrice===document.querySelector('.overview-model-table')&&probeToolbar===document.querySelector('.model-price-controls')`),true);
  }
  await read('probeObserver.disconnect()');
  if (!baseline) {
    await fixture('benchmark-changed');
    await mouse('[data-benchmark-control="refresh"]');
    await wait('!current.benchmark.manual && !current.benchmark.loading');
    assert.equal(await read(`probePrice===document.querySelector('.overview-model-table')&&probeToolbar===document.querySelector('.model-price-controls')`),true);
    assert.equal(await read(`probeRows.filter(n=>[...current.benchmark.body.rows].includes(n)).length`),3,'only the changed benchmark record is replaced');
    for (const priceFails of [false,true]) {
      await fixture('benchmark-hold');await mode('hold');
      await mode(priceFails?'offline':'changed');
      await fixture(priceFails?'benchmark-online':'benchmark-offline');
      await read(`window.probePriceRows=[...document.querySelector('.overview-model-table').tBodies[0].rows];window.probeRows=[...current.benchmark.body.rows];`);
      await mouse('[data-model-control="refresh"]');
      await wait('current.loading');
      assert.equal(await read('current.benchmark.refresh.disabled'),false,'price does not disable benchmark');
      await mouse('[data-benchmark-control="refresh"]');
      await wait('current.benchmark.manual');
      await mode('release');await fixture('benchmark-release');
      await wait('!current.loading && !current.benchmark.manual && !current.benchmark.loading');
      assert.equal(await read(`probePriceRows.every((n,i)=>n===document.querySelector('.overview-model-table').tBodies[0].rows[i])&&probeRows.every((n,i)=>n===current.benchmark.body.rows[i])`),true);
      assert.equal(await read(`document.querySelector('.model-price-controls [role="status"]').textContent.includes('failed')`),priceFails);
      assert.equal(await read(`current.benchmark.status.textContent.includes('failed')`),!priceFails);
      assert.equal(await read(`document.getElementById('notice').textContent===''`),true,'source failures stay local');
      observations.push({label:priceFails?'price-fail-harbor-success':'price-success-harbor-fail',...await fixture('models-status'),benchmark:await fixture('benchmark-status')});
    }
    await mode('changed');await fixture('benchmark-online');
    for (const [selector, predecessor, pending] of [
      ['[data-model-control="refresh"]','.model-section-heading a','current.loading'],
      ['[data-benchmark-control="refresh"]','.benchmark-section .model-section-heading a','current.benchmark.manual']
    ]) {
      for (const activation of [['Enter','Enter',13],[' ','Space',32]]) {
        await read(`document.querySelector(${JSON.stringify(predecessor)}).focus()`);
        await key('Tab','Tab',9);
        assert.equal(await read(`document.activeElement===document.querySelector(${JSON.stringify(selector)})`),true);
        await key(...activation);
        await wait(`!${pending}`);
        const focus=await read(`(()=>{const n=document.querySelector(${JSON.stringify(selector)});return {
          focused:document.activeElement===n,outline:getComputedStyle(n).outlineStyle,active:n.matches(':active')};})()`);
        assert.deepEqual(focus,{focused:true,outline:'solid',active:false},'keyboard-only refresh restores accessible focus');
        observations.push({label:'keyboard-refresh',selector,key:activation[0],...focus});
      }
      await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
      const point=await read(`(()=>{const n=document.querySelector(${JSON.stringify(selector)});n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
      await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]},id);
      await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
      await wait(`!${pending}`);
      assert.equal(await read(`getComputedStyle(document.querySelector(${JSON.stringify(selector)})).outlineStyle`),'none');
      await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
    }
    await read(`window.probePriceRows=[...document.querySelector('.overview-model-table').tBodies[0].rows];window.probeRows=[...current.benchmark.body.rows];
      const n=current.benchmark.body.rows[0].cells[1].firstChild;const range=document.createRange();range.selectNodeContents(n);
      getSelection().removeAllRanges();getSelection().addRange(range);window.probeSelection=getSelection().toString();
      current.benchmark.picker.open=true;window.probeModelState=current;location.hash='#/watch';`);
    await wait(`current.section==='watch'`);
    await read(`location.hash='#/models'`);
    await wait(`current===probeModelState&&!current.loading`);
    assert.equal(await read(`probeRows.every((n,i)=>n===current.benchmark.body.rows[i])&&probePriceRows.every((n,i)=>n===document.querySelector('.overview-model-table').tBodies[0].rows[i])`),true);
    // Real health/SSE lookups and same-result redisplay must not rebuild rows.
    await read(`liveConnection.resync();show(current)`);
    await wait('!current.loading');
    assert.equal(await read(`probeRows.every((n,i)=>n===current.benchmark.body.rows[i])`),true);
    checks.push('one changed Harbor record preserves other rows; independently enabled concurrent requests, reciprocal source-local failures, route return and real health resync retain both tables');
  }
  checks.push('native price refresh >5s, unchanged/changed canonical prices, benchmark status/date-only refresh and sibling DOM identity');
  return {observations,checks,requests};
}
module.exports = {probeIsolation};
