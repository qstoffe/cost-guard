// Separate preview state: independent unknowns, neutral lifecycle, keyed upgrade.
const assert = require('node:assert/strict');
module.exports = (controller, view, input, helpText) => {
  const saved = structuredClone(input.view), base = saved.active_cards[0];
  const previews = Array.from({length:5}, (_,i) => ({session_id:'preview-'+i,title:'Catalog session '+i,
    activity_ms:100+i,activity_origin:'catalog',total_ccost:i===0?null:String(i),comparison_cost_complete:true,
    display:{activity_clock:'14:26',activity_date_time:'2026-11-15 14:26',total_ccost:String(i)},
    display_units:{usd:{total_ccost:'$0.0'+i}}}));
  const show = (active=[], earlier=[], values=previews) => {
    input.view={...saved,active_cards:active,history_cards:[],recent_finished_cards:[],
      earlier_previews:values,earlier_cards:earlier,history_state:'loading',history_epoch:0,
      history_checked:20,history_total:3217}; controller.update(input);
  };
  const indicators = row => row.children.slice(2).map(cell =>
    cell.querySelectorAll('span').find(node => node.className === 'metric-spinner'));
  const assertPending = (row, indices) => {
    const spinners = indicators(row);
    for (const index of indices) {
      assert.equal(row.children[index + 2].textContent, '');
      assert.equal(spinners[index]?.attributes['aria-label'], ['Loading prompt CCost', 'Loading total CCost', 'Loading context'][index]);
      assert.equal(spinners[index].tabIndex, undefined);
    }
  };
  for(const count of [0,1,2,3,5]) {
    const active=Array.from({length:count},(_,i)=>({...structuredClone(base),session_id:'running-'+i}));
    show(active);
    assert.equal(view.promptRows.size,5+count);
    assert.equal(view.body.children.length,5+count,'no extra loading/status row');
    assert.equal(view.needsHistory,true,'unhydrated previews do not release history interest');
    for(const row of view.body.children.filter(r=>r.dataset.id.startsWith('preview-'))) {
      assertPending(row,[0,2]);
      assert.equal(row.className,'');assert.doesNotMatch(row.attributes['aria-label'],/Prompt|Completed|Ended|Running/);
      assert.equal(row.children[0].textContent,'14:26');
      assert.match(helpText(row.children[0].children[0]),/^Session activity · /);
      assert.doesNotMatch(helpText(row.children[1].children[0].children[0]),/Prompt/);
    }
  }
  show();
  const row=view.promptRows.get('preview-0');
  assertPending(row,[0,1,2]);
  const [promptSpinner,,contextSpinner] = indicators(row);
  const qualified={...previews[0],total_ccost:'0',display:{...previews[0].display,total_ccost:'0'}};
  show([],[],[qualified,...previews.slice(1)]);
  assert.equal(view.promptRows.get('preview-0'),row);assert.equal(row.children[3].textContent,'0');
  for(const [minutes,state,reason] of [
    [7,'waiting','capture_in_progress'],
    [12,'retrying','http_timeout'],
    [30,'unavailable','http_auth_failure']
  ]) {
    const retained={...qualified,total_state:'retained',hydration_state:state,hydration_reason:reason};
    const arriving=[1,2,3].map(i=>({...previews[i],session_id:`burst-${minutes}-${i}`,activity_ms:200+i}));
    show([],[],[retained,previews[4],...arriving]);
    assert.equal(view.promptRows.get('preview-0'),row);
    assert.equal(view.promptRows.size,5);
    assertPending(row,[0,2]);
    assert.equal(indicators(row)[0],promptSpinner);
    assert.equal(indicators(row)[2],contextSpinner);
    assert.equal(row.children[3].textContent,'0');
    assert.match(helpText(row.children[3].children[0]),/Last qualified value/);
  }
  show([],[],[{...previews[0],hydration_state:'unknown',total_state:'partial'},...previews.slice(1)]);
  assertPending(row,[0,1,2]);
  const absent={...qualified,metric_absences:{prompt_ccost:'complete_empty_history',ctx:'complete_empty_history'}};
  show([],[],[absent,...previews.slice(1)]);
  assert.deepEqual(row.children.slice(2).map(cell=>cell.textContent),['?','0','?']);
  assert.equal(helpText(row.children[2].children[0]),'No prompt is recorded for this session.');
  assert.equal(helpText(row.children[4]),'No recorded context is available for this session.');
  assert.equal(view.needsHistory,true,'one confirmed empty session does not qualify all previews');
  show([],[],previews.map(value=>({...value,metric_absences:absent.metric_absences})));
  assert.equal(view.needsHistory,false,'provider-confirmed empty histories satisfy the current capacity');
  show();
  assertPending(row,[0,1,2]);
  assert.equal(view.needsHistory,true,'unqualified preview data restores demand');
  assert.equal(row.children[4].attributes['aria-describedby'],undefined);
  const real={...structuredClone(base),session_id:'preview-0',title:'Catalog session 0',focal_id:'',
    rows:[{...structuredClone(base.rows[0]),prompt:{...structuredClone(base.rows[0].prompt),
      in_progress:false,completed_at_ms:50,completed_successfully:true}}]};
  show([],[real]);
  assert.equal(view.promptRows.get('preview-0'),row);
  assert.ok(row.children[2].textContent);
  assert.equal(indicators(row)[0],undefined);
  assert.match(row.attributes['aria-label'],/Completed/);
  assert.equal([...view.promptRows.keys()].filter(id=>id==='preview-0').length,1);
  real.session_summary.cost=null;
  show([],[real],[qualified,...previews.slice(1)]);
  assert.equal(row.children[3].textContent,'0','rich upgrade retains qualified catalog Total while scalar lane loads');
  show();controller.health({kind:'identity_changed',terminal:true});
  assert.equal(view.promptRows.size,0,'host/authorization transitions withdraw previews');
  controller.health({kind:'connected'});input.view=saved;controller.update(input);
};
