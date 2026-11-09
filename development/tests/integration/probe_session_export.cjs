// Hidden, owned Chromium only. Native dialog success is NOT claimed by this probe.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  const directory = path.dirname(output);
  const profile = await fs.mkdtemp(path.join(directory, 'export-browser-'));
  const workspace = await fs.mkdtemp(path.join(directory, 'export-host-'));
  const downloads = await fs.mkdtemp(path.join(directory, 'export-download-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_session_export.py', workspace],
    {windowsHide:true, stdio:['pipe','pipe','pipe']});
  const serverExit = new Promise(resolve => server.once('exit', resolve));
  let serverError = ''; server.stderr.on('data', value => serverError += value.toString());
  const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const fixture = async command => { server.stdin.write(JSON.stringify({command})+'\n'); return JSON.parse((await lines.next()).value); };
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-background-networking', '--remote-debugging-pipe', '--user-data-dir='+profile, 'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const browserExit = new Promise(resolve => child.once('exit', resolve));
  const pending = new Map(); let sequence = 0, buffer = '', sessionId;
  child.stdio[4].on('data', value => {
    buffer += value.toString(); let end;
    while ((end = buffer.indexOf('\0')) >= 0) {
      const message = JSON.parse(buffer.slice(0, end)); buffer = buffer.slice(end+1);
      if (pending.has(message.id)) {
        const entry = pending.get(message.id); pending.delete(message.id); clearTimeout(entry.timer);
        message.error ? entry.reject(new Error(message.error.message)) : entry.resolve(message.result);
      }
    }
  });
  const command = (method, params={}, target=sessionId) => new Promise((resolve,reject) => {
    const id = ++sequence, timer = setTimeout(() => reject(new Error('CDP timeout: '+method)), 15000);
    pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(target?{sessionId:target}:{})})+'\0');
  });
  const evaluate = async expression => {
    const result = await command('Runtime.evaluate', {expression,returnByValue:true,awaitPromise:true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const until = async (check, label) => {
    const end = Date.now()+15000;
    while (Date.now()<end) { if (await check()) return; await new Promise(resolve=>setTimeout(resolve,50)); }
    throw new Error('Condition timeout: '+label);
  };
  const click = async () => {
    const point = await evaluate('(() => {const r=current.detail.exporter.button.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()');
    await command('Input.dispatchMouseEvent', {type:'mousePressed',button:'left',clickCount:1,...point});
    await command('Input.dispatchMouseEvent', {type:'mouseReleased',button:'left',clickCount:1,...point});
  };
  let evidence = {outcome:'FAIL'};
  const deadline = setTimeout(() => {child.kill();server.kill();}, 90000);
  try {
    const ready = await lines.next();
    if (ready.done) throw new Error('Fixture failed: '+serverError);
    const launch = JSON.parse(ready.value);
    const version = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget', {url:'about:blank'});
    ({sessionId} = await command('Target.attachToTarget', {targetId,flatten:true}));
    await command('Page.enable');
    await command('Page.navigate', {url:launch.url});
    await until(()=>evaluate('typeof csrf !== "undefined" && !!csrf && hostState.kind === "connected"'), 'authorization');
    await evaluate(`location.hash='#/sessions/${launch.session}'`);
    await until(()=>evaluate('!!current?.detail?.data && !current.detail.exporter.button.disabled'), 'observed selection');
    const layouts = [];
    for (const width of [1280,360]) {
      await command('Emulation.setDeviceMetricsOverride', {width,height:900,deviceScaleFactor:1,mobile:false});
      layouts.push(await evaluate('({width:innerWidth,noPageOverflow:document.documentElement.scrollWidth<=innerWidth,buttonHeight:current.detail.exporter.button.getBoundingClientRect().height,rows:current.detail.body.children.length})'));
    }
    assert.ok(layouts.every(value=>value.noPageOverflow && value.rows===3));
    const before = (await fixture('count')).requests;
    // Real API invoked from trusted user activation. Headless Chromium aborts its
    // unsupported native dialog; record this separately from mocked save proof.
    await evaluate(`window.pickerProbe={available:typeof showSaveFilePicker==='function'};
      if(pickerProbe.available){const original=showSaveFilePicker;window.showSaveFilePicker=async options=>{
        pickerProbe.activation=navigator.userActivation.isActive;try{return await original(options);}catch(error){pickerProbe.error=error.name;throw error;}};}`);
    await click();
    await until(()=>evaluate('!current.detail.exporter.operation'), 'native picker cancellation');
    const picker = await evaluate('pickerProbe');
    assert.equal((await fixture('count')).requests, before, 'cancelled picker performs no native export');
    // Actual authenticated standard browser download, no picker support.
    await evaluate('window.showSaveFilePicker=undefined');
    await command('Browser.setDownloadBehavior', {behavior:'allow',downloadPath:downloads}, null);
    await evaluate('current.detail.exporter.button.focus()');
    await click();
    const filename = `opencode-${launch.session}-sanitized.json`;
    await until(async()=>{try{await fs.access(path.join(downloads,filename));return true;}catch{return false;}}, 'download');
    const transfer = JSON.parse(await fs.readFile(path.join(downloads,filename),'utf8'));
    assert.equal(transfer.info.id,launch.session); assert.equal(transfer.messages.length,3);
    assert.equal(transfer.messages[1].outcome,'succeeded'); assert.equal(transfer.messages[2].type,'user');
    assert.equal(await evaluate('document.activeElement === current.detail.exporter.button'),true);
    await until(()=>evaluate('current.detail.exporter.url === null'), 'object URL release');
    await fixture('invalid');
    await click();
    await until(()=>evaluate('current.detail.exporter.notice.textContent.includes("incomplete export")'), 'malformed source feedback');
    assert.deepEqual(await fs.readdir(downloads),[filename], 'no corrupt second download');
    await evaluate('location.hash="#/settings"');
    await until(()=>evaluate('current.section === "settings"'), 'navigation');
    evidence = {outcome:'PASS',browser:version.product,layouts,native_picker:picker,
      checks:['canonical selected detail','trusted-click picker activation/cancel without source work',
        'authenticated fallback file has native lifecycle/types/unicode','focus retained','object URL released',
        'malformed export saves no partial file','navigation preserved'],
      limitations:['Hidden native picker abort only; actual visible destination selection/write/cancel remains unverified.',
        'Synthetic LIVE-style native service, no Desktop session-list visibility assertion.'],
      inference_calls:0,desktop_effects:false};
  } catch(error) {evidence.error=error.stack; evidence.serverError=serverError;}
  finally {
    await command('Browser.close',{},null).catch(()=>{}); await browserExit;
    server.stdin.write('{"command":"stop"}\n'); server.stdin.end(); await serverExit;
    clearTimeout(deadline);
    for (const entry of pending.values()) clearTimeout(entry.timer);
    await fs.rm(profile,{recursive:true,force:true}); await fs.rm(workspace,{recursive:true,force:true}); await fs.rm(downloads,{recursive:true,force:true});
    await fs.writeFile(output,JSON.stringify(evidence,null,2)+'\n');
  }
  console.log(JSON.stringify(evidence));
  assert.equal(evidence.outcome,'PASS');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
