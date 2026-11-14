// Genuine Tab help access; session Duration must not borrow prompt Duration.
const assert=require('node:assert/strict');
module.exports=async({evaluate,until,command,pip,checks})=>{
  await evaluate(`{
    const p=structuredClone(liveValue),c=p.view.active_cards[0],r=c.rows[0];
    c.state='observed';c.session_summary.duration_ms=123000;
    c.session_summary.display.duration_ms='2m 3s';
    r.display.watch_duration_ms='11s';
    p.view.active_cards=[c];miniWatch.update(p);
    window.totalKeyboardRow=miniWatch.view.promptRows.get(c.session_id);
    totalKeyboardRow.cells[2].firstChild.focus();
  }`);
  for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',
    {type,key:'Tab',code:'Tab',windowsVirtualKeyCode:9},pip);
  const panel=`miniWatch.view.doc.getElementById('context-help')`;
  await until(`${panel}?.matches(':popover-open')`);
  assert.equal(await evaluate('miniWatch.view.doc.activeElement===totalKeyboardRow.cells[3].firstChild'),true);
  assert.match(await evaluate(`${panel}.textContent`),/Duration: 2m 3s$/);
  assert.doesNotMatch(await evaluate(`${panel}.textContent`),/Duration: 11s/);
  assert.equal(await evaluate(`totalKeyboardRow.cells[3].firstChild.getAttribute('aria-describedby')`),'context-help');
  for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',
    {type,key:'Escape',code:'Escape',windowsVirtualKeyCode:27},pip);
  assert.equal(await evaluate(`${panel}.matches(':popover-open')`),false);
  assert.equal(await evaluate(`totalKeyboardRow.cells[3].firstChild.hasAttribute('aria-describedby')`),false);
  checks.push('Real Tab opens Total whole-session 2m 3s (not prompt 11s); Escape closes popup and removes ARIA relationship');
};
