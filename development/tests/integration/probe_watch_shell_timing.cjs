// Real browser DOM over a synthetic, source-qualified Live DTO.
const assert = require('node:assert/strict');
const dates = require('./web_date_time.cjs');

module.exports = async (evaluate, command, session) => {
  const browserCases = [['sv-SE', 'Asia/Tokyo'], ['en-US', 'America/New_York']];
  for (const [locale, timezoneId] of browserCases) {
    await command('Emulation.setLocaleOverride', {locale}, session);
    await command('Emulation.setTimezoneOverride', {timezoneId}, session);
    dates.verify(await evaluate(`(() => {const vectors = ${JSON.stringify(dates.vectors)}; return ${dates.expression};})()`));
  }
  const probe = await evaluate(`(() => {
    const view = INPUT.view, card = view.active_cards.find(value => value.session_id === 'root');
    const row = card.rows[0], tool = row.tool;
    const render = () => ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const start = Date.parse('2026-03-29T00:45:20.123Z');
    tool.running_invocations = [{...tool.running_invocation, kind:'shell', mode:'foreground',
      text:'command:\\npy -3 evaluate.py --fixture isolated\\n\\nworkdir:\\nC:/fixture',
      qualification:'Sensitive argument/value redacted.', started_at_ms:start,
      shell_timing:{anchor:'execution', timeout_ms:3220000, estimated_duration_ms:1200000, sample_count:2}}];
    view.now_ms = start + 60000;
    view.timezone_id = 'Europe/Stockholm';
    render();
    const rendered = [...state.watch.cards.values()].find(value => value.value.session_id === 'root');
    const root = rendered.runningDetail, job = [...root.jobs.values()][0];
    const collapsed = !root.node.open;
    root.node.open = true; job.node.open = true;
    root.summary.focus({preventScroll:true});
    job.input.scrollIntoView({block:'nearest'});
    const input = job.input.firstChild, selection = getSelection();
    selection.setBaseAndExtent(input, 0, input, 14);
    const focus = document.activeElement, selected = selection.toString(), y = scrollY;
    const timing = job.timing.node;
    const values = () => Object.fromEntries(job.timing.rows.filter(([label]) => !label.hidden)
      .map(([label, value]) => [label.textContent, value.textContent]));
    const initial = values();
    view.now_ms += 1000; render();
    const tick = values();
    const stable = timing === job.timing.node && root.node.open && job.node.open &&
      input === job.input.firstChild && focus === document.activeElement && selection.toString() === selected && y === scrollY;
    const overflow = document.documentElement.scrollWidth > innerWidth;
    const commandNote = job.note.textContent;
    view.timezone_id = 'America/New_York'; render();
    const changedZone = values();
    view.now_ms = start - 5000; render();
    const clockSkew = values();
    view.now_ms = start + 1200000; render();
    const pastEstimate = values();
    view.now_ms = start + 3220000; render();
    const pastDeadline = values();
    view.now_ms = start + 60000;
    Object.assign(tool.running_invocations[0].shell_timing, {estimated_duration_ms:null, sample_count:1});
    render(); const oneSample = values();
    job.node.open = false; render();
    const manualCollapse = !job.node.open;
    const linked = tool.running_invocations, legacy = tool.running_invocation;
    tool.running_invocations = []; tool.running_invocation = null; render();
    const withheld = root.node.open && !timing.isConnected && !timing.textContent.includes('2026-') && !job.input.textContent
      && /no source-qualified call details/i.test(root.note.innerText) && !root.note.querySelector('.metric-spinner');
    tool.running_invocations = linked; tool.running_invocation = legacy; render();
    const recovered = root.node.open && !job.node.open && job.timing.node.isConnected;
    const lastNode = job.timing.node;
    row.prompt.in_progress = false; render();
    const cleared = !lastNode.isConnected && !lastNode.textContent.includes('2026-') && !job.input.textContent &&
      !rendered.root.isConnected && root.jobs.size === 0;
    selection.removeAllRanges();
    row.prompt.in_progress = true; render();
    const revived = [...state.watch.cards.values()].find(value => value.value.session_id === 'root').runningDetail;
    revived.node.open = true; [...revived.jobs.values()][0].node.open = true;
    return {initial,tick,collapsed,stable,overflow,commandNote,changedZone,clockSkew,pastEstimate,pastDeadline,oneSample,
      manualCollapse,withheld,recovered,cleared};
  })()`);

  assert.equal(probe.initial.Started, '2026-03-29 01:45:20 (native execution start)');
  assert.equal(probe.initial['Timeout deadline'], '2026-03-29 03:39:00');
  assert.equal(probe.initial['Estimated finish'], '~2026-03-29 03:05:20 (Low confidence · 2 similar completed runs)');
  assert.equal(probe.initial.Elapsed, '1m');
  assert.equal(probe.initial.Timeout, '3,220,000 ms (53m 40s)');
  assert.equal(probe.initial['Time to timeout'], '52m 40s');
  assert.equal(probe.initial.Progress, undefined);
  assert.equal(probe.tick.Elapsed, '1m 1s');
  assert.equal(probe.tick['Time to timeout'], '52m 39s');
  assert.equal(probe.tick['Estimated finish'], probe.initial['Estimated finish']);
  assert.equal(probe.changedZone.Started, '2026-03-28 20:45:20 (native execution start)');
  assert.equal(probe.changedZone['Time to timeout'], '52m 39s');
  assert.match(probe.clockSkew.Elapsed, /ahead of the Watch clock/);
  for (const frame of [probe.clockSkew, probe.pastEstimate, probe.oneSample])
    assert.equal(frame['Estimated finish'], undefined);
  assert.equal(probe.oneSample.Timeout, probe.initial.Timeout);
  assert.equal(probe.pastDeadline['Time to timeout'], 'Deadline passed; still running');
  assert.equal(probe.commandNote, 'Sensitive argument/value redacted.');
  for (const check of ['stable', 'collapsed', 'manualCollapse', 'withheld', 'recovered', 'cleared'])
    assert.equal(probe[check], true, check);
  assert.equal(probe.overflow, false);
  const {nodes} = await command('Accessibility.getFullAXTree', {}, session);
  assert.ok(nodes.some(node => node.role?.value === 'DisclosureTriangle'), 'native disclosure is exposed to AX');
  assert.ok(nodes.some(node => node.name?.value === 'Timeout deadline'), 'open timing terms are exposed to AX');
  return {dst: true, browserCases, localZoneChange: true, durationTick: true,
    privacyLifecycle: true, accessibleDisclosure: true};
};
