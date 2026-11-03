// Owned headless Chrome, synthetic Watch only. Raster pixels are not desktop proof.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const {inflateSync} = require('node:zlib');
const {createHash} = require('node:crypto');
const [browser, output, baseline] = process.argv.slice(2);
function paintedSpan(png, row, magenta=false) {
  const width=png.readUInt32BE(16),height=png.readUInt32BE(20),channels=png[25]===2?3:4;
  assert.equal(png[24],8);assert.ok([2,6].includes(png[25]));assert.ok(row>=0 && row<height);
  const chunks=[];
  for (let offset=8;offset<png.length;) {
    const length=png.readUInt32BE(offset);
    if (png.toString('ascii',offset+4,offset+8)==='IDAT') chunks.push(png.subarray(offset+8,offset+8+length));
    offset+=length+12;
  }
  const raw=inflateSync(Buffer.concat(chunks)),stride=width*channels;
  let prior=Buffer.alloc(stride),current;
  for (let y=0;y<=row;y++) {
    const offset=y*(stride+1),filter=raw[offset];current=Buffer.alloc(stride);
    for (let x=0;x<stride;x++) {
      const a=x>=channels?current[x-channels]:0,b=prior[x],c=x>=channels?prior[x-channels]:0,p=a+b-c;
      const pa=Math.abs(p-a),pb=Math.abs(p-b),pc=Math.abs(p-c);
      const predictor=[0,a,b,Math.floor((a+b)/2),pa<=pb&&pa<=pc?a:pb<=pc?b:c][filter];
      current[x]=(raw[offset+1+x]+predictor)&255;
    }
    prior=current;
  }
  const background=[...current.subarray(0,3)],pixels=[];
  for (let x=0;x<width;x++) {
    const rgb=[...current.subarray(x*channels,x*channels+3)];
    if (magenta?rgb[0]===255&&rgb[1]===0&&rgb[2]===255:rgb.some((value,i)=>value!==background[i])) pixels.push(x);
  }
  assert.ok(pixels.length);return {left:pixels[0],right:pixels.at(-1),width:pixels.at(-1)-pixels[0]+1};
}
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.mkdir(output, {recursive:true});
  const server = spawn('py', ['-3', 'development/tests/integration/serve_web_watch.py'], {windowsHide:true,stdio:['ignore','pipe','pipe']});
  const ready = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const profile = await fs.mkdtemp(path.join(output,'owned-profile-'));
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check',
    '--disable-extensions','--disable-background-networking','--remote-debugging-pipe','--user-data-dir='+profile,
    'about:blank'], {windowsHide:true,stdio:['ignore','ignore','ignore','pipe','pipe']});
  let sequence=0, buffer=''; const pending=new Map();
  child.stdio[4].on('data', chunk => {
    buffer+=chunk.toString(); let index;
    while ((index=buffer.indexOf('\0'))>=0) {
      const value=JSON.parse(buffer.slice(0,index)); buffer=buffer.slice(index+1);
      const entry=pending.get(value.id);
      if (entry) {pending.delete(value.id); clearTimeout(entry.timer); value.error?entry.reject(new Error(JSON.stringify(value.error))):entry.resolve(value.result);}
    }
  });
  const command=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence, timer=setTimeout(()=>reject(new Error('CDP timeout: '+method)),15000);
    pending.set(id,{resolve,reject,timer});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');
  });
  const deadline=setTimeout(()=>{child.kill();server.kill();},120000);
  const cases=[];
  try {
    assert.match((await ready.next()).value,/Watch fixture ready/);
    const version=await command('Browser.getVersion');
    const {targetId}=await command('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await command('Target.attachToTarget',{targetId,flatten:true});
    const evaluate=async expression=>{
      const result=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);
      assert.equal(result.exceptionDetails,undefined,JSON.stringify(result.exceptionDetails));return result.result.value;
    };
    for (const dpr of [1,1.5,1.875,2.25]) for (const theme of ['classic','light','dark'])
        for (const [width,height] of [[360,800],[1280,400],[1280,900]]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:dpr,mobile:false},sessionId);
      await command('Page.navigate',{url:'http://127.0.0.1:18754/case.html?theme='+theme},sessionId);
      await evaluate(`new Promise(resolve=>{if(document.readyState==='complete')resolve();else addEventListener('load',resolve,{once:true});})`);
      for (const font of [100,150,200]) for (const count of [1,3]) {
        const geometry=await evaluate(`(() => {
          window.originalAccounts ||= structuredClone(INPUT.view.accounts.accounts);
          INPUT.view.accounts.accounts=structuredClone(originalAccounts.slice(0,${count}));
          INPUT.view.accounts.accounts[0].observation.label='Long subscription identity Å日本語 '+ 'unbroken'.repeat(12);
          document.documentElement.style.fontSize='${15*font/100}px'; redraw();
          const cards=[...document.querySelectorAll('.watch-subscription')],first=cards[0],grid=first.parentNode;
          const style=getComputedStyle(first),r=first.getBoundingClientRect();
          return {dpr:devicePixelRatio,viewportScale:visualViewport.scale,innerWidth,innerHeight,cssWidths:cards.map(n=>n.getBoundingClientRect().width),
            computedWidth:style.width,maxWidth:style.maxWidth,boxSizing:style.boxSizing,tracks:getComputedStyle(grid).gridTemplateColumns,
            rootFont:getComputedStyle(document.documentElement).fontSize,overflow:document.documentElement.scrollWidth>innerWidth,
            readable:cards.every(n=>[n,...n.querySelectorAll('h4,p,.watch-quota-summary')].every(v=>v.scrollWidth<=v.clientWidth && v.scrollHeight<=v.clientHeight)),
            text:first.textContent,left:r.left,gridLeft:grid.getBoundingClientRect().left};})()`);
        assert.equal(geometry.dpr,dpr);assert.equal(geometry.viewportScale,1);
        assert.equal(geometry.overflow,false);assert.equal(geometry.readable,true,JSON.stringify({dpr,theme,font,count,geometry}));
        assert.ok(Math.abs(geometry.left-geometry.gridLeft)<1);
        if (!baseline) assert.ok(geometry.cssWidths.every(value=>value*dpr<=450),JSON.stringify(geometry));
        cases.push({theme,font,count,...geometry});
        if (theme==='classic' && font===100 && count===1 && width===1280 && height===900) {
          await evaluate(`(() => {const card=document.querySelector('.watch-subscription');card.scrollIntoView();
            const ruler=document.createElement('div');ruler.id='pixel-ruler';ruler.textContent='450 raster pixels';
            Object.assign(ruler.style,{width:(450/devicePixelRatio)+'px',height:'20px',background:'#ff00ff',color:'#000',font:'12px sans-serif',marginBottom:'4px'});
            card.parentNode.parentNode.insertBefore(ruler,card.parentNode);document.body.style.paddingBottom='1000px';
            window.scrollTo(0,ruler.getBoundingClientRect().top+scrollY-20);})()`);
          const rect=await evaluate(`(() => {const r=document.querySelector('.watch-subscription').getBoundingClientRect();return {x:r.x,y:r.y+scrollY,width:r.width,height:r.height};})()`);
          const image=await command('Page.captureScreenshot',{format:'png',clip:{...rect,scale:1},captureBeyondViewport:true},sessionId);
          const bytes=Buffer.from(image.data,'base64'),rasterWidth=bytes.readUInt32BE(16);
          assert.ok(Math.abs(rasterWidth-rect.width*dpr)<=1,'PNG raster density agrees with DPR');
          if (!baseline) assert.ok(rasterWidth<=450,'actual captured card border-box raster <=450');
          const name=`${baseline?'before':'after'}-${dpr}.png`;await fs.writeFile(path.join(output,name),bytes);
          const screenshot=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sessionId);
          const full=Buffer.from(screenshot.data,'base64');await fs.writeFile(path.join(output,`ruler-${name}`),full);
          const rows=await evaluate(`({card:Math.floor((document.querySelector('.watch-subscription').getBoundingClientRect().bottom-10)*devicePixelRatio),ruler:Math.floor((document.getElementById('pixel-ruler').getBoundingClientRect().bottom-2)*devicePixelRatio)})`);
          const painted=paintedSpan(full,rows.card),ruler=paintedSpan(full,rows.ruler,true);
          // Fractional CSS positioning can leave one antialiased edge pixel;
          // only fully saturated magenta pixels are counted in the ruler.
          assert.ok(ruler.width>=449 && ruler.width<=450,'450-pixel ruler calibration');
          assert.equal(full.readUInt32BE(16),width*dpr,'uncropped PNG density');
          if (!baseline) assert.ok(painted.width<=450,'painted border-box span in uncropped raster');
          cases.at(-1).screenshot={name,rasterWidth,cssClipWidth:rect.width,painted,ruler};
          await evaluate(`document.getElementById('pixel-ruler').remove();document.body.style.paddingBottom=''`);
        }
      }
    }
    // Resolution changes must resize existing cards, even with focus and no publication.
    if (!baseline) {
      await evaluate(`document.querySelector('.watch-period-cost').focus();window.retainedFocus=document.activeElement;window.retainedCard=document.querySelector('.watch-subscription')`);
      await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1.5,mobile:false},sessionId);
      await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
      assert.equal(await evaluate(`document.activeElement===retainedFocus && document.querySelector('.watch-subscription')===retainedCard && retainedCard.getBoundingClientRect().width*devicePixelRatio<=450`),true);
      await command('Emulation.setPageScaleFactor',{pageScaleFactor:1.25},sessionId);
      await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
      assert.equal(await evaluate(`visualViewport.scale===1.25 && retainedCard.getBoundingClientRect().width*devicePixelRatio*visualViewport.scale<=450 && document.activeElement===retainedFocus`),true);
      await command('Emulation.setPageScaleFactor',{pageScaleFactor:1},sessionId);
      for (const [width,height] of [[360,800],[1280,400]]) {
        await command('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1.5,mobile:false},sessionId);
        await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
        assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth && retainedCard.getBoundingClientRect().width*devicePixelRatio<=450 && document.activeElement===retainedFocus`),true);
      }
    }
    let hostEvidence;
    if (!baseline) {
      const host=spawn('py',['-3','development/tests/integration/serve_mini_watch.py'],{windowsHide:true,stdio:['pipe','pipe','pipe']});
      const lines=readline.createInterface({input:host.stdout})[Symbol.asyncIterator]();
      try {
        const launch=JSON.parse((await lines.next()).value); // Private bootstrap remains inside the pipe.
        await command('Page.navigate',{url:launch.url},sessionId);
        const until=async expression=>{
          const end=Date.now()+15000;
          while (Date.now()<end) {if(await evaluate(expression))return;await new Promise(resolve=>setTimeout(resolve,50));}
          throw new Error('Production host condition not reached');
        };
        await until(`typeof hostState!=='undefined' && hostState.kind==='connected'`);
        await evaluate(`location.hash='#/watch'`);await until(`!!document.querySelector('.watch-subscription')`);
        const assets=await evaluate(`Promise.all(['/app.css','/watch.js'].map(async name=>{
          const response=await fetch(name),bytes=await response.arrayBuffer();
          const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
          return {name,hash,cache:response.headers.get('Cache-Control'),csp:response.headers.get('Content-Security-Policy')};}))`);
        for (const asset of assets) {
          assert.equal(asset.hash,createHash('sha256').update(await fs.readFile('src/web/assets'+asset.name)).digest('hex'));
          assert.equal(asset.cache,'no-store');assert.match(asset.csp,/style-src 'self'/);
        }
        const check=()=>evaluate(`({version:document.getElementById('product-version').textContent.trim(),
          widths:[...document.querySelectorAll('.watch-subscription')].map(n=>n.getBoundingClientRect().width*devicePixelRatio),
          cap:getComputedStyle(document.querySelector('.watch-subscription')).maxWidth,inlineErrors:!!document.querySelector('style'),
          value:document.querySelector('.watch-subscription').textContent})`);
        const before=await check();assert.ok(before.widths.every(n=>n<=450));assert.equal(before.inlineErrors,false);
        assert.match(before.version,/^v80\./);assert.match(before.value,/CCost Today.*used/);
        await command('Page.reload',{},sessionId);await until(`!!document.querySelector('.watch-subscription') && hostState.kind==='connected'`);
        const after=await check();assert.deepEqual(after,before);
        hostEvidence={assets,version:before.version,physicalWidthEstimates:before.widths,maxWidth:before.cap,reloadStable:true};
      } finally {
        host.stdin.end();if(host.exitCode===null)await new Promise(resolve=>host.once('exit',resolve));
      }
    }
    await fs.writeFile(path.join(output,'geometry.json'),JSON.stringify({browser:version.product,baseline:!!baseline,cases,hostEvidence,
      limitations:['CDP device metrics emulate effective scale, not Windows OS settings or real Chrome page zoom; no owner desktop measurement.']},null,2)+'\n');
    console.log(JSON.stringify({outcome:'PASS',browser:version.product,cases:cases.length,output}));
  } finally {
    clearTimeout(deadline);try {await command('Browser.close');} catch {child.kill();}
    if (child.exitCode===null) await new Promise(resolve=>child.once('exit',resolve));
    await fetch('http://127.0.0.1:18754/stop').catch(()=>server.kill());
    if (server.exitCode===null) await new Promise(resolve=>server.once('exit',resolve));
    await fs.rm(profile,{recursive:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
