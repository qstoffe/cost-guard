// Real browser DOM over a synthetic, source-qualified Live DTO.
const assert = require('node:assert/strict');

module.exports = async (evaluate, command, session) => {
  const probe = await evaluate(`(() => {
    const view = INPUT.view, card = view.active_cards.find(value => value.session_id === 'root');
    const row = card.rows[0], tool = row.tool;
    const render = () => ReportView.renderLive(document.getElementById('result'), INPUT, state);
    const start = Date.parse('2026-03-29T00:45:20Z');
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
    job.node.open = false; render();
    const manualCollapse = !job.node.open;
    tool.detail_state = 'pending'; render();
    const withheld = root.node.open && !timing.isConnected && !timing.textContent.includes('GMT') && !job.input.textContent;
    tool.detail_state = 'observed'; render();
    const recovered = root.node.open && !job.node.open && job.timing.node.isConnected;
    const lastNode = job.timing.node;
    row.prompt.in_progress = false; render();
    const cleared = !lastNode.isConnected && !lastNode.textContent.includes('GMT') && !job.input.textContent &&
      !rendered.root.isConnected && root.jobs.size === 0;
    selection.removeAllRanges();
    row.prompt.in_progress = true; render();
    const revived = [...state.watch.cards.values()].find(value => value.value.session_id === 'root').runningDetail;
    revived.node.open = true; [...revived.jobs.values()][0].node.open = true;
    return {initial,tick,collapsed,stable,overflow,commandNote,changedZone,clockSkew,pastEstimate,pastDeadline,
      manualCollapse,withheld,recovered,cleared};
  })()`);

  assert.match(probe.initial.Started, /2026-03-29 01:45:20.*[+]1.*native execution start/);
  assert.match(probe.initial['Timeout deadline'], /2026-03-29 03:39:00.*[+]2/);
  assert.match(probe.initial['Estimated finish'], /03:05.*Low confidence.*2 similar completed runs/);
  assert.equal(probe.initial.Elapsed, '1m');
  assert.equal(probe.initial.Timeout, '3,220,000 ms (53m 40s)');
  assert.equal(probe.initial['Time to timeout'], '52m 40s');
  assert.equal(probe.initial.Progress, 'Unknown (no structured phase evidence)');
  assert.equal(probe.tick.Elapsed, '1m 1s');
  assert.equal(probe.tick['Time to timeout'], '52m 39s');
  assert.equal(probe.tick['Estimated finish'], probe.initial['Estimated finish']);
  assert.match(probe.changedZone.Started, /2026-03-28 20:45:20/);
  assert.equal(probe.changedZone['Time to timeout'], '52m 39s');
  assert.match(probe.clockSkew.Elapsed, /ahead of the Watch clock/);
  assert.match(probe.clockSkew['Estimated finish'], /Unavailable/);
  assert.match(probe.pastEstimate['Estimated finish'], /past the historical typical duration/);
  assert.equal(probe.pastDeadline['Time to timeout'], 'Deadline passed; still running');
  assert.equal(probe.commandNote, 'Sensitive argument/value redacted.');
  for (const check of ['stable', 'collapsed', 'manualCollapse', 'withheld', 'recovered', 'cleared'])
    assert.equal(probe[check], true, check);
  assert.equal(probe.overflow, false);
  const {nodes} = await command('Accessibility.getFullAXTree', {}, session);
  assert.ok(nodes.some(node => node.role?.value === 'DisclosureTriangle'), 'native disclosure is exposed to AX');
  assert.ok(nodes.some(node => node.name?.value === 'Timeout deadline'), 'open timing terms are exposed to AX');
  return {dst: true, localZoneChange: true, durationTick: true, privacyLifecycle: true, accessibleDisclosure: true};
};
