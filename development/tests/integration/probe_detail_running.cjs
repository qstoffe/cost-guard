const assert = require('node:assert/strict');

// Open the shipped Detail route with a qualified synthetic call. Replay the
// otherwise racy Live/Detail arrival order against that same attached view.
module.exports = async ({evaluate, until, fixture}) => {
  await fixture('date-shell-open');
  await evaluate(`location.hash = '#/sessions/root-0000'`);
  await until(`current.detail?.data?.activity && !current.detail.busy &&
    current.detail.invocations.root.textContent.includes('python fixture_task.py')`);
  const facts = await evaluate(`(async () => {
    const detail = current.detail, {running, background, root} = detail.invocations;
    await detail.pendingLoad;
    const original = liveValue, health = {...hostState}, api = detail.api, history = structuredClone(detail.data);
    const live = structuredClone(original), card = live.view.active_cards.find(c => c.session_id === detail.id);
    const tool = card.rows.find(r => r.prompt.event_id === card.focal_id).tool;
    const first = tool.running_invocations[0];
    const second = {...first, identity:'call-two', text:'command: second fixture'};
    const worker = {...first, identity:'worker', text:'command: background fixture'};
    const publish = () => { liveValue = live; detail.updateInvocations(); };
    const begin = async reply => {
      let reads = 0;
      detail.api = async (url, request) => {
        if (url !== '/api/detail' || request.action !== 'begin') throw Error('unexpected Detail request');
        reads++;
        return reply;
      };
      await detail.load(false);
      if (reads !== 1) throw Error('expected one begin, saw ' + reads);
      detail.api = api;
    };
    try {
      tool.running_invocations = [first, second]; tool.running_invocation_count = 2;
      tool.background_invocations = [worker]; tool.background_invocation_count = 1; tool.background_kinds = ['shell'];
      publish(); running.node.open = background.node.open = true;
      const calls = [...root.querySelectorAll('details details')];
      const present = () => calls.map(node => node.isConnected && node.checkVisibility());
      const inputs = () => calls.map(node => node.querySelector('pre').textContent);
      const facts = {initial:inputs()};
      // A fresh begin with the same report revision can lack the activity
      // projection. It must be consumed even when the history table is reused.
      await begin({...history, activity:null});
      facts.historyGap = {present:present(), inputs:inputs(), loading:detail.loader.root.checkVisibility()};
      await begin(history);
      facts.recovered = inputs();
      const healthyTool = structuredClone(tool);
      tool.running_invocations = [second]; publish();
      facts.partialList = {present:present(), inputs:inputs()};
      Object.assign(tool, healthyTool);
      tool.detail_state = 'pending'; publish();
      facts.pending = {present:present(), inputs:inputs(), spinner:!!root.querySelector('.metric-spinner')};
      Object.assign(tool, healthyTool); publish();
      connectionStatus('', {...health, kind:'source_unavailable', sourceOutage:false});
      facts.unconfirmedOutage = {present:present(), inputs:inputs()};
      connectionStatus('', health); publish();
      tool.running_invocations = [second]; tool.running_invocation_count = 1; publish();
      facts.foregroundFinished = present();
      tool.background_kinds = []; tool.background_invocations = []; tool.background_invocation_count = 0; publish();
      facts.backgroundFinished = present();
      const scope = card.activity_scope;
      card.activity_scope = 'other-source'; publish();
      facts.conflict = !root.checkVisibility() && !calls.some(node => node.textContent.includes('fixture'));
      card.activity_scope = scope; publish();
      facts.unbound = !root.checkVisibility();
      await begin(history);
      facts.rebound = root.textContent.includes(second.text);
      connectionStatus('', {...health, kind:'source_unavailable', sourceOutage:true});
      facts.confirmedOutage = !root.checkVisibility() && !root.textContent.includes(second.text);
      connectionStatus('', health); publish();
      await begin(history);
      facts.afterOutage = root.textContent.includes(second.text);
      await begin({state:'loading', live_activity:{scope:history.activity.scope, running:[],
        ended:[card.focal_id], observed_at_ms:Math.max(history.live_activity?.observed_at_ms || 0, card.observed_at_ms || 0) + 1}});
      publish();
      facts.ended = !root.checkVisibility() && !root.textContent.includes(second.text);
      return facts;
    } finally { detail.api = api; liveValue = original; connectionStatus('', health); }
  })()`);
  const all = [true, true, true], withheld = ['', '', ''];
  assert.deepEqual(facts.initial, ['command:\npython fixture_task.py', 'command: second fixture', 'command: background fixture']);
  assert.deepEqual(facts.historyGap, {present:all, inputs:withheld, loading:false}, 'history gap');
  assert.deepEqual(facts.recovered, facts.initial, 'qualification restores the same nodes');
  assert.deepEqual(facts.partialList, {present:all, inputs:['', ...facts.initial.slice(1)]}, 'count still supports both calls');
  assert.deepEqual(facts.pending, {present:all, inputs:withheld, spinner:false}, 'partial Live update');
  assert.deepEqual(facts.unconfirmedOutage, {present:all, inputs:withheld}, 'health label without confirmed outage');
  assert.deepEqual(facts.foregroundFinished, [false, true, true], 'one foreground call ended');
  assert.deepEqual(facts.backgroundFinished, [false, true, false], 'background ended independently');
  assert.ok(facts.conflict && facts.unbound && facts.rebound, 'another source retires the binding until fresh Detail');
  assert.ok(facts.confirmedOutage && facts.afterOutage, 'confirmed outage withdraws the row before recovery');
  assert.ok(facts.ended, 'a resultless begin with newer completion proof outranks a stale Live card');
  return ['Same selected Detail retains three invocation nodes without stale input through history, Live and health gaps',
    'Independent foreground/background completion, source switch and newer prompt-end proof retire obsolete rows'];
};
