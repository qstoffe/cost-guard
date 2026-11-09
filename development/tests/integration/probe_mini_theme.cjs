// Real headless Document PiP foregrounds over synthetic shipped HTTP/SSE memberships.
const assert=require('node:assert/strict');
module.exports=async function colors({evaluate,until,fixture,command,sessionId,open,close,capture,layouts,checks}) {
  const publish=async phase=>{const {published}=await fixture('mini-lifecycle-'+phase);
    await until(`liveValue.view.now_ms===${published} && JSON.stringify(miniWatch.observations.view.history_cards)===JSON.stringify(liveValue.view.history_cards) &&
      miniWatch.observations.view.cards_state===liveValue.view.cards_state`);};
  const inspect=()=>evaluate(`(()=>{const v=miniWatch.view,w=miniWatch.window,style=n=>w.getComputedStyle(n);
    const token=name=>{const n=v.doc.createElement('span');n.style.color='var('+name+')';v.root.append(n);
      const value=style(n).color;n.remove();return value;};
    return {normal:style(v.body).color,running:token('--watch-running'),success:token('--watch-success'),error:token('--error'),
      rows:[...v.promptRows.values()].map(row=>({id:row.dataset.id,cls:row.className,color:style(row).color,
        values:[...row.cells].map(cell=>style(cell.firstElementChild||cell).color),label:row.getAttribute('aria-label'),
        same:row.dataset.id!=='mini-lifecycle-4'||row===window.lifecycleRow})),
      fullHistory:[...document.querySelectorAll('.watch-history tbody tr')].map(row=>row.className),
      fullActive:[...document.querySelectorAll('.watch-active tbody tr')].map(row=>row.className)};})()`);
  const check=async(cls='',label='Completed',same=true)=>{
    const value=await inspect(),row=value.rows.find(row=>row.id==='mini-lifecycle-4');
    assert.equal(value.rows.length,5);assert.equal(new Set(value.rows.map(row=>row.id)).size,5);
    assert.ok(row);assert.equal(row.cls,cls);assert.ok(row.label.includes(label));if(same)assert.equal(row.same,true);
    for(const item of value.rows) {
      const expected=item===row&&cls?value[cls.replace('mini-','')]:value.normal;
      assert.equal(item.color,expected);assert.ok(item.values.every(color=>color===expected),'all four values share the foreground');
    }
    assert.ok(value.fullHistory.every(cls=>cls===''),'Full Watch history stays neutral');
    if(cls==='mini-running'||cls==='mini-success')assert.deepEqual(value.fullActive,[cls.replace('mini-','watch-')]);
    return value;
  };
  for(const [theme,color] of [['classic','dark'],['web','light'],['web','dark']]) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},sessionId);
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    for(const width of [650,280]) for(const unit of ['credits','usd']) {
      await evaluate(`ReportView.setUnit('${unit}');miniWatch.settings()`);
      await publish('cold');await open();await evaluate(`miniWatch.window.resizeTo(${width},550)`,true);
      await evaluate(`window.lifecycleRow=miniWatch.view.promptRows.get('mini-lifecycle-4')`);
      const cold=await check();assert.notEqual(cold.normal,cold.success);assert.notEqual(cold.normal,cold.error);
      assert.ok(cold.rows.every(row=>row.cls===''));
      await publish('running');await until(`miniWatch.view.promptRows.get('mini-lifecycle-4')?.className==='mini-running'`);
      await check('mini-running','Running');
      await publish('success');await until(`miniWatch.view.promptRows.get('mini-lifecycle-4')?.className==='mini-success'`);
      await check('mini-success');
      await publish('history-success');await until(`miniWatch.view.promptRows.get('mini-lifecycle-4')?.className===''`);
      await check();
      await evaluate(`ReportView.setUnit('${unit==='credits'?'usd':'credits'}');miniWatch.settings()`);await check();
      await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme==='classic'?'web':'classic'}'})))()`);
      await check();
      await evaluate(`(async()=>{applySettings(await api('/api/settings/theme',{theme:'${theme}'}));ReportView.setUnit('${unit}');miniWatch.settings();})()`);
      await check();
      for(const phase of ['retry','retry','history-success']) {await publish(phase);await check();}
      await evaluate(`miniWatch.render();miniWatch.syncTheme();miniWatch.settings()`);await check();
      await close();await open();await check('','Completed',false);
      await evaluate(`window.lifecycleRow=miniWatch.view.promptRows.get('mini-lifecycle-4')`);
      for(const [phase,label] of [['aborted','Aborted'],['error','Error']]) {
        await publish('running');await check('mini-running','Running');
        await publish(phase);await check('mini-error',label);
        await publish('history-'+phase);await check('',label);
      }
      await publish('unverified');await check('','Unverified');
      await publish('invalidated');await until('miniWatch.view.promptRows.size===0');
      await publish('pending');assert.equal(await evaluate('miniWatch.view.promptRows.size'),0);
      await publish('cold');await check('','Completed',false);
      layouts.push({case:`lifecycle-${theme}-${color}-${width}-${unit}`,cold,final:await inspect()});
      if(width===650&&unit==='credits')await capture(`neutral-history-${theme}-${color}`);
      await close();
    }
  }
  await fixture('running');await until('liveValue.view.active_cards.length===2');
  await evaluate(`ReportView.setUnit('credits');miniWatch.settings()`);
  checks.push('Five successful cold histories; running/success/error/abort to neutral history in same row; retained/repeated SSE, reopen, unverified and proof invalidation/arrival; computed four-cell foregrounds in Classic/Web light/dark × Credits/USD × 650/280 widths; Full Watch classes unchanged');
};
