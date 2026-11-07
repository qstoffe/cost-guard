// Focused live-only presentation grace: real evidence tokens, no acquisition/timers.
const assert = require('node:assert/strict');
module.exports = function liveStatus(vm, context, clock) {
  const Status = vm.runInContext('ReportView.LiveStatus', context), status = new Status();
  assert.equal(status.update(true, 100, 0), false);
  for (const ms of [1000, 5000, 10000, 30000, 59999])
    assert.equal(status.update(false, 999, ms), false);
  assert.equal(status.update(false, 999, 61000), true);
  assert.equal(status.update(true, 100, 61001), true, 'replayed success cannot reset a failed lane');
  assert.equal(status.update(true, 99, 61002), true, 'older evidence cannot recover a lane');
  assert.equal(status.update(true, 101, 61003), false);

  const start = clock(), value = structuredClone(context.input);
  value.state = 'running'; value.source_observed_at_ms = 100;
  Object.assign(value.view, {cards_state:'observed', daily_state:'observed', quota_stale:false, quota_recovering_count:0});
  value.view.active_cards = [structuredClone(context.input.view.history_cards[0])];
  const card = value.view.active_cards[0]; card.session_id = 'quiet-card'; card.state = 'observed'; card.observed_at_ms = 100;
  value.view.daily_usage = {observed_at_ms:100, total:{complete:true, observed_requests:1, priced_requests:1, display:{known_ccost:'42'}}, prompt_count:7};
  const account = structuredClone(context.input.view.accounts.accounts[0]);
  account.observation = {...account.observation, availability:'available', observed_at_ms:100, error_code:null};
  value.view.accounts = {accounts:[account]};
  context.quietValue = value;
  vm.runInContext('globalThis.quietView = new WatchView.View({connection:"Live connected."}); quietView.update(quietValue)', context);
  const view = context.quietView, rendered = [...view.cards.values()].find(c => c.value === card);
  const quota = view.accountCards.grid.children[0], daily = view.daily.children[1];
  card.state = 'partial'; card.session_summary.state = 'partial';
  value.view.daily_state = 'partial'; account.observation.availability = 'partial';
  const update = ms => { clock(start + ms); vm.runInContext('quietView.update(quietValue)', context); };
  update(0);
  for (const ms of [1000, 5000, 10000, 30000, 59999]) {
    value.view.now_ms++; value.source_observed_at_ms++;
    update(ms);
    assert.equal(rendered.message.textContent, '');
    assert.equal(rendered.costStatus.textContent, '');
    assert.equal(view.daily.children[1] === daily, true, 'status-only publications retain daily target');
    assert.doesNotMatch(quota.textContent, /Partial quota|Retained|Updates delayed/);
  }
  update(60000);
  assert.equal(rendered.message.textContent, 'Updates delayed · showing last values');
  assert.match(view.daily.textContent, /Updates delayed · showing last values/);
  assert.match(quota.textContent, /Updates delayed · showing last values/);
  // Cost-only changes and unchanged observed states do not prove successful coverage.
  card.state = 'observed'; card.session_summary.cost.display.known_ccost = '999';
  value.view.daily_state = 'observed'; account.observation.availability = 'available';
  update(61000);
  assert.match(rendered.message.textContent, /Updates delayed/);
  assert.match(view.daily.textContent, /Updates delayed/);
  assert.match(quota.textContent, /Updates delayed/);
  card.observed_at_ms++; value.view.daily_usage.observed_at_ms++; account.observation.observed_at_ms++;
  update(62000);
  assert.equal(rendered.message.textContent, '');
  assert.doesNotMatch(view.daily.textContent, /Updates delayed/);
  assert.doesNotMatch(quota.textContent, /Updates delayed/);
  // Typed actionable failures and genuinely new incomplete native evidence stay visible.
  account.observation.availability = 'stale'; account.observation.error_code = 'auth_failure';
  update(63000); assert.match(quota.textContent, /Authentication unavailable/);
  account.observation.error_code = null; account.observation.availability = 'partial'; account.observation.observed_at_ms++;
  update(64000); assert.match(quota.textContent, /Partial quota data/);
  update(65000); assert.match(quota.textContent, /Partial quota data/, 'actual incomplete observation is not a transient retry');
  clock(start);
};
