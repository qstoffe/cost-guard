// Full Watch's independent loading lanes over three virtual minutes of real DOM updates.
const assert = require('node:assert/strict');
module.exports = async function loading({evaluate, layouts, checks}) {
  const result = await evaluate(`(() => {
    const view=state.watch, originalNow=Date.now, base=originalNow();
    const cases=[];
    try {
      for (const lane of ['history','accounts','daily','partial']) {
        const p=structuredClone(INPUT);
        if(lane==='history') p.view.history_state='loading';
        if(lane==='accounts') p.view.accounts=null;
        if(lane==='daily') {p.view.daily_state='loading';p.view.daily_usage=null;}
        if(lane==='partial') p.view.cards_state='partial';
        Date.now=()=>base;view.update(p);
        const card=[...view.cards.values()][0],row=card.body.firstChild;
        view.earlier.open=true;
        const focus=card.tools.summary;focus.focus({preventScroll:true});
        const scroll=card.root.querySelector('.watch-table-scroll');scroll.scrollLeft=25;
        const beforeScroll=scroll.scrollLeft, beforeCalls=row.cells[6].textContent;
        const notices=[];
        for(let seconds=0;seconds<=180;seconds+=10) {
          Date.now=()=>base+seconds*1000;
          const prompt=p.view.active_cards[0].rows[0].prompt;
          prompt.calls=seconds+1;
          p.view.active_cards[0].rows[0].display.watch_duration_ms=seconds+'s';
          if(seconds===60) p.view.active_cards.push({...structuredClone(p.view.active_cards[0]),session_id:'new-arrival'});
          view.update(p);notices.push(view.empty.textContent);
        }
        const preview=row.querySelector('.watch-prompt-preview'),selection=getSelection(),range=document.createRange();
        range.selectNodeContents(preview);selection.removeAllRanges();selection.addRange(range);
        const selected=selection.toString();view.update(p);
        const stableSelection=selected.length>0&&selection.toString()===selected, focusRetained=document.activeElement===focus;
        selection.removeAllRanges();focus.blur();
        cases.push({lane,notices,cards:view.active.children.length,calls:row.cells[6].textContent,
          duration:row.cells[1].textContent,advanced:beforeCalls!==row.cells[6].textContent,
          rowRetained:card.body.firstChild===row,scrollRetained:scroll.scrollLeft===beforeScroll,
          stableSelection,earlier:view.earlier.open,focusRetained});
        view.update(INPUT);
      }
      return cases;
    } finally {Date.now=originalNow;view.update(INPUT);}
  })()`);
  for (const sample of result) {
    assert.ok(sample.notices.every(text=>text===''), JSON.stringify(sample));
    assert.equal(sample.cards,2); assert.equal(sample.calls,'181'); assert.equal(sample.duration,'180s');
    for (const key of ['advanced','rowRetained','scrollRetained','stableSelection','earlier','focusRetained'])
      assert.equal(sample[key],true,key);
  }
  layouts.push({case:'independent-watch-loading',virtualSecondsPerLane:180,samples:result});
  checks.push('Advancing calls/duration and new cards remain quiet through independent history/accounts/daily/partial delays; real keyed DOM, selection, disclosure and horizontal scroll retained');
};
