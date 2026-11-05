// Focused Full Watch paint/transition proof in an owned hidden Chromium profile.
// Synthetic loopback only; no personal browser, source, provider or model access.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {spawn} = require('node:child_process'), readline = require('node:readline');
const [browser, output] = process.argv.slice(2);
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output));
  await fs.mkdir(output, {recursive:true});
  const profile = await fs.mkdtemp(path.join(output, 'watch-profile-'));
  const server = spawn('py', ['-3', 'development/tests/integration/serve_watch_summary.py'],
    {windowsHide:true, stdio:['ignore','pipe','pipe']});
  const ready = readline.createInterface({input:server.stdout})[Symbol.asyncIterator]();
  const child = spawn(browser, ['--headless=new','--no-first-run','--no-default-browser-check',
    '--disable-extensions','--disable-background-networking','--remote-debugging-pipe',
    '--user-data-dir='+profile,'about:blank'], {windowsHide:true, stdio:['ignore','ignore','ignore','pipe','pipe']});
  const pending = new Map(); let sequence = 0, buffer = '';
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString(); let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0,index)); buffer = buffer.slice(index+1);
      if (!value.id) continue;
      const entry = pending.get(value.id); pending.delete(value.id);
      if (entry) value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result);
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve,reject) => {
    const id = ++sequence; pending.set(id,{resolve,reject});
    child.stdio[3].write(JSON.stringify({id,method,params,...(sessionId ? {sessionId} : {})})+'\0');
  });
  const deadline = setTimeout(() => {child.kill(); server.kill();},90000);
  const cases = [];
  try {
    assert.match((await ready.next()).value, /Synthetic Watch fixture ready/);
    const version = await command('Browser.getVersion');
    for (const [theme,scheme] of [['classic','light'],['web','light'],['web','dark']]) for (const width of [1366,360]) {
      const {targetId} = await command('Target.createTarget',{url:'about:blank'});
      const {sessionId} = await command('Target.attachToTarget',{targetId,flatten:true});
      const evaluate = async expression => {
        const value = await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);
        assert.equal(value.exceptionDetails,undefined,JSON.stringify(value.exceptionDetails));
        return value.result.value;
      };
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},sessionId);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]},sessionId);
      await command('Page.navigate',{url:`http://127.0.0.1:18753/case.html?theme=${theme}&scheme=${scheme}`},sessionId);
      await evaluate(`new Promise(resolve => {const check=()=>typeof state!=='undefined'&&state.watch?resolve(true):setTimeout(check,20);check();})`);
      await evaluate('globalThis.current=state;globalThis.liveValue=INPUT');
      const layouts = [], checks = [];
      await require('./probe_watch_quiet.cjs')({evaluate,layouts,checks});
      const transitions = await evaluate(`(() => {
        const view=state.watch,p=structuredClone(INPUT),value=p.view.active_cards[0],prompt=value.rows[0].prompt;
        const card=[...view.cards.values()][0],history=[...view.cards.values()][1],style=n=>getComputedStyle(n);
        view.earlier.open=true;
        const before={height:view.root.getBoundingClientRect().height,daily:view.daily.textContent,accounts:view.accounts.textContent};
        p.view.daily_state='retrying';view.update(p);
        const quiet=before.height===view.root.getBoundingClientRect().height && before.daily===view.daily.textContent;
        p.view.accounts=null;p.view.daily_usage=null;view.update(p);
        const retained=before.accounts===view.accounts.textContent && before.daily===view.daily.textContent;
        const title=card.title;title.focus({preventScroll:true});
        const focus=document.activeElement;
        Object.assign(prompt,{in_progress:false,completed_successfully:true,aborted:false,has_error:false});view.update(p);
        const success={title:style(title).color,row:style(card.body.firstChild).color,focus:document.activeElement===focus,
          href:title.getAttribute('href'),historical:history.title.className};
        const luminance=color=>color.match(/[\\d.]+/g).slice(0,3).map(Number).map(v=>v/255)
          .map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
        const ink=luminance(success.title),surface=luminance(style(document.body).backgroundColor);
        success.contrast=(Math.max(ink,surface)+.05)/(Math.min(ink,surface)+.05);
        const terminal=[];
        for(const flags of [{completed_successfully:false},{aborted:true},{aborted:false,has_error:true},{has_error:false,in_progress:true}]) {
          Object.assign(prompt,flags);view.update(p);terminal.push({title:title.className,row:card.body.firstChild.className});
        }
        title.blur();
        for(const c of [value,...p.view.history_cards]) {
          c.rows[0].prompt.display.ccost='0';c.rows[0].prompt.display.incoming_context_ccost='N/A';
          c.rows[0].prompt.display_units.credits.ccost='0';
          c.rows[0].prompt.display.extra_ccost='N/A';c.rows[0].prompt.display_units.usd.ccost='$0.00';
        }
        view.update(p);const costs=()=>[...view.cards.values()].map(c=>c.body.firstChild.cells[5].textContent);
        const credits=costs();ReportView.setUnit('usd',view.root);const usd=costs();ReportView.setUnit('credits',view.root);
        const preview=card.body.querySelector('.watch-prompt-preview'),selection=getSelection(),range=document.createRange();
        range.selectNodeContents(preview);selection.removeAllRanges();selection.addRange(range);
        const selectedText=selection.toString();
        prompt.preview='Accepted after selection';view.update(p);
        const selected=selectedText.length>0 && selection.toString()===selectedText && card.body.querySelector('.watch-prompt-preview')===preview;
        selection.removeAllRanges();view.update(p);const updated=card.body.querySelector('.watch-prompt-preview').textContent===prompt.preview;
        view.update(INPUT);return {quiet,retained,success,terminal,credits,usd,selected,updated,earlier:view.earlier.open,
          pageOverflow:document.documentElement.scrollWidth>innerWidth};
      })()`);
      assert.equal(transitions.quiet,true); assert.equal(transitions.retained,true);
      assert.equal(transitions.success.title,transitions.success.row); assert.equal(transitions.success.focus,true);
      assert.ok(transitions.success.contrast>=4.5);
      assert.equal(transitions.success.href,'#/sessions/root'); assert.equal(transitions.success.historical,'');
      assert.deepEqual(transitions.terminal.map(value=>value.title),['','','','watch-running-title']);
      assert.deepEqual(transitions.terminal.map(value=>value.row),['','watch-error','watch-error','watch-running']);
      assert.deepEqual(transitions.credits,['0 (0 + 0)','0 (0 + 0)']);
      assert.deepEqual(transitions.usd,['$0.00 ($0.00 + $0.00)','$0.00 ($0.00 + $0.00)']);
      for (const key of ['selected','updated','earlier']) assert.equal(transitions[key],true,key);
      assert.equal(transitions.pageOverflow,false);
      cases.push({theme,scheme,width,transitions,layouts,checks});
      await command('Target.closeTarget',{targetId});
    }
    await fs.writeFile(path.join(output,'browser.json'),JSON.stringify({outcome:'PASS',browser:version.product,cases,
      limitations:['Synthetic publication/paint only; virtual 30-second delays, no physical desktop or screen-reader proof.']},null,2));
    console.log(JSON.stringify({outcome:'PASS',browser:version.product,cases:cases.length}));
  } finally {
    clearTimeout(deadline);
    if (child.exitCode === null) {const exited=new Promise(resolve=>child.once('exit',resolve));await command('Browser.close');await exited;}
    await fetch('http://127.0.0.1:18753/stop');
    await fs.rm(profile,{recursive:true});
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
