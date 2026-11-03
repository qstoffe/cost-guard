// Actual-DOM assertions for full Watch warning ownership and focus-safe updates.
const assert = require('node:assert/strict');
module.exports = async function checkContext(evaluate) {
  const result = await evaluate(`(() => {
    const original=structuredClone(INPUT.view.active_cards);
    const card=INPUT.view.active_cards[0], item=card.rows[0];
    const root=()=>document.querySelector('.watch-active .watch-card');
    const cell=()=>root().querySelector('tbody tr:last-child td:last-child > span');
    const icon=()=>cell().firstChild;
    const footer=()=>root().querySelector('.watch-context-warning');
    try {
      const earlier=document.querySelector('.watch-history tbody tr td:last-child');
      const both=cell().textContent==='⚠ 120k' && earlier.textContent==='⚠ 120k';
      const ordinary=structuredClone(item); ordinary.prompt.event_id='unrelated';
      ordinary.context_cell.warning=null;
      card.rows.unshift(ordinary);redraw();
      const ownership=!root().querySelector('tbody tr:first-child td:last-child').textContent.includes('⚠') &&
        cell().textContent==='⚠ 120k';
      const transitions=[];
      for (const severity of ['approaching','exceeded','none','approaching']) {
        icon().focus({preventScroll:true}); const focused=icon(), protectedFocus=document.activeElement===focused;
        item.context_cell.warning.severity=severity;card.context_warning.severity=severity;redraw();
        transitions.push({severity,cell:cell().dataset.severity,footer:footer().dataset.severity,
          visible:!icon().hidden,protectedFocus,stable:!protectedFocus||icon()===focused,
          accessible:severity==='none'||(icon().tabIndex===0 && icon().getAttribute('aria-label').includes('context price threshold') &&
            icon().getAttribute('role')==='img' && document.getElementById(icon().getAttribute('aria-describedby'))===footer())});
      }
      const color=getComputedStyle(icon()).color, rowColor=getComputedStyle(cell().closest('tr')).color;
      const singleLine=getComputedStyle(cell().closest('td')).whiteSpace==='nowrap';
      // A compaction invalidates the current estimate even if historical row metrics remain high.
      item.context_cell.watch_next_context_tokens=null;item.context_cell.display.watch_next_context_tokens='N/A';
      item.context_cell.warning.severity='none';card.context_warning.severity='none';redraw();
      const invalidated=cell().textContent==='N/A' && icon().hidden && footer().hidden;
      item.context_cell.watch_next_context_tokens=120000;item.context_cell.display.watch_next_context_tokens='120k';
      redraw();const plain=cell().textContent==='120k';
      item.context_cell.warning.severity='exceeded';item.context_cell.warning.owner_id='not-this-row';redraw();
      const unsupported=cell().textContent==='120k' && icon().hidden;
      return {both,ownership,transitions,color,rowColor,singleLine,invalidated,plain,unsupported};
    } finally {
      document.activeElement?.blur();INPUT.view.active_cards=original;redraw();
    }
  })()`);
  for (const key of ['both','ownership','singleLine','invalidated','plain','unsupported']) assert.equal(result[key],true,key);
  assert.notEqual(result.color,result.rowColor,'gold warning does not replace prompt outcome color');
  for (const sample of result.transitions) {
    assert.equal(sample.cell,sample.severity);assert.equal(sample.footer,sample.severity);
    assert.equal(sample.visible,sample.severity!=='none');assert.equal(sample.stable,true);
    assert.equal(sample.accessible,true);
  }
  return result;
};
