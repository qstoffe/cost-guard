// Availability is a numeric fact, never truthiness of the formatted placeholder.
const assert=require('node:assert/strict');
module.exports=(vm,context,sample,helpText)=>{
  context.capacityView={accounts:{accounts:[structuredClone(sample)]},quota_stale:false};
  vm.runInContext(`globalThis.capacityPage=new AccountCards.View(true);
    globalThis.capacityWatch=new WatchView.View({connection:'Live connected.'})`,context);
  const source=context.capacityView.accounts.accounts[0];
  source.primary.quota.label='weekly Mixed CASE';source.secondary[0].quota.label='5-hour';
  const quotas=[source.primary.quota,source.secondary[0].quota],known=quotas.map(q=>structuredClone(q.ccost_reference));
  const displays=quotas.map(q=>structuredClone({display:q.display,display_units:q.display_units}));
  const lines=card=>card.children.filter(n=>/^watch-(quota|monthly)-capacity/.test(n.className));
  const draw=()=>vm.runInContext(`capacityPage.update(capacityView);
    capacityWatch.update({state:'running',view:capacityView})`,context);
  let savedRows,savedBar;
  for(const phase of ['unknown','known','unknown','known'])for(const unit of ['credits','usd']){
    quotas.forEach((q,index)=>{
      q.ccost_reference=phase==='known'?known[index]:{...known[index],capacity:null,monthly_capacity:null};
      Object.assign(q,structuredClone(displays[index]));
      if(phase==='unknown')for(const tokens of [q.display,...Object.values(q.display_units)]){
        tokens.capacity_help='No positive same-window reference CCost sample.';
        tokens.monthly_capacity_help='No positive same-window reference CCost sample.';
      }
    });
    const raw=JSON.stringify(source);
    vm.runInContext(`ReportView.setUnit('${unit}',capacityPage.root);
      ReportView.syncUnits(capacityWatch.root)`,context);draw();
    const card=context.capacityPage.grid.children[0];
    assert.equal(context.capacityPage.root.textContent,context.capacityWatch.accounts.textContent);
    assert.equal(lines(card).length,2,'unknown primary keeps both semantic rows');
    const footer=card.children.find(n=>n.className==='watch-account-footer'),secondary=footer.children[0].children[0];
    assert.equal(lines(secondary).length,2,'unknown secondary keeps both semantic rows');
    if(savedRows){assert.deepEqual(lines(card),savedRows);assert.equal(card.querySelectorAll('progress')[0],savedBar);}
    savedRows=lines(card);savedBar=card.querySelectorAll('progress')[0];
    assert.equal(card.children.some(n=>n.className==='watch-capacity-spacer'),false);
    assert.match(card.children[2].textContent,/^Weekly Mixed CASE/);
    const usage=helpText(card.children[2].children[0]);
    assert.match(usage,/^Used: [^\n]+\nRemaining: [^\n]+\nReset /);
    assert.doesNotMatch(usage,/Capacity|CCost|÷|rolling|scope|pricing/i);
    assert.equal(card.querySelectorAll('progress')[0].attributes['aria-label'],'Weekly Mixed CASE remaining');
    assert.match(secondary.children[1].textContent,/^5-hour/);
    assert.equal(secondary.children[0].className,'watch-quota-divider');
    assert.equal(JSON.stringify(source),raw,'presentation never rewrites provider identifiers');
    for(const line of [...lines(card),...lines(secondary)]){
      assert.match(line.textContent,phase==='unknown'?/: \?$/:unit==='usd' ? /: ~\$/ : /: ~/);
      const help=helpText(line.children[0]);
      assert.doesNotMatch(help,/Native Used|Native Remaining|rolling|scope/);
      assert.match(help,phase==='unknown'?/No positive same-window reference CCost sample/:/^(Monthly )?Capacity: ~/);
      if(phase==='known')assert.doesNotMatch(help,/÷|×|Unrounded|estimate|Observed|Provider-reported/i);
    }
  }
  context.capacityView.accounts.accounts.push({...structuredClone(source),observation:{...source.observation,id:'second'}});
  draw();assert.equal(context.capacityPage.grid.children.length,2);
  context.capacityView.accounts.accounts.shift();draw();assert.equal(context.capacityPage.grid.children.length,1);
  quotas[0].unlimited=true;quotas[0].ccost_reference={capacity:null,monthly_capacity:null};
  context.capacityView.accounts.accounts=[source];draw();
  assert.match(context.capacityPage.root.textContent,/Unlimited/);
  assert.equal(lines(context.capacityPage.grid.children[0]).length,2);
  assert.match(lines(context.capacityPage.grid.children[0])[0].textContent,/: Unlimited$/);
  assert.match(lines(context.capacityPage.grid.children[0])[1].textContent,/: \?$/);
  quotas[0].unlimited=false;
  // Eligibility is an exported source fact, never inferred from the display label.
  quotas[0].label='Not a monthly label';quotas[0].ccost_reference={...known[0],monthly_applicable:false};
  source.secondary=Array.from({length:4},()=>structuredClone(source.secondary[0]));
  const peer=structuredClone(source);peer.observation.id='ordinal-peer';
  peer.primary.quota.ccost_reference.monthly_applicable=true;
  peer.secondary.forEach((slot,index)=>slot.quota.ccost_reference.monthly_applicable=index%2===0);
  context.capacityView.accounts.accounts=[source,peer];draw();
  const cards=context.capacityPage.grid.children;
  const tracks=card=>[...card.children.filter(n=>n.className==='watch-quota-track'),
    ...card.children.find(n=>n.className==='watch-account-footer').children[0].children.map(group=>group.children.find(n=>n.className==='watch-quota-track'))];
  assert.equal(lines(cards[0]).length,1);
  assert.equal(cards[0].children.filter(n=>n.className==='watch-capacity-spacer').length,1);
  assert.deepEqual(tracks(cards[0]).map(n=>n.style['grid-row']),tracks(cards[1]).map(n=>n.style['grid-row']));
  assert.equal(tracks(cards[0]).length,5,'no hardcoded secondary quota limit');
  context.capacityView.accounts.accounts=[source];draw();
  assert.equal(cards[0].children.filter(n=>n.className==='watch-capacity-spacer').length,0,'lone monthly is compact');
  vm.runInContext(`ReportView.setUnit('credits')`,context);
};
