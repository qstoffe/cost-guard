// Deterministic freshness boundaries, independent of wall-clock timers and live views.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const context = vm.createContext({Date});
vm.runInContext(fs.readFileSync('src/web/assets/cached-reports.js','utf8'),context);
const now = 9000000;
for(const [section, ttl] of [['ai-stats',900000],['token-mix',300000]]) {
  context.section=section; context.now=now;
  const entry=age=>{
    context.result={observed_at_ms:now-age,source:{observed_at_ms:now-age}};
    return vm.runInContext('CachedReports.entry(result,section,now)',context);
  };
  assert.equal(vm.runInContext('CachedReports.entry(null,section,now)',context),'missing');
  assert.equal(entry(0),'fresh'); assert.equal(entry(ttl),'fresh');
  assert.equal(entry(ttl+1),'quiet'); assert.equal(entry(3600000),'quiet');
  assert.equal(entry(3600001),'withhold');
  context.result={observed_at_ms:now,source:{observed_at_ms:now-3600001}};
  assert.equal(vm.runInContext('CachedReports.entry(result,section,now)',context),'withhold','actual acquisition beats view timestamp');
}
assert.deepEqual(vm.runInContext('Object.keys(CachedReports.cadences).sort().join(",")',context),'ai-stats,token-mix');
console.log('PASS historical cache freshness boundary matrix');
