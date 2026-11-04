// Hidden Chromium, fresh owned profiles, actual HTTP/cookie jar/SSE/assets.
// Session time and cookie age are advanced together; this is NOT a multi-day soak.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {setTimeout: delay} = require('node:timers/promises');
const args = process.argv.slice(2), arg = key => args[args.indexOf(key) + 1];
async function main() {
  const browser = arg('--browser'), output = arg('--output');
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.mkdir(output, {recursive: true});
  const workspace = path.join(output, 'fixture');
  await fs.mkdir(workspace);
  const server = spawn('py', ['-3', 'development/tests/integration/serve_web_connection.py', '--workspace', workspace],
    {windowsHide: true, stdio: 'ignore'});
  const profile = await fs.mkdtemp(path.join(output, 'session-profile-'));
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir=' + profile, 'about:blank'], {windowsHide: true, stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe']});
  let next = 0, buffer = '';
  const pending = new Map(), events = new Map();
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString();
    let end;
    while ((end = buffer.indexOf('\0')) >= 0) {
      const message = JSON.parse(buffer.slice(0, end)); buffer = buffer.slice(end + 1);
      const entry = pending.get(message.id);
      if (entry) { pending.delete(message.id); message.error ? entry.reject(new Error(message.error.message)) : entry.resolve(message.result); }
      const key = message.sessionId + ':' + message.method;
      if (events.has(key)) { events.get(key)(); events.delete(key); }
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++next; pending.set(id, {resolve, reject});
    child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
  });
  const until = async check => {
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) { const result = await check(); if (result) return result; await delay(50); }
    throw new Error('session_probe_condition_timeout');
  };
  const fixture = async (action, extra = {}) => {
    await fs.rm(path.join(workspace, 'ack.json'), {force: true});
    await fs.writeFile(path.join(workspace, 'command.json'), JSON.stringify({action, ...extra}));
    await until(async () => { try { return JSON.parse(await fs.readFile(path.join(workspace, 'ack.json'))).action === action; } catch { return false; } });
  };
  let stage = 'fixture readiness';
  const deadline = setTimeout(() => {
    console.error('session_probe_deadline: ' + stage); process.exitCode = 1;
    child.kill(); server.kill();
  }, 90000);
  try {
    const ready = await until(async () => { try { return JSON.parse(await fs.readFile(path.join(workspace, 'ready.json'))); } catch { return null; } });
    const origin = ready.origin;
    stage = 'first authorized page';
    const clients = [];
    const create = async entry => {
      const {browserContextId} = await command('Target.createBrowserContext');
      const {targetId} = await command('Target.createTarget', {url: 'about:blank', browserContextId});
      const {sessionId} = await command('Target.attachToTarget', {targetId, flatten: true});
      await command('Page.enable', {}, sessionId);
      const evaluate = async expression => {
        const value = await command('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true}, sessionId);
        assert.equal(value.exceptionDetails, undefined, 'page evaluation must complete');
        return value.result.value;
      };
      const navigate = async url => {
        const loaded = new Promise(resolve => events.set(sessionId + ':Page.loadEventFired', resolve));
        const result = await command('Page.navigate', {url}, sessionId);
        if (result.loaderId) await loaded;
        else events.delete(sessionId + ':Page.loadEventFired');
      };
      const reload = async () => {
        const loaded = new Promise(resolve => events.set(sessionId + ':Page.loadEventFired', resolve));
        await command('Page.reload', {}, sessionId); await loaded;
      };
      const client = {browserContextId, evaluate, navigate, reload}; clients.push(client);
      await navigate(origin + (entry ? '/probe-entry' : '/'));
      if (entry) await until(async () => await evaluate('typeof hostState !== "undefined" && hostState.kind === "connected"'));
      return client;
    };
    const cookies = async client => (await command('Storage.getCookies', {browserContextId: client.browserContextId})).cookies;
    const first = await create(true);
    stage = 'Watch navigation';
    await first.evaluate('location.hash = "#/watch"');
    await until(() => first.evaluate('document.getElementById("heading").textContent.includes("Watch")'));
    const issued = (await cookies(first))[0];
    assert.ok(issued.httpOnly && issued.sameSite === 'Strict' && issued.path === '/');
    assert.ok(issued.expires - Date.now() / 1000 > 608390);
    assert.equal(await first.evaluate('document.cookie.includes("cg_session_")'), false);
    const second = await create(false);
    stage = 'independent browser authorization';
    await until(() => second.evaluate('typeof hostState !== "undefined" && hostState.kind === "authorization_required"'));
    await fixture('fresh_entry');
    await second.navigate(origin + '/probe-entry');
    await until(() => second.evaluate('hostState.kind === "connected"'));
    assert.notEqual((await cookies(first))[0].value, (await cookies(second))[0].value, 'independent browsers');
    const advance = async seconds => {
      // Chromium itself enforces these aged cookie expirations on later requests.
      for (const client of clients) {
        const stored = await cookies(client);
        await command('Storage.setCookies', {browserContextId: client.browserContextId,
          cookies: stored.map(cookie => ({name: cookie.name, value: cookie.value, domain: cookie.domain,
            path: cookie.path, httpOnly: cookie.httpOnly, secure: cookie.secure, sameSite: cookie.sameSite,
            expires: cookie.expires - seconds}))});
      }
      await fixture('advance_session', {seconds});
    };
    const poll = client => client.evaluate('(async () => (await fetch("/api/live")).status)()');
    await advance(3590);
    stage = 'cookie renewal boundary';
    assert.equal(await poll(first), 200);
    const before = (await cookies(first))[0].expires;
    assert.ok(before < issued.expires - 3580, 'no per-poll renewal');
    // Return just before seven idle days, after the original seven-day cookie TTL.
    await advance(7 * 86400 - 5);
    assert.equal(await poll(first), 200);
    assert.ok((await cookies(first))[0].expires - Date.now() / 1000 > 608390, 'actual browser accepted renewed Set-Cookie');
    assert.equal(await poll(second), 401, 'active peer cannot revive inactive browser');
    await fixture('fresh_entry');
    await second.navigate(origin + '/probe-entry');
    await until(() => second.evaluate('hostState.kind === "connected"'));
    stage = 'repeated daily renewal';
    for (let day = 0; day < 15; day++) {
      await advance(86400);
      for (const client of clients) assert.equal(await poll(client), 200);
    }
    await first.navigate(origin + '/#/watch');
    await first.reload();
    stage = 'reload and settings';
    await until(() => first.evaluate('hostState.kind === "connected"'));
    assert.equal(await first.evaluate('(async () => { const r = await api("/api/settings"); return (await api("/api/settings/theme", {theme:r.webSettings.theme})).webSettings.theme === r.webSettings.theme; })()'), true);
    await advance(7 * 86400);
    stage = 'genuine inactivity recovery guidance';
    assert.equal(await poll(first), 401, 'exact seven-day idle boundary, despite retained cookie');
    await first.evaluate('liveConnection.resync()');
    await until(() => first.evaluate('hostState.kind === "authorization_required"'));
    assert.ok(await first.evaluate('document.getElementById("host-message").textContent.includes("AUTHENTICATION EXPIRED")'));
    console.log(JSON.stringify({browser:path.basename(browser), simulated_days:29, independent_clients:2,
      cookie_renewal:true, idle_boundary:true, csrf_write:true, reload_watch:true, elapsed_multi_day_soak:false}));
  } finally {
    clearTimeout(deadline);
    await command('Browser.close').catch(() => child.kill());
    await once(child, 'exit').catch(() => {});
    if (server.exitCode === null) { await fixture('menu'); await once(server, 'exit'); }
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
