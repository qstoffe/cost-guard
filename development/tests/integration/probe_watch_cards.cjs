// Hidden headless Chromium, fresh owned profile, synthetic origin only.
// Node 22+ built-ins, no package install, personal profile or existing browser attachment.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const checkContext = require('../fixtures/watch_context_browser.cjs');
const checkPromptCost = require('../fixtures/watch_cost_browser.cjs');
const args = process.argv.slice(2);
const argument = key => args[args.indexOf(key) + 1];
const browser = argument('--browser'), output = argument('--output');
const origin = 'http://127.0.0.1:18754';
async function main() {
  assert.ok(path.isAbsolute(browser) && path.isAbsolute(output), 'explicit browser and owned output directory required');
  await fs.mkdir(output, {recursive: true});
  const profile = await fs.mkdtemp(path.join(output, 'watch-owned-profile-'));
  const child = spawn(browser, ['--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--remote-debugging-pipe',
    '--user-data-dir=' + profile, 'about:blank'], {stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'], windowsHide: true});
  const pending = new Map(), listeners = new Map(); let sequence = 0, buffer = '';
  child.stdio[4].on('data', chunk => {
    buffer += chunk.toString();
    let index;
    while ((index = buffer.indexOf('\0')) >= 0) {
      const value = JSON.parse(buffer.slice(0, index)); buffer = buffer.slice(index + 1);
      if (value.id) {
        const entry = pending.get(value.id); pending.delete(value.id);
        if (entry) value.error ? entry.reject(new Error(JSON.stringify(value.error))) : entry.resolve(value.result);
      } else {
        const key = value.sessionId + ':' + value.method;
        if (listeners.has(key)) { listeners.get(key)(value.params); listeners.delete(key); }
      }
    }
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++sequence; pending.set(id, {resolve, reject});
    child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
  });
  const event = (method, sessionId) => new Promise(resolve => listeners.set(sessionId + ':' + method, resolve));
  const deadline = setTimeout(() => { for (const entry of pending.values()) entry.reject(new Error('probe_deadline')); child.kill(); }, 90000);
  const cases = [];
  let version;
  try {
    version = await command('Browser.getVersion');
    for (const theme of ['classic', 'light', 'dark']) for (const [width, height] of [[2560, 1080], [1920, 1080], [1366, 768], [360, 800]]) {
      const {targetId} = await command('Target.createTarget', {url: 'about:blank'});
      const {sessionId} = await command('Target.attachToTarget', {targetId, flatten: true});
      await command('Page.enable', {}, sessionId);
      await command('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false}, sessionId);
      const loaded = event('Page.loadEventFired', sessionId);
      await command('Page.navigate', {url: origin + '/case.html?theme=' + theme}, sessionId);
      await loaded;
      await command('Page.bringToFront', {}, sessionId);
      const evaluate = async expression => {
        const value = await command('Runtime.evaluate', {expression, returnByValue: true}, sessionId);
        assert.equal(value.exceptionDetails, undefined, JSON.stringify(value.exceptionDetails));
        return value.result.value;
      };
      assert.equal(await evaluate('document.querySelector(".watch-earlier").open'), false);
      await evaluate('document.querySelector(".watch-earlier > summary").focus()');
      await command('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r'}, sessionId);
      await command('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13}, sessionId);
      assert.equal(await evaluate('document.querySelector(".watch-earlier").open'), true, 'keyboard opens native disclosure');
      const layout = await evaluate(`(() => {
        const h=document.querySelector('.watch-history'), a=document.querySelector('.watch-active'), c=a.querySelector('.watch-card');
        const details=c.querySelectorAll('details'); details[0].open=true; details[1].open=true;
        details[0].querySelector('summary').focus({preventScroll:true}); const focus=document.activeElement;
        redraw(); const stable=document.activeElement===focus && details[0].open && details[1].open && document.querySelector('.watch-earlier').open;
        const table=c.querySelector('.watch-table-scroll'), row=c.querySelector('tbody tr'), prompt=row.querySelector('.watch-prompt-preview');
         const warning=c.querySelector('.watch-session-summary'), daily=document.querySelector('.watch-daily'), grid=document.querySelector('.watch-account-grid');
        const style=node=>getComputedStyle(node), rect=node=>node.getBoundingClientRect();
        const separators=parent=>[...parent.children].map(node=>parseFloat(style(node).borderTopWidth));
        return {width:innerWidth,height:innerHeight,scrollY,activeTop:a.getBoundingClientRect().top, historyHeight:h.clientHeight,
          historyScroll:h.scrollHeight,historyCards:h.querySelectorAll('article').length,
          historyMaxHeight:style(h).maxHeight,historyOverflow:style(h).overflowY,
          activeSeparators:separators(a),historySeparators:separators(h),
          bodySurface:style(table).backgroundColor,headerSurface:style(c.querySelector('th')).backgroundColor,
          pageSurface:style(document.body).backgroundColor,tableBorder:parseFloat(style(table).borderTopWidth),
          warningAdjacent:warning.previousElementSibling===table && warning.nextElementSibling.className==='watch-activity',
          warningBorder:parseFloat(style(warning).borderTopWidth),warningPadding:parseFloat(style(warning).paddingTop),
          warningGap:rect(warning).top-rect(table).bottom,warningOverflow:warning.scrollWidth>warning.clientWidth,
          dailyGap:rect(grid).top-rect(daily).bottom,
          detailDividers:[...grid.querySelectorAll('.watch-account-details')].every(node=>parseFloat(style(node).borderTopWidth)===1),
          activityColor:style(c.querySelector('.watch-activity')).color,warningColor:style(warning).color,
          rows:c.querySelectorAll('tbody tr').length, historyBorder:parseFloat(getComputedStyle(h).borderTopWidth),
          ellipsis:getComputedStyle(prompt).textOverflow==='ellipsis' && prompt.scrollWidth>prompt.clientWidth,
           completeMetrics:[...row.cells].filter((_,i)=>i!==2).every(cell=>cell.scrollWidth<=cell.clientWidth),
           ordinalVisible:rect(row.querySelector('.watch-prompt-number')).width>0 && row.querySelector('.watch-prompt-number').textContent==='#12',
           historyDivider:parseFloat(style(document.querySelector('.watch-earlier')).borderBottomWidth),
           historyBackground:style(h).backgroundColor,
          pageOverflow:document.documentElement.scrollWidth>innerWidth,
          activeInnerScroll:a.scrollHeight>a.clientHeight,tableVerticalScroll:table.scrollHeight>table.clientHeight,
          horizontalPan:table.scrollWidth>table.clientWidth,runningColor:getComputedStyle(c.querySelector('.watch-running')).color,
          border:getComputedStyle(c).borderTopWidth,background:getComputedStyle(c).backgroundColor,stable}; })()`);
       assert.equal(layout.historyCards, 5); assert.equal(layout.historyScroll, layout.historyHeight);
       assert.equal(layout.historyMaxHeight, 'none'); assert.equal(layout.historyOverflow, 'visible');
        assert.deepEqual(layout.activeSeparators, [1,1]); assert.deepEqual(layout.historySeparators, [1,1,1,1,1]);
       assert.notEqual(layout.bodySurface, layout.pageSurface); assert.notEqual(layout.headerSurface, layout.bodySurface);
       assert.equal(layout.tableBorder, 1); assert.equal(layout.warningAdjacent, true);
       assert.equal(layout.warningBorder, 0); assert.equal(layout.warningPadding, 0);
       assert.ok(layout.warningGap >= 0 && layout.warningGap <= 4); assert.equal(layout.warningOverflow, false);
       assert.equal(layout.dailyGap, 4); assert.equal(layout.detailDividers, true);
       assert.notEqual(layout.activityColor, layout.runningColor); assert.notEqual(layout.warningColor, layout.runningColor);
        assert.equal(layout.rows, 1); assert.equal(layout.historyBorder, 0);
        assert.equal(layout.historyBackground, 'rgba(0, 0, 0, 0)'); assert.equal(layout.historyDivider, 2);
        assert.equal(layout.ordinalVisible, true);
       assert.equal(layout.ellipsis, true); assert.equal(layout.completeMetrics, true);
      assert.equal(layout.scrollY, 0, 'layout assertions use the unscrolled document');
      assert.equal(layout.pageOverflow, false); assert.equal(layout.activeInnerScroll, false);
       assert.equal(layout.tableVerticalScroll, false); assert.equal(layout.stable, true);
        assert.equal(layout.border, '1px'); assert.equal(layout.background, 'rgba(0, 0, 0, 0)');
         if (width === 360) assert.equal(layout.horizontalPan, true);
       await command('Input.dispatchKeyEvent', {type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9}, sessionId);
       const headers = await evaluate(`(() => {
           const names=['Started','Duration','Prompt','Model','Effort','CCost','Calls','Token Mix %','Ictx','Δ Ctx'];
           const help=n=>{n.focus({preventScroll:true});return document.querySelector('#context-help').textContent;};
          return [...document.querySelectorAll('table')].every(table=>[...table.querySelectorAll('th')]
             .every((th,i)=>th.querySelector('button').textContent===(i===0&&table.closest('.watch-history')?'Finished':names[i]) && help(th.querySelector('button')).length>20))
            && [...document.querySelectorAll('tbody tr')].every(row=>row.cells.length===10 && /^\\d\\d:\\d\\d$/.test(row.cells[0].textContent)
               && (row.closest('.watch-history')?/^\\d{4}-\\d\\d-\\d\\d \\d\\d:\\d\\d [+-]\\d{4}$/:/^\\d{4}-\\d\\d-\\d\\d \\d\\d:\\d\\d$/).test(help(row.cells[0].firstChild))); })()`);
        assert.equal(headers, true, 'both tables share the ten columns and local clock disclosures');
        await evaluate(`INPUT.view.history_state='loading';INPUT.view.history_epoch=0;INPUT.view.history_checked=4;INPUT.view.history_total=12;redraw()`);
        assert.equal(await evaluate(`document.querySelectorAll('.watch-history article').length`),0,
          'provisional legacy cards cannot bypass producer readiness');
        const loadingAX = (await command('Accessibility.getFullAXTree',{},sessionId)).nodes
          .filter(node=>!node.ignored).map(node=>node.name?.value||'').join('\n');
        assert.match(loadingAX,/Loading earlier sessions….*4\/12 checked/);
        await evaluate(`INPUT.view.history_state='observed';redraw()`);
        assert.equal(await evaluate(`document.querySelectorAll('.watch-history article').length`),5);
        const historyReadiness = {loadingDOM:true,loadingAX:true,verifiedFive:true};
       await evaluate(`document.activeElement.blur();window.scrollTo(0,0)`);
       const hover = await evaluate(`(() => { const r=document.querySelector('.watch-history th button').getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
        await command('Input.dispatchMouseEvent', {type:'mouseMoved',...hover}, sessionId);
        await new Promise(resolve=>setTimeout(resolve,650));
       assert.equal(await evaluate(`document.querySelectorAll(':popover-open').length`), 1, 'pointer hover opens header explanation');
        await command('Input.dispatchMouseEvent', {type:'mouseMoved',x:0,y:0}, sessionId);
        await new Promise(resolve=>setTimeout(resolve,200));
       assert.equal(await evaluate(`document.querySelectorAll(':popover-open').length`), 0);
       // Real focus, Escape and touch-style click exercise native top-layer help.
       await evaluate(`document.querySelector('.watch-active th:nth-child(8) button').focus({preventScroll:true})`);
       const help = await evaluate(`(() => {
         const button=document.activeElement, panel=document.getElementById(button.getAttribute('aria-describedby'));
         return {open:panel.matches(':popover-open'),text:panel.textContent,within:panel.getBoundingClientRect().right<=innerWidth}; })()`);
       assert.equal(help.open, true); assert.equal(help.within, true);
       assert.match(help.text, /I — Input[\s\S]*C — Cached input[\s\S]*W — Cache write[\s\S]*O — Output[\s\S]*reasoning/);
       await command('Input.dispatchKeyEvent', {type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27}, sessionId);
       await command('Input.dispatchKeyEvent', {type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27}, sessionId);
       assert.equal(await evaluate(`document.querySelectorAll(':popover-open').length`), 0);
        await evaluate(`document.activeElement.click()`);
        assert.equal(await evaluate(`document.querySelectorAll(':popover-open').length`), 1);
        await evaluate(`document.querySelector('.watch-active th:nth-child(9) button').focus({preventScroll:true})`);
        const ictxHelp = await evaluate(`(() => {
          const panel=document.getElementById(document.activeElement.getAttribute('aria-describedby'));
          return {open:panel.matches(':popover-open'),text:panel.textContent}; })()`);
        assert.equal(ictxHelp.open, true); assert.match(ictxHelp.text, /first request[\s\S]*estimated[\s\S]*N\/A[\s\S]*unavailable/);
        await evaluate(`document.querySelector('.watch-session-summary .help-value').focus({preventScroll:true})`);
        assert.match(await evaluate(`document.querySelector('#context-help').textContent`), /next request[\s\S]*not a session spending limit/);
       await evaluate(`document.activeElement.blur(); document.querySelector('.watch-earlier').open=false`);
       assert.equal(await evaluate(`parseFloat(getComputedStyle(document.querySelector('.watch-earlier')).borderBottomWidth)`), 0);
       await evaluate(`document.querySelector('.watch-earlier').open=true`);
       const quotas = await evaluate(`(() => {
         const cards=[...document.querySelectorAll('.watch-subscription')], monthly=cards[0];
         const summary=monthly.querySelector('.watch-quota-summary'), details=monthly.querySelector('.watch-primary-details');
          const native=summary.firstChild.textContent, cost=summary.querySelector('.watch-period-cost').textContent, fill=monthly.querySelector('progress').value;
          monthly.querySelector('.watch-quota-capacity .help-value').focus({preventScroll:true});
          const costHelp=document.querySelector('#context-help').textContent.includes('Native Used: 2088/25000 AI credits');
          ReportView.setUnit('usd', document.getElementById('result'));
          const usd=summary.querySelector('.watch-period-cost').textContent, unchanged=summary.firstChild.textContent===native && monthly.querySelector('progress').value===fill;
          ReportView.setUnit('credits', document.getElementById('result'));
          document.activeElement.blur();
         const rect=node=>node.getBoundingClientRect();
         const aligned=cards.every((card,i)=>cards.slice(0,i).filter(other=>rect(other).top===rect(card).top)
           .every(other=>[0,1,2,3,4].every(track=>Math.abs(rect(card.children[track]).top-rect(other.children[track]).top)<1)));
          const resetGaps=cards.flatMap(card=>[...card.querySelectorAll('.watch-quota-track')].map(track=> {
            const next=track.nextElementSibling, reset=next.className==='watch-primary-details'?next.firstChild:next;
            return rect(reset).top-rect(track.querySelector('progress')||track).bottom;
          }));
          return {native,cost,fill,usd,unchanged,aligned,costHelp,resetGaps,
           legible:cards.every(card=>[...card.querySelectorAll('.watch-quota-summary,.watch-primary-details,.watch-secondary-quota')]
             .every(node=>node.scrollWidth<=node.clientWidth)),
           monthlyDivider:monthly.querySelector('.watch-account-details')!==null,
           secondary:cards[1].querySelector('.watch-secondary-quota').textContent}; })()`);
        assert.equal(quotas.native, 'Monthly · 8.4% used');
        assert.equal(quotas.cost, ' (2088)'); assert.equal(quotas.usd, ' ($20.88)');
        assert.equal(quotas.fill, .08352); assert.equal(quotas.unchanged, true);
        assert.equal(quotas.costHelp, true);
        assert.ok(quotas.resetGaps.every(gap=>gap>=0 && gap<=4), JSON.stringify(quotas.resetGaps));
       assert.equal(quotas.aligned, true); assert.equal(quotas.legible, true);
        assert.equal(quotas.monthlyDivider, false);
          assert.match(quotas.secondary, /Weekly · 100% used \(840\)Weekly Capacity: 840 \(guesstimate\)Monthly Capacity: 3600 \(guesstimate\)Reset/);
       const polish = await evaluate(`(() => {
         const style=n=>getComputedStyle(n), rect=n=>n.getBoundingClientRect();
         const cards=[...document.querySelectorAll('.watch-subscription')], first=cards[0], grid=first.parentNode;
         const original=INPUT.view.accounts.accounts, originalTheme=document.documentElement.dataset.theme;
         const snapshot=()=>({widths:cards.map(n=>rect(n).width),
           overflow:document.documentElement.scrollWidth>innerWidth,
           accessible:cards.every(n=>[n.querySelector('h4'),...n.querySelectorAll('p,.watch-quota-summary')]
             .every(v=>v.scrollWidth<=v.clientWidth && v.scrollHeight<=v.clientHeight)),
           firstLeft:rect(first).left,gridLeft:rect(grid).left});
          const normal=snapshot(), header=style(first.querySelector('h4')), bar=style(first.querySelector('progress'));
          const dimensions={headerFont:header.fontSize,headerLineHeight:header.lineHeight,padding:parseFloat(header.paddingTop),
            barHeight:parseFloat(bar.height),radius:parseFloat(bar.borderRadius),root:style(document.documentElement).fontSize,
            viewportScale:visualViewport.scale,devicePixelRatio};
         const framing=[...document.querySelectorAll('.watch-card')].every(n=>parseFloat(style(n).borderRadius)>0 &&
           parseFloat(style(n).paddingLeft)>0 && rect(n).width===rect(n.parentNode).width);
         const zoom=[];
         for (const percent of [150,200]) {
           document.documentElement.style.fontSize=(15*percent/100)+'px';
           zoom.push({percent,root:parseFloat(style(document.documentElement).fontSize),...snapshot()});
         }
          document.documentElement.style.fontSize='';
          // Reproduce the previous effective 30rem rule using real layout at 150% text size.
          document.documentElement.style.fontSize='22.5px';
          grid.style.gridTemplateColumns='repeat(auto-fit,minmax(0,min(100%,30rem)))';
          cards.forEach(card=>card.style.maxWidth='none');
          const priorRule150=snapshot();
          document.documentElement.style.fontSize=''; grid.style.gridTemplateColumns='';
          cards.forEach(card=>card.style.maxWidth='');
         const singleNode=first.cloneNode(true); grid.replaceChildren(singleNode);
         const single={width:rect(singleNode).width,left:rect(singleNode).left,gridLeft:rect(grid).left};
         // Force a fresh accepted publication to restore the original cards.
         INPUT.view.accounts.accounts=[...original]; INPUT.view.accounts.now_ms++; redraw();
         const account=structuredClone(original[1]), primary=account.primary, secondary=account.secondary[0];
         const outcomes=[];
         function render(p,s,availability='available',restricted=false) {
           for (const [slot,fraction] of [[primary,p],[secondary,s]]) {
              slot.used_fraction=fraction;slot.used_percent=fraction===null?'—':fraction<1&&fraction>=.9995?'<100%':String(fraction*100)+'%';
              slot.exhausted=fraction===1;slot.restricted=restricted;
              // Keep the current prepared display variant coherent with this synthetic publication.
              Object.assign(slot.quota.quota_display.used, {fraction,percent:slot.used_percent,exhausted:slot.exhausted});
              slot.quota.unlimited=false;
           }
           account.observation.availability=availability;
           account.observation.status=restricted?'blocked':'unknown';
           INPUT.view.accounts.accounts=[account]; redraw();
           const card=document.querySelector('.watch-subscription'), head=card.querySelector('h4');
           const bars=[...card.querySelectorAll('progress')], labels=[...card.querySelectorAll('.watch-quota-summary')];
           return {p,s,availability,restricted,flag:card.dataset.exhausted,
             colors:labels.map(n=>style(n).color),barColors:bars.map(n=>style(n).color),
             fractions:bars.map(n=>n.value),aria:bars.map(n=>n.getAttribute('aria-valuetext')),
             head:style(head).color,band:style(head).backgroundColor,body:style(card).backgroundColor,
             error:style(card).getPropertyValue('--error').trim(),
             cost:style(card.children[1]).color,warning:card.textContent.includes('not current'),
             restriction:card.textContent.includes('Provider restriction reported')};
         }
         for (const fraction of [0,.499,.5,.75,.999,.99999,1,.25]) outcomes.push(render(fraction,.25));
         outcomes.push(render(.25,1),render(1,1),render(.25,.25),render(1,.25,'stale'),render(null,null,'partial',true));
         // An unlimited quota never has a bar or exhaustion; provider warnings stay separate.
         primary.quota.unlimited=true;primary.used_fraction=null;primary.exhausted=false;redraw();
         const unlimited=document.querySelectorAll('.watch-subscription progress').length===0 &&
           document.querySelector('.watch-subscription').dataset.exhausted==='false';
         const card=document.querySelector('.watch-subscription'), body=style(card).backgroundColor;
         const rgb=color=>color.match(/[\\d.]+/g).slice(0,3).map(Number);
         const luminance=color=>rgb(color).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
           .reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
         const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
         const exhausted=outcomes.find(v=>v.p===1), contrastHeader=contrast(exhausted.head,exhausted.band), contrastUsage=contrast(exhausted.colors[0],body);
         INPUT.view.accounts.accounts=original; redraw();
          return {normal,zoom,single,priorRule150,framing,outcomes,unlimited,contrastHeader,contrastUsage,...dimensions,theme:originalTheme}; })()`);
       assert.equal(polish.framing, true);
       for (const sample of [polish.normal,...polish.zoom]) {
         assert.equal(sample.overflow, false); assert.equal(sample.accessible, true);
          assert.ok(sample.widths.every(value=>value<=450));
         assert.ok(Math.abs(sample.firstLeft-sample.gridLeft)<1);
       }
       assert.ok(polish.single.width<=451 && Math.abs(polish.single.left-polish.single.gridLeft)<1);
       assert.ok(polish.padding>=6 && polish.padding<=7); assert.equal(polish.headerFont,'12.75px');
        assert.equal(polish.barHeight,12.4375); assert.equal(polish.radius,2);
       assert.ok(polish.contrastHeader>=4.5 && polish.contrastUsage>=4.5);
       const cyan=polish.outcomes[0].colors, normalBand=polish.outcomes[0].band;
       // Summary text normally inherits ink, whereas non-exhausted bars retain teal.
       const teal=polish.outcomes[0].barColors;
       for (const result of polish.outcomes) {
         const flags=[result.p===1,result.s===1];
         assert.equal(result.flag,String(flags.some(Boolean)));
         assert.equal(result.body,polish.outcomes[0].body);
         assert.equal(result.cost,polish.outcomes[0].cost);
         flags.forEach((full,i)=> {
           assert.equal(result.colors[i],full?polish.outcomes[6].colors[0]:cyan[i]);
           if (result.p!==null) assert.equal(result.barColors[i],full?polish.outcomes[6].barColors[0]:teal[i]);
         });
         if (!flags.some(Boolean)) assert.equal(result.band,normalBand);
         else assert.notEqual(result.band,normalBand);
       }
        assert.equal(polish.outcomes.at(-2).warning,false, 'brief stale refresh stays quiet; actionable restrictions remain visible');
       assert.equal(polish.outcomes.at(-1).restriction,true);
        assert.equal(polish.unlimited,true);
         const promptCost = await checkPromptCost(evaluate);
         const context = await checkContext(evaluate);
         await evaluate(`document.querySelector('.watch-earlier').open=false; window.scrollTo(0,0)`);
         const contextShot = await command('Page.captureScreenshot', {format:'png',captureBeyondViewport:false}, sessionId);
         await fs.writeFile(path.join(output, `context-${theme}-${width}.png`), Buffer.from(contextShot.data,'base64'));
         await evaluate(`document.querySelector('.watch-earlier').open=true; window.scrollTo(0,0)`);
      const screenshot = await command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false}, sessionId);
        await fs.writeFile(path.join(output, `watch-${theme}-${width}.png`), Buffer.from(screenshot.data, 'base64'));
       await evaluate('document.querySelector(".watch-account-grid").scrollIntoView()');
       const subscriptions = await command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false}, sessionId);
       await fs.writeFile(path.join(output, `subscriptions-${theme}-${width}.png`), Buffer.from(subscriptions.data, 'base64'));
       await evaluate('window.scrollTo(0,0)');
       const transitions = await evaluate(`(() => {
         const a=document.querySelector('.watch-active'), h=document.querySelector('.watch-history');
         const originals=[...INPUT.view.active_cards], node=a.children[1];
         INPUT.view.active_cards.reverse();redraw();
          const reordered=a.children[0]===node && getComputedStyle(node).borderTopWidth==='1px';
         INPUT.view.active_cards.pop();redraw();
          const removed=a.children.length===1 && getComputedStyle(a.firstChild).borderTopWidth==='1px';
         const moved=INPUT.view.active_cards.pop(); INPUT.view.history_cards.unshift({...moved,focal_id:''});redraw();
          const transitioned=a.children.length===0 && [...h.children].every(card=>getComputedStyle(card).borderTopWidth==='1px');
         INPUT.view.active_cards=originals;INPUT.view.history_cards.shift();redraw();
          const row=a.querySelector('tbody tr'), oldMix=row.cells[7].textContent;
          INPUT.view.active_cards[0].rows[0].prompt.token_mix_percent=[25,75,0,0];
          INPUT.view.active_cards[0].rows[0].prompt.display.token_mix_percent='25/75/0/0';redraw();
          const updated=row===a.querySelector('tbody tr') && row.cells[7].textContent==='25/75/0/0' && oldMix!=='25/75/0/0';
          const number=row.querySelector('.watch-prompt-number'), preview=row.querySelector('.watch-prompt-preview');
          const selection=window.getSelection(),range=document.createRange();range.selectNodeContents(preview);selection.removeAllRanges();selection.addRange(range);
          INPUT.view.active_cards[0].rows[0].prompt.preview='New preview';redraw();
          const selected=row.querySelector('.watch-prompt-preview')===preview && selection.toString().length>0;
          selection.removeAllRanges();redraw();
          const previewUpdated=row.querySelector('.watch-prompt-preview').textContent==='New preview';
          INPUT.view.history_cards=[];redraw();
          const noEmptyDivider=parseFloat(getComputedStyle(document.querySelector('.watch-earlier')).borderBottomWidth)===0;
         window.scrollTo(0,100); const before=scrollY, focus=document.activeElement;
         INPUT.view.daily_state='refreshing';const daily=document.querySelector('.watch-daily').firstChild;redraw();
         const stable=scrollY===before && document.activeElement===focus && document.querySelector('.watch-daily').firstChild===daily;
          return {reordered,removed,transitioned,updated,selected,previewUpdated,noEmptyDivider,stable}; })()`);
        assert.deepEqual(transitions, {reordered:true,removed:true,transitioned:true,updated:true,selected:true,previewUpdated:true,noEmptyDivider:true,stable:true});
      const scale = await evaluate(`(() => {
        const base=INPUT.view.active_cards[0];
        INPUT.view.active_cards=Array.from({length:100},(_,i)=>({...base,session_id:'scale-'+i}));redraw();
        const a=document.querySelector('.watch-active'); const count=a.children.length;
        const scroll=a.scrollHeight>a.clientHeight;
        INPUT.view.active_cards[0].rows.at(-1).prompt.in_progress=false;redraw();
        const success=getComputedStyle(a.querySelector('tr.watch-success')).color;
        INPUT.view.active_cards[0].rows.at(-1).prompt.aborted=true;redraw();
        const error=getComputedStyle(a.querySelector('tr.watch-error')).color;
        return {count,scroll,success,error}; })()`);
      assert.equal(scale.count, 100); assert.equal(scale.scroll, false);
      assert.notEqual(scale.success, layout.runningColor); assert.notEqual(scale.error, layout.runningColor);
           cases.push({theme, ...layout, quotas, polish, context, promptCost, transitions, scale, historyReadiness,
             contextScreenshot:`context-${theme}-${width}.png`, screenshot: `watch-${theme}-${width}.png`, outcome: 'PASS'});
      await command('Target.closeTarget', {targetId});
    }
    await fs.writeFile(path.join(output, 'browser.json'), JSON.stringify({outcome: 'PASS', browser: version.product, userAgent: version.userAgent, cases,
      limitations: ['Synthetic loopback fixture only; no real-installation browser/SSE, physical input, native fullscreen, screen-reader or macOS proof.']}, null, 2));
    console.log(JSON.stringify({outcome:'PASS', browser:version.product, cases:cases.length, evidence:path.join(output,'browser.json')}));
  } finally {
    try { if (child.exitCode === null) { const exited=once(child,'exit'); await command('Browser.close'); await exited; } }
    finally { clearTimeout(deadline); if (child.exitCode !== null) await fs.rm(profile, {recursive:true}); }
  }
}
main().catch(error => { console.error(error); process.exitCode=1; });
