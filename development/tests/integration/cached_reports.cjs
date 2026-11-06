// Deterministic freshness boundaries, independent of wall-clock timers and live views.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const context = vm.createContext({Date});
vm.runInContext(fs.readFileSync('src/web/assets/cached-reports.js','utf8'),context);
const now = 9000000;
for(const [section, ttl] of [['models',3600000],['ai-stats',900000],['token-mix',300000],['comparisons',300000]]) {
  context.section=section; context.now=now;
  const entry=age=>{
    context.result={observed_at_ms:now-age,source:{observed_at_ms:now-age}};
    return vm.runInContext('CachedReports.entry(result,section,now)',context);
  };
  assert.equal(vm.runInContext('CachedReports.entry(null,section,now)',context),'missing');
  assert.equal(entry(0),'fresh'); assert.equal(entry(ttl),'fresh');
  assert.equal(entry(ttl+1),ttl===3600000?'withhold':'quiet'); assert.equal(entry(3600000),ttl===3600000?'fresh':'quiet');
  assert.equal(entry(3600001),'withhold');
  context.result={observed_at_ms:now,source:{observed_at_ms:now-3600001}};
  assert.equal(vm.runInContext('CachedReports.entry(result,section,now)',context),'withhold','actual acquisition beats view timestamp');
}
assert.deepEqual(vm.runInContext('Object.keys(CachedReports.cadences).sort().join(",")',context),'ai-stats,comparisons,models,token-mix');
vm.runInContext(fs.readFileSync('src/web/assets/render.js','utf8'),context);
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
