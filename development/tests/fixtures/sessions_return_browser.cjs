// Shipped app/HTTP/history with synthetic source facts; no installed history or UI.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command, newTab}) => {
  const checks = [];
  const catalog = (period, offset = 0) => until(`current?.catalog?.data?.period===${JSON.stringify(period)} &&
    current.catalog.data.offset===${offset} && !current.catalog.busy && !current.catalog.operation`);
  const detail = () => until('!!current?.detail?.data && !current.detail.busy');
  const reloadDetail = async () => {
    await evaluate('window.returnBeforeReload=true');
    await command('Page.reload');
    // Wait for this document's replacement, not the independent SSE writable state.
    await until('window.returnBeforeReload!==true && typeof csrf!=="undefined" && !!csrf && typeof current!=="undefined" && !!current?.detail?.data && !current.detail.busy');
  };
  const backLink = () => evaluate('current.detail.back.getAttribute("href")');
  const recordRequests = `window.returnRequests=[];window.returnFetch=fetch;
    window.fetch=(url,options)=>{if(url==='/api/sessions' && options?.body){
      const value=JSON.parse(options.body);if(!value.action)returnRequests.push(value);}
      return returnFetch(url,options);};`;
  await fixture('period-source');
  await evaluate(recordRequests + `location.hash='#/sessions'`);
  await catalog('today');
  // Seed scalar keys using the existing fixture command. This is navigation
  // evidence, not a 5,000-root cold-index throughput benchmark.
  await fixture('catalog-index');
  // Actual period/sort/page controls and anchors; retain existing keyboard help.
  for (const [period, total, sort, direction, offset] of [
    ['today',30,'activity',-1,0], ['30-days',120,'activity',-1,25],
    ['all',5000,'name',1,25], ['month',70,'name',-1,0], ['7-days',70,'name',-1,25]
  ]) {
    await evaluate(`current.catalog.periodButtons.find(item=>item.key===${JSON.stringify(period)}).button.click()`);
    await catalog(period);
    await evaluate(`if(current.catalog.sort!==${JSON.stringify(sort)} || current.catalog.direction!==${direction})
      current.catalog.headers.find(item=>item.key===${JSON.stringify(sort)}).th.querySelector('button').click()`);
    await until(`current.catalog.data.sort===${JSON.stringify(sort)} && current.catalog.data.direction===${direction} &&
      !current.catalog.operation && !current.catalog.busy`);
    if (offset) {
      await evaluate('current.catalog.next.click()');
      await catalog(period, offset);
    }
    const listHash = await evaluate('location.hash');
    const expected = `#/sessions?period=${period}&sort=${sort}&direction=${direction}`;
    const previousLength = await evaluate('history.length');
    const sessionHash = await evaluate(`current.catalog.body.querySelector('a.session-name').getAttribute('href')`);
    if (period === 'all') {
      await command('Emulation.setFocusEmulationEnabled', {enabled:true});
      await evaluate(`current.catalog.body.querySelector('a.session-name').focus();
        window.returnClick=null;document.addEventListener('click',event=>{
          returnClick={button:event.button,prevented:event.defaultPrevented,target:event.target.tagName};
        },{once:true,capture:true})`);
      assert.equal(await evaluate(`document.activeElement.matches('a.session-name')`), true);
      await command('Input.dispatchKeyEvent', {type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
      await command('Input.dispatchKeyEvent', {type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
      assert.equal(await evaluate('location.hash'), listHash, 'Enter retains the existing title-help action');
      assert.equal(await evaluate(`document.activeElement.matches('a.session-name')`), true);
      assert.equal(await evaluate('window.returnClick'), null, 'help must not dispatch an unintended navigation');
      await evaluate(`current.catalog.body.querySelector('a.session-name').click()`);
    } else await evaluate(`current.catalog.body.querySelector('a.session-name span:last-child').click()`);
    await detail();
    assert.equal(await evaluate('location.hash'), sessionHash);
    assert.equal(await evaluate('history.length'), previousLength + 1, 'one entry, no unexpected history jumps');
    assert.equal(await backLink(), expected);
    assert.deepEqual(await evaluate(`({
      text:current.detail.back.textContent,
      tag:current.detail.back.tagName,
      tabIndex:current.detail.back.tabIndex,
      nested:current.detail.back.querySelectorAll('a,button,input,[tabindex]').length,
      title:current.detail.back.getAttribute('title')
    })`), {text:'↩ Back to Show All Sessions',tag:'A',tabIndex:0,nested:0,title:null});
    const accessibility = await command('Accessibility.getFullAXTree');
    assert.equal(accessibility.nodes.filter(node=>!node.ignored && node.role?.value==='link' &&
      node.name?.value==='Back to Show All Sessions').length, 1, 'one native link with no spoken arrow');
    assert.deepEqual(await evaluate('history.state'), {sessionsReturn:{detail:sessionHash,list:expected}});
    if (offset) {
      await evaluate('history.back()'); await catalog(period, offset);
      assert.equal(await evaluate('location.hash'), listHash, 'native Back retains the pinned original page');
      await evaluate('history.forward()'); await detail();
      assert.equal(await backLink(), expected);
      await reloadDetail();
      await evaluate(recordRequests);
      assert.equal(await backLink(), expected, 'reload retains only this entry origin');
      assert.equal(await newTab(sessionHash), '#/sessions', 'same URL in a new tab has no list origin');
    }
    await evaluate('window.returnRequests.length=0;current.detail.back.focus();current.detail.back.scrollIntoView()');
    if (period === '30-days') {
      await command('Input.dispatchKeyEvent', {type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
      await command('Input.dispatchKeyEvent', {type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
      await command('Input.dispatchKeyEvent', {type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9,modifiers:8});
      await command('Input.dispatchKeyEvent', {type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9,modifiers:8});
      assert.equal(await evaluate('document.activeElement===current.detail.back'), true);
      assert.equal(await evaluate('current.detail.back.matches(":focus-visible")'), true);
      await command('Input.dispatchKeyEvent', {type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
      await command('Input.dispatchKeyEvent', {type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    } else {
      const point = await evaluate(`(()=>{const r=current.detail.back.getBoundingClientRect();
        return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
      if (period === 'all') {
        await command('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[point]});
        await command('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]});
      } else {
        await command('Input.dispatchMouseEvent', {type:'mousePressed',button:'left',clickCount:1,...point});
        await command('Input.dispatchMouseEvent', {type:'mouseReleased',button:'left',clickCount:1,...point});
      }
    }
    await catalog(period);
    assert.equal(await evaluate('location.hash'), expected);
    assert.equal(await evaluate('current.catalog.data.total'), total);
    assert.match(await evaluate('current.catalog.label.textContent'), /Page 1 of/);
    assert.equal(await evaluate(`returnRequests.some(request=>request.offset===0 && request.epoch===null &&
      request.period===${JSON.stringify(period)} && request.sort===${JSON.stringify(sort)} &&
      request.direction===${direction})`), true, 'fresh page-one admission without the frozen epoch');
    assert.equal(await evaluate('current.catalog.status.hidden'), true, 'no unsolicited warning');
    checks.push(`${period}: ${sort}/${direction}, origin page ${offset / 25 + 1} → page 1, ${total} matching sessions`);
  }
  // A cached detail previously opened from a list must not retain that origin.
  const known = await evaluate(`current.catalog.body.querySelector('a.session-name').getAttribute('href')`);
  await evaluate(`location.hash='#/watch'`);
  await until('current?.section==="watch"');
  await evaluate(`location.hash=${JSON.stringify(known)}`);
  await detail();
  assert.equal(await backLink(), '#/sessions');
  await reloadDetail();
  assert.equal(await backLink(), '#/sessions', 'direct entry reload cannot invent origin');
  await evaluate('current.detail.back.click()');
  await catalog('today');
  await evaluate(`current.catalog.periodButtons.find(item=>item.key==='30-days').button.click()`);
  await catalog('30-days');
  checks.push('native Back/Forward, reload, new-tab URL, reused detail from Watch/direct navigation and subsequent period changes');
  checks.push('curved-arrow visible label, exact arrow-free accessibility name, one native tab stop, keyboard focus, Enter/pointer/touch return');
  return checks;
};
