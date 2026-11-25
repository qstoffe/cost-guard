// Actual shipped title help and configured-local timestamps in owned hidden Chromium.
const assert = require('node:assert/strict');
module.exports = async function probe({evaluate, until, command, tab, checks}) {
  await evaluate(`globalThis.originalMix=current.result;globalThis.mixFacts=JSON.stringify(current.result.view)`);
  const help = `document.getElementById('context-help')`;
  const focus = async () => {
    await evaluate(`current.tokenMix.title.focus()`);
    await until(`${help}?.matches(':popover-open')`);
    return evaluate(`${help}.textContent`);
  };
  for (const locale of ['en-US', 'sv-SE']) for (const timezoneId of ['America/New_York', 'Asia/Tokyo']) {
    await command('Emulation.setLocaleOverride', {locale}, tab);
    await command('Emulation.setTimezoneOverride', {timezoneId}, tab);
    for (const [instant, expected] of [
      ['2026-03-29T00:30Z', '2026-03-29 01:30'], ['2026-03-29T01:30Z', '2026-03-29 03:30'],
      ['2026-10-25T00:30Z', '2026-10-25 02:30'], ['2026-10-25T01:30Z', '2026-10-25 02:30'],
      ['2026-12-31T23:30Z', '2027-01-01 00:30']]) {
      await evaluate(`current.tokenMix.update({...originalMix, observed_at_ms:Date.parse('${instant}'),
        view:{...originalMix.view,timezone_id:'Europe/Stockholm',token_mix_period:{
          period:'all',start_ms:Date.parse('${instant}'),end_ms:Date.parse('${instant}')}}})`);
      await focus();
      const text = await evaluate(`(() => { const live = Date.now;
        try {
          Date.now = () => Date.parse('${instant}') + 8000;
          ContextHelp.refresh(current.tokenMix.title);
          return ${help}.textContent;
        } finally { Date.now = live; }
      })()`);
      assert.ok(text.endsWith(`Start not yet known – ${expected}:08`), text);
      assert.doesNotMatch(text, /GMT|Europe|[+-]\d{2}:\d{2}/);
      assert.doesNotMatch(text, /Observed|CLI|Partial pricing|CCost|Deleted|telemetry/);
      assert.doesNotMatch(await evaluate(`current.tokenMix.root.textContent`), /Partial|\?|Incomplete token telemetry/);
      assert.equal(await evaluate(`current.tokenMix.root.querySelectorAll('.partial').length`), 0);
      assert.equal(await evaluate(`ReportView.timestamp(Date.parse('${instant}'),'UTC')`), instant.replace('T',' ').replace('Z',''));
      // The Sessions row uses the response's configured timezone, not the emulated OS zone.
      await evaluate(`globalThis.dateCatalog=new SessionsCatalog.View(()=>{});dateCatalog.update({
        state:'observed',offset:0,total:1,size:50,sort:'activity',direction:-1,
        view:{timezone_id:'Europe/Stockholm',session_usage:[{session_id:'synthetic',title:'Synthetic',last_activity_ms:Date.parse('${instant}')}]} });`);
      assert.equal(await evaluate(`dateCatalog.body.rows[0].cells[0].textContent`), expected);
      await evaluate(`ReportView.setTimezone('Europe/Stockholm');connectionStatus('Synthetic offline evidence',
        {kind:'offline',writable:false,authenticatedAt:Date.parse('${instant}'),observedAt:Date.parse('${instant}')})`);
       assert.equal(await evaluate(`document.getElementById('host-details').textContent`), '');
       assert.equal(await evaluate(`document.getElementById('host-state').hidden`), true);
      assert.equal(await evaluate(`CachedReports.interval({scope:{timezone_id:'Europe/Stockholm'},
        view:{ai_stats:[{period:'all',start_ms:null,end_ms:Date.parse('${instant}')}] }},'all')`),
        `All available history → ${expected} (Europe/Stockholm)`);
    }
  }
  await command('Emulation.setLocaleOverride', {locale:'en-US'}, tab);
  await command('Emulation.setTimezoneOverride', {timezoneId:'America/New_York'}, tab);
  await evaluate(`connectionStatus('Live connected.',{kind:'connected',writable:true});current.tokenMix.update(originalMix)`);
  assert.equal(await evaluate(`JSON.stringify(current.result.view)===mixFacts`), true, 'presentation never edits source facts');
  for (const state of ['complete', 'unpriced', 'empty']) {
    await evaluate(`(()=>{const value=structuredClone(originalMix);const mix=value.view.token_mix;
      if('${state}'==='complete'){mix.cost_complete=true;mix.exact_total_tokens=mix.known_total_tokens;}
      if('${state}'==='unpriced'){mix.priced_requests=0;mix.cost_complete=false;}
      if('${state}'==='empty'){mix.request_count=0;mix.known_total_tokens=null;mix.observed_total_tokens='0';value.view.model_token_mix=[];value.view.publisher_token_mix=[];}
      current.tokenMix.update(value);})()`);
    const text = await focus();
    if (state==='complete' || state==='empty') assert.doesNotMatch(text,/Partial pricing:/);
    assert.doesNotMatch(await evaluate(`current.tokenMix.summary.textContent`),/N\/A|Partial|\?|unavailable/);
    if (state==='empty') assert.match(await evaluate(`current.tokenMix.root.textContent`),/No usage yet|N\/A/);
  }
  assert.equal(await evaluate(`current.tokenMix.summary.querySelectorAll('strong.help-value[tabindex="0"]').length`),4);
  assert.equal(await evaluate(`current.tokenMix.summary.querySelectorAll('div > span.help-value,.help-label,[title]').length`),0);
  await evaluate(`current.tokenMix.update(originalMix);current.tokenMix.title.scrollIntoView({block:'center'});current.tokenMix.title.blur()`);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape'},tab);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},tab);
  const point = await evaluate(`(()=>{const r=current.tokenMix.title.getBoundingClientRect();return {x:r.left+12,y:r.top+r.height/2}})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},tab);
  await until(`${help}.matches(':popover-open')`);
  assert.match(await evaluate(`${help}.textContent`),/recorded tokens for the selected period/);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},tab);
  await until(`!${help}.matches(':popover-open')`);
  await command('Emulation.setTouchEmulationEnabled',{enabled:true},tab);
  for (const type of ['touchStart','touchEnd']) await command('Input.dispatchTouchEvent',{
    type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]},tab);
  await until(`${help}.matches(':popover-open')`);
  assert.match(await evaluate(`${help}.textContent`),/recorded tokens for the selected period/);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape'},tab);
  await command('Emulation.setTouchEmulationEnabled',{enabled:false},tab);
  await evaluate(`current.tokenMix.title.blur()`);
  const forbidden = /\b\d{1,2}\/\d{1,2}\/\d{4}\b|\b\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M\b|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?) \d{1,2},? \d{4}\b/i;
  const surfaces = [];
  for (const section of ['models','watch','accounts','ai-stats','settings']) {
    await evaluate(`location.hash='#/${section}'`);
     await until(`current.section==='${section}' && !current.loading && document.getElementById('result').textContent.length>0`);
     if (['models','ai-stats'].includes(section)) await until(`!!current.result`);
     assert.doesNotMatch(await evaluate(`document.getElementById('result').textContent`), forbidden, section+' visible dates');
     if (section === 'models') {
       const day = await evaluate(`(() => {
         const parent = document.createElement('div'), result = structuredClone(current.result);
         result.view.timezone_id = 'America/New_York';
         const model = {publisher:'Fixture', model:'Calendar day', selectable:true,
           release_date:'2026-11-21', display:{relative_cost:'N/A'}};
         result.view.model_catalog = {...result.view.model_catalog, rows:[model]};
         ReportView.render(parent, result, {section:'models'});
         return parent.querySelector('.overview-model-table tbody tr td:nth-child(4)').textContent;
       })()`);
       assert.equal(day, '2026-11-21', 'Models release day never shifts to the prior configured-local day');
     }
    const texts = await evaluate(`(()=>{const texts=[];for(const node of document.querySelectorAll('#result .help-value,#result .help-action')){
      if(node.getClientRects().length && node.tabIndex>=0){node.focus();ContextHelp.refresh(node);const help=document.getElementById('context-help');if(help?.matches(':popover-open'))texts.push(help.textContent);}}
      document.activeElement?.blur();return texts;})()`);
    for (const text of texts) assert.doesNotMatch(text, forbidden, section+' help dates');
    surfaces.push({section,helpTargets:texts.length});
  }
  checks.push({renderedRouteDateSearch:surfaces,locale:'en-US',browserTimezone:'America/New_York'});
  checks.push('Token Mix exact-period title actual focus/hover/touch, complete/partial/unpriced/empty help; no old heading boilerplate; unchanged canonical facts');
  checks.push('en-US/sv-SE × New York/Tokyo browser zones; configured Stockholm/UTC, spring/fall DST/year boundary across title, Sessions cells, host status and AI Stats interval');
};
