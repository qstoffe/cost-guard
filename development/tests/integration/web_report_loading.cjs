// Deterministic finite progress/admission state; no browser or source acquisition.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
let now = 0, next = 0;
const timers = new Map();
const context = vm.createContext({AbortController, Date, console,
  setTimeout(fn, ms) { const id = ++next; timers.set(id, {fn, ms}); return id; },
  clearTimeout(id) { timers.delete(id); }});
vm.runInContext(fs.readFileSync('src/web/assets/report-loading.js', 'utf8') + '\nthis.Loading=ReportLoading;', context);
const L = context.Loading;
async function main() {
  for (const section of L.sections) {
    const state = {section}; L.reset(state);
    const values = [state.percent];
    const stages = section === 'models' ? ['sampling', 'account-analysis', 'finalizing'] :
      ['history-cache', 'history-load', 'history-projection', 'finalizing'];
    let sequence = 0;
    for (const stage of stages) for (const done of [0, 1, 9, 10]) {
      L.observe(state, {phase:'history', stage, completed:done, total:10, sequence:++sequence});
      values.push(state.percent);
    }
    assert.deepEqual(values, [...values].sort((a,b)=>a-b));
    assert.ok(values.at(-1)<100, 'even final counts cannot declare applied success');
    const label = state.stage, percent = state.percent;
    L.observe(state, {phase:'catalog', sequence:1});
    assert.equal(state.stage,label); assert.equal(state.percent,percent);
    L.waiting(state,'busy'); assert.equal(state.stage,'Waiting for report slot…');
    assert.equal(state.percent,percent, 'queue waiting never advances progress');
    L.reset(state); L.observe(state,{phase:'catalog',sequence:1});
    const opaque = state.percent;
    now += 10000; L.observe(state,{phase:'catalog',sequence:2});
    assert.equal(state.percent,opaque, 'no advancement from time in opaque work');
    L.waiting(state,'source_starting'); assert.equal(state.stage,'Waiting for source…');
  }
  const history = {section:'comparisons'}; L.reset(history);
  L.observe(history,{stage:'history-load',completed:4,total:100,sequence:1});
  const before = history.percent;
  L.observe(history,{stage:'date-messages',completed:10,total:10,sequence:2});
  assert.equal(history.percent,before, 'a finished batch is not finished global history');
  assert.match(history.stage,/Reading session trees/);
  const runTimer = () => { const [id,timer] = timers.entries().next().value; timers.delete(id); now += timer.ms; timer.fn(); return timer.ms; };
  const attempt = new L.Attempt(()=>now), delays=[];
  for (let index=0;index<40;index++) {
    const wait=attempt.backoff(new Error('busy')); delays.push(runTimer()); await wait;
  }
  assert.deepEqual(delays.slice(0,4),[500,1000,2000,4000]);
  assert.ok(delays.every(delay=>delay<=30000),'pending admission has bounded, throttled backoff');
  for (const code of ['http_auth_failure','source_permission_denied','registration_invalid','unsupported_schema',
      'report_unavailable','invalid_request','report_timeout','cancelled']) {
    const error=Object.assign(new Error(code),{retryable:true});
    assert.equal(L.retryable(error),false,code);
  }
  assert.equal(L.retryable(Object.assign(new Error('connection_refused'),{retryable:true})),true);
  assert.equal(L.retryable(new Error('connection_refused')),false);
  assert.equal(L.retryable(Object.assign(new Error('source_unavailable'),{retryable:true})),true);
  assert.equal(L.retryable(Object.assign(new Error('source_unavailable'),{retryable:false})),false);
  assert.equal(L.retryable(new Error('source_unavailable')),false);
  const cancelled=new L.Attempt(()=>now), wait=cancelled.pause(4000);
  cancelled.cancel(); await assert.rejects(wait,/cancelled/); assert.equal(timers.size,0);
  const unavailable=new L.Attempt(()=>now);
  for(let index=0;index<40;index++) {
    const wait=unavailable.backoff(new Error('source_starting')); runTimer(); await wait;
  }
  const legacy=new L.Attempt(()=>now);
  for(let index=0;index<40;index++) {
    const wait=legacy.backoff(Object.assign(new Error('source_unavailable'),{retryable:true}));
    runTimer();await wait;
  }
  const expired=new L.Attempt(()=>now); now+=2*86400000;
  assert.doesNotThrow(()=>expired.check({writable:true}));
  const resumable=new L.Attempt(()=>now); now+=600000;
  assert.doesNotThrow(()=>resumable.check({writable:true}));
  resumable.cancel(); assert.throws(()=>resumable.check({writable:true}),/cancelled/);
  for (const kind of ['offline','stopped','identity_changed','authorization_required'])
    assert.throws(()=>new L.Attempt(()=>now).check({kind,writable:false}),new RegExp(kind));
  assert.doesNotThrow(()=>new L.Attempt(()=>now).check({kind:'reconnecting',writable:false}));
  const frames=new Map(),listeners=new Map();
  context.document={hidden:false,addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:name=>listeners.delete(name)};
  context.requestAnimationFrame=fn=>{const id=++next;frames.set(id,fn);return id;};
  context.cancelAnimationFrame=id=>frames.delete(id);
  const painting=L.paintCompletion({},new AbortController().signal);
  const [id,frame]=frames.entries().next().value;frames.delete(id);frame();
  context.document.hidden=true;listeners.get('visibilitychange')();await painting;
  assert.equal(frames.size,0);assert.equal(listeners.size,0,'hidden completion cannot strand the attempt');
  const settled = async promise => { let done = false; promise.then(()=>{done=true;},()=>{done=true;}); await null; await null; return done; };
  timers.clear();
  const polling=new L.Attempt(()=>now), slow=polling.poll('job-a',500);
  polling.notify('job-b');
  assert.equal(await settled(slow),false,'another job identity never wakes this wait');
  polling.notify('job-a');
  assert.equal(await settled(slow),true,'terminal hint wakes the matching status wait');
  assert.equal(timers.size,0,'woken wait leaves no timer');
  polling.notify('job-a');
  const replay=polling.poll('job-a',500);
  assert.equal(await settled(replay),false,'replayed terminal hint wakes at most once');
  runTimer(); await replay;
  const early=new L.Attempt(()=>now); early.notify('job-c');
  assert.equal(await settled(early.poll('job-c',500)),true,'hint before the wait is coalesced');
  assert.equal(timers.size,0);
  const changed=new L.Attempt(()=>now); changed.notify('job-d');
  const other=changed.poll('job-e',500);
  assert.equal(await settled(other),false,'changed job identity invalidates the hint');
  runTimer(); await other;
  const recovering=new L.Attempt(()=>now), backoff=recovering.backoff(new Error('busy'));
  recovering.notify('job-f');
  assert.equal(await settled(backoff),false,'terminal hints never shorten recovery backoff');
  runTimer(); await backoff;
  const stopped=new L.Attempt(()=>now), stoppedWait=stopped.poll('job-g',500);
  stopped.cancel(); stopped.notify('job-g');
  await assert.rejects(stoppedWait,/cancelled/); assert.equal(timers.size,0);
  const late=new L.Attempt(()=>now); late.cancel(); late.notify('job-h');
  await assert.rejects(late.poll('job-h',500),/cancelled/);
  console.log('PASS: four monotonic work maps, opaque/batch/stale evidence, throttled unlimited pending, cancel, factual terminal errors and once-per-job terminal wake');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
