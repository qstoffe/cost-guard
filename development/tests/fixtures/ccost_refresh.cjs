// Explicit canonical evidence drives display-only retention, never formatted text.
module.exports = (vm, context) => {
  const assert = require('node:assert/strict');
  const R = vm.runInContext('ReportView', context);
  const costs = new R.CostDisplay();
  const row = (amount, complete) => ({
    ccost:amount, unresolved_cost:!complete, calls:2,
    display:{ccost:amount == null ? '0' : amount, incoming_context_ccost:'0',
      cost_detail_help:`Total CCost: ${amount ?? '0'}`, mini_cost_models:[['Main Model','fixture/model — high']],
      mini_cost_amounts:[`${amount ?? '0'} Credits`]},
    display_units:{usd:{ccost:amount == null ? '$0.00' : `$${(Number(amount)/100).toFixed(2)}`,
      cost_detail_help:`Total CCost: $${(Number(amount)/100).toFixed(2)}`,
      mini_cost_amounts:[`$${(Number(amount)/100).toFixed(2)}`]}}
  });
  const scope = ['source-A','root','prompt-1'];
  for (const unit of ['credits','usd']) {
    R.setUnit(unit);
    const expected = value => unit === 'usd' ? `$${(value/100).toFixed(2)}` : String(value);
    const select = value => {
      const frozen = JSON.stringify(value);
      const shown = costs.select(value, scope);
      assert.equal(JSON.stringify(value),frozen,'raw DTO and coverage are immutable');
      assert.equal(shown.ccost,value.ccost);
      assert.equal(shown.unresolved_cost,value.unresolved_cost);
      return shown;
    };
    costs.values.clear();
    assert.equal(R.display(select(row(null,false)),'ccost'),expected(0));
    assert.equal(R.display(select(row('125',false)),'ccost'),expected(125),'positive partial subtotal qualifies');
    for (const raw of [null,'0','0']) {
      const shown = select(row(raw,false));
      assert.equal(R.display(shown,'ccost'),expected(125),'observed unresolved zero cannot erase known cost');
      assert.equal(R.display(shown,'cost_detail_help'),`Total CCost: ${expected(125)}`);
      assert.equal(R.display(shown,'mini_cost_amounts')[0],unit === 'usd' ? '$1.25' : '125 Credits');
    }
    assert.equal(R.display(select(row('100',true)),'ccost'),expected(100),'qualified correction may decrease');
    assert.equal(R.display(select(row('0',true)),'ccost'),expected(0),'verified real zero replaces known amount');
    select(row('125',true));
    for(const changed of [['source-B','root','prompt-1'],['source-A','root','prompt-2'],['source-A','other','prompt-1']])
      assert.equal(R.display(costs.select(row(null,false),changed),'ccost'),expected(0),'identity changes cannot inherit');
    for(const placeholder of [null,'','N/A','Not Applicable','—','Loading…'])
      assert.equal(R.display({display:{ccost:placeholder}},'ccost'),expected(0));
    assert.equal(R.display(null,'billed_cost'),'N/A','native billing is not a CCost amount');
    assert.equal(R.display(null,'context_tokens'),'N/A');
    costs.values.clear();
    const component = (amount, known, complete) => ({...row('200',complete),
      incoming_context_ccost:amount, incoming_context_ccost_known:known,
      display:{ccost:'200',incoming_context_ccost:amount ?? '0'},
      display_units:{usd:{ccost:'$2.00',incoming_context_ccost:'$'+(Number(amount)/100).toFixed(2)}}});
    select(component('75',true,true));
    const partial = select(component(null,false,false));
    assert.equal(R.display(partial,'ccost'),expected(200));
    assert.equal(R.display(partial,'incoming_context_ccost'),expected(75),'aggregate progress cannot erase a missing component');
    assert.equal(partial.incoming_context_ccost,null);
    assert.equal(R.display(select(component('0',true,true)),'incoming_context_ccost'),expected(0));
    const mix = amount => ({total_cost:'200',cost_complete:false,costs:amount == null ? null : [amount,'0','0','0'],
      display:{mix_input_cost:amount ?? '0'},display_units:{usd:{mix_input_cost:'$'+(Number(amount)/100).toFixed(2)}}});
    costs.select(mix('75'),['mix'],'total_cost',false);
    assert.equal(R.display(costs.select(mix(null),['mix'],'total_cost',false),'mix_input_cost'),expected(75));
    assert.equal(R.display(costs.select(mix(null),['other-period'],'total_cost',false),'mix_input_cost'),expected(0));
    const group = (model, amount, complete) => ({...row('200',false),
      display:{ccost:'200',mini_cost_models:[['Main Model',model]],mini_cost_amounts:[`${amount ?? '0'} Credits`],
        mini_cost_ready:[Number(amount)>0 || complete]},
      display_units:{usd:{ccost:'$2.00',mini_cost_amounts:['$'+(Number(amount)/100).toFixed(2)]}}});
    select(group('provider/model-A — high','75',true));
    assert.equal(R.display(select(group('provider/model-A — high',null,false)),'mini_cost_amounts')[0],
      unit === 'usd' ? '$0.75' : '75 Credits','same model group retains independently of aggregate');
    assert.equal(R.display(select(group('provider/model-B — high',null,false)),'mini_cost_amounts')[0],
      unit === 'usd' ? '$0.00' : '0 Credits','new model group cannot inherit an arbitrary array slot');
    const W = vm.runInContext('WatchView',context), live = new R.CostDisplay();
    const view = (amount, context) => ({source_label:'fixture',active_cards:[{session_id:'root',
      session_summary:{context:context ? {context_scope:context} : null,cost:null},
      rows:[{prompt:{...row(amount,false),event_id:'prompt'}}]}]});
    W.costProjection(view('125','source-A'),live,'v2');
    const retry = W.costProjection(view(null,null),live,'unknown');
    assert.equal(R.display(retry.active_cards[0].rows[0].prompt,'ccost'),expected(125),
      'missing context/generation during retry is not a new source');
    const changed = W.costProjection(view(null,'source-B'),live,'v2');
    assert.equal(R.display(changed.active_cards[0].rows[0].prompt,'ccost'),expected(0),
      'explicit context source changes still isolate amounts');
  }
  R.setUnit('credits');
};
