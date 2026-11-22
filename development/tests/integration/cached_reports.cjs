// Deterministic freshness boundaries, independent of wall-clock timers and live views.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const context = vm.createContext({Date});
vm.runInContext(fs.readFileSync('src/web/assets/render.js','utf8'),context);
vm.runInContext(fs.readFileSync('src/web/assets/cached-reports.js','utf8'),context);
const now = 900000000;
for(const [section, ttl] of [['models',3600000],['ai-stats',900000],['token-mix',300000],['comparisons',300000]]) {
  context.section=section; context.now=now;
  const entry=age=>{
    context.result={observed_at_ms:now-age,source:{observed_at_ms:now-age}};
    return vm.runInContext('CachedReports.entry(result,section,now)',context);
  };
  assert.equal(vm.runInContext('CachedReports.entry(null,section,now)',context),'missing');
  assert.equal(entry(0),'fresh'); assert.equal(entry(ttl),'fresh');
   assert.equal(entry(ttl+1),'quiet'); assert.equal(entry(3600000),ttl===3600000?'fresh':'quiet');
   assert.equal(entry(3600001),'quiet');
   assert.equal(entry(2*86400000),'quiet');
  context.result={observed_at_ms:now,source:{observed_at_ms:now-3600001}};
   assert.equal(vm.runInContext('CachedReports.entry(result,section,now)',context),'quiet','actual acquisition beats view timestamp');
   for(const observed of [null,undefined,-1,now+1,NaN,'1']) {
     context.result={source:{observed_at_ms:observed}};
     assert.equal(vm.runInContext('CachedReports.entry(result,section,now)',context),'withhold');
   }
}
assert.deepEqual(vm.runInContext('Object.keys(CachedReports.cadences).sort().join(",")',context),'ai-stats,comparisons,models,token-mix');
// Actual server intervals survive configured-local midnight, DST and year/month rollover.
for(const [start,end,expected] of [
  ['2026-10-24T22:00:00Z','2026-10-25T23:00:00Z','2026-10-25 00:00 → 2026-10-26 00:00'],
  ['2026-03-28T23:00:00Z','2026-03-29T22:00:00Z','2026-03-29 00:00 → 2026-03-30 00:00'],
  ['2026-12-30T23:00:00Z','2026-12-31T23:30:00Z','2026-12-31 00:00 → 2027-01-01 00:30']]) {
  context.result={scope:{timezone_id:'Europe/Stockholm'},view:{ai_stats:[
    {period:'today',start_ms:Date.parse(start),end_ms:Date.parse(end)},
    {period:'all',start_ms:null,end_ms:Date.parse(end)}]}};
  assert.equal(vm.runInContext(`CachedReports.interval(result,'today')`,context),expected+' (Europe/Stockholm)');
  assert.match(vm.runInContext(`CachedReports.interval(result,'all')`,context),/^All available history →/);
  context.result.view.ai_stats[0].start_ms=null;
  assert.equal(vm.runInContext(`CachedReports.interval(result,'today')`,context),null);
  assert.ok(vm.runInContext(`CachedReports.interval(result,'all')`,context),'one malformed scope never hides unrelated rows');
}
for(const count of [null,-1,0,1.5,'3',Number.MAX_SAFE_INTEGER+1]) {
  context.result={source:{status:'partial',omitted_roots:count}};
  assert.equal(vm.runInContext('ReportView.historyWarning(result)',context),'Partial source history. Values may be incomplete.');
}
context.result={source:{status:'partial',omitted_roots:3}};
assert.match(vm.runInContext('ReportView.historyWarning(result)',context),/3 changing root sessions.*omitted.*do not cover the full source/);
context.result={source:{status:'partial',omitted_roots:1}};
assert.match(vm.runInContext('ReportView.historyWarning(result)',context),/1 changing root session could/);
context.result={source:{status:'acquired',omitted_roots:3}};
assert.equal(vm.runInContext('ReportView.historyWarning(result)',context),'');
console.log('PASS historical cache freshness boundary matrix');
