// Actual-DOM assertions for session-scoped inline guidance and focus-safe updates.
const assert = require('node:assert/strict');
module.exports = async function checkContext(evaluate) {
  const result = await evaluate(`(() => {
    const original=structuredClone(INPUT.view.active_cards);
    const card=INPUT.view.active_cards[0], item=card.rows[0], value=card.session_summary;
    const root=()=>document.querySelector('.watch-active .watch-card');
    const summary=()=>root().querySelector('.watch-session-summary');
    const icon=()=>summary().firstChild;
    try {
      const earlier=document.querySelector('.watch-history .watch-session-summary');
      const both=summary().textContent.includes('Session Context: 120k') && earlier.textContent.includes('Session Context: 120k');
      const ectx=root().querySelector('tbody td:nth-child(9)').textContent;
      const undecorated=!/[~≈⚠]/.test(ectx) && !root().querySelector('.watch-context-warning');
      const transitions=[];
      for (const severity of ['approaching','exceeded','none','approaching']) {
        icon().focus({preventScroll:true}); const focused=icon(), protectedFocus=document.activeElement===focused;
        value.context.warning.severity=severity;redraw();
        const line=summary().textContent, color=getComputedStyle(summary()).color;
        transitions.push({severity,actual:summary().dataset.severity,visible:!icon().hidden,
          stable:!protectedFocus||icon()===focused,color,iconColor:getComputedStyle(icon()).color,
          costColor:getComputedStyle(summary().children[3]).color,
          placement:severity==='none'?!line.includes('⚠')&&!line.includes('threshold'):
            /120k \\(.*[Pp]rice threshold.*\\) · Session CCost:/.test(line),
          accessible:severity==='none'||(icon().tabIndex===0 && icon().getAttribute('aria-label').includes('price threshold') &&
            icon().getAttribute('role')==='img')});
      }
      const ordinaryColor=getComputedStyle(summary()).color;
      value.context.watch_next_context_tokens=null;value.context.display.watch_next_context_tokens='N/A';redraw();
      const invalidated=summary().textContent.startsWith('Session Context: N/A · Session CCost:') && icon().hidden && summary().dataset.severity==='none';
      value.context.watch_next_context_tokens=120000;value.context.display.watch_next_context_tokens='120k';
      value.context.warning.severity='none';redraw();
      const plain=summary().textContent.startsWith('Session Context: 120k · Session CCost:');
      const originalCost=value.cost.display.known_ccost;
      ReportView.setUnit('usd',document.getElementById('result'));
      const usd=summary().textContent.includes('$');
      ReportView.setUnit('credits',document.getElementById('result'));
      const credits=summary().textContent.includes(originalCost);
      return {both,undecorated,transitions,ordinaryColor,invalidated,plain,usd,credits};
    } finally {
      document.activeElement?.blur();INPUT.view.active_cards=original;redraw();
    }
  })()`);
  for (const key of ['both','undecorated','invalidated','plain','usd','credits']) assert.equal(result[key],true,key);
  for (const sample of result.transitions) {
    assert.equal(sample.actual,sample.severity);assert.equal(sample.visible,sample.severity!=='none');
    assert.equal(sample.stable,true);assert.equal(sample.accessible,true);assert.equal(sample.placement,true);
    assert.equal(sample.costColor,sample.color,'entire summary inherits severity');
    if (sample.severity==='exceeded') assert.equal(sample.color,sample.iconColor);
    else assert.equal(sample.color,result.ordinaryColor);
  }
  return result;
};
