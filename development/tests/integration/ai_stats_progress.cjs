// Deterministic selected-scope progress, retained results and serialized rapid priority.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({console,CachedReports:{observation:r=>r.observed_at_ms}});
vm.runInContext(fs.readFileSync('src/web/assets/ai-stats.js','utf8')+'\nthis.Stats=AIStatsView;',context);
const S=context.Stats;
async function main(){
  const state={period:'7-days',percent:0,loading:true,active:'shared',request:{stats_scope:'7-days'}};
  const work=(done,total,ready=false,rows=[])=>({result:{view:{ai_stats:rows,
    ai_stats_work:{scopes:{'7-days':{completed:done,total,ready}}}}}});
  S.observe(state,work(2,10)); const first=state.percent;
  S.observe(state,work(2,20)); assert.equal(state.percent,first,'growing denominator never rewinds progress');
  assert.equal(state.stage,'The robots are counting their adventures…');
  S.observe(state,work(10,20)); assert.ok(state.percent>first && state.percent<100);
  S.observe(state,work(20,20,true)); assert.ok(state.percent<100,'coverage alone is not an applied period result');
  S.observe(state,work(20,20,true,[{period:'7-days'}])); assert.ok(state.percent<100,'legacy rows are not fun-policy results');
  const calls=[],pending=[];
  const api=async(_path,value)=>{calls.push(value.stats_scope);await new Promise(resolve=>pending.push(resolve));};
  const priority=S.prioritize(state,api);
  state.request.stats_scope='today'; S.prioritize(state,api);
  state.request.stats_scope='30-days'; S.prioritize(state,api);
  pending.shift()(); await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(calls,['7-days','30-days']);
  pending.shift()(); await priority; assert.equal(state.priorityUpdate,false);
  console.log('PASS: scope progress, denominator growth, no provisional 100%, serialized rapid priority');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
