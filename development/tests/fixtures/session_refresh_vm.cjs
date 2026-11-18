// Passive refresh exercises the shipped load/poll path, not just direct paints.
const assert = require('node:assert/strict');
module.exports = async ({vm, context, Node, input, document, delays}) => {
  const requests = [];
  let response = JSON.parse(JSON.stringify(input.first)), failure;
  context.refreshApi = async (_, request) => {
    requests.push(request);
    if (request.action === 'open') return {token:'refresh'};
    if (request.action === 'close' || request.action === 'retry') return {};
    if (failure) throw new Error(failure);
    const page = JSON.parse(JSON.stringify(response));
    if (page.result) {
      page.offset = request.offset;
      page.result.view.prompt_blocks[0].rows =
        page.result.view.prompt_blocks[0].rows.slice(request.offset, request.offset + 25);
    }
    return page;
  };
  vm.runInContext("globalThis.refresh = new SessionDetail.View(refreshApi, 'root-0000')", context);
  const view = context.refresh;
  new Node('main').append(view.root);
  view.attached = true;
  assert.equal(view.loader.root.hidden, false, 'cold open still has real loading');
  await view.poll();
  const row = view.body.children[0], footer = view.footer.textContent;
  const silent = () => {
    assert.equal(view.status.hidden, true);
    assert.equal(view.status.textContent, '', 'no hidden live-region update text either');
    assert.equal(view.retry.hidden, true, 'no passive Retry tab stop or layout');
    assert.equal(view.loader.root.hidden, true);
    assert.equal(view.scroll.attributes['aria-busy'], 'false');
    assert.equal(view.body.children[0], row);
    assert.equal(view.activityFeedback.children.length, 0);
    assert.equal(view.activityAnnouncement.textContent, '');
  };
  silent();
  for (const pending of [
    {state:'loading', pending:true, result:null},
    {state:'observed', pending:true, result:null},
    {state:'loading', result:null, acquisition:{phase:'verifying', percent:35}},
    {...input.first, pending:true}
  ]) {
    response = pending;
    for (let cycle = 0; cycle < 3; cycle++) {
      await view.poll(); silent();
      assert.equal(view.footer.textContent, footer);
      assert.equal(delays.at(-1), 5000, 'retained live detail never polls at 500ms');
    }
  }
  const beforeHidden = requests.length;
  document.hidden = true;
  await view.poll();
  assert.equal(requests.length, beforeHidden);
  assert.equal(delays.at(-1), 30000);
  document.hidden = false;
  await view.poll(); silent();
  failure = 'offline';
  await view.poll();
  silent();
  failure = null;
  for (const pending of [
    {state:'loading', pending:true, result:null},
    {state:'observed', pending:true, result:null},
    {state:'loading', result:null, acquisition:{phase:'reading'}},
    {...input.first, pending:true}
  ]) {
    response = pending; await view.poll();
    silent();
  }
  response = {state:'loading', result:null,
    acquisition:{phase:'failed', reason:'detail_no_progress', retry_available:true}};
  await view.poll();
  silent();
  response = {state:'loading', pending:true, result:null, acquisition:{phase:'queued'}};
  await view.retrySource();
  assert.equal(requests.filter(request => request.action === 'retry').length, 1);
  silent();
  response = JSON.parse(JSON.stringify(input.first));
  await view.poll(); silent();
  response.state = 'source_unavailable'; await view.poll();
  silent();
  response.state = 'observed'; await view.poll(); silent();
  response = JSON.parse(JSON.stringify(input.changed));
  response.result.view.prompt_blocks[0].rows.at(-1).in_progress = true;
  response.revision = 'quiet-running';
  await view.poll(); silent();
  assert.equal(view.body.children.length, 101);
  assert.match(view.body.children.at(-1).textContent, /\[RUNNING\]/);
  const runningFooter = view.footer.textContent;
  response.activity_refresh = 'pending';
  await view.poll();
  const acknowledgement = view.activityFeedback.firstChild;
  assert.match(acknowledgement.textContent, /Checking any running prompts/);
  for (let cycle = 0; cycle < 30; cycle++) await view.poll();
  assert.equal(view.activityFeedback.children.length, 1);
  assert.equal(view.activityFeedback.firstChild, acknowledgement);
  assert.equal(view.body.children.length, 101);
  assert.equal(view.footer.textContent, runningFooter);
  failure = 'offline';
  await view.poll();
  assert.equal(view.activityFeedback.firstChild, acknowledgement);
  assert.match(view.activityAnnouncement.textContent, /Running status may be out of date/);
  failure = null;
  response.activity_refresh = null;
  response.result.view.prompt_blocks[0].rows.at(-1).in_progress = false;
  response.revision = 'quiet-completed';
  await view.poll(); silent();
  assert.doesNotMatch(view.body.children.at(-1).textContent, /\[RUNNING\]/);
  assert.ok(requests.some(request => request.action === 'chunk' && request.offset === 100));
  view.detach();
  response = JSON.parse(JSON.stringify(input.first));
  const authority = response.value_authority;
  const qualified = JSON.parse(JSON.stringify(authority));
  for (const key of Object.keys(qualified.totals)) qualified.totals[key] = 'known';
  for (const key of Object.keys(qualified.rows)) qualified.rows[key] = 'known';
  for (const key of Object.keys(authority.totals)) authority.totals[key] = 'pending';
  for (const key of Object.keys(authority.rows)) authority.rows[key] = 'pending';
  vm.runInContext("globalThis.qualification = new SessionDetail.View(refreshApi, 'root-0000')", context);
  const recovered = context.qualification;
  new Node('main').append(recovered.root); recovered.attached = true;
  await recovered.poll();
  const revision = recovered.data.revision, footerNode = recovered.footer.children[4].firstChild;
  assert.equal(footerNode.textContent, 'Loading…');
  response.value_authority = qualified;
  await recovered.poll();
  assert.equal(recovered.data.revision, revision, 'authority recovery does not need a table revision');
  assert.equal(recovered.footer.children[4].firstChild, footerNode);
  assert.equal(footerNode.textContent, String(response.result.view.prompt_blocks[0].total_calls));
  assert.notEqual(recovered.footer.children[9].textContent, 'Loading…');
  recovered.detach();
};
