// No UI automation, third-party DOM, build or package installation. Run by test_web_views.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; this.text = ''; this.disabled = false; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; this.text = ''; }
  setAttribute(key, value) { this.attrs[key] = value; }
  getAttribute(key) { return this.attrs[key]; }
  removeAttribute(key) { delete this.attrs[key]; }
  addEventListener(key, fn) { this.events[key] = fn; }
  click() { if (!this.disabled) return this.events.click?.(); }
}
const all = (node, tag) => [...(node.tag === tag ? [node] : []), ...node.children.flatMap(child => all(child, tag))];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(condition) {
  for (let i = 0; i < 500; i++) { if (condition()) return; await delay(10); }
  assert.fail('bounded UI condition timed out');
}
async function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const ids = Object.fromEntries(['status', 'result', 'notice', 'refresh', 'cancel', 'heading', 'skip', 'content'].map(id => [id, new Node('div')]));
  const nav = ['overview', 'sessions', 'live', 'models', 'accounts', 'reports', 'token-mix'].map(key => {
    const node = new Node('a'); node.setAttribute('href', '#/' + key); return node;
  });
  const handlers = {};
  const location = {hash: '#bootstrap=' + input.credential};
  const history = {replaceState: (_, __, value) => { location.hash = value.slice(value.indexOf('#')); }};
  let cookie = '', requests = 0, offline = false;
  const wire = async (path, options = {}) => {
    if (offline) throw new Error('offline');
    const headers = {...options.headers, Origin: input.origin};
    if (cookie) headers.Cookie = cookie;
    requests++;
    const response = await fetch(input.origin + path, {...options, headers});
    if (response.headers.get('set-cookie')) cookie = response.headers.get('set-cookie').split(';')[0];
    return response;
  };
  const context = vm.createContext({document: {createElement: tag => new Node(tag),
    getElementById: id => ids[id], querySelectorAll: () => nav}, window: {addEventListener: (key, fn) => { handlers[key] = fn; }},
    location, history, URLSearchParams, fetch: wire, setTimeout, Date, console});
  for (const path of ['/render.js', '/app.js']) {
    const response = await fetch(input.origin + path);
    assert.equal(response.status, 200);
    vm.runInContext(await response.text(), context);
  }
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.equal(location.hash, '#/overview');
  assert.match(ids.result.textContent, /CCost = reference valuation/);
  const navigate = key => { location.hash = '#/' + key; handlers.hashchange(); };
  navigate('sessions');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /1–50 of 55/);
  assert.equal(all(ids.result, 'tbody')[0].children.length, 50);
  const next = all(ids.result, 'button').find(node => node.textContent === 'Next');
  next.click();
  assert.match(ids.result.textContent, /51–55 of 55/);
  const sessionLink = all(ids.result, 'a').find(node => node.href === '#/sessions/root-0000');
  assert.ok(sessionLink, 'session locator links are reachable on the last page');
  navigate('sessions/root-0000');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  const snapshot = ids.result.textContent;
  assert.match(snapshot, /Running at snapshot · provisional|1–50 of 151/);
  const headers = all(ids.result, 'th').map(node => node.textContent);
  assert.deepEqual(headers, ['Prompt', 'CCost', 'Calls', 'Duration', '~Ictx', '~Ictx CCost', '~Extra CCost', 'I/C/W/O %']);
  const totals = all(ids.result, 'tfoot')[0].textContent;
  for (let i = 0; i < 3; i++) all(ids.result, 'button').find(node => node.textContent === 'Next').click();
  assert.match(ids.result.textContent, /151–151 of 151/);
  assert.equal(all(ids.result, 'tfoot')[0].textContent, totals);
  assert.match(ids.result.textContent, /Running at snapshot · provisional/);
  const frozen = ids.result.textContent, count = requests;
  await delay(650);
  assert.equal(ids.result.textContent, frozen);
  assert.equal(requests, count, 'no global Watch or silent refresh');
  navigate('sessions'); // Back-equivalent hash event restores the same list page.
  assert.match(ids.result.textContent, /51–55 of 55/);
  navigate('sessions/root-0000');
  assert.equal(ids.result.textContent, frozen);
  ids.refresh.click();
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.notEqual(ids.result.textContent, snapshot, 'explicit refresh captures a new observation');
  assert.match(ids.result.textContent, /1–50 of 152/);
  const last = ids.result.textContent;
  offline = true;
  ids.refresh.click();
  await until(() => ids.notice.textContent.includes('STALE'));
  assert.equal(ids.result.textContent, last);
  offline = false;
  navigate('sessions/missing');
  await until(() => ids.notice.textContent.includes('No matching session'));
  navigate('sessions/root-0001');
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.match(ids.result.textContent, /exists but has no prompt rows/);
  navigate('live');
  assert.match(ids.notice.textContent, /Unavailable/);
  assert.equal(ids.refresh.disabled, true);
  // Actual canonical DTOs exercise compaction, linked-child, running and hostile text.
  for (const [index, result] of input.examples.entries()) {
    context.example = result;
    vm.runInContext('ReportView.render(output, example, {pages: {}})', context);
    const block = result.view.prompt_blocks[0];
    assert.ok(ids.result.textContent.includes('Full-session CCost ' + block.total_ccost));
    assert.ok(ids.result.textContent.includes(block.title));
    assert.equal(all(ids.result, 'img').length, 0);
    assert.equal(all(ids.result, 'script').length, 0);
    if (index === 0) assert.match(ids.result.textContent, /Compaction/);
    if (index === 1) assert.match(ids.result.textContent, /Running at snapshot · provisional/);
    if (index === 2) assert.match(ids.result.textContent, /Aborted|Error/);
    if (index === 3) {
      assert.match(ids.result.textContent, /Partial source data/);
      assert.match(ids.result.textContent, /incomplete|Unknown/);
    }
  }
  assert.match(ids.result.textContent, /Å日本語/);
  context.example = input.overview;
  vm.runInContext('ReportView.render(output, example, {pages: {}})', context);
  for (const account of input.overview.view.accounts_quotas.accounts) {
    assert.ok(ids.result.textContent.includes(account.observation.label));
    assert.ok(ids.result.textContent.includes(account.observation.availability));
    assert.ok(ids.result.textContent.includes('Billed today'));
  }
  // Reload with an ordinary deep link must not erase it or require the bootstrap again.
  location.hash = '#/sessions/root-0000';
  const reloaded = vm.createContext({document: context.document, window: context.window, location, history,
    URLSearchParams, fetch: wire, setTimeout, Date, console});
  vm.runInContext(await (await fetch(input.origin + '/render.js')).text(), reloaded);
  ids.notice.textContent = 'reload pending';
  vm.runInContext(await (await fetch(input.origin + '/app.js')).text(), reloaded);
  await until(() => ids.notice.textContent.includes('Snapshot captured'));
  assert.equal(location.hash, '#/sessions/root-0000');
  assert.match(ids.heading.textContent, /Session root-0000/);
  console.log('web views passed: real HTTP, facade, pagination, frozen/refresh/stale, missing/empty, deep links, safe text');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
