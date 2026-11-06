// Deterministic measurement semantics, not browser font/native geometry evidence.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('src/web/assets/mini.js','utf8');
const context = vm.createContext({});
vm.runInContext(source.replace('return {Controller};','return {headerWidth};'),context);
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
assert.equal(measure(low.view,true),420);
assert.deepEqual(low.reads,[[lower,'false'],[lower,'true'],[reference,'false'],[reference,'true']]);
assert.deepEqual(low.original,{text:lower,expanded:'false'});
assert.equal(low.removed(),true);
const larger='CCost Today 9 000 000 000 · 99999999 prompts';
const high=fixture(larger,{[larger]:[530,520],[reference]:[400,420]});
assert.equal(measure(high.view,true),530,'larger real text, including its wider collapsed state, wins');
const actual=fixture(lower,{[lower]:[300,310]});
assert.equal(measure(actual.view),310,'non-reserving measurement still covers both disclosure states');
assert.equal(actual.reads.length,2);
const failed=fixture(lower,null);
assert.throws(()=>measure(failed.view,true),/layout failed/);
assert.equal(failed.removed(),true,'failed measurements must not leave clones');
