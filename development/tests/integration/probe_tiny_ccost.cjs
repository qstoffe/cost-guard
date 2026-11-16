// Real shared source-derived Decimal projections, delivered through the HTTP/SSE fixture.
const assert = require('node:assert/strict');
module.exports = async ({command,evaluate,until,owner,mini,checks,layouts,full,prompt,total}) => {
  await evaluate(owner,`window.tinyAccounts=new AccountCards.View();
    document.body.append(tinyAccounts.root)`);
  const account = '.live-account-cards .account-subscription .metric-value .help-value';
  for (const mode of ['tiny','tiny-partial']) {
    await evaluate(owner,`(() => {
      window.tinyPublication={...liveValue,view:structuredClone(liveValue.probe_ccost_unavailable['${mode}'])};
      const p=tinyPublication;
      p.source_observed_at_ms=p.view.now_ms=Date.now();
      p.view.history_cards=[];p.view.recent_finished_cards=[];
      for(const c of p.view.active_cards) {
        c.session_id+='-${mode}';c.observed_at_ms=Date.now();
        c.rows[0].prompt.in_progress=true;c.rows[0].prompt.execution_unverified=false;
      }
      current.watch.update(p);miniWatch.update(p);
      tinyAccounts.update(p.view);
      window.tinyNodes=[document.querySelector(${JSON.stringify(full)}),
        miniWatch.view.root.querySelector(${JSON.stringify(prompt)}),
        miniWatch.view.root.querySelector(${JSON.stringify(total)}),
        document.querySelector(${JSON.stringify(account)})];
    })()`);
    for(const [theme,scheme,width] of [['classic','light',1280],['web','dark',360],['web','light',1280]]) {
      for(const id of [owner,mini]) await command('Emulation.setEmulatedMedia',
        {features:[{name:'prefers-color-scheme',value:scheme}]},id);
      await command('Emulation.setDeviceMetricsOverride',
        {width,height:900,deviceScaleFactor:1,mobile:false},owner);
      await evaluate(owner,`document.documentElement.dataset.theme='${theme}';
        miniWatch.window.document.documentElement.dataset.theme='${theme}'`);
      for(const [unit,expected] of [['credits','<0.1'],['usd','<$0.01'],['credits','<0.1']]) {
        await evaluate(owner,`ReportView.setUnit('${unit}',document.body);
          ReportView.setUnit('${unit}',miniWatch.view.root);
          current.watch.update(tinyPublication);miniWatch.render()`);
        for(const [id,selector,index] of [[owner,full,0],[mini,prompt,1],[mini,total,2],[owner,account,3]]) {
          const facts=await evaluate(id,`(() => {
            const n=document.querySelector(${JSON.stringify(selector)}),r=n.getBoundingClientRect();
            return {text:n.textContent,aria:n.getAttribute('aria-label'),width:r.width,
              fits:n.scrollWidth<=n.clientWidth+1,
              same:n===${id===mini?'opener.':''}tinyNodes[${index}]};
          })()`);
          assert.equal(facts.text,index===3?'CCost Today: '+expected:expected);
          assert.equal(facts.same,true,'unit toggle preserves amount DOM');
          assert.ok(facts.width>0 && facts.fits,JSON.stringify(facts));
          if(index===1 || index===2) assert.equal(facts.aria,
            (index===1?'Prompt':'Whole-session')+' reference CCost: '+expected);
          layouts.push({mode,theme,scheme,viewportWidth:width,unit,surface:index,...facts});
        }
        assert.equal(await evaluate(owner,'miniWatch.view.dailyAmount.textContent'),expected);
        assert.ok((await evaluate(owner,'current.watch.daily.textContent')).includes(expected));
        // Existing prompt/session popup amounts update with units, no new precision or interaction.
        for(const selector of [prompt,total]) {
          await command('Page.bringToFront',{},mini);
          await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9},mini);
          await evaluate(mini,`document.querySelector(${JSON.stringify(selector)}).focus()`);
          await until(mini,`document.querySelector('#context-help')?.matches(':popover-open')`);
          assert.ok((await evaluate(mini,`document.querySelector('#context-help').textContent`)).includes(expected));
          await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27},mini);
          await evaluate(mini,'document.activeElement?.blur()');
        }
      }
    }
  }
  await command('Emulation.setDeviceMetricsOverride',
    {width:1280,height:900,deviceScaleFactor:1,mobile:false},owner);
  await evaluate(owner,'tinyAccounts.root.remove()');
  checks.push('Source-priced 0.001 Credit, complete/partial: Full/Mini prompt, whole-session Total, daily and subscription CCost Today; Credits↔USD live text/help/AX, retained DOM and unclipped dark/light amounts');
};
