// Exact shipped baseline/current controllers; deterministic timer/HTTP replay.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Node {
  constructor(tag,text=''){this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.textContent=text;}
  append(...nodes){for(const node of nodes)this.insertBefore(node,null);}
  insertBefore(node,before){node.remove();const i=before?this.children.indexOf(before):this.children.length;this.children.splice(i,0,node);node.parentNode=this;}
  replaceChildren(...nodes){for(const node of [...this.children])node.remove();this.append(...nodes);}
  remove(){if(this.parentNode){const a=this.parentNode.children;a.splice(a.indexOf(this),1);this.parentNode=null;}}
  contains(node){return this===node||this.children.some(child=>child.contains(node));}
  classList={toggle(){}};
  setAttribute(k,v){this.attributes[k]=v;} removeAttribute(k){delete this.attributes[k];} addEventListener(){}
}
async function replay(script, input){
  let clock=0,sequence=0,requests=0,appearance=null;
  const timers=new Map();
  const context={URLSearchParams,AbortController,Date:class extends Date{static now(){return clock;}},
    document:{hidden:false,activeElement:null,addEventListener(){}},window:{getSelection:()=>null},
    location:{hash:'#/sessions?period=all'},history:{replaceState(){}},
    setTimeout:(fn,delay)=>{const id=++sequence;timers.set(id,{fn,at:clock+delay});return id;},clearTimeout:id=>timers.delete(id),
    ReportView:{element:(tag,text)=>new Node(tag,text),text:(node,text)=>{node.textContent=text;},
      headerHelp:{},timestamp:()=>null,display:()=>'',metricToken:()=>null,metric(){},
      CostDisplay:class{select(value){return value;}}},
    ContextHelp:{heading:node=>node,value(){},refresh(){}},
    api:async(_,request)=>{
      if(request.action)return {};
      requests++;
      const reply=clock>=12000?{...input.arrival,pending_sort:false}:input.arrival;
      return {...reply,passive:!!request.passive};
    }};
  vm.createContext(context);vm.runInContext(script+';globalThis.View=SessionsCatalog.View',context);
  const view=new context.View(context.api);
  view.configure(new URLSearchParams('period=all'));view.update(input.first);view.attached=true;
  // Row source observation at t=0, next ordinary poll at t=5s, scalars at t=12s.
  view.timer=context.setTimeout(()=>view.poll(),5000);
  view.wake?.('source:1');
  for(let frame=1;frame<=150;frame++){
    const until=frame*100;
    while([...timers.values()].some(timer=>timer.at<=until)){
      const [id,timer]=[...timers].sort((a,b)=>a[1].at-b[1].at)[0];timers.delete(id);clock=timer.at;
      await timer.fn();await Promise.resolve();
      if(appearance===null&&view.body.children[0]?.dataset.id===input.arrival.view.session_usage[0].session_id)appearance=clock;
    }
    clock=until;view.wake?.('source:1'); // Same hint on 150 clock-only Live frames.
  }
  assert.equal(view.body.children.length,25);view.detach();
  return {roots:input.roots,arm:input.arm,observation_to_dom_simulated_ms:appearance,
    page_requests_in_15_simulated_seconds:requests,clock_only_frames:150};
}
(async()=>{
  const input=JSON.parse(fs.readFileSync(0,'utf8'));
  const current=fs.readFileSync('src/web/assets/sessions.js','utf8'),results=[];
  for(const item of input.results)results.push(await replay(item.arm==='baseline'?input.baseline:current,item));
  for(const result of results)assert.equal(result.observation_to_dom_simulated_ms,result.arm==='baseline'?15000:100);
  console.log(JSON.stringify(results));
})().catch(error=>{console.error(error);process.exitCode=1;});
