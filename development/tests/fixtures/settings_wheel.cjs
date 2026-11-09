// Policy edges only; actual native popup/hit testing is in probe_settings_wheel.
const assert = require('node:assert/strict');
module.exports = (Settings, context) => {
  context.CSS = {supports:()=>true}; context.HTMLSelectedContentElement = class {};
  context.getComputedStyle = node => node.style;
  const view = new Settings.View(()=>{throw new Error('Wheel must never save');});
  const select = view.controls.get('miniWatchSize');
  const option = select.children.find(n=>n.value==='fit-on-open');
  let top=0;
  const description = {clientHeight:100,scrollHeight:1000,dataset:{},
    style:{visibility:'visible',position:'absolute',lineHeight:'20px'},
    get scrollTop(){return top;},set scrollTop(value){top=Math.max(0,Math.min(900,value));}};
  option.parentNode=select; option.choiceHelp=description;
  select.options=select.children.filter(n=>n.tag==='option');
  select.open=true; select.matches=()=>select.open;
  select.querySelector=()=>option;
  const target={closest:selector=>selector==='option'?option:null};
  const wheel = (overrides={}) => {
    let prevented=false;
    select.events.wheel({currentTarget:select,target,deltaY:1,deltaX:0,deltaMode:0,
      preventDefault(){prevented=true;},...overrides});
    return prevented;
  };
  assert.equal(wheel({deltaY:50}),false); assert.equal(top,50);
  assert.equal(wheel({deltaMode:1,deltaY:2}),false); assert.equal(top,90);
  assert.equal(wheel({deltaMode:2,deltaY:2}),false); assert.equal(top,290);
  assert.equal(wheel({deltaY:10000}),false); assert.equal(top,900);
  assert.equal(wheel(),false,'bottom passes through');
  assert.equal(wheel({deltaY:-10000}),false); assert.equal(top,0);
  assert.equal(wheel({deltaY:-1}),false,'top passes through');
  for (const event of [{ctrlKey:true},{deltaX:10},{deltaY:0},
      {target:{closest:()=>description}}]) {
    assert.equal(wheel(event),false); assert.equal(top,0);
  }
  select.open=false; assert.equal(wheel(),false); select.open=true;
  for (const [property,value] of [['visibility','hidden'],['position','static']]) {
    const original=description.style[property]; description.style[property]=value;
    assert.equal(wheel(),false); description.style[property]=original;
  }
  description.scrollHeight=100; assert.equal(wheel(),false); description.scrollHeight=1000;
  option.parentNode={}; assert.equal(wheel(),false); option.parentNode=select;
  select.dataset.helpInput='keyboard';
  assert.equal(wheel({target:{closest:()=>null},deltaY:25}),false); assert.equal(top,25);
  select.events.pointermove({target:{closest:()=>option}});
  assert.equal(select.dataset.helpInput,'pointer');assert.equal(description.dataset.preview,'true');
  const other=select.options.find(n=>n!==option);
  select.events.focusin({target:{closest:()=>other}});
  assert.equal(description.dataset.preview,'false');assert.equal(other.choiceHelp.dataset.preview,'true');
  select.events.pointermove({target:{closest:()=>null}});
  assert.equal(other.choiceHelp.dataset.preview,'true','moving into the sibling pane retains preview without focus changes');
  assert.equal(top,25,'switching preview preserves its independent scroll offset');
  console.log('Enhanced Settings wheel policy: pixels/lines/pages, boundary pass-through and scoped preview passed');
};
