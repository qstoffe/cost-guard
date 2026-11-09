// Shipped authenticated UI in an owned hidden Chromium; manually stepped work, no private data.
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {spawn}=require('node:child_process'),readline=require('node:readline');
const [browser,outputPath]=process.argv.slice(2),output=path.resolve(outputPath);
async function main(){
  await fs.mkdir(output,{recursive:true});await fs.stat(browser);
  const profile=await fs.mkdtemp(path.join(output,'loading-browser-'));
  const config=await fs.mkdtemp(path.join(output,'loading-config-'));
  const server=spawn('py',['-3','development/tests/integration/serve_mini_watch.py',config,'--report-loading'],{windowsHide:true,stdio:['pipe','pipe','pipe']});
  const lines=readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  let serverErrors='';server.stderr.on('data',b=>serverErrors+=b.toString());
  const fixture=async command=>{server.stdin.write(JSON.stringify({command:'loading-'+command})+'\n');assert.equal(JSON.parse((await lines.next()).value).ok,true);};
  const child=spawn(browser,['--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
    '--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  let sequence=0,buffer='',tab;const pending=new Map(),errors=[];
  child.stdio[4].on('data',chunk=>{buffer+=chunk.toString();let i;while((i=buffer.indexOf('\0'))>=0){
    const value=JSON.parse(buffer.slice(0,i));buffer=buffer.slice(i+1);const entry=pending.get(value.id);
    if(entry){pending.delete(value.id);clearTimeout(entry.timer);value.error?entry.reject(new Error(JSON.stringify(value.error))):entry.resolve(value.result);}
    else if(value.method==='Runtime.exceptionThrown')errors.push(value.params.exceptionDetails.text);
  }});
  const command=(method,params={},sessionId=tab)=>new Promise((resolve,reject)=>{const id=++sequence;
    const timer=setTimeout(()=>reject(new Error('CDP timeout: '+method)),20000);pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');});
   const evaluate=async (expression,target=tab)=>{const value=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},target);
    assert.equal(value.exceptionDetails,undefined,JSON.stringify(value.exceptionDetails));return value.result.value;};
   const until=async (expression,target=tab)=>{const ready=await evaluate(`new Promise(resolve=>{const end=Date.now()+10000;const check=()=>{
     if(${expression})resolve(true);else if(Date.now()>end)resolve(false);else setTimeout(check,30);};check();})`,target);
    assert.equal(ready,true,expression+' '+serverErrors+' '+JSON.stringify(await evaluate(`({hidden:document.hidden,section:typeof current==='undefined'?null:current?.section,loading:typeof current==='undefined'?null:current?.loading,progress:typeof current==='undefined'?null:current?.progressSequence,message:typeof current==='undefined'?null:current?.message})`)));};
  const facts=[],layouts=[];let outcome='FAIL',failure=null;
  const deadline=setTimeout(()=>{console.error('Report-loading probe exceeded 180s');child.kill();server.kill();},180000);
  const noCancel=async()=>{
    assert.equal(await evaluate(`!document.querySelector('#cancel') &&
      ![...document.querySelectorAll('button,[role="button"]')].some(node=>/^(cancel|stop loading|abort)$/i.test(node.textContent.trim()))`),true);
    const ax=await command('Accessibility.getFullAXTree');
    assert.equal(ax.nodes.some(n=>n.role?.value==='button' && /^(cancel|stop loading|abort)$/i.test(n.name?.value||'')),false);
  };
  try{
    const launch=JSON.parse((await lines.next()).value);
    const target=await command('Target.createTarget',{url:'about:blank'});
    tab=(await command('Target.attachToTarget',{targetId:target.targetId,flatten:true})).sessionId;
    await command('Target.activateTarget',{targetId:target.targetId});
    await command('Page.enable');await command('Runtime.enable');
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
    await command('Page.navigate',{url:launch.url});
    await until(`typeof current!=='undefined' && current?.active && document.querySelector('.report-loading')`);
    for(const section of ['models','token-mix','ai-stats','comparisons']){
      await fixture('hold');
      if(section!=='models')await evaluate(`location.hash='#/${section}'`);
       await until(`current?.section==='${section}' && current.active && document.querySelector('.report-loading')`);
       await noCancel();
      assert.equal(await evaluate(`document.getElementById('refresh').hidden`),true,'no initial Load action');
      await evaluate(`window.__loader=document.querySelector('.report-loading');window.__bar=__loader.querySelector('progress');window.__values=[__bar.value];window.__heights=[__loader.getBoundingClientRect().height];`);
      for(let index=0;index<5;index++){
         await fixture('step');
         await until(section==='ai-stats'?`current.stage.includes('(${index+1}/10 roots)')`:`current.progressSequence>=${index+2}`);
        assert.equal(await evaluate(`__loader===document.querySelector('.report-loading') && __bar===__loader.querySelector('progress')`),true);
        await evaluate(`__values.push(__bar.value);__heights.push(__loader.getBoundingClientRect().height)`);
      }
      const values=await evaluate(`__values`),heights=await evaluate(`__heights`);
      assert.deepEqual(values,[...values].sort((a,b)=>a-b));assert.ok(values.at(-1)<100);
      assert.ok(Math.max(...heights)-Math.min(...heights)<1,'stable changing-stage geometry');
      for(const theme of ['classic','light','dark'])for(const width of [360,1366]){
        await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
        await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'},{name:'prefers-reduced-motion',value:'reduce'}]});
        const layout=await evaluate(`(()=>{document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';
          const r=__loader.getBoundingClientRect(),b=__bar.getBoundingClientRect(),s=__loader.querySelector('.report-loading-stage').getBoundingClientRect();
          return {width:${width},height:r.height,barWidth:b.width,center:Math.abs(b.x+b.width/2-(r.x+r.width/2)),below:s.y>=b.bottom,
            overflow:document.documentElement.scrollWidth>innerWidth,value:__bar.value,max:__bar.max,accessible:__bar.getAttribute('aria-valuetext'),text:__loader.textContent};})()`);
        assert.equal(layout.max,100);assert.equal(layout.below,true);assert.ok(layout.center<1);assert.equal(layout.overflow,false);
        assert.match(layout.accessible,/^\d+ percent$/);assert.doesNotMatch(layout.text,/≈|Approximately|~\d/);
         if(section==='comparisons'){
           const chrome=await evaluate(`({notice:getComputedStyle(document.getElementById('notice')).display,
             search:getComputedStyle(document.querySelector('.report-search')).display,
             pager:getComputedStyle(document.querySelector('.comparisons-view .pager')).visibility})`);
           assert.deepEqual(chrome,{notice:'none',search:'none',pager:'hidden'},'no blank notice or visible empty pager');
         }
         layouts.push({section,theme,...layout});
      }
      const ax=await command('Accessibility.getFullAXTree');assert.ok(ax.nodes.some(n=>n.role?.value==='progressbar'&&n.value?.value===values.at(-1)));
      const image=await command('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(output,section+'.png'),Buffer.from(image.data,'base64'));
        // Existing admitted acquisition continues through route changes and real hidden-tab visibility.
        await evaluate(`window.__state=current;window.__job=current.active;location.hash='#/watch'`);
        await until(`current.section==='watch'`);
        const cover=await command('Target.createTarget',{url:'about:blank'});
        if(section==='comparisons'){
          const peer=(await command('Target.attachToTarget',{targetId:cover.targetId,flatten:true})).sessionId;
          await command('Runtime.enable',{},peer);await command('Page.enable',{},peer);
          await command('Page.navigate',{url:launch.url.split('#')[0]+'#/comparisons'},peer);
          await until(`typeof current!=='undefined' && !!current?.active`,peer);
          assert.equal(await evaluate(`current.active`,peer),await evaluate(`__job`),'competing tab coalesces the original Comparisons job');
        }
        await command('Target.activateTarget',{targetId:cover.targetId});await until(`document.hidden`);
        await fixture('complete');await until(`!__state.loading && !!__state.result`);
        await command('Target.closeTarget',{targetId:cover.targetId});
        await command('Target.activateTarget',{targetId:target.targetId});
        await evaluate(`history.back()`);await until(`current.section==='${section}' && !current.loading`);
        assert.equal(await evaluate(`current===__state && !current.failed && current.percent===100`),true);
        await noCancel();
        assert.equal(await evaluate(`current.percent`),100,'inactive completion is recorded without waiting for a visible animation frame');
      assert.equal(await evaluate(`document.querySelectorAll('.report-loading').length`),0);
       facts.push(section+': no DOM/AX Cancel; automatic entry, monotonic progress, hidden/inactive completion, Back restoration, themes/narrow/reduced-motion');
      await fixture('hold');
      await evaluate(`window.__content=output.firstChild;window.__focus=output.querySelector('button,a');__focus?.focus();acquire(current,true);true`);
       await until(`current.loading && current.active`);
       await noCancel();
       assert.equal(await evaluate(`output.firstChild===__content && !output.querySelector('progress') && (!__focus || document.activeElement===__focus) && !document.getElementById('report-updating')`),true);
      await fixture('step');await fixture('complete');await until(`!current.loading`);
       facts.push(section+': quiet refresh retains data/focus without central loader');
       await fixture('failed');await evaluate(`acquire(current,true);true`);await until(`current.failed && !current.loading`);
       await noCancel();
       assert.equal(await evaluate(`!document.getElementById('refresh').hidden && getComputedStyle(document.querySelector('.toolbar')).display!=='none'`),true);
       await fixture('complete');await evaluate(`acquire(current);true`);await until(`!current.loading && !current.failed`);
       await fixture('source');await evaluate(`acquire(current);true`);
       await until(`current.stage==='Waiting for source…'`);await noCancel();
       await fixture('ready');await until(`!current.loading && !current.failed`);
       facts.push(section+': source wait and genuine failure retain Retry without Cancel');
    }
    // HTTP 429 enters bounded waiting without allocating a duplicate job.
    await fixture('hold');await fixture('busy');
    await evaluate(`acquire(current);true`);await until(`current.stage==='Waiting for report slot…' && !current.active`);
     await noCancel();
     await evaluate(`window.__waiting=current;window.__attempt=current.attempt;location.hash='#/watch'`);
     await until(`current.section==='watch' && !!__waiting.active`);
     assert.equal(await evaluate(`__waiting.attempt===__attempt && !__attempt.reason`),true);
     await fixture('complete');await until(`!__waiting.loading && !__waiting.failed`);
     await evaluate(`history.back()`);await until(`current.section==='comparisons'`);
     facts.push('temporary 429 pending intent survives navigation and admits once with bounded backoff');
    assert.deepEqual(errors,[]);outcome='PASS';console.log(JSON.stringify({outcome,checks:facts.length,layouts:layouts.length}));
   }catch(error){failure=error.stack;console.error(failure);throw error;}finally{
     clearTimeout(deadline);await fs.writeFile(path.join(output,'browser.json'),JSON.stringify({outcome,failure,facts,layouts,errors,
      limitations:['Manually stepped fixture jobs, not production process timing.','No physical screen-reader speech or non-Chromium platform certification.']},null,2));
     server.stdin.end('{"command":"stop"}\n');await command('Browser.close').catch(()=>{});
     if(server.exitCode===null)await new Promise(resolve=>server.once('exit',resolve));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
