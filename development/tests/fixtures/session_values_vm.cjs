// Detail display observations are qualified independently; raw DTOs never change.
const assert = require('node:assert/strict');
const pending = require('./pending_value.cjs');
module.exports = ({vm, context, Node, input, document}) => {
  vm.runInContext("globalThis.stable = new SessionDetail.View(api, 'root-0000')", context);
  const view = context.stable;
  new Node('main').append(view.root);
  const data = JSON.parse(JSON.stringify(input.first));
  const block = data.result.view.prompt_blocks[0];
  block.rows = [block.rows[0]]; const row = block.rows[0];
  row.in_progress = true; row.event_id = 'live-prompt'; row.id = 'live-row';
  const keys = ['total_calls','duration_ms','total_ccost','total_incoming_context_ccost','total_extra_ccost','total_token_mix_percent'];
  data.value_authority = {scope:'source/session/epoch', totals:Object.fromEntries(keys.map(key=>[key,'pending'])),
    rows:{'live-prompt':'pending'}};
  row.token_mix_percent = null; row.display.token_mix_percent = 'running - consider ABORT';
  const mix = () => view.body.children[0].children[9].textContent;
  const cold = JSON.parse(JSON.stringify(data));
  cold.result.view.prompt_blocks[0].rows[0].token_mix_percent=[2,96,1,1];
  view.update(cold);
  const mixSlot = () => view.body.children[0].children[9].firstChild;
  const indicator = pending(mixSlot(), 'prompt token mix');
  view.update(data);
  assert.equal(pending(mixSlot(), 'prompt token mix'), indicator, 'raw, unqualified percentages do not resolve the slot');
  pending(view.footer.children[4].firstChild, 'session total calls');
  row.token_mix_percent = [2,96,1,1]; row.display.token_mix_percent = '2/96/1/1';
  block.total_calls=42; block.duration_ms=9000; block.total_ccost='12';
  block.total_incoming_context_ccost='70'; block.total_extra_ccost='30'; block.total_token_mix_percent=[2,96,1,1];
  block.display.duration_ms='9s'; block.display.total_ccost='12';
  block.display_units={credits:{total_ccost:'12',total_incoming_context_ccost:'70',total_extra_ccost:'30'},
    usd:{total_ccost:'$1.20',total_incoming_context_ccost:'$0.70',total_extra_ccost:'$0.30'}};
  data.value_authority.totals=Object.fromEntries(keys.map(key=>[key,'known']));
  data.value_authority.rows['live-prompt']='known';
  view.update(data);
  const cells=[...view.footer.children], targets=cells.map(cell=>cell.children[0]), before=cells.map(cell=>cell.textContent);
  assert.equal(mix(), '2/96/1/1');
  assert.equal(indicator.parentNode, null);
  assert.deepEqual(before.slice(3), ['12','42','9s','—','70','30','2/96/1/1']);
  const raw=JSON.stringify(data);
  for (let poll=0;poll<5;poll++) view.update(data);
  assert.equal(JSON.stringify(data),raw);
  assert.ok(cells.every((cell,index)=>cell===view.footer.children[index] && targets[index]===cell.children[0]));
  document.activeElement=targets[3]; targets[3].events.focus();
  const help=document.body.children.at(-1);
  row.token_mix_percent=null; row.display.token_mix_percent='running';
  data.value_authority.rows['live-prompt']='pending';
  data.value_authority.totals=Object.fromEntries(keys.map(key=>[key,'pending']));
  Object.assign(block,{total_calls:null,duration_ms:null,total_ccost:'0',
    total_incoming_context_ccost:null,total_extra_ccost:null,total_token_mix_percent:null});
  block.display.duration_ms='N/A'; block.display.total_ccost='0';
  block.display_units={credits:{total_ccost:'0'},usd:{total_ccost:'$0.00'}};
   for(let poll=0;poll<5;poll++) {
     view.update(data); view.sourceStatus(data);
     assert.equal(view.status.hidden,true,'qualified retained scalars refresh silently');
     assert.equal(view.status.textContent,'');
   }
  assert.equal(mix(),'2/96/1/1');
  assert.deepEqual(cells.map(cell=>cell.textContent),before);
  assert.equal(document.activeElement,targets[3]);
  assert.equal(document.body.children.at(-1),help);
  vm.runInContext('ReportView.setUnit("usd", stable.root)',context);
  assert.equal(cells[3].textContent,'$1.20');
  assert.equal(cells[7].textContent,'$0.70');
  assert.equal(cells[8].textContent,'$0.30');
  vm.runInContext('ReportView.setUnit("credits", stable.root)',context);
  document.activeElement=null;
  // Independent field qualification and authoritative decreases/zero are replacements.
  data.value_authority.totals.total_calls='known'; block.total_calls=0; view.update(data);
  assert.equal(cells[4].textContent,'0'); assert.equal(cells[5].textContent,'9s');
  data.value_authority.totals.total_ccost='known'; view.update(data);
  assert.equal(cells[3].textContent,'0');
  data.value_authority.totals.duration_ms='known'; block.duration_ms=1000; block.display.duration_ms='1s';view.update(data);
  assert.equal(cells[5].textContent,'1s');
  row.token_mix_percent=[0,98,1,1];row.display.token_mix_percent='0/98/1/1';
  data.value_authority.rows['live-prompt']='known';view.update(data);assert.equal(mix(),'0/98/1/1');
  row.in_progress=false;view.update(data);assert.equal(mix(),'0/98/1/1');
  row.token_mix_percent=null;data.value_authority.rows['live-prompt']='invalidated';view.update(data);
   assert.equal(mix(),'?','supported withdrawal explains missing recorded token evidence');
  row.id='new-prompt';row.event_id='new-prompt';row.in_progress=true;
  data.value_authority.rows={'new-prompt':'pending'};view.update(data);
  pending(mixSlot(), 'prompt token mix'); // No cross-prompt reuse.
  data.value_authority.scope='other-source';view.update(data);
  assert.equal(cells[5].parentNode,null,'incompatible source clears even protected old cells');
  assert.notEqual(view.footer.children[7].textContent,'70','source switch clears prior component');
  view.invalidateValues();
  assert.equal(view.body.children.length,0);assert.equal(view.footer.children.length,0);
  assert.equal(view.values.mixes.size,0);assert.equal(view.values.totals.size,0);
  assert.equal(view.scroll.hidden,true);
  // Legacy DTOs lack detail authority: keep compatible source costs, never
  // reuse them across source/generation switches or unidentified observations.
  const legacy = JSON.parse(JSON.stringify(data));
  delete legacy.value_authority;
  const legacyRow = legacy.result.view.prompt_blocks[0].rows[0];
  legacyRow.unresolved_cost = true;
  const cost = () => view.body.children[0].children[3].textContent;
  const publishCost = amount => {
    legacyRow.ccost = amount; legacyRow.display.ccost = amount;
    legacyRow.display_units = {credits:{ccost:amount},usd:{ccost:'$'+(Number(amount)/100).toFixed(2)}};
    view.update(legacy);
  };
  for (const unit of ['credits','usd']) {
    vm.runInContext(`ReportView.setUnit('${unit}', stable.root)`, context);
    legacy.result.source = {identity:'legacy-a',generation:'one'};
    publishCost('125'); publishCost('0');
    assert.equal(cost(),unit === 'usd' ? '$1.25' : '125','compatible source retains partial cost');
    legacy.result.source.identity = 'legacy-b'; publishCost('0');
    assert.equal(cost(),unit === 'usd' ? '$0.00' : '0','source switch isolates legacy costs');
    publishCost('125'); legacy.result.source.generation = 'two'; publishCost('0');
    assert.equal(cost(),unit === 'usd' ? '$0.00' : '0','generation switch isolates legacy costs');
    delete legacy.result.source; publishCost('125'); publishCost('0');
    assert.equal(cost(),unit === 'usd' ? '$0.00' : '0','unidentified observations cannot retain costs');
  }
};
