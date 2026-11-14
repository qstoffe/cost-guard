// Real hidden Chromium DOM + actual Document PiP; source-shaped synthetic frames.
const assert = require('node:assert/strict');
module.exports = async (evaluate, command, sessionId) => {
  const ready = await command('Runtime.evaluate', {
    expression: 'mini.measure.loaded', awaitPromise: true, returnByValue: true}, sessionId);
  assert.equal(ready.exceptionDetails, undefined);
  const opened = await command('Runtime.evaluate', {
    expression: 'mini.toggle()', awaitPromise: true, userGesture: true, returnByValue: true}, sessionId);
  assert.equal(opened.exceptionDetails, undefined);
  assert.equal(await evaluate('Boolean(mini.window && mini.view)'), true, 'actual Document PiP opened');
  const observations = [];
  for (let index = 0; index < 5; index++) {
    const facts = await evaluate(`(() => {
      const view = FRAMES[${index}]; syntheticNow=view.now_ms;
      const publication={state:'running',view}; INPUT.view=view;
      ReportView.renderLive(document.getElementById('result'),publication,state); mini.update(publication);
      const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='ses_current');
      const row=card.body.children[0];
      const miniRow=mini.window.document.querySelector('tbody tr[data-id]');
      return {full:row.className, fullAria:row.getAttribute('aria-label'),
        mini:miniRow.className, miniAria:miniRow.getAttribute('aria-label'),
        fullActive:state.watch.active.contains(card.root), fullHistory:state.watch.history.contains(card.root),
        miniRows:mini.window.document.querySelectorAll('tbody tr[data-id]').length,
        parent:view.active_cards.concat(view.history_cards)[0].rows[0].prompt.parent_outcome,
        duration:row.children[1].textContent, toolVisible:!card.running.hidden,
        color:getComputedStyle(row).color, titleColor:getComputedStyle(card.title).color}; })()`);
    const running = index < 3;
    assert.equal(facts.full === 'watch-running', running);
    assert.equal(facts.mini === 'mini-running', running);
    assert.equal(/Running/.test(facts.fullAria), running);
    assert.equal(/Running/.test(facts.miniAria), running);
    assert.equal(facts.miniRows, 1, 'no duplicate/sixth Mini row');
    if (index === 1 || index === 2) {
      assert.match(facts.fullAria, /subagent activity/);
      assert.match(facts.miniAria, /subagent activity/);
      assert.equal(facts.parent, 'cancellation');
      assert.equal(facts.toolVisible, false, 'cancelled parent delegation not reopened');
      assert.equal(facts.color, facts.titleColor);
    }
    if (!running) {
      assert.match(facts.fullAria, /Aborted/); assert.match(facts.miniAria, /Aborted/);
      assert.equal(facts.fullActive, index === 3);
      assert.equal(facts.fullHistory, index === 4);
    }
    observations.push(facts);
  }
  assert.equal(observations[3].duration, observations[4].duration);
  // Reconnect/cold presentation reconstructs final source facts, not green success.
  assert.equal(await evaluate(`(() => {
    const next={connection:'Live connected.'}; ReportView.renderLive(document.getElementById('result'),INPUT,next);
    return [...next.watch.cards.values()][0].body.children[0].getAttribute('aria-label'); })()`),
    observations[4].fullAria);
  await evaluate('mini.close()');
  return {frames: observations.length, realPiP: true, cancelledParentPreserved: true, terminalClockFrozen: true};
};
