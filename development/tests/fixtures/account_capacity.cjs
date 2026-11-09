// Availability is a numeric fact, never truthiness of the formatted placeholder.
const assert=require('node:assert/strict');
module.exports=(vm,context,sample,helpText)=>{
  context.capacityView={accounts:{accounts:[structuredClone(sample)]},quota_stale:false};
  vm.runInContext(`globalThis.capacityPage=new AccountCards.View(true);
    globalThis.capacityWatch=new WatchView.View({connection:'Live connected.'})`,context);
  const source=context.capacityView.accounts.accounts[0];
  source.primary.quota.label='weekly Mixed CASE';source.secondary[0].quota.label='5-hour';
  const quotas=[source.primary.quota,source.secondary[0].quota],known=quotas.map(q=>structuredClone(q.ccost_reference));
  const lines=card=>card.children.filter(n=>/^watch-(quota|monthly)-capacity/.test(n.className));
  const draw=()=>vm.runInContext(`capacityPage.update(capacityView);
    capacityWatch.update({state:'running',view:capacityView})`,context);
  for(const phase of ['unknown','known','unknown','known'])for(const unit of ['credits','usd']){
    quotas.forEach((q,index)=>q.ccost_reference=phase==='known'?known[index]:{capacity:null,monthly_capacity:null});
    const raw=JSON.stringify(source);
    vm.runInContext(`ReportView.setUnit('${unit}',capacityPage.root);
      ReportView.syncUnits(capacityWatch.root)`,context);draw();
    const card=context.capacityPage.grid.children[0];
    assert.equal(context.capacityPage.root.textContent,context.capacityWatch.accounts.textContent);
    assert.equal(lines(card).length,phase==='known'?2:0);
    const footer=card.children.find(n=>n.className==='watch-account-footer'),secondary=footer.children[0].children[0];
    assert.equal(lines(secondary).length,phase==='known'?2:0);
    assert.equal(card.children.some(n=>n.className==='watch-capacity-spacer'),false);
    assert.match(card.children[2].textContent,/^Weekly Mixed CASE/);
    assert.match(helpText(card.children[2].children[0]),/^Weekly Mixed CASE/);
    assert.equal(card.querySelectorAll('progress')[0].attributes['aria-label'],'Weekly Mixed CASE remaining');
    assert.match(secondary.children[0].textContent,/^5-hour/);
    assert.equal(JSON.stringify(source),raw,'presentation never rewrites provider identifiers');
    for(const line of [...lines(card),...lines(secondary)]){
      assert.match(line.textContent,unit==='usd' ? /: ~\$/ : /: ~/);
      assert.doesNotMatch(helpText(line.children[0]),/rounding|÷|×|guesstimate/i);
    }
  }
  context.capacityView.accounts.accounts.push({...structuredClone(source),observation:{...source.observation,id:'second'}});
  draw();assert.equal(context.capacityPage.grid.children.length,2);
  context.capacityView.accounts.accounts.shift();draw();assert.equal(context.capacityPage.grid.children.length,1);
  quotas[0].unlimited=true;quotas[0].ccost_reference={capacity:null,monthly_capacity:null};
  context.capacityView.accounts.accounts=[source];draw();
  assert.match(context.capacityPage.root.textContent,/Unlimited/);
  assert.equal(lines(context.capacityPage.grid.children[0]).length,0);
  vm.runInContext(`ReportView.setUnit('credits')`,context);
};
