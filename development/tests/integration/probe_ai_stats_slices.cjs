// Actual production ReportJobs/processes, canonical fixed history and disposable cache.
module.exports = async ({command, evaluate, until, config, checks}) => {
  const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
  const {spawn} = require('node:child_process'), readline = require('node:readline');
  const root = path.join(config, 'slices'); await fs.mkdir(root);
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', root, '--stats-slices'],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  let errors = ''; server.stderr.on('data', value => { errors += value; });
  const targets = [];
  const open = async url => {
    const {targetId} = await command('Target.createTarget', {url:'about:blank'}); targets.push(targetId);
    const tab = (await command('Target.attachToTarget', {targetId, flatten:true})).sessionId;
    await command('Runtime.enable', {}, tab); await command('Page.enable', {}, tab);
    await command('Page.navigate', {url}, tab);
    await command('Page.bringToFront', {}, tab);
    await until(`typeof csrf!=='undefined' && csrf && hostState.writable`, tab);
    return tab;
  };
  try {
    const launch = JSON.parse((await lines.next()).value);
    const tab = await open(launch.url);
    // The fixture's finite non-Stats page isn't part of this check.
    await evaluate(`location.hash='#/ai-stats'`, tab);
    await until(`current.section==='ai-stats' && current.loading && current.active &&
      current.percent>30 && !current.result`, tab);
    const initial = await evaluate(`({id:current.active,percent:current.percent})`, tab);
    const peer = await open(launch.url.split('#')[0] + '#/ai-stats');
    await until(`current?.section==='ai-stats' && current.loading && !!current.active`, peer);
    assert.equal(await evaluate(`current.active`, peer), initial.id);
    await command('Page.bringToFront', {}, tab);
    await evaluate(`document.querySelectorAll('.ai-stats-periods button')[1].focus(); selectStats(current,'7-days')`, tab);
    assert.equal(await evaluate(`current.period==='7-days' && current.loading`, tab), true);
    await until(`!current.loading && current.result?.view.ai_stats.some(r=>r.period==='7-days')`, tab);
    const narrow = await evaluate(`({id:current.active, work:current.result.view.ai_stats_work,
      focused:document.activeElement.textContent, period:current.period})`, tab);
    assert.ok(narrow.work.remaining > 0, 'narrow coherent result must precede wider missing work');
    assert.equal(narrow.work.scopes['7-days'].ready, true);
    assert.equal(narrow.work.scopes['30-days'].ready, false);
    assert.equal(narrow.focused, '7 days');
    await evaluate(`selectStats(current,'today'); selectStats(current,'30-days')`, tab);
    await until(`current.loading && !!current.active`, tab);
    await until(`!current.loading && current.result?.view.ai_stats.some(r=>r.period==='30-days')`, tab);
    assert.equal(await evaluate(`current.period`, tab), '30-days');
    await command('Page.bringToFront', {}, peer);
    await until(`!current.loading && current.result?.view.ai_stats.some(r=>r.period==='30-days')`, peer);
    server.stdin.write('{"command":"stats-slices-status"}\n');
    const status = JSON.parse((await lines.next()).value);
    assert.equal(status.active, false);
    assert.equal(status.loads.reduce((sum, row) => sum + row.hydrated, 0), 24,
      'return to broad coverage must reuse every stable root, not restart');
    assert.ok(status.work.some(job => job.kind === 'ai-stats' && job.scope === '7-days' && job.status === 'complete'),
      'latest selection must own logical completion; already coherent evidence needs no extra child');
    assert.ok(status.loads.length > 2);
    assert.equal(errors, '');
    checks.push(`production slices/two tabs: 7 days coherent at ${narrow.work.completed}/24 roots; ` +
      `30 days resumes, ${status.loads.length} finite children, exactly 24 total hydrations, no active child`);
  } catch (error) {
    server.stdin.write('{"command":"stats-slices-status"}\n');
    const status = (await lines.next()).value;
    throw new Error(error.message + ' production fixture: ' + status + ' ' + errors);
  } finally {
    for (const targetId of targets) await command('Target.closeTarget', {targetId}).catch(()=>{});
    server.stdin.write('{"command":"stop"}\n');
    await new Promise(resolve=>server.once('exit',resolve));
  }
};
