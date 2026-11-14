// Real DOM/AX/PiP transitions; synthetic publications, not private incident replay.
const assert = require('node:assert/strict');
module.exports = async ({command,evaluate,until,owner,checks,layouts}) => {
  const run = (text,gesture=false) => evaluate(owner,text,gesture);
  await run(`miniWatch.toggle()`,true);
  await until(owner,`!!miniWatch.view`);
  let pip;
  for(const target of (await command('Target.getTargets')).targetInfos.filter(t=>t.type==='page')) {
    const {sessionId}=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
    if(await evaluate(sessionId,`!!document.querySelector('.mini-watch')`)) {pip=sessionId;break;}
  }
  assert.ok(pip,'actual Document PiP accessibility target');
  await run(`window.stablePublication=structuredClone(liveValue);
    window.stableMiniUpdate=miniWatch.update.bind(miniWatch);miniWatch.update=()=>{};
    window.stableWatch=current.watch;window.stableWatchUpdate=stableWatch.update.bind(stableWatch);stableWatch.update=()=>{};
    window.applyStable=()=>{stableWatchUpdate(stablePublication);stableMiniUpdate(stablePublication);miniWatch.render();};
    const base=stablePublication.view.history_cards[0]||stablePublication.view.active_cards[0];
    stablePublication.view.active_cards=[];
    stablePublication.view.history_cards=Array.from({length:5},(_,i)=>{
      const card=structuredClone(base);card.session_id='stable-'+i;card.focal_id='';
      card.rows=card.rows.slice(0,1);Object.assign(card.rows[0].prompt,{in_progress:false,
        execution_unverified:false,completed_successfully:true,completed_at_ms:1000+i,event_id:'stable-prompt-'+i});
      return card;
    });
    Object.assign(stablePublication.view,{history_scope:'stable-source',history_state:'observed',history_epoch:1,
      recent_finished_cards:[stablePublication.view.history_cards[4]]});
    window.stableHistory=structuredClone(stablePublication.view.history_cards);
    stableWatch.earlier.open=true;applyStable();
    window.stableRows=[...miniWatch.view.body.children];window.stableCards=[...stableWatch.history.children];
    stableCards[0].querySelector('details').open=true;
    window.stableTop=stableCards[0].getBoundingClientRect().top;
    window.stableBounds=[miniWatch.window.outerWidth,miniWatch.window.outerHeight];`);
  for(let epoch=1;epoch<=3;epoch++) for(const state of ['loading','pending','refreshing','retrying','unavailable','observed']) {
    const frame=await run(`(()=>{
      stablePublication.view.now_ms=(stablePublication.view.now_ms||Date.now())+1;
      stablePublication.view.history_state='${state}';stablePublication.view.history_epoch=${epoch};applyStable();
      return {count:miniWatch.view.body.children.length,
        sameRows:stableRows.every((n,i)=>miniWatch.view.body.children[i]===n),
        sameCards:stableCards.every((n,i)=>stableWatch.history.children[i]===n),
        status:stableWatch.history.querySelector('[role=status]')?.textContent||'',
        mini:miniWatch.view.body.textContent,full:stableWatch.history.textContent,
        expanded:stableCards[0].querySelector('details').open,
        top:stableCards[0].getBoundingClientRect().top,
        bounds:[miniWatch.window.outerWidth,miniWatch.window.outerHeight]};
    })()`);
    assert.equal(frame.count,5);assert.equal(frame.sameRows,true);assert.equal(frame.sameCards,true);
    assert.equal(frame.status,'');assert.equal(frame.expanded,true);
    assert.doesNotMatch(frame.mini+' '+frame.full,/Loading earlier|Refreshing|Retrying/);
    assert.equal(frame.top,await run(`stableTop`));assert.deepEqual(frame.bounds,await run(`stableBounds`));
    for(const session of [owner,pip]) {
      const ax=(await command('Accessibility.getFullAXTree',{},session)).nodes.filter(n=>!n.ignored).map(n=>n.name?.value||'').join('\n');
      assert.doesNotMatch(ax,/Loading earlier sessions|Refreshing|Retrying/);
    }
    layouts.push({surface:'Full/PiP',epoch,state,rows:frame.count,stable:true});
  }
  for(let count=0;count<5;count++) {
    await run(`stablePublication.view.history_cards=stableHistory.slice(0,${count});
      stablePublication.view.recent_finished_cards=[];
      stablePublication.view.history_state='observed';applyStable();
      stablePublication.view.history_state='retrying';applyStable();`);
    assert.equal(await run(`miniWatch.view.promptRows.size`),count);
    assert.doesNotMatch(await run(`miniWatch.view.body.textContent+' '+stableWatch.history.textContent`),/Loading earlier|Refreshing|Retrying/);
  }
  await run(`Object.assign(stablePublication.view,{history_cards:[],history_epoch:0,history_state:'loading',
    history_scope:'new-source'});applyStable();`);
  assert.match(await run(`stableWatch.history.textContent`),/Loading earlier sessions/);
  await run(`stablePublication.view.history_state='unavailable';applyStable();`);
  assert.match(await run(`stableWatch.history.textContent`),/Unable to load earlier/);
  await run(`miniWatch.update=stableMiniUpdate;stableWatch.update=stableWatchUpdate;miniWatch.close();
    stableWatch.update(liveValue);`);
  checks.push('FR000703: 18 post-observation Full DOM/AX and actual PiP frames, five physical rows, keyed cards/expansion/geometry; 0–4 completed populations, cold source and real unavailable feedback');
};
