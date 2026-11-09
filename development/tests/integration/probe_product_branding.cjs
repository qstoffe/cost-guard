// Shipped authenticated HTTP/assets in hidden Chromium; synthetic publications only.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const readline = require('node:readline');
const [browser, output, expectedVersion] = process.argv.slice(2);

async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  assert.match(expectedVersion, /^v\d+\.\d+$/);
  await fs.stat(browser);
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'branding-browser-'));
  const config = await fs.mkdtemp(path.join(path.dirname(output), 'branding-config-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_mini_watch.py', config],
    {windowsHide:true, stdio:['pipe', 'pipe', 'pipe']});
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir=' + profile, 'about:blank'],
    {windowsHide:true, stdio:['ignore', 'ignore', 'ignore', 'pipe', 'pipe']});
  const pending = new Map(), errors = [];
  let sequence = 0, buffer = '';
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString();
    let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0, index)); buffer = buffer.slice(index + 1);
      const entry = pending.get(value.id);
      if (entry) {
        clearTimeout(entry.timer); pending.delete(value.id);
        value.error ? entry.reject(new Error(value.error.message)) : entry.resolve(value.result);
      } else if (value.method === 'Runtime.exceptionThrown') errors.push(value.params.exceptionDetails.text);
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++sequence, timer = setTimeout(() => reject(new Error('CDP timeout: ' + method)), 15000);
    pending.set(id, {resolve, reject, timer});
    child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
  });
  const deadline = setTimeout(() => { child.kill(); server.kill(); }, 90000);
  let evidence = {outcome:'FAIL'};
  try {
    const launch = JSON.parse((await lines.next()).value); // Private one-use URL, never retained.
    const version = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget', {url:'about:blank'});
    const {sessionId} = await command('Target.attachToTarget', {targetId, flatten:true});
    await command('Page.enable', {}, sessionId);
    await command('Runtime.enable', {}, sessionId);
    const evaluate = async expression => {
      const result = await command('Runtime.evaluate', {expression, returnByValue:true, awaitPromise:true}, sessionId);
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
      return result.result.value;
    };
    const until = async expression => {
      const end = Date.now() + 15000;
      while (Date.now() < end) {
        if (await evaluate(expression)) return;
        await new Promise(resolve => setTimeout(resolve, 25));
      }
      throw new Error('Rendered condition not reached');
    };
    await command('Page.navigate', {url:launch.url}, sessionId);
    await until(`document.querySelector('#product-version')?.textContent===${JSON.stringify(expectedVersion)}`);
    const statusVersion = await evaluate(`fetch('/api/status').then(r=>r.json()).then(v=>v.product_version)`);
    assert.equal(statusVersion, expectedVersion);
    const routes = [];
    for (const [route, title] of [['models','Models'], ['watch','Watch'], ['accounts','Accounts'],
      ['sessions','Sessions'], ['ai-stats','AI Stats'], ['settings','Settings']]) {
      await evaluate(`location.hash=${JSON.stringify('#/' + route)}`);
      await until(`document.title===${JSON.stringify(title + ' · Cost Guard')}`);
      const facts = await evaluate(`({heading:document.querySelector('header h1').textContent.trim(),
        title:document.title,visible:!!document.querySelector('header h1').getBoundingClientRect().width})`);
      assert.equal(facts.heading, 'Cost Guard ' + expectedVersion);
      assert.ok(facts.visible); assert.doesNotMatch(facts.heading + facts.title, /Beta/);
      assert.equal((facts.heading.match(/Cost Guard/g) || []).length, 1);
      routes.push({route, ...facts});
    }
    await command('Page.captureScreenshot', {format:'png'}, sessionId).then(result =>
      fs.writeFile(output.replace(/\.json$/, '.png'), Buffer.from(result.data, 'base64')));
    assert.deepEqual(errors, []);
    evidence = {outcome:'PASS', browser:version.product, statusVersion, routes,
      limitations:['Hidden Chromium and synthetic publications; no physical OS browser handoff, native desktop or real history proof.']};
  } finally {
    await fs.writeFile(output, JSON.stringify(evidence, null, 2));
    clearTimeout(deadline);
    try { await command('Browser.close'); } catch (_) {}
    child.kill(); server.stdin.end();
    for (const entry of pending.values()) clearTimeout(entry.timer);
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
