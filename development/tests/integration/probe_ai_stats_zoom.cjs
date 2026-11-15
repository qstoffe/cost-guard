// Actual per-tab browser zoom, isolated headless profile; no desktop accelerators.
module.exports = async ({command,evaluate,until,fixture,tab,checks,config}) => {
  const assert=require('node:assert/strict'), fs=require('node:fs/promises'), path=require('node:path');
  const extension=path.join(config,'zoom-extension');
  await fs.mkdir(extension);
  await fs.writeFile(path.join(extension,'manifest.json'),JSON.stringify({manifest_version:3,
    name:'Synthetic AI Stats zoom probe',version:'1.0',permissions:['tabs'],background:{service_worker:'worker.js'}}));
  await fs.writeFile(path.join(extension,'worker.js'),'chrome.runtime.onInstalled.addListener(()=>{});');
  await command('Extensions.loadUnpacked',{path:extension});
  let worker;
  for(let attempt=0;attempt<100 && !worker;attempt++) {
    worker=(await command('Target.getTargets')).targetInfos.find(t=>t.type==='service_worker' && t.url.endsWith('/worker.js'));
    if(!worker) await new Promise(resolve=>setTimeout(resolve,30));
  }
  assert.ok(worker,'owned zoom extension service worker');
  const session=(await command('Target.attachToTarget',{targetId:worker.targetId,flatten:true})).sessionId;
  await command('Runtime.enable',{},session);
  const {windowId}=await command('Browser.getWindowForTarget',{targetId:(await command('Target.getTargets')).targetInfos.find(t=>t.type==='page' && t.url.includes('#/ai-stats')).targetId});
  await command('Emulation.clearDeviceMetricsOverride',{},tab);
  const cases=await fixture('stats-evidence'), result=cases.find(c=>c.name==='podium-three').result;
  await evaluate(`current.result=${JSON.stringify(result)};current.period='all';current.stats.update(current);`);
  const inspect=require('./probe_ai_stats_layout.cjs').inspect, evidence=[];
  for(const width of [360,520,1280,1920]) {
    await command('Browser.setWindowBounds',{windowId,bounds:{width,height:1000}});
    for(const zoom of [1,1.25,1.5,2]) {
      const actual=await evaluate(`(async()=>{
        const tabs=await chrome.tabs.query({});
        const targets=tabs.filter(t=>t.url?.includes('#/ai-stats'));
        if(targets.length!==1) throw new Error('owned_zoom_tab_count');
        const target=targets[0];
        await chrome.tabs.setZoomSettings(target.id,{mode:'automatic',scope:'per-tab'});
        await chrome.tabs.setZoom(target.id,${zoom});
        return chrome.tabs.getZoom(target.id);
      })()`,session);
      assert.equal(actual,zoom);
      await evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
      for(const theme of ['classic','light','dark']) {
        await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
        await evaluate(`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}'`);
        for(const count of [0,1,2,3]) for(const long of [false,true]) {
          await evaluate(`current.result=${JSON.stringify(result)};
            for(const metric of current.result.view.ai_stats[0].metrics) if(metric.podium) {
              metric.podium=metric.podium.slice(0,${count});
              if(${long}) for(const row of metric.podium) row.label='LongUnbrokenModelName'.repeat(4)+' gjpqy Åé';
            }
            current.stats.update(current);`);
          const geometry=await evaluate(`({width:innerWidth,dpr:devicePixelRatio,...(${inspect.toString()})()})`);
          assert.deepEqual(geometry.issues,[],JSON.stringify({width,zoom,theme,count,long,geometry}));
          assert.equal(geometry.pageOverflow,false);
          assert.equal(geometry.equalRows,true);
          evidence.push({width,zoom,theme,count,long,viewport:geometry.width,dpr:geometry.dpr});
        }
      }
    }
  }
  const wide=evidence.find(r=>r.width===1280 && r.zoom===1), zoomed=evidence.find(r=>r.width===1280 && r.zoom===2);
  assert.ok(zoomed.viewport<wide.viewport && zoomed.dpr>wide.dpr,
    'actual browser zoom changes CSS viewport and DPR: '+JSON.stringify({wide,zoomed}));
  checks.push('actual Chrome per-tab 100/125/150/200% zoom × 360/520/1280/1920 outer width × Classic/light/dark × 0/1/2/3 rows × normal/long names: unclipped text, equal siblings and no overflow');
  return evidence;
};
