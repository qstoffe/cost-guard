// Owner-authoritative appearance in actual hidden Document PiP, not a popup facsimile.
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
module.exports = async ({evaluate,until,command,sessionId,pipSession,checks,layouts,output,screenshots}) => {
  const original = await evaluate(`({theme:document.documentElement.dataset.theme,
    width:miniWatch.window.outerWidth,height:miniWatch.window.outerHeight})`);
  const change = async value => {
    await evaluate(`location.hash='#/settings'`);
    await until(`document.getElementById('web-theme')?.disabled===false`);
    await evaluate(`(() => {const select=document.getElementById('web-theme');select.focus();
      select.value='${value}';select.dispatchEvent(new Event('change'));})()`);
    await until(`!document.getElementById('web-theme').disabled && document.getElementById('web-theme').value==='${value}'`);
    assert.equal(await evaluate(`document.activeElement.id`),'web-theme');
  };
  const media = async scheme => {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},sessionId);
    // Deliberately disagree: changing only PiP's media used to conceal the defect.
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme==='light'?'dark':'light'}]},pipSession);
  };
  const parity = async () => {
    await until(`miniWatch.window.getComputedStyle(miniWatch.window.document.body).backgroundColor === getComputedStyle(document.body).backgroundColor`);
    return evaluate(`(() => {const w=miniWatch.window,d=w.document,v=miniWatch.view;
       v.body.parentNode.querySelector('th .help-trigger').focus();
      const roles=win=>{const style=win.getComputedStyle(win.document.documentElement);return Object.fromEntries(
        [...style].filter(key=>key.startsWith('--')).map(key=>[key,style.getPropertyValue(key).trim()]));};
      const color=(node,property='color')=>w.getComputedStyle(node)[property];
      return {owner:roles(window),mini:roles(w),theme:d.documentElement.dataset.theme,
        ownerDark:matchMedia('(prefers-color-scheme: dark)').matches,miniDark:w.matchMedia('(prefers-color-scheme: dark)').matches,
        scheme:w.getComputedStyle(d.documentElement).colorScheme,width:w.innerWidth,height:w.innerHeight,
        colors:{canvas:color(d.body,'backgroundColor'),text:color(d.body),table:color(v.body.parentNode,'backgroundColor'),
          heading:color(v.body.parentNode.querySelector('th'),'backgroundColor'),return:color(v.summary),earlier:color(v.earlierToggle),
          daily:color(v.daily),running:color(v.body.querySelector('.mini-running')),quota:color(v.accounts.querySelector('progress')),
          accounts:color(v.accounts,'backgroundColor'),help:color(d.getElementById('context-help'),'backgroundColor')},
        pageOverflow:d.documentElement.scrollWidth>w.innerWidth || d.documentElement.scrollHeight>w.innerHeight,
        scrollbar:w.getComputedStyle(v.accounts).scrollbarColor,
        inlineRoles:[...d.documentElement.style].filter(key=>key.startsWith('--'))};})()`);
  };
  const rgb = hex => {
    const value=hex.slice(1),full=value.length===3?[...value].map(c=>c+c).join(''):value;
    return [0,2,4].map(index=>parseInt(full.slice(index,index+2),16));
  };
  const css = hex => `rgb(${rgb(hex).join(', ')})`;
  const luminance = hex => rgb(hex).map(value=>value/255).map(value=>value<=.04045?value/12.92:((value+.055)/1.055)**2.4)
    .reduce((sum,value,index)=>sum+value*[.2126,.7152,.0722][index],0);
  const contrast = (a,b) => (Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
  const assertWeb = result => {
    for(const [key,value] of Object.entries(result.owner)) assert.equal(result.mini[key],value,key);
    assert.equal(result.theme,'web');assert.equal(result.ownerDark,!result.miniDark);
    assert.equal(result.scheme,result.ownerDark?'dark':'light');assert.equal(result.pageOverflow,false);
    for(const [name,key] of Object.entries({canvas:'--bg',text:'--ink',table:'--panel',heading:'--surface',
      return:'--accent',earlier:'--ink',daily:'--ink',running:'--watch-running',quota:'--watch-quota-fill',accounts:'--panel',help:'--surface'}))
      assert.equal(result.colors[name],css(result.owner[key]),name);
    for(const key of ['--ink','--muted','--accent','--warn','--error','--watch-success','--watch-running'])
      for(const background of ['--bg','--panel','--surface']) assert.ok(contrast(result.owner[key],result.owner[background])>=4.5,key+' contrast');
    assert.ok(contrast(result.owner['--watch-quota-fill'],result.owner['--surface'])>=3,'quota fill contrast');
    assert.ok(result.scrollbar.includes(css(result.owner['--control-line'])),'semantic scrollbar thumb');
  };
  await evaluate(`window.themeProbe={row:miniWatch.view.body.rows[0],publication:miniWatch.publication,
    streams:probeStreams};miniWatch.view.earlierToggle.click()`);
  for(const scheme of ['light','dark']) {
    await media(scheme);
    for(const choice of ['web','classic','web','default','web']) {
      await change(choice);
      const result=await parity();
      layouts.push({case:'owner-theme-'+scheme+'-'+choice,...result});
      if(choice==='web') assertWeb(result);
      else {
        assert.equal(result.theme,'classic');assert.equal(result.colors.canvas,'rgb(16, 17, 18)');
        assert.equal(result.colors.text,'rgb(229, 229, 229)');assert.deepEqual(result.inlineRoles,[]);
        assert.equal(result.scheme,'dark');
      }
      assert.equal(await evaluate(`miniWatch.view.body.rows[0]===themeProbe.row && miniWatch.publication===themeProbe.publication && !miniWatch.view.earlier.hidden`),true);
    }
  }
  // No settings callback, data publication, report refresh or explicit render after media change.
  for(const scheme of ['light','dark','light']) {
    await media(scheme);const result=await parity();assertWeb(result);
    layouts.push({case:'owner-media-event-'+scheme,...result});
  }
  for(const width of [560,280]) for(const scheme of ['light','dark']) {
    await evaluate(`miniWatch.window.resizeTo(${width},250)`,true);
    await until(`miniWatch.window.innerWidth<=${width}`);
    await media(scheme);const result=await parity();assertWeb(result);
    await command('Runtime.evaluate',{expression:`document.querySelector('.mini-prompts > table th button').focus()`},pipSession);
    await until(`(() => {const w=miniWatch.window,p=w.document.getElementById('context-help'),r=p.getBoundingClientRect();return p.matches(':popover-open') && r.left>=0 && r.right<=w.innerWidth+1 && r.bottom<=w.innerHeight+1;})()`);
    const focus=await evaluate(`(() => {const v=miniWatch.view,w=miniWatch.window,help=v.doc.getElementById('context-help');
      const box=help.getBoundingClientRect();return {open:help.matches(':popover-open'),outline:w.getComputedStyle(v.doc.activeElement).outlineStyle,
        within:box.left>=0 && box.right<=w.innerWidth+1 && box.bottom<=w.innerHeight+1};})()`);
    assert.equal(focus.open,true);assert.notEqual(focus.outline,'none');assert.equal(focus.within,true);
    layouts.push({case:`theme-compact-${width}-${scheme}`,...result,focus});
    const image=await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},pipSession);
    const name=output.replace(/\.json$/,'')+`-owner-web-${scheme}-${width}.png`;
    await fs.writeFile(name,Buffer.from(image.data,'base64'));screenshots.push(path.basename(name));
    await command('Runtime.evaluate',{expression:`document.activeElement.blur()`},pipSession);
  }
  assert.equal(await evaluate('probeStreams'),await evaluate('themeProbe.streams'));
  assert.deepEqual(await evaluate(`({local:localStorage.length,session:sessionStorage.length})`),{local:0,session:0});
  await change(original.theme==='classic'?'default':original.theme);
  await evaluate(`miniWatch.view.earlierToggle.click();miniWatch.window.resizeTo(${original.width},${original.height})`,true);
  await command('Emulation.setEmulatedMedia',{features:[]},sessionId);
  await command('Emulation.setEmulatedMedia',{features:[]},pipSession);
  await evaluate(`location.hash='#/watch'`);await until(`document.body.dataset.section==='watch'`);
  checks.push('Owner-resolved Web roles/canvas/controls/tables/popovers/quotas and WCAG text contrast match despite opposite PiP media; Default/Classic/Web round trips, media-only events, compact/narrow focus and one SSE preserve keyed state without browser storage');
};
