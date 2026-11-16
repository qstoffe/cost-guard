// Shipped app/HTTP/history with synthetic source facts; no installed history or UI.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command, newTab}) => {
  const checks = [];
  const catalog = (period, offset = 0) => until(`current?.catalog?.data?.period===${JSON.stringify(period)} &&
    current.catalog.data.offset===${offset} && !current.catalog.busy && !current.catalog.operation`);
  const detail = () => until('!!current?.detail?.data && !current.detail.busy');
  const backLink = () => evaluate('current.detail.back.getAttribute("href")');
  await fixture('period-source');
  await evaluate(`window.returnRequests=[];window.returnFetch=fetch;
    window.fetch=(url,options)=>{if(url==='/api/sessions' && options?.body){
      const value=JSON.parse(options.body);if(!value.action)returnRequests.push(value);}
      return returnFetch(url,options);};location.hash='#/sessions'`);
  await catalog('today');
  // Actual period/sort/page controls and anchors, including a keyboard activation.
  for (const [period, total, sort, direction, offset] of [
    ['today',30,'activity',-1,0], ['30-days',120,'activity',-1,0],
    ['all',5000,'name',1,0], ['month',70,'name',-1,0], ['7-days',70,'name',-1,25]
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
      await evaluate(`current.catalog.body.querySelector('a.session-name').focus()`);
      await command('Input.dispatchKeyEvent', {type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'});
      await command('Input.dispatchKeyEvent', {type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    } else await evaluate(`current.catalog.body.querySelector('a.session-name span:last-child').click()`);
    await detail();
    assert.equal(await evaluate('location.hash'), sessionHash);
    assert.equal(await evaluate('history.length'), previousLength + 1, 'one entry, no unexpected history jumps');
    assert.equal(await backLink(), expected);
    assert.deepEqual(await evaluate('history.state'), {sessionsReturn:{detail:sessionHash,list:expected}});
    if (offset) {
      await evaluate('history.back()'); await catalog(period, offset);
      assert.equal(await evaluate('location.hash'), listHash, 'native Back retains the pinned original page');
      await evaluate('history.forward()'); await detail();
      assert.equal(await backLink(), expected);
      await command('Page.reload');
      await until('typeof csrf !== "undefined" && csrf && hostState.writable');
      await detail();
      assert.equal(await backLink(), expected, 'reload retains only this entry origin');
      assert.equal(await newTab(sessionHash), '#/sessions', 'same URL in a new tab has no list origin');
    }
    await evaluate('window.returnRequests.length=0;current.detail.back.click()');
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
  await command('Page.reload');
  await until('typeof csrf !== "undefined" && csrf && hostState.writable');
  await detail();
  assert.equal(await backLink(), '#/sessions', 'direct entry reload cannot invent origin');
  await evaluate('current.detail.back.click()');
  await catalog('today');
  await evaluate(`current.catalog.periodButtons.find(item=>item.key==='30-days').button.click()`);
  await catalog('30-days');
  checks.push('native Back/Forward, reload, new-tab URL, reused detail from Watch/direct navigation and subsequent period changes');
  return checks;
};
