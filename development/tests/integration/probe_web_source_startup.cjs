// Owned headless Chromium + synthetic production HTTP host. No shared desktop.
const assert = require('node:assert/strict'), path = require('node:path'), fs = require('node:fs/promises');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output, python] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.mkdir(output,{recursive:true});
  const profile = await fs.mkdtemp(path.join(output,'startup-profile-'));
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check',
    '--disable-extensions','--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],
    {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence = 0, buffer = '';
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0,index)); buffer = buffer.slice(index+1);
      const entry = pending.get(value.id); pending.delete(value.id);
      if (entry) value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result);
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve,reject) => {
    const id = ++sequence; pending.set(id,{resolve,reject});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId ? {sessionId} : {})})+'\0');
  });
  const deadline = setTimeout(() => child.kill(), 60000);
  const cases = [];
  try {
    for (const mode of ['success','failure','ai-stats']) {
      const server = spawn(python || 'py', [...(python ? [] : ['-3']),'development/tests/integration/serve_web_source_startup.py',mode==='ai-stats'?'success':mode,...(mode==='ai-stats'?['--ai-stats']:[])],
        {windowsHide:true,stdio:['pipe','pipe','pipe']});
      const lines = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
      let errors = ''; server.stderr.on('data', chunk => errors += chunk.toString());
      const serverDeadline = setTimeout(() => server.kill(), 40000);
      try {
        const first = await lines.next(); assert.equal(first.done,false,errors);
        const {url} = JSON.parse(first.value);
        const tabs = [];
        for (let index=0;index<2;index++) {
          const {targetId} = await command('Target.createTarget',{url:'about:blank'});
          const {sessionId} = await command('Target.attachToTarget',{targetId,flatten:true});
          await command('Target.activateTarget',{targetId});
          const evaluate = async expression => {
            const value = await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);
            assert.equal(value.exceptionDetails,undefined,JSON.stringify(value.exceptionDetails));
            return value.result.value;
          };
          await command('Page.navigate',{url:index ? url.split('/#')[0]+'/#/watch' : url},sessionId);
          if (!index && mode==='ai-stats') await evaluate(`new Promise(resolve=>{const end=Date.now()+5000;const check=()=>{
            if(typeof csrf!=='undefined'&&csrf){location.hash='#/ai-stats';resolve(true);}else if(Date.now()>end)resolve(false);else setTimeout(check,20);};check();})`);
          await evaluate(`new Promise(resolve=>{const end=Date.now()+8000;const check=()=>{
            if(document.getElementById('host-warning')?.textContent==='Starting OpenCode server…')resolve(true);
            else if(Date.now()>end)resolve(false);else setTimeout(check,20);};check();})`).then(async value=>assert.equal(value,true,
              JSON.stringify({mode,index,errors,state:await evaluate(`({warning:document.getElementById('host-warning')?.textContent,status:document.getElementById('status')?.textContent,section:typeof current==='undefined'?null:current?.section})`)})));
          tabs.push({targetId,sessionId,evaluate});
        }
        assert.equal(await tabs[0].evaluate(`document.getElementById('host-state').hidden`),false);
        assert.equal(await tabs[0].evaluate(`document.getElementById('status').getAttribute('role')`),'status');
        // Refresh/route changes remain responsive and cannot become launch authority.
        await command('Target.activateTarget',{targetId:tabs[0].targetId});
        assert.equal(await tabs[0].evaluate(`new Promise(resolve=>{const end=Date.now()+3000;const check=()=>{
          if(current.stage==='Waiting for source…')resolve(true);else if(Date.now()>end)resolve(false);else setTimeout(check,20);};check();})`),true);
        const waitingCode = await tabs[0].evaluate(`api('/api/status').then(value=>value.report_source.error)`);
        assert.equal(waitingCode,'source_starting');
        await tabs[0].evaluate(`location.hash='#/settings';true`);
        await tabs[0].evaluate(`new Promise(resolve=>setTimeout(()=>resolve(document.body.dataset.section),50))`).then(value=>assert.equal(value,'settings'));
        await tabs[0].evaluate(`location.hash='#/${mode==='ai-stats'?'ai-stats':'models'}';true`);
        server.stdin.write('counts\n');
        assert.deepEqual(JSON.parse((await lines.next()).value),{wake:1,acquire:0});
        server.stdin.write('release\n');
        const waitFor = expression => tabs[0].evaluate(`new Promise(resolve=>{const end=Date.now()+10000;const check=()=>{
          if(${expression})resolve(true);else if(Date.now()>end)resolve(false);else setTimeout(check,30);};check();})`);
        if (mode!=='failure') {
          const complete = await waitFor(`current?.result && !current.loading`);
          assert.equal(complete,true,await tabs[0].evaluate(`JSON.stringify({notice:document.getElementById('notice').textContent,result:document.getElementById('result').textContent,status:document.getElementById('status').textContent})`)+errors);
          assert.equal(await waitFor(`document.getElementById('host-state').hidden && document.getElementById('status').textContent==='Live connected.'`),true);
        } else {
          assert.equal(await waitFor(`document.getElementById('host-message').textContent.includes('Start OpenCode manually')`),true);
        }
        assert.notEqual(await tabs[0].evaluate(`document.getElementById('host-warning').textContent`),'Starting OpenCode server…');
        await command('Page.reload',{},tabs[1].sessionId);
        await tabs[1].evaluate(`new Promise(resolve=>setTimeout(()=>resolve(true),200))`);
        server.stdin.write('counts\n'); const counts = JSON.parse((await lines.next()).value);
        assert.equal(counts.wake,1); assert.equal(counts.acquire,mode!=='failure'?1:0);
        for (const tab of tabs) await command('Target.closeTarget',{targetId:tab.targetId});
        cases.push({mode,startingVisible:true,accessibleStatus:true,navigationResponsive:true,
          automaticReadiness:mode!=='failure',truthfulFallback:mode==='failure',wakeCount:counts.wake,waitingCode});
      } finally {
        server.stdin.end('stop\n');
        await new Promise(resolve=>server.once('exit',resolve));
        clearTimeout(serverDeadline);
      }
    }
    console.log(JSON.stringify({browser:(await command('Browser.getVersion')).product,cases}));
  } finally {clearTimeout(deadline);child.kill();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
