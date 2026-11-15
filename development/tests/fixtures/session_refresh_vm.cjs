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
    assert.equal(view.loader.root.hidden, true);
    assert.equal(view.scroll.attributes['aria-busy'], 'false');
    assert.equal(view.body.children[0], row);
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
      assert.equal(delays.at(-1), response.result ? 5000 : 500, 'existing poll cadence is unchanged');
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
  assert.equal(view.status.hidden, false);
  assert.match(view.status.textContent, /updates unavailable.*offline/);
  const error = view.status.textContent;
  failure = null;
  for (const pending of [
    {state:'loading', pending:true, result:null},
    {state:'observed', pending:true, result:null},
    {state:'loading', result:null, acquisition:{phase:'reading'}},
    {...input.first, pending:true}
  ]) {
    response = pending; await view.poll();
    assert.equal(view.status.hidden, false);
    assert.equal(view.status.textContent, error, 'pending work is not successful fault recovery');
  }
  response = {state:'loading', result:null,
    acquisition:{phase:'failed', reason:'detail_no_progress', retry_available:true}};
  await view.poll();
  assert.match(view.status.textContent, /No forward progress/);
  assert.equal(view.retry.hidden, false);
  response = {state:'loading', pending:true, result:null, acquisition:{phase:'queued'}};
  await view.retrySource();
  assert.equal(requests.filter(request => request.action === 'retry').length, 1);
  assert.equal(view.status.hidden, false, 'explicit retry keeps the last fault until recovery');
  assert.match(view.status.textContent, /No forward progress/);
  response = JSON.parse(JSON.stringify(input.first));
  await view.poll(); silent();
  response.state = 'source_unavailable'; await view.poll();
  assert.equal(view.status.hidden, false);
  assert.match(view.status.textContent, /Source unavailable/);
  response.state = 'observed'; await view.poll(); silent();
  response = JSON.parse(JSON.stringify(input.changed));
  response.result.view.prompt_blocks[0].rows.at(-1).in_progress = true;
  response.revision = 'quiet-running';
  await view.poll(); silent();
  assert.equal(view.body.children.length, 101);
  assert.match(view.body.children.at(-1).textContent, /\[RUNNING\]/);
  response.result.view.prompt_blocks[0].rows.at(-1).in_progress = false;
  response.revision = 'quiet-completed';
  await view.poll(); silent();
  assert.doesNotMatch(view.body.children.at(-1).textContent, /\[RUNNING\]/);
  assert.ok(requests.some(request => request.action === 'chunk' && request.offset === 100));
  view.detach();
};
