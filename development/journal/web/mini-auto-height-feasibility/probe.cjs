// FR 000591 measurement only: native APIs, no synthetic activation overrides.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const {spawn} = require('node:child_process');
const [executable, output] = process.argv.slice(2);

async function main() {
  assert.ok(path.isAbsolute(executable) && path.isAbsolute(output));
  await fs.stat(executable);
  const profile = await fs.mkdtemp(path.join(path.dirname(output), 'pip-feasibility-profile-'));
  const server = http.createServer((request, response) => {
    response.writeHead(200, {'Content-Type':'text/html; charset=utf-8'});
    response.end(`<!doctype html><html><body><button id="open">Open diagnostic PiP</button>
      <script>
      document.querySelector('#open').addEventListener('click', async () => {
        try {
          window.beforeOpenActivation = navigator.userActivation.isActive;
          window.probePiP = await documentPictureInPicture.requestWindow({
            width:650, height:300, preferInitialWindowPlacement:true});
          probePiP.document.body.innerHTML = '<p data-probe-pip>Native PiP feasibility only</p>';
          window.openFinished = true;
        } catch (error) { window.openError = {name:error.name, message:error.message}; }
      });
      </script></body></html>`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = spawn(executable, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir='+profile, 'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const closed = new Promise(resolve => browser.once('exit', resolve));
  const pending = new Map();
  let sequence = 0, buffer = '';
  browser.stdio[4].on('data', chunk => {
    buffer += chunk.toString();
    let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0,index));
      buffer = buffer.slice(index+1);
      const request = pending.get(value.id);
      if (request) {
        pending.delete(value.id); clearTimeout(request.timer);
        value.error ? request.reject(new Error(JSON.stringify(value.error))) : request.resolve(value.result);
      }
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve,reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => {pending.delete(id); reject(new Error('CDP timeout: '+method));},10000);
    pending.set(id,{resolve,reject,timer});
    browser.stdio[3].write(JSON.stringify({id,method,params,...(sessionId ? {sessionId} : {})})+'\0');
  });
  const evaluate = async (expression, sessionId) => {
    const result = await command('Runtime.evaluate', {
      expression, returnByValue:true, awaitPromise:true, userGesture:false}, sessionId);
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const until = async (expression, sessionId) => {
    const deadline = Date.now()+10000;
    while (Date.now()<deadline) {
      if (await evaluate(expression,sessionId)) return;
      await new Promise(resolve => setTimeout(resolve,25));
    }
    throw new Error('Condition not reached: '+expression);
  };
  const result = {frId:'000591', measuredAt:new Date().toISOString(),
    fixture:'Minimal loopback document; no product changes, real source, or credentials',
    mode:'Strictly headless, disposable profile, CDP input to open; every evaluation userGesture:false',
    physicalDesktopGeometry:'UNVERIFIED', cases:[]};
  const deadline = setTimeout(() => browser.kill(),45000);
  try {
    result.browser = await command('Browser.getVersion');
    const {targetId} = await command('Target.createTarget',{url:'about:blank'});
    const {sessionId:ownerSession} = await command('Target.attachToTarget',{targetId,flatten:true});
    await command('Page.enable',{},ownerSession);
    await command('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/`},ownerSession);
    await until(`!!document.querySelector('#open')`,ownerSession);
    result.support = await evaluate(`({secure:isSecureContext, requestWindow:typeof window.documentPictureInPicture?.requestWindow})`,ownerSession);
    const point = await evaluate(`(() => {const r=document.querySelector('#open').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`,ownerSession);
    for (const type of ['mousePressed','mouseReleased']) {
      await command('Input.dispatchMouseEvent',{type,button:'left',clickCount:1,...point},ownerSession);
    }
    await until(`window.openFinished || window.openError`,ownerSession);
    result.open = await evaluate(`({finished:!!window.openFinished,error:window.openError || null,activationAtClick:window.beforeOpenActivation})`,ownerSession);
    if (!result.open.finished) throw new Error('Genuine headless PiP opening failed');
    const targets = await command('Target.getTargets');
    let pipSession;
    for (const target of targets.targetInfos.filter(item => item.targetId !== targetId && item.type === 'page')) {
      const attached = await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
      if (await evaluate(`!!document.querySelector('[data-probe-pip]')`,attached.sessionId)) {
        pipSession = attached.sessionId; break;
      }
    }
    assert.ok(pipSession,'Actual PiP target available');
    const read = () => evaluate(`(() => {const w=probePiP;return {
      activation:{opener:navigator.userActivation.isActive,pip:w.navigator.userActivation.isActive},
      outer:{width:w.outerWidth,height:w.outerHeight},inner:{width:w.innerWidth,height:w.innerHeight}};})()`,ownerSession);
    for (const context of ['opener','pip']) {
      for (const method of ['resizeTo','resizeBy']) {
        await until(`!navigator.userActivation.isActive && !probePiP.navigator.userActivation.isActive`,ownerSession);
        const before = await read();
        assert.deepEqual(before.activation,{opener:false,pip:false});
        const win = context === 'opener' ? 'probePiP' : 'window';
        const call = method === 'resizeTo' ? 'w.resizeTo(w.outerWidth,w.outerHeight+61)' : 'w.resizeBy(0,-47)';
        const invocation = await evaluate(`(() => {const w=${win};const activation={
          opener:${context === 'opener' ? 'navigator' : 'opener.navigator'}.userActivation.isActive,
          pip:w.navigator.userActivation.isActive};
          try {${call};return {activation,returned:true,error:null};}
          catch(error) {return {activation,returned:false,error:{name:error.name,message:error.message}};}})()`,
          context === 'opener' ? ownerSession : pipSession);
        assert.deepEqual(invocation.activation,{opener:false,pip:false});
        await evaluate(`new Promise(resolve=>probePiP.requestAnimationFrame(()=>probePiP.requestAnimationFrame(resolve)))`,ownerSession);
        result.cases.push({context,method,userGesture:false,
          requestedHeightDelta:method === 'resizeTo' ? 61 : -47,before,invocation,after:await read()});
      }
    }
    result.outcome = 'MEASURED';
  } catch (error) {
    result.outcome = 'SETUP_OR_MEASUREMENT_FAILURE';
    result.failure = error.message;
  } finally {
    clearTimeout(deadline);
    try { await command('Browser.close'); } catch (_) { browser.kill(); }
    await closed;
    await new Promise(resolve => server.close(resolve));
    await fs.writeFile(output, JSON.stringify(result,null,2)+'\n');
  }
  console.log(JSON.stringify(result,null,2));
  if (result.outcome !== 'MEASURED') process.exitCode = 1;
}
main().catch(error => {console.error(error.message);process.exitCode=1;});
