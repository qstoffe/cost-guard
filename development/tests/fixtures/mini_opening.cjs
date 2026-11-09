// Deterministic measurement semantics, not browser font/native geometry evidence.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('src/web/assets/mini.js','utf8');
const context = vm.createContext({});
vm.runInContext(source.replace('return {Controller};','return {headerWidth, contentHeight, targetHeight};'),context);
const measure = vm.runInContext('MiniWatch.headerWidth',context);
function fixture(real, widths) {
  const reads=[], original={text:real,expanded:'false'}, daily={textContent:real};
  let expanded='false', removed=false;
  const clone={classList:{add(){}},setAttribute(){},inert:false,
    querySelector:selector=>selector==='.mini-earlier-toggle'?{setAttribute:(name,value)=>{expanded=value;}}:daily,
    getBoundingClientRect(){reads.push([daily.textContent,expanded]);
      if(widths===null)throw new Error('layout failed');
      return {width:widths[daily.textContent][expanded==='true'?1:0]};},
    remove(){removed=true;}};
  const view={root:{firstElementChild:{cloneNode:()=>clone},append(node){assert.equal(node,clone);}}};
  return {view,reads,original,removed:()=>removed};
}
const reference='CCost Today 90 000 · 999 prompts', lower='CCost Today 1 · 2 prompts';
const low=fixture(lower,{[lower]:[300,310],[reference]:[400,420]});
assert.equal(measure(low.view,true),400);
assert.deepEqual(low.reads,[[lower,'false'],[reference,'false']]);
assert.deepEqual(low.original,{text:lower,expanded:'false'});
assert.equal(low.removed(),true);
const larger='CCost Today 9 000 000 000 · 99999999 prompts';
const high=fixture(larger,{[larger]:[530,520],[reference]:[400,420]});
assert.equal(measure(high.view,true),530,'larger real text, including its wider collapsed state, wins');
const actual=fixture(lower,{[lower]:[300,310]});
assert.equal(measure(actual.view),300,'non-reserving measurement uses actual header text');
assert.equal(actual.reads.length,1);
const failed=fixture(lower,null);
assert.throws(()=>measure(failed.view,true),/layout failed/);
assert.equal(failed.removed(),true,'failed measurements must not leave clones');
const contentHeight=vm.runInContext('MiniWatch.contentHeight',context);
let removed=false, appended=false;
const copy={classList:{add(){}},setAttribute(){},style:{},getBoundingClientRect:()=>({height:123.25}),
  querySelector(){throw new Error('Manual fit must not inspect/sample future rows');},remove(){removed=true;}};
const visible={doc:{},root:{cloneNode:()=>copy,parentNode:{append(node){assert.equal(node,copy);appended=true;}}},
  sessionRow(){throw new Error('No synthetic running-row reserve in manual fit');}};
assert.equal(contentHeight(visible,417,false),124);
assert.equal(copy.style.width,'417px');assert.equal(copy.inert,true);
assert.ok(appended && removed,'manual measurement removes its inert artifact');
copy.getBoundingClientRect=()=>{throw new Error('layout failed');};removed=false;
assert.throws(()=>contentHeight(visible,417,false),/layout failed/);assert.equal(removed,true);
const targetHeight=vm.runInContext('MiniWatch.targetHeight',context);
copy.getBoundingClientRect=()=>({height:123.25});visible.root.getBoundingClientRect=()=>({width:417});
visible.doc.body={};visible.doc.defaultView={outerWidth:600,innerWidth:584,outerHeight:220,innerHeight:178,
  screen:{availHeight:1200},getComputedStyle:()=>({paddingTop:'7.5px',paddingBottom:'7.5px'})};
assert.equal(targetHeight(visible,false),185);
Object.assign(visible.doc.defaultView,{outerHeight:850,innerHeight:808});
assert.equal(targetHeight(visible,false),185,'old tall bounds must not distort native frame/zoom');
visible.root.currentCSSZoom=2;visible.doc.body.currentCSSZoom=2;
assert.equal(targetHeight(visible,false),200);assert.equal(copy.style.width,'208.5px','measure CSS width, not twice-zoomed viewport width');
