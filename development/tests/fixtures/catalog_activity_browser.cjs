// Same synthetic root/source through real HTTP Sessions + canonical Watch capture
// and actual headless Document PiP. No personal profiles, histories or desktop.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks = [], measurements = [];
  const finished = Date.parse('2026-11-15T01:18:00Z');
  const later = Date.parse('2026-11-15T01:52:00Z');
  await fixture('parity-source');
  await evaluate(`window.parityNativeNow=Date.now;Date.now=()=>Date.parse('2026-11-15T02:00:00Z');
    location.hash='#/sessions'`);
  await until(`current.catalog?.data?.view.session_usage[0]?.session_id==='root-0000' &&
    current.catalog.data.view.session_usage[0].activity_state==='ready'`);
  await until(`liveValue?.view?.history_cards[0]?.session_id==='root-0000' && miniWatch.measure?.ready`);
  await evaluate('miniWatch.toggle()', true);
  await until(`miniWatch.window && miniWatch.view?.body.rows.length===1`);
  const read = () => evaluate(`(()=>{
    const catalog=current.catalog, row=catalog.body.rows[0], card=liveValue.view.history_cards[0];
    const mini=miniWatch.view.body.rows[0], prompt=card.rows[0].prompt;
    return {id:row.dataset.id,miniId:card.session_id,raw:row.value.last_activity_ms,
      miniRaw:prompt.completed_at_ms,zone:catalog.renderTimezone,clock:row.activity.textContent,
      miniClock:mini.cells[0].textContent,miniHelp:mini.activityHelp,state:row.value.activity_state,
      scope:catalog.data.candidate_scope,order:catalog.data.order_state};})()`);
  for (const action of ['initial', 'parity-metadata', 'parity-archive', 'parity-child-metadata']) {
    if (action !== 'initial') {
      await fixture(action);
      await until(`api('/api/sessions',{token:current.catalog.token,period:'today'}).then(data=>
        !data.pending_sort && data.view.session_usage[0]?.activity_state==='ready')`, 15000);
      await evaluate('current.catalog.load()');
      await until(`current.catalog.data.view.session_usage[0]?.activity_state==='ready' && !current.catalog.busy`);
    }
    const value = await read();
    assert.equal(value.id,'root-0000'); assert.equal(value.miniId,value.id);
    assert.equal(value.raw,finished); assert.equal(value.miniRaw,finished);
    assert.equal(value.clock,'2026-11-15 01:18'); assert.equal(value.miniClock,'01:18');
    assert.equal(value.miniHelp,'2026-11-15 01:18'); assert.equal(value.zone,'UTC');
    assert.equal(value.scope,'source_catalog_metadata'); assert.equal(value.order,'verified');
    measurements.push({action,...value});
  }
  await evaluate(`window.parityRow=current.catalog.body.rows[0];window.parityTime=parityRow.activity;
    parityTime.focus({preventScroll:true})`);
  await until(`document.getElementById('context-help')?.matches(':popover-open')`);
  assert.match(await evaluate(`document.getElementById('context-help').textContent`),/2026-11-15 01:18/);
  for (const timezoneId of ['America/New_York','Asia/Tokyo']) {
    await command('Emulation.setTimezoneOverride',{timezoneId});
    await evaluate('current.catalog.rows(current.catalog.data.view.session_usage);miniWatch.render()');
    const value = await read();
    assert.equal(value.clock,'2026-11-15 01:18'); assert.equal(value.miniClock,'01:18');
    assert.equal(await evaluate('document.activeElement===parityTime && parityRow.isConnected'),true);
  }
  await fixture('parity-new-prompt');
  await until(`liveValue.view.history_cards[0]?.rows[0]?.prompt.completed_at_ms===${later}`);
  await until(`current.catalog.body.rows[0]?.value.last_activity_ms===${later}`, 15000);
  const advanced = await read();
  assert.equal(advanced.raw,later); assert.equal(advanced.miniRaw,later);
  assert.equal(advanced.clock,'2026-11-15 01:52'); assert.equal(advanced.miniClock,'01:52');
  assert.match(await evaluate(`document.getElementById('context-help').textContent`),/2026-11-15 01:52/);
  const counters = await fixture('parity-observe');
  assert.equal(counters.source_instance,'synthetic-month'); assert.equal(counters.roots,1);
  assert.ok(counters.metrics.attempts<=5, JSON.stringify(counters));
  measurements.push({action:'new-prompt',...advanced}, counters);
  checks.push('Same synthetic root/source: raw completed event and configured-local 01:18 agree in Sessions and actual Document PiP; 01:52 root/archive and child metadata never replace it');
  checks.push('Real later prompt advances both to 01:52; focused activity help refreshes in place; browser New York/Tokyo does not change configured UTC clocks');
  checks.push('Bounded revision-keyed scalar acquisition counters; no inference/private history/profile/visible desktop');
  await evaluate('miniWatch.close();Date.now=parityNativeNow');
  return {checks,measurements};
};
