// Authenticated source -> summary -> DTO -> keyed table and shared help.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks = [], layouts = [];
  await fixture('models-source');
  await evaluate("location.hash='#/sessions?period=today&sort=model&direction=1'");
  await until('current.catalog?.data?.sort==="model" && current.catalog.data.total===30 && !current.catalog.busy && !current.catalog.operation');
  const page = () => evaluate('current.catalog.data.view.session_usage.map(row=>[row.session_id,row.model,row.multiple_models])');
  const ascending = await page();
  assert.equal(ascending.length,25);
  assert.equal(ascending[0][1],'Model-00');
  assert.equal(await evaluate('current.catalog.body.rows[0].cells[2].textContent'),'Model-00*');
  assert.equal(await evaluate('current.catalog.body.rows[1].cells[2].textContent'),'Model-01');
   assert.equal(await evaluate('current.catalog.body.rows[2].cells[2].textContent'),'Model-02*');
  const duration = await evaluate(`(()=>{
    const view=current.catalog,values=view.data.view.session_usage,target=view.body.rows[0].cells[5].firstChild;
    const states=[];
    for(const state of ['pending','retained','ready','unavailable','ready']) {
      view.rows(values.map(value=>({...value,metric_states:{...value.metric_states,duration:state}})));
      states.push({state,same:target===view.body.rows[0].cells[5].firstChild,
        help:target.classList.contains('help-value'),cursor:getComputedStyle(target).cursor,
        tab:target.tabIndex,description:target.getAttribute('aria-describedby')});
    }
    view.rows(values);return states;
  })()`);
  for(const state of duration) {
    assert.equal(state.same,true);assert.equal(state.help,false);assert.notEqual(state.cursor,'help');
    assert.equal(state.tab,-1);assert.equal(state.description,null);
  }
  await evaluate("current.catalog.headers.find(header=>header.key==='duration').th.firstChild.focus()");
  assert.match(await evaluate("document.getElementById('context-help').textContent"),/Execution duration, excluding idle gaps/);
  await evaluate('current.catalog.body.rows[0].cells[3].firstChild.focus()');
  const costHelp=await evaluate("document.getElementById('context-help').textContent");
  assert.match(costHelp,/^Session Models:\n• /);
  assert.match(costHelp,/\n\nSub Agents:\n• /);
  assert.doesNotMatch(costHelp,/Prompt #|Partial cost coverage|CCost:|Subtotal:|Session Model \d/);
  checks.push('Sessions CCost compact whole-session sections; Duration plain keyed value/cursor/tab/ARIA in pending/retained/ready/unavailable, with header help retained');
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  await evaluate('window.modelTarget=current.catalog.body.rows[0].cells[2].firstChild;modelTarget.focus()');
  await until('document.getElementById("context-help")?.matches(":popover-open")');
  const help = await evaluate('document.getElementById("context-help").textContent');
   assert.equal(help,'Model-00\n\nMain models\n• main-provider/Earlier · high\n• main-provider/Model-00 · high\n\nSubagents\n• child-provider/Child · high');
  await fixture('models-update');
  await until('document.getElementById("context-help").textContent.includes("child-provider/Child-new")');
  assert.equal(await evaluate('document.activeElement===modelTarget && modelTarget.isConnected'),true);
  await evaluate('current.catalog.body.rows[1].cells[2].firstChild.focus()');
   assert.doesNotMatch(await evaluate('document.getElementById("context-help").textContent'),/\nSubagents\n/);
  await evaluate('current.catalog.body.rows[2].cells[2].firstChild.focus()');
   assert.match(await evaluate('document.getElementById("context-help").textContent'),/\nSubagents\n• main-provider\/Model-02/);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await evaluate('document.activeElement.blur()');
  const point = await evaluate('(()=>{const r=modelTarget.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()');
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
  await until('document.getElementById("context-help").matches(":popover-open")');
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0});
  await until('document.getElementById("context-help").hidden');
  await command('Emulation.setTouchEmulationEnabled',{enabled:true});
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
   await until('document.getElementById("context-help").matches(":popover-open")');
   await command('Emulation.setTouchEmulationEnabled',{enabled:false});
   await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
   await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
   await until('!current.catalog.operation && !current.catalog.next.disabled && !current.catalog.next.navigationDisabled');
   await evaluate('current.catalog.next.click()');
   await until('current.catalog.data.offset===25 && !current.catalog.operation && !current.catalog.busy');
  assert.equal(await evaluate('current.catalog.body.rows.length'),5);
  assert.equal(await evaluate('current.catalog.body.rows[4].cells[2].textContent'),'');
  assert.equal(await evaluate(`current.catalog.body.rows[4].cells[2].querySelector('.metric-spinner')?.getAttribute('aria-label')`),
    'Loading model');
  assert.match(await evaluate('current.catalog.body.rows[4].value.display.model_help'),/No attributable executed main-thread model[\s\S]*Sub-agents/);
  await evaluate("location.hash='#/sessions?period=today&sort=model&direction=-1'");
  await until('current.catalog.data.direction===-1 && !current.catalog.busy');
  assert.equal((await page())[0][1],'Model-29');
  for (const width of [360,1366]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    const geometry = await evaluate('({width:innerWidth,page:document.documentElement.scrollWidth,columns:current.catalog.headers.length})');
    assert.ok(geometry.page<=width+1);assert.equal(geometry.columns,7);layouts.push(geometry);
    for (const [theme,scheme] of [['classic','light'],['web','light'],['web','dark']]) {
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:scheme},
        {name:'prefers-reduced-motion',value:'reduce'}]});
      const measurement=await evaluate(`(()=>{
        document.documentElement.dataset.theme=${JSON.stringify(theme)};
        const view=current.catalog, values=view.data.view.session_usage, row=view.body.rows[0], name=row.name;
        const measure=()=>({widths:view.headers.map(({th})=>th.getBoundingClientRect().width),
          heights:[...view.body.rows].map(r=>r.getBoundingClientRect().height),
          pan:[view.pan.clientWidth,view.pan.scrollWidth,view.pan.scrollHeight]});
        const pending={session_id:row.dataset.id,title:row.value.title,metric_state:'unavailable'};
        const empty={...pending,indexed:true,has_summary:true,model:'N/A',ccost:'0',complete:true,
          prompt_count:0,display:{ccost:'0',duration_ms:'0s'},
          metric_absences:{model:'complete_empty_history',ctx:'complete_empty_history',activity:'complete_empty_history'}};
        const original=measure(), states=[];
        for (const first of [pending,empty,pending,values[0]]) {
          view.rows([first,...values.slice(1)]);
          const spinner=row.metrics[0].querySelector('.metric-spinner');
          states.push({geometry:measure(),same:row===view.body.rows[0] && name===row.name,
            cells:[...row.cells].map(cell=>cell.textContent), animation:spinner&&getComputedStyle(spinner).animationName,
            pending:spinner?.getAttribute('aria-label')??null,
            help:row.metrics[0].classList.contains('help-value')});
        }
        return {original,states};
      })()`);
      for (const state of measurement.states) {
        assert.deepEqual(state.geometry,measurement.original);
        assert.equal(state.same,true);
      }
      for (const index of [0,2]) {
        const state=measurement.states[index];
        assert.deepEqual(state.cells.slice(2),['','','','','']);
        assert.equal(state.pending,'Loading model');assert.equal(state.animation,'none');assert.equal(state.help,false);
      }
      const absent=measurement.states[1];
      assert.deepEqual(absent.cells.slice(2),['?','0','0','0s','?']);
      assert.equal(absent.help,true);
      layouts.push({width,theme,scheme,...measurement.original});
    }
  }
  checks.push('source-backed latest main identity/star, two bullet groups, main-only omission, same-model roles, child-only not substituted for main model');
  checks.push('shared keyboard/Escape, hover/leave, touch, focused open-help source-revision refresh');
  checks.push('period-qualified Model asc/desc, unknown last, 25+5 paging, long name and 360/1366 seven-column layouts');
  checks.push('pending/final/known metric transitions, real zero and no layout changes at 360/1366 in Classic and Web Light/Dark, reduced motion');
  return {checks,layouts};
};
