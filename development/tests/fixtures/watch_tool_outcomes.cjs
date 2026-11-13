// Presentation-only outcome/disclosure regression; canonical classification stays in Python.
const assert = require('node:assert/strict');
module.exports = (card, helpText, document, select) => {
  const outcomes = [
    {tool_name: 'grep', outcome: 'failed', count: 2},
    {tool_name: 'execute', outcome: 'cancelled', count: 1},
    {tool_name: '<img src=x onerror=alert(1)>', outcome: 'cancelled', count: 1}
  ];
  const tool = {counts: [['grep', 4], ['execute', 3], ['a', 1], ['b', 1], ['c', 1], ['d', 1],
    ['<img src=x onerror=alert(1)>', 1]], failed_count: 2, cancelled_count: 2,
    failed_or_cancelled_count: 4, outcomes, running_tool: 'execute', display: {running_ms: '12s'}};
  card.drawActivity(tool);
  assert.match(card.tools.summary.textContent, /^12 tool calls/);
  assert.match(card.tools.summary.textContent, /4 failed \/ cancelled/);
  assert.equal(card.tools.list.children.length, 10, 'all seven tools and three outcome groups, no cap');
  assert.deepEqual(card.tools.list.children.slice(-3).map(node => node.textContent),
    ['2 × grep failed', '1 × execute cancelled', '1 × <img src=x onerror=alert(1)> cancelled']);
  assert.equal(card.tools.list.children.some(node => /failed \/ cancelled/.test(node.textContent)), false);
  assert.ok(card.tools.list.children.slice(-3).every(node => node.className === 'watch-activity-error'));
  assert.ok(card.tools.list.children.slice(0, 7).every(node => !node.children[0].className));
  assert.equal(card.tools.list.querySelectorAll('img').length, 0, 'tool names stay literal text');
  assert.equal(card.running.className, 'watch-running-tool');
   assert.equal(card.runningDetail.summary.textContent, 'Running: execute 12s');
   assert.match(card.runningDetail.note.textContent, /Awaiting verified live source/);
  assert.equal(card.running.hidden, false);
  assert.match(helpText(card.tools.summary), /subset, not extra calls/);
  assert.match(helpText(card.tools.summary), /missing evidence is not success/);
  const first = card.tools.list.children[0]; card.tools.node.open = true;
  card.drawActivity(tool);
  assert.equal(card.tools.list.children[0], first, 'unchanged activity keeps DOM');
  assert.equal(card.tools.node.open, true);
  const details = [
    {identity:'call-a',revision:'r1',tool_name:'grep',text:'path:\nsrc/a.py',qualification:'',reason:'File not found'},
    {identity:'call-b',revision:'r1',tool_name:'grep',text:'path:\nsrc/a.py',qualification:'',reason:'Failure reason unavailable'}
  ];
  const detailed = {...tool, failed_invocations:details};
  card.drawActivity(detailed, true);
  const group = card.tools.rows.get(JSON.stringify(['grep','failed']));
  const a = group.jobs.get('call-a'), b = group.jobs.get('call-b');
  group.node.open = true; b.node.open = true;
  assert.equal(a.node.open, false, 'failed inputs initially private');
  assert.equal(group.jobs.size, 2, 'identical inputs are separate physical calls');
  assert.match(b.summary.textContent, /Failed call 2/);
  for (const focus of [card.tools.summary, b.summary]) {
    document.activeElement = focus;
    card.drawActivity({...detailed, counts:[['grep',5]], failed_invocations:[
      details[0], {...details[1], revision:'corrected',reason:'Permission denied'}]}, true);
    assert.equal(group.jobs.get('call-b'), b);
    assert.equal(group.node.open, true); assert.equal(b.node.open, true);
    assert.equal(document.activeElement, focus);
    assert.match(b.note.textContent, /Permission denied/);
  }
  document.activeElement = null;
  select(b.input); card.drawActivity(detailed, true);
  assert.equal(group.jobs.get('call-b'), b);
  assert.equal(b.node.open, true);
  select(null);
  card.drawActivity({...detailed, outcomes:[{tool_name:'grep',outcome:'failed',count:25}],
    failed_or_cancelled_count:25}, true);
  assert.match(group.note.textContent, /\+23 additional failed calls not shown/);
  document.activeElement = b.summary;
  card.drawActivity({...detailed, failed_invocations:[details[0]],
    outcomes:[{tool_name:'grep',outcome:'failed',count:1}], failed_or_cancelled_count:1}, true);
  assert.equal(group.jobs.has('call-b'), false, 'authoritative removal wins over focus');
  assert.equal(b.input.textContent, '', 'removed nodes cannot retain former input');
  assert.equal(b.node.open, false);
  document.activeElement = null;
  card.drawActivity(detailed, true);
  card.drawActivity(detailed, false);
  assert.equal(group.jobs.size, 0, 'disconnect/invalidation clears failed inputs too');
  const changed = {...tool, failed_count: 0, cancelled_count: 0, failed_or_cancelled_count: 0, outcomes: []};
  card.drawActivity(changed);
  assert.doesNotMatch(card.tools.summary.textContent, /failed|cancelled/);
  assert.equal(card.tools.list.children.length, 7, 'latest correction applies after interaction ends');
  card.drawActivity({...tool, outcomes: outcomes.slice(0, 1), running_tool: ''});
  assert.equal(card.tools.list.children.at(-1).textContent, '2 × unidentified tool/outcome');
  assert.equal(card.running.hidden, true);
  card.drawActivity({counts: [['execute', 1]], failed_count: 0, cancelled_count: 1,
    failed_or_cancelled_count: 1, outcomes: [{tool_name: 'execute', outcome: 'cancelled', count: 1}]});
  assert.match(card.tools.summary.textContent, /1 failed \/ cancelled/);
  assert.equal(card.tools.list.children.at(-1).textContent, '1 × execute cancelled');
  card.drawActivity({counts: [['execute', 1]], failed_count: 0, outcomes: []});
  assert.doesNotMatch(card.tools.summary.textContent, /failed|cancelled/);
  assert.equal(card.tools.list.children.length, 1);
};
