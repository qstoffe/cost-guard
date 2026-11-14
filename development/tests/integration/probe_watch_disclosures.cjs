// Full rendered DOM over Python-produced, synthetic source-shaped publications.
const assert = require('node:assert/strict');
module.exports = async evaluate => {
  const facts = await evaluate(`(() => {
    const saved=structuredClone(INPUT), render=()=>ReportView.renderLive(document.getElementById('result'), INPUT, state);
    INPUT.view=structuredClone(DISCLOSURES[0]); render();
    const card=[...state.watch.cards.values()].find(c=>c.value.session_id==='root');
    const group=card.tools.rows.get(JSON.stringify(['read','failed']));
    const failure=[...group.jobs.values()][1], running=[...card.runningDetail.jobs.values()][0];
    const background=[...card.backgroundDetail.jobs.values()][0], skill=card.skills.list.firstElementChild;
    for(const target of [card.tools,card.skills,group,failure,card.runningDetail,running,card.backgroundDetail,background])
      target.node.open=true;
    const anchor=failure.input.firstChild, selection=getSelection(), range=document.createRange();
    range.selectNodeContents(anchor); selection.removeAllRanges(); selection.addRange(range);
    failure.summary.focus({preventScroll:true});
    let stable=true, privateCleared=true, focus=true, selected=true, noRemount=true, pending=0;
    const before=performance.getEntriesByType('resource').length;
    const observer=new MutationObserver(()=>{}); observer.observe(card.activity,{childList:true,subtree:true});
    const survivors=new Set([group.node,group.summary,group.list,failure.node,failure.summary,failure.input,
      card.runningDetail.node,running.node,background.node,skill]);
    for(let i=1;i<DISCLOSURES.length;i++) {
      INPUT.view=structuredClone(DISCLOSURES[i]); render();
      stable &&= group.node.open && failure.node.open && card.tools.node.open && card.skills.node.open &&
        card.running.open && running.node.open && card.background.open && background.node.open &&
        group.jobs.get(failure.identity)===failure && card.runningDetail.jobs.get(running.identity)===running &&
        card.skills.list.firstElementChild===skill && group.node.isConnected && !group.node.hidden;
      focus &&= document.activeElement===failure.summary;
      selected &&= failure.input.firstChild===anchor && selection.anchorNode===anchor;
      noRemount &&= !observer.takeRecords().some(r=>[...r.removedNodes].some(n=>survivors.has(n)));
      if(INPUT.view.active_cards[0].state==='partial') {
        pending++;
        privateCleared &&= failure.input.textContent==='' && running.input.textContent==='' &&
          background.input.textContent==='' && /temporarily unavailable/.test(failure.note.textContent);
      }
    }
    observer.disconnect(); selection.removeAllRanges(); document.activeElement?.blur();
    failure.summary.focus({preventScroll:true});
    for(const name of ['failed_invocations','running_invocations','background_invocations'])
      INPUT.view.active_cards[0].rows[0].tool[name].reverse();
    render();
    const reordered=group.jobs.get(failure.identity)===failure &&
      document.activeElement===failure.summary && failure.node.open && group.node.open;
    const corrected=/Permission denied/.test(failure.note.textContent);
    document.activeElement?.blur();
    for(const target of [group,failure,card.runningDetail,running,card.backgroundDetail,background,card.skills])
      target.node.open=false;
    for(const frame of DISCLOSURES.slice(1)) { INPUT.view=structuredClone(frame); render(); }
    const closed=[group,failure,card.runningDetail,running,card.backgroundDetail,background,card.skills].every(t=>!t.node.open);
    // An observed count with no detail list keeps the established arrow, not old calls.
    const tool=INPUT.view.active_cards[0].rows[0].tool;
    tool.failed_invocations=[]; render();
    const arrow=group.node.isConnected && !group.node.hidden && group.jobs.size===0 && failure.input.textContent==='';
    INPUT.view=structuredClone(DISCLOSURES[0]); render();
    const restored=[...group.jobs.values()][0];
    const current=INPUT.view.active_cards[0].rows[0].tool;
    current.outcomes=[]; current.failed_or_cancelled_count=0; current.failed_count=0; render();
    const removed=!group.node.isConnected && group.jobs.size===0;
    const cleared=restored.input.textContent==='' && !restored.node.open;
    const noNetwork=performance.getEntriesByType('resource').length===before;
    INPUT.view=structuredClone(DISCLOSURES[0]); render();
    const old=[...card.runningDetail.jobs.values()][0];
    INPUT.view.active_cards[0].activity_scope='replacement'; render();
    const switched=old.input.textContent==='' && !old.node.open &&
      [...state.watch.cards.values()].find(c=>c.value.session_id==='root')!==card;
    Object.assign(INPUT,saved); render();
    return {stable,privateCleared,focus,selected,noRemount,pending,reordered,corrected,closed,arrow,removed,cleared,noNetwork,switched};
  })()`);
  assert.deepEqual(facts, {stable:true,privateCleared:true,focus:true,selected:true,noRemount:true,pending:4,
    reordered:true,corrected:true,closed:true,arrow:true,removed:true,cleared:true,noNetwork:true,switched:true});
  return facts;
};
