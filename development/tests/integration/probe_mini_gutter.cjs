// Real PiP geometry: unused gutter versus authentic browser-owned scrollbars.
const assert=require('node:assert/strict');
function inspect(view) {
  const doc=view.doc,w=doc.defaultView,p=view.prompts,table=view.body.parentNode;
  const rect=node=>{const r=node.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width};};
  const metrics=node=>({rect:rect(node),clientWidth:node.clientWidth,offsetWidth:node.offsetWidth,scrollWidth:node.scrollWidth});
  const style=w.getComputedStyle(doc.body),body=rect(doc.body),border=rect(table);
  return {body:metrics(doc.body),root:metrics(view.root),prompts:metrics(p),table:metrics(table),
    padding:[parseFloat(style.paddingLeft),parseFloat(style.paddingRight)],
    insets:[border.left-body.left,body.right-border.right],gutter:p.offsetWidth-p.clientWidth,
    scrollbarGutter:w.getComputedStyle(p).scrollbarGutter,vertical:p.scrollHeight>p.clientHeight+1,
    horizontal:p.scrollWidth>p.clientWidth+1,documentGutter:w.innerWidth-doc.documentElement.clientWidth,
    documentOverflow:doc.documentElement.scrollWidth>w.innerWidth+1,
    documentVertical:doc.documentElement.scrollHeight>w.innerHeight+1,
    headerTop:rect(table.tHead.rows[0].cells[0]).top,regionTop:rect(p).top,
    accountsClear:rect(view.accounts).top>=rect(p).bottom-1,columns:table.tHead.rows[0].cells.length,
    outer:[w.outerWidth,w.outerHeight]};
}
module.exports=async({evaluate,until,fixture,command,sessionId,open,close,capture,layouts,checks})=>{
  const read=()=>evaluate(`(${inspect.toString()})(miniWatch.view)`);
  const settle=()=>evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
  for(const theme of ['classic','web'])for(const color of ['light','dark']) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},sessionId);
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    await fixture('density-3-1');await until('liveValue.view.active_cards.length===3');await open();
    // Reproduce the original declaration in this exact native window, then restore shipped CSS.
    await evaluate(`miniWatch.view.prompts.style.scrollbarGutter='stable'`);await settle();
    const before=await read();await capture(`gutter-${theme}-${color}-before`);
    await evaluate(`miniWatch.view.prompts.style.scrollbarGutter=''`);await settle();
    const after=await read();await capture(`gutter-${theme}-${color}-after`);
    layouts.push({case:`gutter-pair-${theme}-${color}`,before,after});
    assert.equal(after.gutter,0,JSON.stringify(after));
    assert.equal(after.scrollbarGutter,'auto');assert.deepEqual(after.outer,before.outer);
    if(before.gutter>0)assert.ok(before.insets[1]-after.insets[1]>=before.gutter-1);
    for(const count of [0,1,3,5,6,10,5,1]) {
      await fixture(`density-${count}-1`);await until(`miniWatch.view.promptRows.size===${count}`);await settle();
      const value=await read();layouts.push({case:`gutter-${theme}-${color}-${count}`, ...value});
      assert.equal(value.vertical,count>5,JSON.stringify(value));
      assert.equal(value.documentOverflow,false);assert.equal(value.horizontal,false);
      assert.equal(value.accountsClear,true);assert.equal(value.columns,5);
      assert.deepEqual(value.outer,after.outer,'row/scrollbar transitions never resize native PiP');
      assert.ok(Math.abs(value.insets[0]-value.padding[0])<=1,JSON.stringify(value));
      assert.ok(Math.abs(value.insets[1]-value.padding[1]-value.gutter)<=1,JSON.stringify(value));
      if(count<=5)assert.equal(value.gutter,0);
      else {
        await evaluate('miniWatch.view.prompts.scrollTop=miniWatch.view.prompts.scrollHeight');await settle();
        const scrolled=await read();
        assert.ok(Math.abs(scrolled.headerTop-scrolled.regionTop)<=1,'sticky header stays at the region top');
        assert.equal(await evaluate(`(()=>{const v=miniWatch.view,p=v.prompts,last=v.body.lastElementChild;
          return p.scrollTop>0&&last.getBoundingClientRect().bottom<=p.getBoundingClientRect().bottom+1;})()`),true);
        await evaluate('miniWatch.view.prompts.scrollTop=0');
      }
    }
    await close();
  }
  await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'default'})))()`);
  checks.push('Paired original-stable/shipped gutter screenshots and DOM geometry in Classic/Web light/dark; 0/1/3/5/6/10→5→1 rows, authentic internal scrollbar, sticky header, reachable last row, symmetric body padding and no passive native resize');
};
module.exports.inspect=inspect;
