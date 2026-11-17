// Authenticated shipped HTTP + canonical synthetic source, then explicit display DTO transitions.
const assert = require('node:assert/strict');
module.exports = async ({evaluate, until, fixture, command}) => {
  const checks=[],layouts=[];
  await fixture('detail-values-source');
  await evaluate("location.hash='#/sessions/root'");
  await until('current?.detail?.data?.value_authority?.rows.u_next === "known"');
  await evaluate(`window.detail=current.detail;window.mix=()=>[...detail.body.rows].find(r=>
    r.dataset.id===detail.data.result.view.prompt_blocks[0].rows.find(r=>r.event_id==='u_next').id).cells[9];
    window.originalMix=mix().textContent;window.footerCells=[...detail.footer.cells];
    window.footerTargets=footerCells.map(c=>c.firstChild);window.footerText=footerCells.map(c=>c.textContent);
    window.scope=detail.data.value_authority.scope;window.revision=detail.data.revision;
     detail.activity.tools.node.open=true;
     window.refreshNotices=[];
     const sourceStatus=detail.sourceStatus.bind(detail);
     detail.sourceStatus=value=>{sourceStatus(value);refreshNotices.push({
        state:value.state,pending:value.pending,reason:value.acquisition?.reason,status:detail.status.textContent,
       hidden:detail.status.hidden,loader:detail.loader.root.hidden});};`);
  assert.match(await evaluate('originalMix'),/^\d+\/\d+\/\d+\/\d+$/);
  for(const selector of ['detail.body.rows[0].cells[3].firstChild','detail.footer.cells[3].firstChild']) {
    await evaluate(`${selector}.focus()`);
    const costHelp=await evaluate("document.getElementById('context-help').textContent");
    assert.match(costHelp,/Session Models:\n• .+ — .+ — \(.+\)/);
    assert.doesNotMatch(costHelp,/Partial cost coverage|Partial pricing|CCost:|Subtotal:|independently rounded/);
    assert.equal(costHelp.includes('Prompt #'),selector.includes('body'));
    await evaluate('document.activeElement.blur()');
  }
  checks.push('Session Detail prompt/Complete-session CCost use compact grouped sections without coverage boilerplate and preserve prompt identifier scope');
  assert.equal(await evaluate(`detail.scroll.nextElementSibling===detail.context.root &&
    detail.context.root.nextElementSibling===detail.activity.root &&
    detail.root.querySelectorAll('.watch-session-summary').length===1 &&
    !detail.root.textContent.includes('Total CCost:')`),true);
  await fixture('detail-values-partial');
  await until('detail.data.revision !== revision && detail.data.value_authority.totals.total_calls === "pending"');
  assert.equal(await evaluate('mix().textContent===originalMix'),true);
  assert.deepEqual(await evaluate('[...detail.footer.cells].map(c=>c.textContent)'),await evaluate('footerText'));
  assert.equal(await evaluate('footerCells.every((c,i)=>c===detail.footer.cells[i] && c.firstChild===footerTargets[i])'),true);
  assert.equal(await evaluate('detail.activity.tools.node.open'),true);
  assert.equal(await evaluate('detail.values.retained && detail.status.hidden && !detail.status.textContent'),true);
  assert.equal(await evaluate('refreshNotices.every(n=>n.hidden && !n.status && n.loader)'),true,
    'real HTTP qualified partial refresh never exposes an informational notice');
  await evaluate('window.revision=detail.data.revision');
  await fixture('detail-values-correction');
  await until('detail.data.revision !== revision && detail.data.value_authority.rows.u_next === "invalidated"');
   assert.equal(await evaluate('mix().textContent'),'?');
  await fixture('detail-values-source');
  await until('detail.data.value_authority.rows.u_next === "known"');
  await fixture('fail');
  await until('refreshNotices.some(n=>n.reason==="source_unavailable")');
  assert.equal(await evaluate('detail.status.hidden && !detail.status.textContent'),true,
    'retained detail failures remain silent; shared source health owns outage notices');
  assert.equal(await evaluate('mix().textContent===originalMix'),true);
  await fixture('recover');
  await fixture('detail-values-epoch');
  // The exhausted source-unavailable attempt owns a 30s automatic cooldown;
  // allow that existing lane plus the ordinary 5s detail poll to recover.
  await until('detail.data.value_authority.scope!==scope', 60000);
  assert.equal(await evaluate('footerCells[3]!==detail.footer.cells[3]'),true);
  checks.push('real HTTP full→partial→complete corrected withdrawal→recovery→outage→source epoch; qualified mix/footer retention, invalidation, stable footer nodes and Tool Calls expansion');
  // Stop only the fixture view timer; the following cases deliberately supply
  // detached DTOs to the shipped renderer, not pretend source measurements.
  await evaluate(`clearTimeout(detail.timer);detail.attached=false;ReportView.setUnit('credits',detail.root);
    window.dto=structuredClone(detail.data);window.block=dto.result.view.prompt_blocks[0];
     window.paint=()=>{const value=structuredClone(dto);detail.update(value);detail.sourceStatus(value);};
    window.target=block.rows.find(r=>r.event_id==='u_next');
    window.qualified=()=>{for(const key of Object.keys(dto.value_authority.totals))dto.value_authority.totals[key]='known';};
    qualified();block.total_calls=42;block.duration_ms=9000;block.display.duration_ms='9s';
    block.total_ccost='12';block.display.total_ccost='12';
    block.display_units={credits:{total_ccost:'12',total_incoming_context_ccost:'70',total_extra_ccost:'30'},
      usd:{total_ccost:'$1.20',total_incoming_context_ccost:'$0.70',total_extra_ccost:'$0.30'}};
    block.total_incoming_context_ccost='70';block.total_extra_ccost='30';block.total_token_mix_percent=[2,96,1,1];
    target.token_mix_percent=[2,96,1,1];target.display.token_mix_percent='2/96/1/1';paint();
    window.cost=detail.footer.cells[3].firstChild;window.duration=detail.footer.cells[5].firstChild;
    window.oldCells=[...detail.footer.cells];window.oldTargets=oldCells.map(c=>c.firstChild);
    cost.focus();window.selectedNode=duration.firstChild;window.range=document.createRange();
    range.selectNodeContents(duration);getSelection().removeAllRanges();getSelection().addRange(range);
    window.selectedText=getSelection().toString();window.y=scrollY;
     window.help=document.getElementById('context-help');
     window.tableTop=detail.scroll.getBoundingClientRect().top;
     window.quietFrames=[];window.quietObserver=new MutationObserver(()=>quietFrames.push({
       text:detail.status.textContent,status:detail.status.getBoundingClientRect().height,
       loader:detail.loader.root.getBoundingClientRect().height}));
     quietObserver.observe(detail.root,{subtree:true,childList:true,attributes:true,characterData:true});`);
  await evaluate(`for(const key of Object.keys(dto.value_authority.totals))dto.value_authority.totals[key]='pending';
    dto.value_authority.rows.u_next='pending';target.token_mix_percent=null;target.display.token_mix_percent='running - consider ABORT';
    block.total_calls=null;block.duration_ms=null;block.display.duration_ms='N/A';block.total_token_mix_percent=null;
    block.total_incoming_context_ccost=null;block.total_extra_ccost=null;block.display.total_ccost='0';
    for(let i=0;i<10;i++)paint();`);
  assert.equal(await evaluate(`oldCells.every((c,i)=>c===detail.footer.cells[i] && c.firstChild===oldTargets[i]) &&
    document.activeElement===cost && duration.firstChild===selectedNode &&
    getSelection().toString()===selectedText && Math.abs(scrollY-y)<2 &&
    !help.hidden && cost.getAttribute('aria-describedby')===help.id`),true);
  assert.deepEqual(await evaluate('[...detail.footer.cells].slice(3).map(c=>c.textContent)'),
    ['12','42','9s','—','70','30','2/96/1/1']);
  await evaluate(`(async()=>{
    for(let cycle=0;cycle<3;cycle++)for(const pending of [
      {state:'loading',pending:true,result:null},
      {state:'observed',pending:true,result:null},
      {state:'loading',result:null,acquisition:{phase:'verifying',percent:35}}
    ]){detail.sourceStatus(pending);await new Promise(requestAnimationFrame);}
    for(let cycle=0;cycle<3;cycle++){
      ReportView.setUnit('usd',detail.root);paint();ReportView.setUnit('credits',detail.root);paint();
    }
  })()`);
  assert.equal(await evaluate(`quietFrames.length>0 && quietFrames.every(f=>!f.text && f.status===0 && f.loader===0) &&
    Math.abs(detail.scroll.getBoundingClientRect().top-tableTop)<2 &&
    document.activeElement===cost && !help.hidden && getSelection().toString()===selectedText`),true,
    'pending/retained frames have no banner, loader, reserved space, status announcement or lost interaction');
  await evaluate(`quietObserver.disconnect();ReportView.setUnit('usd',detail.root)`);
  assert.equal(await evaluate('cost.textContent'),'$1.20');
  assert.deepEqual(await evaluate('[detail.footer.cells[7].textContent,detail.footer.cells[8].textContent]'),['$0.70','$0.30']);
  await evaluate(`ReportView.setUnit('credits',detail.root);getSelection().removeAllRanges();cost.blur();
    qualified();block.total_calls=0;block.duration_ms=1000;block.display.duration_ms='1s';
    block.total_ccost='0';block.display.total_ccost='0';block.display_units={credits:{total_ccost:'0'},usd:{total_ccost:'$0.00'}};
    target.token_mix_percent=[0,98,1,1];target.display.token_mix_percent='0/98/1/1';dto.value_authority.rows.u_next='known';paint();`);
  assert.deepEqual(await evaluate('[detail.footer.cells[3].textContent,detail.footer.cells[4].textContent,detail.footer.cells[5].textContent]'),['0','0','1s']);
  await evaluate(`detail.sourceStatus({state:'source_unavailable',result:null});
    window.sourceError=detail.status.textContent;
    detail.sourceStatus({state:'observed',pending:true,result:null});`);
   assert.equal(await evaluate('detail.status.hidden && !detail.status.textContent && !sourceError'),true);
  await evaluate('paint()');
  assert.equal(await evaluate('detail.status.hidden && !detail.status.textContent'),true,
    'qualified successful recovery remains silent');
   checks.push('silent real partial refresh and repeated pending/retained rendered frames; zero status/loader height or text, no table shift, repeated units and retained focus/selection/help; detail-only faults stay silent under shared source-health ownership');
  checks.push('explicit DTO pending refresh preserves focused open help, selected text/text-node, cells/targets and scroll; units change retained observations; authoritative smaller/zero values replace atomically');
  // Exact shared header text and source-backed model/call cell help.
  const helpText = async expression => {
    await evaluate(`document.activeElement?.blur();${expression}.focus();ContextHelp.refresh(${expression})`);
    return evaluate("document.getElementById('context-help').textContent");
  };
  for (const [column,key] of [[1,'model'],[4,'calls'],[5,'duration']]) {
    assert.equal(await helpText(`detail.root.querySelectorAll('thead button')[${column}]`),
      await evaluate(`ReportView.headerHelp.${key}`));
  }
  const modelHelp=await helpText('detail.body.rows[0].cells[1].firstChild');
  const callsHelp=await helpText('detail.body.rows[0].cells[4].firstChild');
  assert.match(modelHelp,/Subagent|Main prompt/);
  assert.match(callsHelp,/github-copilot\/gpt-test.*calls/s);
  assert.doesNotMatch(callsHelp,/Total Calls|price tier/);
  assert.equal(await evaluate(`!detail.body.rows[0].cells[2].querySelector('[tabindex]') &&
    !detail.body.rows[0].cells[5].querySelector('[tabindex]')`),true);
  checks.push('shared Watch Model/Calls/Duration header help; source-projected model/subagent effort and compact request groups; no Effort/Duration cell help target');
  // Relocated Context uses the same component, warning observations and interaction.
  await evaluate(`window.contextValue={watch_next_context_tokens:120000,display:{watch_next_context_tokens:'120k'},
    warning:{severity:'approaching',text:'[Approaching price threshold >100.0K]',multiplier:'2.4',
      display:{warning_cost:'(2.4x more expensive)'}}};block.session_context=contextValue;
    window.reference=new WatchView.ContextLine();paint();reference.update(structuredClone(contextValue));`);
  for(const severity of ['approaching','exceeded','none']) {
    await evaluate(`contextValue.warning.severity='${severity}';block.session_context=contextValue;paint();
      reference.update(structuredClone(contextValue));`);
    assert.equal(await evaluate('detail.context.root.innerHTML===reference.root.innerHTML'),true);
  }
  await evaluate("contextValue.warning.severity='exceeded';paint()");
  const contextHelp = 'detail.context.contextHelp';
  assert.match(await helpText(contextHelp),/not a session spending limit/);
  await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  assert.equal(await evaluate("document.getElementById('context-help').hidden"),true);
  await evaluate('document.activeElement.blur()');
  const point=await evaluate(`(()=>{const n=${contextHelp};n.scrollIntoView({block:'center'});const r=n.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point});
  await until('!document.getElementById("context-help").hidden');
  await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point]});
  await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await until('!document.getElementById("context-help").hidden');
  for(const width of [360,1366]) for(const theme of ['light','dark']) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme}]});
    await evaluate("document.documentElement.dataset.theme='web'");
    const layout=await evaluate(`({overflow:document.documentElement.scrollWidth>innerWidth+1,
      order:detail.scroll.nextElementSibling===detail.context.root,
      severity:detail.context.root.dataset.severity,color:getComputedStyle(detail.context.contextValue).color})`);
    assert.equal(layout.overflow,false);assert.equal(layout.order,true);assert.equal(layout.severity,'exceeded');
    layouts.push({width,theme,...layout});
  }
  await evaluate(`contextValue.watch_next_context_tokens=null;contextValue.display.watch_next_context_tokens='N/A';
    contextValue.context_state='invalidated';paint();`);
  assert.equal(await evaluate("detail.context.contextValue.textContent==='N/A' && detail.context.warningIcon.hidden"),true);
  await evaluate('detail.invalidateValues()');
  assert.equal(await evaluate('!detail.body.children.length && !detail.footer.children.length && detail.scroll.hidden'),true);
  checks.push('single table→Context→Tool Calls order; Watch Context DOM parity for approaching/exceeded/no warning, keyboard/Escape/hover/emulated touch, unavailable/invalidation; 360/1366 light/dark no page overflow; authority loss clears table');
  return {checks,layouts};
};
