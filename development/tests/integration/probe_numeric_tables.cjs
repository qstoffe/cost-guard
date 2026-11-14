// Canonical fixture exports through actual Full/Mini PiP, Sessions and detail DOM.
const assert = require('node:assert/strict');
module.exports = async ({command,evaluate,until,owner,mini,checks,layouts}) => {
  const full = '.watch-active tbody td:nth-child(6) .help-value';
  const prompt = '.mini-prompts tbody td:nth-child(3) .mini-cost-value';
  const total = '.mini-prompts tbody td:nth-child(4) .mini-cost-value';
  for (const unit of ['credits','usd']) {
    for (const mode of ['mixed','zero','absent','mixed']) {
      await evaluate(owner,`(() => {
        document.activeElement?.blur();miniWatch.window.document.activeElement?.blur();
        ReportView.setUnit('${unit}',current.watch.root);ReportView.setUnit('${unit}',miniWatch.view.root);
        const p={...liveValue,view:structuredClone(liveValue.probe_ccost_unavailable['${mode}'])};
        p.source_observed_at_ms=p.view.now_ms=Date.now();
        // Distinct synthetic sessions isolate each source fixture's state.
        for(const c of [...p.view.active_cards,...p.view.history_cards]) {
          c.observed_at_ms=Date.now();c.session_id+='-numeric-${mode}';
        }
        current.watch.update(p);miniWatch.update(p);
      })()`);
      for (const [id,selector] of [[owner,full],[mini,prompt],[mini,total]]) {
        const text=await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).textContent`);
        // The whole-session fixture includes one supported zero-cost compaction.
        // Mini intentionally uses its priced subtotal, not prompt unknownness.
        if(mode==='absent') assert.equal(text,id===mini && selector===total ? (unit==='usd'?'$0.00':'0') : 'N/A');
        else if(mode==='zero') assert.equal(text,unit==='usd'?'$0.00':'0');
        else {
          assert.match(text,unit==='usd'?/^\$\d/:/^[<\d]/);
          assert.doesNotMatch(text,/\?|Partial /);
        }
        layouts.push({unit,mode,surface:id===mini?'Mini':'Full',selector,text});
      }
      if(mode==='mixed') {
        for (const [id,selector] of [[owner,full],[mini,prompt],[mini,total]]) {
          await command('Page.bringToFront',{},id);
          await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},id);
          await evaluate(id,`document.querySelector(${JSON.stringify(selector)}).focus()`);
          await until(id,`document.querySelector('#context-help')?.matches(':popover-open')`);
          const help=await evaluate(id,`document.querySelector('#context-help').textContent`);
          assert.doesNotMatch(help,/\?\s*(?:\$|[<\d])/);
          await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},id);
        }
      }
    }
  }
  await evaluate(owner,`miniWatch.close();window.numericSessions=new SessionsCatalog.View(()=>Promise.resolve());
    numericSessions.data={view:{timezone_id:'UTC'}};
    window.numericDetail=new SessionDetail.View(()=>Promise.resolve(),'root');document.body.append(numericSessions.root,numericDetail.root)`);
  for(const unit of ['credits','usd']) {
    for(const mode of ['mixed','absent','zero','mixed']) {
      await evaluate(owner,`ReportView.setUnit('${unit}',document.body);
        numericSessions.rows(liveValue.probe_ccost_unavailable['${mode}'].probe_sessions);numericSessions.pan.hidden=false;
        numericDetail.update({revision:'${unit}-${mode}',state:'observed',result:{observed_at_ms:Date.now(),
          view:liveValue.probe_ccost_unavailable['${mode}'].probe_detail}})`);
      const cells=await evaluate(owner,`['.sessions-catalog tbody td:nth-child(5)',
        '.session-detail tbody td:nth-child(4)','.session-detail tfoot td:nth-child(4)']
        .map(selector=>document.querySelector(selector).textContent)`);
      for(const text of cells) {
        if(mode==='absent') assert.equal(text,'N/A');
        else assert.match(text,unit==='usd'?/^\$\d/:/^[<\d]/);
        assert.doesNotMatch(text,/\?|Partial /);
      }
      layouts.push({unit,mode,surface:'Sessions/detail/footer',cells});
    }
  }
  checks.push('Both units: canonical partial, unavailable, zero and refresh-back values in Full Watch, Mini/PiP, Sessions, detail/footer and cost-help amounts; no numeric prefix or replacement decoration');
};
