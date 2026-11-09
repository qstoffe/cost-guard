// Rendered metric-column minima, Session ratio and complete three-part header.
const assert=require('node:assert/strict');
function inspect(view) {
  const w=view.doc.defaultView,header=view.root.firstElementChild,bounds=header.getBoundingClientRect();
  const parts=[view.summary.querySelector('.mini-brand'),view.fitButton,view.dailyText].map(node=>{
    const range=view.doc.createRange();range.selectNodeContents(node);const rects=[...range.getClientRects()].filter(r=>r.width&&r.height);
    const r=node.getBoundingClientRect(),style=w.getComputedStyle(node);
    return {text:node.textContent,left:r.left,right:r.right,top:r.top,bottom:r.bottom,font:style.fontFamily,size:style.fontSize,
      fits:rects.every(n=>n.left>=r.left-1&&n.right<=r.right+1)&&node.scrollWidth<=node.clientWidth+1};});
  const widths=[...view.body.parentNode.tHead.rows[0].cells].map(n=>n.getBoundingClientRect().width);
  const other=widths[0]+widths[2]+widths[3]+widths[4];
  return {fits:parts.every(p=>p.fits&&p.left>=bounds.left-1&&p.right<=bounds.right+1),parts,width:bounds.width,
    columns:widths,ratio:widths[1]/other,gutter:view.prompts.offsetWidth-view.prompts.clientWidth,
    documentOverflow:view.doc.documentElement.scrollWidth>w.innerWidth+1};
}
module.exports=async({evaluate,command,sessionId,open,close,read,capture,layouts,checks})=>{
  await evaluate(`window.widthUpdate=miniWatch.update.bind(miniWatch);miniWatch.update=p=>widthUpdate(window.widthPublication||p)`);
  for(const theme of ['classic','web'])for(const color of ['light','dark'])for(const font of ['system-ui','serif']) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},sessionId);
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    for(const [unit,cost,count] of [['credits','90 000',999],['credits','9 000 000 000',99999999],['usd','$123456.78',99999999]]) {
      await evaluate(`(()=>{ReportView.setUnit('${unit}');const p=structuredClone(liveValue);p.view.now_ms++;
        p.view.daily_usage.prompt_count=${count};p.view.daily_usage.display_units={${unit}:{daily_ccost:'${cost}'}};
        window.widthPublication=p;miniWatch.update(p);miniWatch.measure.body.style.fontFamily='${font}';})()`);
      await open();await evaluate(`miniWatch.window.document.body.style.fontFamily='${font}';miniWatch.render()`);
      const value=await read();assert.equal(value.header.parts[2].text,`CCost Today ${cost} · ${count} prompts`);
      assert.equal(value.header.documentOverflow,false);assert.equal(value.header.fits,true,JSON.stringify(value));
      assert.equal(await evaluate(`miniWatch.view.root.querySelectorAll('table').length`),1);
      assert.equal(await evaluate(`miniWatch.view.root.querySelector('.mini-earlier-toggle')`),null);
      if(cost==='90 000'&&value.outer[0]+2>=value.request.width+16) {
        assert.ok(value.header.ratio>=1.4&&value.header.ratio<=1.95,JSON.stringify(value));
        assert.ok(value.header.columns[2]<value.header.columns[1]);
      }
      layouts.push({case:`width-${theme}-${color}-${font}-${unit}-${count}`,...value});
      if(cost==='90 000'&&font==='system-ui')await capture(`${theme}-${color}`);await close();
    }
  }
  for(const unit of ['credits','usd'])for(const width of [650,280]) {
    const amount=unit==='credits'?'?9 000 000':'?$123456.78',total=unit==='credits'?'90 000 000 000':'$987654321.00';
    await evaluate(`(()=>{ReportView.setUnit('${unit}');const p=structuredClone(liveValue);p.view.now_ms++;
      p.view.cards_state='observed';for(const card of [...p.view.active_cards,...p.view.history_cards]){card.state='observed';
        for(const row of card.rows)row.prompt.display_units={${unit}:{ccost:'${amount}'}};
        card.session_summary.cost.display_units={${unit}:{known_ccost:'${total}'}};}
      window.widthPublication=p;miniWatch.update(p);})()`);
    await open();await evaluate(`miniWatch.window.resizeTo(${width},550)`,true);
    await evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
    const value=await evaluate(`(()=>{const v=miniWatch.view,w=miniWatch.window;return {
      documentOverflow:v.doc.documentElement.scrollWidth>w.innerWidth+1,
      horizontal:v.prompts.scrollWidth>v.prompts.clientWidth+1,
       costs:[...v.promptRows.values()].flatMap(row=>[2,3].map(index=>{const cell=row.cells[index],n=cell.firstChild,r=v.doc.createRange();r.selectNodeContents(n);
         return {index,text:n.textContent,fits:[...r.getClientRects()].every(x=>x.left>=cell.getBoundingClientRect().left-1&&x.right<=cell.getBoundingClientRect().right+1)};}))};})()`);
    assert.equal(value.documentOverflow,false);assert.ok(value.costs.length>0);
    for(const cost of value.costs){assert.equal(cost.text,cost.index===2?amount:total);assert.equal(cost.fits,true);}
    if(width===280)assert.equal(value.horizontal,true,'oversized independent amounts pan within the table, never clip');
    layouts.push({case:`paired-cost-${unit}-${width}`,...value});await close();
  }
  await evaluate(`miniWatch.update=window.widthUpdate;delete window.widthPublication;delete window.widthUpdate;
    miniWatch.measure.body.style.fontFamily='';ReportView.setUnit('credits');miniWatch.update(liveValue)`);
  await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'default'})))()`);
  checks.push('24 real layouts: themes/light/dark/system/serif, reference/long Today and USD; one table, compact metrics and feasible ~1.6 Session ratio, native requested/achieved geometry; four oversized paired-cost layouts preserve both amounts and narrow table panning');
};
module.exports.inspect=inspect;
