const assert = require('node:assert/strict');

// Session Detail via its real route, qualified synthetic detail + Live publications.
module.exports = async ({evaluate, until, fixture}) => {
  await fixture('date-shell-open');
  const started = '2026-03-29 01:45:20 (native execution start)';
  await until('current.detail.invocations.running.jobs.size === 1');
  await evaluate(`window.shellDetail = current.detail.invocations.running;
    shellDetail.summary.click();
    window.shellJob = [...shellDetail.jobs.values()][0];
    shellJob.input.scrollIntoView({block:'nearest'});
    shellDetail.summary.focus({preventScroll:true});
    window.shellInput = shellJob.input.firstChild;
    getSelection().setBaseAndExtent(shellInput, 0, shellInput, 7);
    window.shellY = scrollY;
    window.shellFocus = document.activeElement;
    window.shellRows = () => Object.fromEntries(shellJob.timing.rows
      .filter(([term]) => !term.hidden).map(([term, value]) => [term.textContent, value.textContent]));`);
  const initial = await evaluate('shellRows()');
  assert.equal(initial.Started, started);
  assert.equal(initial['Estimated finish'], '~2026-03-29 03:05:20 (Low confidence · 2 similar completed runs)');
  assert.equal(initial['Timeout deadline'], '2026-03-29 03:39:00');
  assert.equal(initial.Elapsed, '1m');
  assert.equal(initial['Time to timeout'], '52m 40s');
  assert.equal(await evaluate('shellJob.note.textContent'), 'Sensitive argument/value redacted.');
  await fixture('date-shell-tick');
  await until(`shellRows().Elapsed === '1m 1s'`);
  assert.deepEqual(await evaluate(`({parent:shellDetail.node.open, child:shellJob.node.open,
    focus:document.activeElement === shellFocus, node:shellJob.input.firstChild === shellInput,
    selection:getSelection().toString(), scroll:scrollY === shellY})`),
    {parent:true, child:true, focus:true, node:true, selection:'command', scroll:true});
  await fixture('date-shell-zone');
  await until(`shellRows().Started === '2026-03-28 20:45:20 (native execution start)'`);
  assert.equal((await evaluate('shellRows()'))['Time to timeout'], '52m 38s');
  await evaluate('shellDetail.summary.click()');
  assert.equal(await evaluate('shellDetail.node.open'), false);
  await evaluate('shellDetail.summary.click()');
  assert.equal(await evaluate('shellDetail.node.open && shellJob.node.open'), true);
  await fixture('date-shell-clear');
  await until('current.detail.invocations.root.hidden');
  assert.equal(await evaluate('shellDetail.jobs.size === 0 && !shellJob.input.textContent'), true);
  return ['Session Detail qualified Shell start/ETA/deadline to seconds, source zone shift, live elapsed countdown, stable focus/selection/scroll, close/reopen and cleared inputs'];
};
