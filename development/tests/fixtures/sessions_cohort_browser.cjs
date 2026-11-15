// Actual HTTP/DTO/action banner DOM. Scalar facts are explicitly seeded fixtures.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture}) => {
  const checks = [];
  await fixture('catalog-navigation-source'); await fixture('catalog-index');
  await evaluate(`location.hash='#/sessions?period=all&sort=activity&direction=-1'`);
  await until('current.catalog?.data?.total===324 && !current.catalog.busy && !current.catalog.operation');
  await fixture('catalog-clear');
  await evaluate(`window.cohortClick=performance.now();current.catalog.headers[3].th.querySelector('button').click()`);
  await until('current.catalog.operation?.pending && !current.catalog.busy');
  const load = () => evaluate('current.catalog.load()');
  await fixture('catalog-navigation-partial'); await load();
  assert.equal(await evaluate('current.catalog.status.textContent'),'Sorting sessions by CCost · 20 of 324 sessions');
  await fixture('catalog-navigation-arrive');
  for (let i=0;i<3;i++) {
    await fixture('catalog-churn'); await load();
    assert.equal(await evaluate('current.catalog.operation.total'),324);
    assert.ok(await evaluate('current.catalog.operation.completed')>=20);
    assert.doesNotMatch(await evaluate('current.catalog.status.textContent'),/worker|revalidating|cache|Indexed|Prepared/);
  }
  await fixture('catalog-navigation-finish'); await load();
  await until('!current.catalog.operation && current.catalog.data.sort==="ccost" && !current.catalog.busy');
  const first = await evaluate(`({elapsed_ms:performance.now()-cohortClick,total:current.catalog.data.total,
    progress:current.catalog.data.progress,rows:current.catalog.data.view.session_usage,
    banner_hidden:current.catalog.status.hidden,spinners:current.catalog.pager.querySelectorAll('[aria-busy=true]').length})`);
  assert.equal(first.total,324); assert.equal(first.banner_hidden,true); assert.equal(first.spinners,0);
  assert.equal(first.rows[0].session_id,'root-0000');
  assert.equal(first.rows[0].metric_states.ccost,'snapshot');
  assert.equal((await fixture('catalog-navigation-observe')).arrivals_qualified,0);
  // Existing focused help exposes snapshot semantics outside the simple banner.
  await evaluate('current.catalog.body.rows[0].cells[3].querySelector("span").focus()');
  await until('document.getElementById("context-help")?.textContent.includes("Navigation snapshot")');
  await load(); // Acknowledge actual application; no second poller.
  await fixture('catalog-navigation-resume');
  await until('current.catalog.data.total===326 && !current.catalog.busy',60000);
  assert.equal(await evaluate('current.catalog.status.hidden'),true);
  assert.equal((await fixture('catalog-navigation-observe')).arrivals_qualified,2);
  checks.push({contract:'20/324 remains bounded under arrivals/hot revision; applies before additions; then silent 326',
    fixture_click_to_apply_ms:Math.round(first.elapsed_ms),first_view_total:first.total,
    note:'Seeded scalar work measures HTTP/controller/DOM latency, not source throughput'});
  return {checks,layouts:[]};
};
