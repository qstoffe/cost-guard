// Real rendered header fit, not merely request arguments or a nowrap assertion.
const assert = require('node:assert/strict');
function inspect(view) {
  const w=view.doc.defaultView, header=view.root.firstElementChild, bounds=header.getBoundingClientRect();
  const parts=[view.summary.querySelector('.mini-brand'),view.earlierToggle,view.dailyText].map(node=>{
    const range=view.doc.createRange();range.selectNodeContents(node);
    const lines=[...range.getClientRects()].filter(r=>r.width>0 && r.height>0);
    return {text:node.textContent,lines:lines.map(r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom})),
      overflow:node.scrollWidth>node.clientWidth+1 && w.getComputedStyle(node).overflowX==='hidden'};
  });
  const fits=parts.every(p=>p.lines.length===1 && !p.overflow && p.lines[0].left>=bounds.left-1 && p.lines[0].right<=bounds.right+1) &&
    parts.slice(1).every((p,i)=>p.lines[0].left>=parts[i].lines[0].right &&
      p.lines[0].top<parts[i].lines[0].bottom && p.lines[0].bottom>parts[i].lines[0].top);
  return {fits,width:bounds.width,parts,documentOverflow:view.doc.documentElement.scrollWidth>w.innerWidth+1};
}
async function probe({evaluate,open,close,read,capture,layouts,checks}) {
  const widths=[];
  const inspectSource=inspect.toString();
  for(const theme of ['classic','web'])for(const font of ['system-ui','serif']) {
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    await evaluate(`window.probeFont='${font}';miniWatch.measure.body.style.fontFamily='${font}'`);
    for(const [unit,cost,count,state] of [['credits','6 152',106,'observed'],['usd','$123456.78',99999999,'observed'],
        ['credits','',0,'loading'],['credits','',0,'unavailable']]) {
      await evaluate(`(()=>{ReportView.setUnit('${unit}');const p=structuredClone(liveValue);p.view.now_ms++;
        if('${state}'!=='observed')p.view.daily_usage=null;
        else {p.view.daily_usage.prompt_count=${count};p.view.daily_usage.total.display_units={${unit}:{known_ccost:'${cost}'}};}
        p.view.daily_state='${state}';miniWatch.observations.view=null;miniWatch.update(p);})()`);
      await open();
      const value=await read();
      value.measurement=await evaluate(`(()=>{const v=miniWatch.measure.view,h=v.root.firstElementChild.cloneNode(true);h.classList.add('mini-header-measuring');v.root.append(h);
        const result={width:h.getBoundingClientRect().width,parts:[...h.children].map(n=>({width:n.getBoundingClientRect().width,font:getComputedStyle(n).font})),
        actual:[...miniWatch.view.root.firstElementChild.children].map(n=>({width:n.getBoundingClientRect().width,font:miniWatch.window.getComputedStyle(n).font}))};h.remove();return result;})()`);
      assert.equal(value.header.documentOverflow,false);
      const limited=value.outer[0]+2<value.request.width+16;
      if(limited) {
        assert.match(await evaluate('miniWatch.feedback.textContent'),/Browser size limits/);
        assert.ok(value.header.parts.every(p=>!p.overflow),'native limits must not hide header text');
        layouts.push({case:'intrinsic-width-native-clamp',theme,font,unit,state,...value});
        widths.push(value.request.width);await close();continue;
      }
      assert.equal(value.header.fits,true,JSON.stringify({theme,font,unit,state,value}));
      if(theme==='classic' && font==='system-ui' && unit==='credits' && state==='observed')await capture();
      const narrower=await evaluate(`(()=>{const v=miniWatch.view,r=v.root,old=r.style.width;
        r.style.width=(r.getBoundingClientRect().width-6)+'px';
        try{return (${inspectSource})(v);}finally{r.style.width=old;}})()`);
      assert.equal(narrower.fits,false,JSON.stringify({value,narrower}));
      layouts.push({case:'intrinsic-width',theme,font,unit,state,...value,narrower});
      widths.push(value.request.width);
      await close();
    }
  }
  assert.ok(Math.max(...widths)-Math.min(...widths)>30,'snapshot/fonts must change the measured width');
  assert.ok(Math.min(...widths)<634,'ordinary headers must improve on the former request');
  await evaluate(`window.probeFont='';miniWatch.measure.body.style.fontFamily='';ReportView.setUnit('credits');miniWatch.update(liveValue)`);
  await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'default'})))()`);
  checks.push('16 header snapshots: themes/fonts, Credits/USD, long counts, loading/unavailable; unclamped achieved one-line layout breaks when reduced by 6 CSS pixels; native clamps separately assert truthful limitation/accessibility');
}
module.exports=probe;
module.exports.inspect=inspect;
