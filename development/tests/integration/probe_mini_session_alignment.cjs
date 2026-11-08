// Mini-only paired cost scopes, stable contextual help and intrinsic widths in hidden PiP.
const assert = require('node:assert/strict');
module.exports = async function alignment({evaluate,until,fixture,command,sessionId,pipSession,layouts,checks}) {
  const original = await evaluate(`({width:miniWatch.window.outerWidth,height:miniWatch.window.outerHeight,
    theme:document.documentElement.dataset.theme,earlierHidden:miniWatch.view.earlier.hidden})`);
  const input = (method,params) => command(method,params,pipSession);
  const key = async key => {
    for(const type of ['keyDown','keyUp']) await input('Input.dispatchKeyEvent',{type,key,code:key,windowsVirtualKeyCode:key==='Tab'?9:27});
  };
  const help = `miniWatch.view.doc.getElementById('context-help')`;
  const previousPublication=await evaluate('liveValue.view.now_ms');
  await fixture('history-3-2-1');
  await until(`liveValue.view.now_ms!==${previousPublication} && miniWatch.view.promptRows.size===2 && miniWatch.view.historyRows.size===3`);
  // The real transport replays its latest snapshot every ten seconds. These local
  // synthetic corrections must not be replaced by that unchanged fixture replay.
  // New source publications and all explicit synthetic updates still reach the SUT.
  await evaluate(`window.costUpdate=miniWatch.update;window.costEpoch=liveValue.view.now_ms;
    miniWatch.update=function(p){if(p===liveValue && p?.view?.now_ms===costEpoch)return;return costUpdate.call(this,p);}`);
  await evaluate(`(() => {const p=structuredClone(liveValue);p.view.now_ms++;
    for(const card of [...p.view.active_cards,...p.view.history_cards]) {
      card.title='Full untruncated session name '.repeat(15);
      card.session_summary.cost.display_units={credits:{known_ccost:'562'},usd:{known_ccost:'$5.62'}};
      const item=card.rows[0];item.model='Example Model';item.effort='high';item.display.watch_duration_ms='4m 12s';
      Object.assign(item.prompt,{prompt_number:7,calls:12,linked_agent_count:2,has_additional_model:true,
        unresolved_cost:true,aborted:true,abort_reason:'quota_limit',
        cost_detail:{model_count:2,calls_complete:false,parts:[{role:'main',provider_id:'example',model_id:'model'}]}});
      item.prompt.display_units={credits:{ccost:'49'},usd:{ccost:'$0.49'}};
    }
    p.view.active_cards[1].rows[0].prompt.display_units={credits:{ccost:'173'},usd:{ccost:'$1.73'}};
    p.view.active_cards[1].rows[0].prompt.prompt_number=11;
    p.view.history_cards[1].rows[0].prompt.prompt_number=20;
    p.view.history_cards[2].rows[0].prompt.prompt_number=null;
    ReportView.setUnit('credits');miniWatch.update(p);miniWatch.view.earlier.hidden=false;
    window.costRow=miniWatch.view.historyBody.rows[0];window.costTarget=costRow.querySelector('.mini-cost-value > span:first-child');
    window.nameTarget=miniWatch.view.body.rows[0].querySelector('.mini-session');})()`);
  assert.deepEqual(await evaluate(`[...miniWatch.view.body.parentNode.querySelectorAll('th')].map(n=>n.textContent)`),
    ['Session','CCost (Total)','Duration','Ctx']);
  assert.deepEqual(await evaluate(`[...miniWatch.view.historyBody.parentNode.querySelectorAll('th')].map(n=>n.textContent)`),
    ['Finished','Session','CCost (Total)','Ctx']);
  assert.deepEqual(await evaluate(`[...miniWatch.view.body.rows].map(row=>row.cells[1].textContent)`),['49 (562)','173 (562)']);
  assert.deepEqual(await evaluate(`[...miniWatch.view.historyBody.rows].map(row=>row.cells[2].textContent)`),Array(3).fill('49 (562)'));
  for (const [table, numbers] of [['body',[7,11]],['historyBody',[7,20,null]]]) {
    for (const [index, number] of numbers.entries()) for (const target of ['mini-session','mini-cost-value > span:first-child']) {
      await key('Tab');
      await evaluate(`miniWatch.view.${table}.rows[${index}].querySelector('.${target}').focus()`);
      await until(`${help}?.matches(':popover-open')`);
      const content = await evaluate(`${help}.textContent`);
      assert.ok(content.includes(number == null ? 'Prompt number unavailable' : 'Prompt #'+number));
      if(target==='mini-session') assert.equal(content, 'Full untruncated session name '.repeat(15)+'\n'+
        (number == null ? 'Prompt number unavailable' : 'Prompt #'+number+' in this session'));
      else assert.match(content,/Main model: Example Model[\s\S]*Effort: high[\s\S]*Duration: 4m 12s[\s\S]*Calls: 12/);
      await key('Escape'); await evaluate('miniWatch.view.doc.activeElement.blur()');
    }
  }
  await key('Tab'); await evaluate(`costTarget.focus();costTarget.scrollIntoView({block:'center'})`);
  await until(`${help}?.matches(':popover-open')`);
  assert.match(await evaluate(`${help}.textContent`),/Prompt #7\nMain model: Example Model \[example\/model\]\nEffort: high\nDuration: 4m 12s\nCalls: 12/);
  assert.match(await evaluate(`${help}.textContent`),/Linked subagents[\s\S]*Multiple models[\s\S]*Partial pricing[\s\S]*Aborted · quota limit/);
  await evaluate(`(()=>{const p=structuredClone(miniWatch.publication);p.view.now_ms++;
    const item=p.view.history_cards[0].rows[0];item.prompt.prompt_number=8;item.model='Corrected model';
    item.prompt.display_units.credits.ccost='?59';miniWatch.update(p);})()`);
  assert.equal(await evaluate(`miniWatch.view.historyBody.rows[0]===costRow && costRow.querySelector('.mini-cost-value > span:first-child')===costTarget && miniWatch.view.doc.activeElement===costTarget`),true);
  assert.equal(await evaluate('costTarget.textContent'),'?59');
  assert.match(await evaluate(`${help}.textContent`),/Prompt #8\nMain model: Corrected model/);
  await key('Escape'); await evaluate('miniWatch.settings()');
  assert.equal(await evaluate(`${help}.matches(':popover-open')`),false,'Live refresh cannot reopen dismissed help');
  await evaluate('costTarget.blur()');
  for(const target of ['nameTarget','costTarget',`miniWatch.view.body.rows[0].querySelector('.mini-cost-value > span:first-child')`,
    `miniWatch.view.historyBody.rows[0].querySelector('.mini-session')`]) {
    await evaluate(`${target}.scrollIntoView({block:'center'});miniWatch.window.scrollTo(0,0)`);
    await input('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
    const point=await evaluate(`(()=>{const r=${target}.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
    await input('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
    assert.equal(await evaluate(`${help}.matches(':popover-open')`),false,'shared hover delay');
    await until(`${help}.matches(':popover-open')`);
    assert.match(await evaluate(`${help}.textContent`),target==='nameTarget'?/Prompt #7 in this session/:
      target.includes('body.rows')?/Prompt #7\nMain model/:/Prompt #8/);
    await input('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
    await until(`!${help}.matches(':popover-open')`);
    for(const type of ['touchStart','touchEnd']) await input('Input.dispatchTouchEvent',{
      type,touchPoints:type==='touchStart'?[{...point,id:1,radiusX:1,radiusY:1,force:1}]:[]});
    await until(`${help}.matches(':popover-open')`);
    await key('Escape'); await evaluate(`${target}.blur()`);
    await key('Tab'); await evaluate(`${target}.focus()`);
    await until(`${help}.matches(':popover-open')`);
    await key('Escape'); await evaluate(`${target}.blur()`);
  }
  const openingWidth=await evaluate('miniWatch.measure.read(miniWatch).width');
  for(const [prompt,total,expected] of [['N/A','562','N/A (562)'],['49','Loading…','49 (Loading…)'],
      ['?49','?562','?49 (?562)'],['0','0','0 (0)'],['49','N/A','49 (N/A)']]) {
    await evaluate(`(()=>{const p=structuredClone(miniWatch.publication);p.view.now_ms++;
      for(const card of [...p.view.active_cards,...p.view.history_cards]) {
        card.rows[0].prompt.display_units={credits:{ccost:'${prompt}'}};
        card.session_summary.cost.display_units={credits:{known_ccost:'${total}'}};
      }miniWatch.update(p);})()`);
    assert.equal(await evaluate('costTarget.textContent'),expected);
    assert.equal(await evaluate(`miniWatch.view.body.rows[0].cells[1].textContent`),expected);
  }
  await evaluate(`(()=>{const p=structuredClone(miniWatch.publication);p.view.now_ms++;
    for(const card of [...p.view.active_cards,...p.view.history_cards]) {
      card.rows[0].prompt.display_units={credits:{ccost:'?123 456'},usd:{ccost:'?$1 234.56'}};
      card.session_summary.cost.display_units={credits:{known_ccost:'?987 654 321'},usd:{known_ccost:'?$9 876 543.21'}};
    }miniWatch.update(p);})()`);
  assert.equal(await evaluate('miniWatch.measure.read(miniWatch).width'),openingWidth,'table costs never widen Fit on open');
  for(const width of [650,520,280]) {
    await evaluate(`miniWatch.window.resizeTo(${width},550)`,true);
    for(const [font,zoom] of [['100%',1],['150%',1],['100%',1.25]]) {
      await command('Runtime.evaluate',{expression:`document.documentElement.style.fontSize='${font}';document.documentElement.style.zoom='${zoom}'`},pipSession);
      for(const [theme,scheme] of [['classic','light'],['web','light'],['web','dark']]) {
        await evaluate(`document.documentElement.dataset.theme='${theme}';miniWatch.settings()`);
        await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme}]},sessionId);
        for(const unit of ['credits','usd']) {
          await evaluate(`ReportView.setUnit('${unit}');miniWatch.settings()`);
          const result=await evaluate(`(() => {const v=miniWatch.view,w=miniWatch.window,d=w.document;
            const rect=node=>node.getBoundingClientRect(),style=node=>w.getComputedStyle(node);
            const zoom=parseFloat(style(d.documentElement).zoom);
            const errors=[],costs=[];
            for(const body of [v.body,v.historyBody]) {
              const table=body.parentNode,costIndex=body===v.body?1:2;
              if(table.querySelectorAll('th').length!==4) errors.push('extra column');
              const heading=table.querySelectorAll('th')[costIndex],range=d.createRange();range.selectNodeContents(heading);
              if(range.getBoundingClientRect().height>rect(heading).height+1) errors.push('wrapped heading');
              for(const row of body.rows) {
                const cell=row.cells[costIndex],value=cell.querySelector('.mini-cost-value'),title=row.querySelector('.mini-session');
                if(rect(value).right>rect(cell).right+1||rect(value).left<rect(cell).left-1||value.scrollWidth>value.clientWidth+1) errors.push('clipped cost');
                if(style(cell).textAlign!=='right'||style(value).whiteSpace!=='nowrap') errors.push('cost alignment');
                if(title.textContent.includes('(')||style(title).textOverflow!=='ellipsis') errors.push('Session scope');
                if(!row.getAttribute('aria-label').includes(title.textContent)||title.hasAttribute('title')) errors.push('accessible title');
                costs.push(value.textContent);
              }
            }
            if(v.historyBody.rows[0]!==costRow||costRow.querySelector('.mini-cost-value > span:first-child')!==costTarget) errors.push('rerender reset');
            return {errors,costs,width:w.innerWidth,font:style(d.documentElement).fontSize,
              scroll:v.prompts.scrollWidth>v.prompts.clientWidth,
              pageOverflow:d.documentElement.scrollWidth>w.innerWidth+1,
              secondVertical:[v.earlier,...v.prompts.querySelectorAll('table')].some(n=>['auto','scroll'].includes(style(n).overflowY))};})()`);
          layouts.push({case:`session-alignment-${width}-${font}-zoom${zoom}-${theme}-${scheme}-${unit}`,...result});
          assert.deepEqual(result.errors,[],JSON.stringify(result));
          assert.equal(result.pageOverflow,false);
          assert.deepEqual(result.costs,Array(5).fill(unit==='credits'?'?123 456 (?987 654 321)':'?$1 234.56 (?$9 876 543.21)'));
          assert.equal(result.secondVertical,false);
          await key('Tab'); await evaluate('costTarget.focus();costTarget.scrollIntoView({block:"center"})');
          await until(`${help}.matches(':popover-open')`);
          const bounds=await evaluate(`(()=>{const r=${help}.getBoundingClientRect(),w=miniWatch.window;return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:w.innerWidth,height:w.innerHeight}})()`);
          assert.ok(bounds.left>=0&&bounds.top>=0&&bounds.right<=bounds.width+1&&bounds.bottom<=bounds.height+1,JSON.stringify(bounds));
          await key('Escape');await evaluate('costTarget.blur()');
          if(width===280) assert.equal(result.scroll,true,'extreme narrowing pans the session region');
        }
      }
    }
  }
  await command('Runtime.evaluate',{expression:`document.documentElement.style.fontSize='';document.documentElement.style.zoom=''`},pipSession);
  await evaluate(`document.documentElement.dataset.theme='${original.theme}';ReportView.setUnit('credits');miniWatch.settings();
    miniWatch.window.resizeTo(${original.width},${original.height})`,true);
  await evaluate('miniWatch.update=costUpdate;delete window.costUpdate;delete window.costEpoch');
  await fixture('running');await until(`miniWatch.view.body.rows.length===2`);
  await evaluate(`miniWatch.view.earlier.hidden=${original.earlierHidden};
    miniWatch.view.earlierToggle.setAttribute('aria-expanded','${!original.earlierHidden}');miniWatch.view.prompts.scrollTop=0`);
  checks.push('Four-column name-only Session and prompt (whole-session) costs; concurrent scopes, independent zero/N/A/partial/pending, historical model/effort/duration/calls, mixed/subagents, live focus/corrections/Escape, delayed hover/keyboard/touch; 3 widths, enlarged font/CSS zoom, themes and units; table costs do not widen opening fit');
};
