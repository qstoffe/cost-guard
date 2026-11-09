// Real hidden Chromium assertions for the full-Watch prompt-local cost column.
const assert = require('node:assert/strict');
module.exports = async function checkPromptCost(evaluate, expectedCredits = '1250', expectedUSD = '$12.50') {
  const result = await evaluate(`(() => {
    const active=document.querySelector('.watch-active'), history=document.querySelector('.watch-history');
    const cell=parent=>parent.querySelector('tbody tr').cells[5];
    const values=()=>[active,history].map(parent=>cell(parent).textContent);
    const credits=values();
    ReportView.setUnit('usd',document.getElementById('result')); const usd=values();
    ReportView.setUnit('credits',document.getElementById('result'));
    const restored=values();
    const help=[], details=[];
    for (const parent of [active,history]) {
      const button=parent.querySelector('th:nth-child(6) button');
      button.focus({preventScroll:true});
      const panel=document.getElementById(button.getAttribute('aria-describedby'));
      help.push({name:button.textContent,open:panel.matches(':popover-open'),text:panel.textContent,
        role:panel.getAttribute('role'),within:panel.getBoundingClientRect().right<=innerWidth});
      button.blur(); button.click(); help.at(-1).click=panel.matches(':popover-open'); panel.hidePopover();
      for (const unit of ['credits','usd','credits']) {
        ReportView.setUnit(unit,document.getElementById('result'));
        const target=cell(parent).firstChild;
        target.focus({preventScroll:true});
        const p=INPUT.view[parent===active?'active_cards':'history_cards'][0].rows[0].prompt;
        const tokens={...p.display,...p.display_units[unit]};
        details.push({unit,value:target.textContent,total:tokens.ccost,split:panel.textContent.startsWith(
          'Incoming Context CCost (I): '+tokens.incoming_context_ccost+'\\nExtra CCost (E): '+tokens.extra_ccost+'\\n'),
          rich:panel.textContent.endsWith(tokens.cost_detail_help),
          intrinsic:target.getBoundingClientRect().width<cell(parent).getBoundingClientRect().width,
          focus:document.activeElement===target,open:panel.matches(':popover-open')});
        target.blur();
      }
    }
    const geometry=[];
    for (const zoom of [100,150,200]) {
      document.documentElement.style.fontSize=(15*zoom/100)+'px';
      const rows=[...document.querySelectorAll('.watch-prompt-table tbody tr')];
      geometry.push({zoom,complete:rows.every(row=>[...row.cells].filter((_,i)=>i!==2)
        .every(node=>node.scrollWidth<=node.clientWidth)),
        numbered:rows.every(row=>row.querySelector('.watch-prompt-number').getBoundingClientRect().width>0),
        oneLine:rows.every(row=>getComputedStyle(row.cells[5]).whiteSpace==='nowrap'),
        pageOverflow:document.documentElement.scrollWidth>innerWidth});
    }
    document.documentElement.style.fontSize='';window.scrollTo(0,0);
    return {credits,usd,restored,help,details,geometry}; })()`);
  assert.equal(result.credits[0], expectedCredits);
  assert.equal(result.usd[0], expectedUSD);
  assert.deepEqual(result.restored, result.credits);
  for (const help of result.help) {
    assert.equal(help.name, 'CCost');
    assert.equal(help.open, true); assert.equal(help.click, true);
    assert.equal(help.within, true); assert.equal(help.role, 'tooltip');
    assert.match(help.text, /Estimated reference cost of this prompt, not your bill[\s\S]*value for Incoming\/Extra CCost and model\/subagent details/);
  }
  for (const detail of result.details) {
    assert.equal(detail.value,detail.total);
    for (const key of ['split','rich','intrinsic','focus','open']) assert.equal(detail[key],true,JSON.stringify({key,detail}));
  }
  for (const sample of result.geometry) {
    assert.equal(sample.complete, true); assert.equal(sample.numbered, true);
    assert.equal(sample.oneLine, true); assert.equal(sample.pageOverflow, false);
  }
  return result;
};
