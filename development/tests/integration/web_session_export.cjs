// Controlled picker, host reads and destination commit. Not a native dialog test.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const crypto = require('node:crypto');
const window = {}, downloads = [];
class Node {
  constructor(text) { this.textContent = text; this.children = []; this.events = {}; }
  setAttribute() {}
  append(...nodes) { this.children.push(...nodes); }
  addEventListener(key, fn) { this.events[key] = fn; }
  click() { downloads.push(this.download); }
  remove() {}
}
const context = vm.createContext({window, document:{hidden:false}, crypto, AbortController, URL, Blob, Response,
  setTimeout:(fn,ms) => {const timer=setTimeout(fn,ms); timer.unref(); return timer;}, clearTimeout,
  ReportView:{element:(_, text)=>new Node(text)}, ContextHelp:{attach(){},dismiss(){}}});
vm.runInContext(fs.readFileSync('src/web/assets/session-export.js','utf8')+'\nglobalThis.Action=SessionExport.Action;',context);

async function main() {
  const calls = [], order = [];
  let hold, badName = false, rejectWrite = false;
  const action = new context.Action(async (path, body, signal, attachment) => {
    assert.equal(path,'/api/detail/export'); calls.push(body);
    if (body.action==='start') return {state:'preparing'};
    if (body.action==='status') {
      if (hold) await new Promise(resolve => hold = resolve);
      return {state:'ready',size:2};
    }
    if (body.action==='chunk') {
      assert.equal(attachment,true); assert.equal(body.offset,0);
      return {blob:new Blob(['PK']),filename:`opencode-ses_${badName?'other':'test'}-analysis.zip`};
    }
    assert.equal(body.action,'cancel');
  },'ses_test');
  const click = () => action.button.events.click();
  const idle = () => { assert.equal(action.button.disabled,false); assert.equal(action.spinner.hidden,true); };
  action.update('lease','ready','scope','Ångström.zip');
  window.showSaveFilePicker = async options => {
    order.push('picker'); assert.equal(options.suggestedName,'Ångström.zip');
    return {createWritable:async()=>({
      async write(blob){ assert.equal(await blob.text(),'PK'); order.push('write'); if(rejectWrite) throw Error('destination failed'); },
      async close(){order.push('close');}, async abort(){order.push('abort');}
    })};
  };
  hold=true;
  const completed=click();
  assert.deepEqual(order,['picker'],'original click opens the destination immediately');
  assert.equal(action.button.disabled,true); assert.equal(action.button.children.at(-1),action.spinner);
  assert.equal(action.spinner.hidden,false); await click();
  await new Promise(setImmediate);
  assert.equal(typeof hold,'function'); assert.deepEqual(order,['picker'],'no premature writes');
  action.update('renewed','ready','scope','New title.zip'); hold(); await completed;
  assert.deepEqual(order,['picker','write','close']); idle();
  assert.deepEqual(calls.map(c=>c.action),['start','status','chunk','cancel']);
  assert.equal(calls[0].token,'lease'); assert.equal(new Set(calls.map(c=>c.id)).size,1);
  assert.match(action.notice.textContent,/ZIP saved/);

  action.update('renewed','ready','scope','Ångström.zip'); hold=false; rejectWrite=true;
  await click(); assert.equal(order.at(-1),'abort'); assert.match(action.notice.textContent,/no completed export/); idle();
  const count=calls.length;
  window.showSaveFilePicker=async()=>{throw Object.assign(Error(),{name:'AbortError'});};
  await click(); assert.equal(calls.length,count); assert.match(action.notice.textContent,/cancelled/); idle();
  delete window.showSaveFilePicker;
  badName=true; await click(); assert.deepEqual(downloads,[]); assert.match(action.notice.textContent,/invalid or incomplete/);
  badName=false; await click(); assert.deepEqual(downloads,['Ångström.zip']); assert.match(action.notice.textContent,/browser controls/); idle();
  hold=true; const cancelled=click(); await new Promise(setImmediate);
  action.cancel.events.click(); hold(); await cancelled;
  assert.equal(downloads.length,1); assert.match(action.notice.textContent,/cancelled/); idle();

  const app=fs.readFileSync('src/web/assets/app.js','utf8');
  Object.assign(context,{hostState:{terminal:false},hostInstance:'owned-host',csrf:'owned-csrf',current:null,
    connectionStatus(){},fetch:async()=>context.response});
  vm.runInContext(app.slice(app.indexOf('async function api('),app.indexOf('\nfunction show('))+'\nglobalThis.request=api;',context);
  const headers={'X-CG-Instance':'owned-host','Content-Type':'application/zip','Content-Length':'2',
    'Content-Disposition':'attachment; filename="opencode-ses_test-analysis.zip"'};
  const chunk=()=>context.request('/api/detail/export',{action:'chunk',id:'c'.repeat(32),offset:0},undefined,true);
  context.response=new Response('PK',{headers});
  assert.equal((await chunk()).filename,'opencode-ses_test-analysis.zip');
  for (const invalid of [{'Content-Disposition':'attachment; filename="Title.zip"'},
    {'Content-Disposition':'attachment; filename="../opencode-ses_test-analysis.zip"'},
    {'Content-Length':'1048577'},{'Content-Length':'3'},{'Content-Type':'application/json'},{'X-CG-Instance':''}]) {
    context.response=new Response('PK',{headers:{...headers,...invalid}});
    await assert.rejects(chunk(),/export_invalid_response/);
  }
  console.log('PASS single click, refresh, destination cancellation/failure, fallback and protected chunks');
}
const deadline=setTimeout(()=>{throw Error('Export flow did not finish');},10000);
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>clearTimeout(deadline));
