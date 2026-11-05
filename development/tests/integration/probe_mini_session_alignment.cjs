// Rendered first-cell alignment and intrinsic suffix widths in actual hidden Document PiP.
const assert = require('node:assert/strict');
module.exports = async function alignment({evaluate,until,fixture,command,sessionId,pipSession,layouts,checks}) {
  const original = await evaluate(`({width:miniWatch.window.outerWidth,height:miniWatch.window.outerHeight,
    theme:document.documentElement.dataset.theme,earlierHidden:miniWatch.view.earlier.hidden})`);
  await fixture('history-3-6');
  await until(`miniWatch.view.promptRows.size===6 && miniWatch.view.historyRows.size===3`);
  await evaluate(`(() => {const p=structuredClone(liveValue);p.view.now_ms++;
    const values=['0','N/A','Loading…','?12','123 456 789','23'];
    const usd=['$0.00','N/A','Loading…','?$0.12','$1 234 567.89','$0.23'];
    for(const cards of [p.view.active_cards,p.view.history_cards]) cards.forEach((card,index)=>{
      card.title=index%3===0?'Short':index%3===1?'Beginning of a very long title '.repeat(30):'';
      card.session_summary.cost.display_units={credits:{known_ccost:values[index]},usd:{known_ccost:usd[index]}};
    });miniWatch.update(p);miniWatch.view.earlier.hidden=false;
    miniWatch.view.earlierToggle.setAttribute('aria-expanded','true');
    window.alignmentRow=miniWatch.view.body.rows[0];})()`);
  for(const width of [560,800,280]) {
    await evaluate(`miniWatch.window.resizeTo(${width},400)`,true);
    await until(`miniWatch.window.innerWidth<=${width}`);
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
            const errors=[],suffixes=[],titleWidths=[];
            for(const body of [v.body,v.historyBody]) {
              const table=body.parentNode,header=table.querySelector('th'),head=header.querySelector('.mini-session-heading');
              const cells=[header,...[...body.rows].map(row=>row.cells[0])];
              if(table.querySelectorAll('th').length!==(body===v.body?5:2)) errors.push('extra column');
              if(head.children[0].textContent!=='Session'||head.children[1].textContent!==' (Total CCost)') errors.push('header text');
              header.querySelector('button').focus();
               if(!v.doc.getElementById('context-help').textContent.includes('Session — The name of the session.\\n\\nTotal CCost —')) errors.push('header scope');
              for(const cell of cells) {
                const value=cell.querySelector('.mini-session-value'),left=value.children[0],right=value.children[1],s=style(cell);
                const start=rect(cell).left+(parseFloat(s.borderLeftWidth)+parseFloat(s.paddingLeft))*zoom;
                const end=rect(cell).right-(parseFloat(s.borderRightWidth)+parseFloat(s.paddingRight))*zoom;
                const range=d.createRange();range.selectNodeContents(right);
                if(Math.abs(rect(left).left-start)>1||Math.abs(rect(right).right-end)>1) errors.push('not edge anchored');
                if(rect(left).right>rect(right).left+1) errors.push('overlap');
                if(Math.abs(rect(right).width-range.getBoundingClientRect().width)>1) errors.push('reserved suffix width');
                if(right.scrollWidth>right.clientWidth+1||style(right).whiteSpace!=='pre') errors.push('clipped suffix');
                if(cell!==header) {
                  if(!right.textContent.startsWith(' (')||!right.textContent.endsWith(')')) errors.push('row parentheses');
                  if(style(left).textOverflow!=='ellipsis'||style(left).whiteSpace!=='nowrap') errors.push('title overflow');
                   if(!cell.parentNode.getAttribute('aria-label').includes(left.textContent) || cell.querySelector('.help-trigger')) errors.push('accessible title without row cue');
                  if(left.textContent==='Short'&&left.scrollWidth>left.clientWidth+1) errors.push('short title clipped');
                  suffixes.push(right.textContent);titleWidths.push(rect(left).width);
                } else if(range.getBoundingClientRect().height>rect(right).height+1) errors.push('wrapped heading');
              }
            }
            const active=v.body.rows[1].cells[0].querySelector('.mini-session');
            if(active.scrollWidth<=active.clientWidth) errors.push('long title not constrained');
            if(v.body.rows[0]!==alignmentRow||v.earlier.hidden) errors.push('rerender reset');
            return {errors,suffixes,titleWidths,width:w.innerWidth,font:style(d.documentElement).fontSize,
              scroll:v.prompts.scrollWidth>v.prompts.clientWidth,
              pageOverflow:d.documentElement.scrollWidth>w.innerWidth||d.documentElement.scrollHeight>w.innerHeight};})()`);
          layouts.push({case:`session-alignment-${width}-${font}-zoom${zoom}-${theme}-${scheme}-${unit}`,...result});
          assert.deepEqual(result.errors,[],JSON.stringify(result));
          assert.equal(result.pageOverflow,false);
          assert.deepEqual(result.suffixes,unit==='credits'?
            [' (0)',' (N/A)',' (Loading…)',' (?12)',' (123 456 789)',' (23)',' (0)',' (N/A)',' (Loading…)']:
            [' ($0.00)',' (N/A)',' (Loading…)',' (?$0.12)',' ($1 234 567.89)',' ($0.23)',' ($0.00)',' (N/A)',' (Loading…)']);
          assert.ok(result.titleWidths[0]>result.titleWidths[4],'short amount leaves more title width than large total');
          if(width===280) assert.equal(result.scroll,true,'extreme narrowing pans the session region');
        }
      }
    }
  }
  await command('Runtime.evaluate',{expression:`document.documentElement.style.fontSize='';document.documentElement.style.zoom=''`},pipSession);
  await evaluate(`document.documentElement.dataset.theme='${original.theme}';ReportView.setUnit('credits');miniWatch.settings();
    miniWatch.window.resizeTo(${original.width},${original.height})`,true);
  await fixture('running');await until(`miniWatch.view.body.rows.length===2`);
  await evaluate(`miniWatch.view.earlier.hidden=${original.earlierHidden};
    miniWatch.view.earlierToggle.setAttribute('aria-expanded','${!original.earlierHidden}');miniWatch.view.prompts.scrollTop=0`);
  checks.push('Both single first cells edge-anchor Session and natural-width parenthesized cost; short/long/fallback titles, all display states, live identity, 3 widths, enlarged font/CSS zoom, themes and units preserve suffixes without page overflow');
};
