// Hidden fresh-profile Chromium: canonical capture frames -> shipped SSE/presenter -> actual DOM.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const http = require('node:http');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const args = process.argv.slice(2), arg = key => args[args.indexOf(key) + 1];

async function main() {
  const browser = arg('--browser'), output = arg('--output'), framesPath = arg('--frames');
  assert.ok([browser, output, framesPath].every(path.isAbsolute), 'explicit browser and owned evidence paths required');
  await fs.mkdir(output, {recursive:true});
  const fixture = JSON.parse(await fs.readFile(framesPath, 'utf8'));
  const frames = fixture.frames.map(view => ({state:'running', view}));
  let index = 0, sequence = 0;
  const streams = new Set();
  const snapshot = () => ({instance_id:'pre-response-fixture', sequence, values:{live:frames[index]}});
  const publish = (next, number = sequence + 1, body = frames[next]) => {
    index = next; sequence = number;
    for (const stream of streams) stream.write(`id: pre-response-fixture:${number}\nevent: live\ndata: ${JSON.stringify(body)}\n\n`);
  };
  const extras = fixture.unverified ? `<div id="mini"></div><div id="detail"></div>
    <script src="/mini.js"></script><script src="/session.js"></script>
    <script>window.mini=new MiniWatch.View(document,()=>{},document.getElementById('mini'));
    window.detail=new SessionDetail.View(()=>{},'ses_current');document.getElementById('detail').append(detail.root);
    window.renderExtras=async view=>{mini.drawPrompts(view);const data=await(await fetch('/fixture-details')).json();
      detail.update({revision:String(view.now_ms),result:{view:data,observed_at_ms:Date.now()}})};</script>` : '';
  const html = `<!doctype html><meta charset="utf-8"><div id="result"></div>
    <script src="/help.js"></script><script src="/render.js"></script><script src="/account-cards.js"></script><script src="/watch.js"></script><script src="/live.js"></script>
    ${extras}
    <script>window.state={connection:'Live connected.'};window.updates=0;window.last=null;
    LiveConnection.connect(async p=>(await fetch(p)).json(),live=>{window.last=live;window.updates++;
      ReportView.renderLive(document.getElementById('result'),live,state);window.renderExtras?.(live.view)},s=>{window.health=s});</script>`;
  const assets = new Map(await Promise.all(['help','render','account-cards','watch','live'].map(async name =>
    ['/' + name + '.js', await fs.readFile('src/web/assets/' + name + '.js')])));
  if (fixture.unverified) {
    // Expose the shipped View only to this owned presenter probe; no PiP/native geometry claim.
    assets.set('/mini.js', (await fs.readFile('src/web/assets/mini.js','utf8')).replace('return {Controller};','return {Controller, View};'));
    assets.set('/session.js', await fs.readFile('src/web/assets/session.js'));
  }
  const server = http.createServer((request, response) => {
    if (request.url === '/api/events') {
      response.writeHead(200, {'Content-Type':'text/event-stream','Cache-Control':'no-store'});
      response.write('retry: 10\n\n'); streams.add(response);
      response.on('close', () => streams.delete(response)); return;
    }
    response.setHeader('Cache-Control', 'no-store');
    if (request.url === '/api/live') {
      response.setHeader('Content-Type','application/json'); response.end(JSON.stringify(snapshot()));
    } else if (request.url === '/fixture-details') {
      response.setHeader('Content-Type','application/json'); response.end(JSON.stringify(fixture.details[index]));
    } else if (assets.has(request.url)) {
      response.setHeader('Content-Type','text/javascript'); response.end(assets.get(request.url));
    } else { response.setHeader('Content-Type','text/html'); response.end(html); }
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const profile = await fs.mkdtemp(path.join(output, 'owned-profile-'));
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check',
    '--disable-extensions','--disable-background-networking','--remote-debugging-pipe',
    '--user-data-dir=' + profile,'about:blank'], {stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(), listeners = new Map(), exceptions = []; let id = 0, buffer = '', phase = 'startup';
  const command = (method, params = {}, sessionId) => new Promise((resolve,reject) => {
    const key = ++id; pending.set(key,{resolve,reject});
    child.stdio[3].write(JSON.stringify({id:key,method,params,...(sessionId?{sessionId}:{})}) + '\0');
  });
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let end;
    while ((end = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0,end)); buffer = buffer.slice(end+1);
      if (value.id) {
        const item = pending.get(value.id); pending.delete(value.id);
        if (item) value.error ? item.reject(new Error(JSON.stringify(value.error))) : item.resolve(value.result);
      } else {
        if (value.method === 'Runtime.exceptionThrown') exceptions.push(value.params.exceptionDetails);
        const key = value.sessionId + ':' + value.method;
        if (listeners.has(key)) { listeners.get(key)(value.params); listeners.delete(key); }
      }
    }
  });
  const event = (method, session) => new Promise(resolve => listeners.set(session + ':' + method,resolve));
  const deadline = setTimeout(() => {
    for (const item of pending.values()) item.reject(new Error(JSON.stringify({error:'probe_deadline',phase,exceptions})));
    child.kill(); server.closeAllConnections();
  }, 60000);
  try {
    const version = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget',{url:'about:blank'});
    const {sessionId} = await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},sessionId);
    await command('Runtime.enable',{},sessionId);
    const evaluate = async expression => {
      const value = await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);
      assert.equal(value.exceptionDetails,undefined,JSON.stringify(value.exceptionDetails));
      return value.result.value;
    };
    const wait = predicate => evaluate(`new Promise(resolve=>{const check=()=>{if(${predicate}){
      observer.disconnect();resolve(true)}};const observer=new MutationObserver(check);
      observer.observe(document,{childList:true,subtree:true,attributes:true,characterData:true});check()})`);
    const row = `document.querySelector('article[data-session="${fixture.stopped}"] tbody tr')`;
    const read = () => evaluate(`(()=>{const row=${row},card=row.closest('article');return {
      running:row.classList.contains('watch-running'),label:row.getAttribute('aria-label'),
      duration:row.cells[1].textContent,ccost:row.cells[5].textContent,calls:row.cells[6].textContent,
      earlier:!!card.closest('.watch-history'),count:window.last.view.running.count}})()`);
    const loaded = event('Page.loadEventFired',sessionId);
    await command('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/`},sessionId); await loaded;
    phase = 'initial-running';
    await wait(`${row}?.classList.contains('watch-running')`);
    const initial = await read(); assert.equal(initial.count,fixture.unverified ? 1 : 6);
    if (fixture.unverified) {
      const extrasReady = `document.querySelector('#mini tbody tr')?.getAttribute('aria-label')?.includes('Unverified') && document.querySelector('#detail tbody tr:last-child')?.textContent.includes('[UNVERIFIED]')`;
      phase = 'unverified-presenters';
      publish(1); await wait(`${row}?.getAttribute('aria-label')?.includes('Unverified') && ${extrasReady}`);
      const uncertain = await read();
      assert.equal(await evaluate(`document.querySelector('#result').textContent.includes('No running prompts')`),false);
      assert.equal(uncertain.running,false); assert.equal(uncertain.count,null); assert.equal(uncertain.duration,'N/A');
      assert.equal(uncertain.ccost,initial.ccost); assert.equal(uncertain.calls,initial.calls);
      const inspectExtras = () => evaluate(`({mini:document.querySelector('#mini tbody tr').textContent,
        detail:document.querySelector('#detail tbody tr:last-child').textContent,
        total:document.querySelector('#detail tfoot').textContent})`);
      const extraState = await inspectExtras(); assert.match(extraState.mini,/Unverified/); assert.match(extraState.detail,/N\/A/);
      phase = 'unchanged-unverified';
      publish(2); await wait(`window.last?.view.now_ms===${frames[2].view.now_ms}`);
      assert.deepEqual(await read(),uncertain);
      const loadedAgain = event('Page.loadEventFired',sessionId);
      phase = 'reload-unverified';
      await command('Page.reload',{},sessionId); await loadedAgain; await wait(extrasReady);
      assert.deepEqual(await read(),uncertain);
      for (const stream of streams) stream.end();
      phase = 'reconnect-unverified';
      await evaluate(`new Promise(resolve=>{const original=fetch;window.fetch=async(...args)=>{
        const result=await original(...args);if(args[0]==='/api/live'){window.fetch=original;resolve(true)}return result}})`);
      assert.deepEqual(await read(),uncertain);
      publish(2,sequence,frames[0]); assert.deepEqual(await read(),uncertain);
      phase = 'terminal-recovery';
      publish(3); await wait(`${row}?.getAttribute('aria-label')?.includes('Error')`);
      const terminal = await read(); assert.equal(terminal.running,false);
      const result={status:'ok',browser:version.product,initial,uncertain,terminal,extras:extraState,
        reload:true,reconnect:true,stale_event_rejected:true,synthetic:true,model_requests:0};
      await fs.writeFile(path.join(output,'result.json'),JSON.stringify(result,null,2));
      console.log(JSON.stringify(result)); await command('Browser.close'); return;
    }
    publish(1); await wait(`${row} && !${row}.classList.contains('watch-running')`);
    const terminal = await read();
    assert.match(terminal.label,/Aborted.*quota limit/); assert.equal(terminal.count,5);
    assert.equal(terminal.ccost,initial.ccost); assert.equal(terminal.calls,initial.calls);
    const terminalSequence = sequence;
    publish(1,terminalSequence,frames[0]); // Duplicate active body must not replace terminal truth.
    assert.equal((await read()).running,false);
    publish(2,terminalSequence+1); await wait(`${row}?.closest('.watch-history')`);
    const historical = await read(); assert.equal(historical.duration,terminal.duration);
    assert.equal(historical.running,false);
    const reloaded = event('Page.loadEventFired',sessionId);
    await command('Page.reload',{},sessionId); await reloaded;
    await wait(`${row}?.closest('.watch-history')`);
    assert.deepEqual(await read(),historical);
    for (const stream of streams) stream.end(); // Real EventSource reconnect, no new acquisition owner.
    await evaluate(`new Promise(resolve=>{const original=fetch;window.fetch=async(...args)=>{
      const result=await original(...args);if(args[0]==='/api/live'){window.fetch=original;resolve(true)}return result}})`);
    publish(2); await wait(`window.last?.view.now_ms===${frames[2].view.now_ms} && ${row}?.closest('.watch-history')`);
    assert.deepEqual(await read(),historical);
    const result = {status:'ok',browser:version.product,initial,terminal,historical,
      reload:true,reconnect:true,stale_event_rejected:true,model_requests:0};
    await fs.writeFile(path.join(output,'result.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
    await command('Browser.close');
  } finally {
    clearTimeout(deadline); child.kill();
    for (const stream of streams) stream.end(); server.closeAllConnections(); server.close();
  }
}
main().catch(error=>{console.error(error);process.exitCode=1});
