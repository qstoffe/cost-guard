// Real shipped toolbar geometry/styles; invoked by the authenticated Models probe.
const assert = require('node:assert/strict');

async function probeToolbar({command, evaluate, id}) {
  const layouts = [];
    const original = await evaluate(id, `(()=>{const p=document.querySelector('.model-price-controls');return {date:p.children[3].textContent,status:p.children[4].textContent,labels:[...document.querySelectorAll('.model-tools:not(.benchmark-tools) .model-filters label span')].map(n=>n.textContent)};})()`);
  const measure = () => evaluate(id, `(()=>{
    const price=document.querySelector('.model-price-controls'), button=price.querySelector('button');
    const filters=document.querySelector('.model-filters'), date=price.children[3], status=price.children[4];
    const rect=node=>{const r=node.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,height:r.height,center:r.top+r.height/2};};
    const style=node=>{const s=getComputedStyle(node);return {font:s.fontFamily,size:s.fontSize,padding:s.padding,minHeight:s.minHeight};};
    const nodes=[...price.children].filter(n=>n.textContent).concat([...filters.children]);
    const boxes=nodes.map(rect);
    const fits=boxes.every(r=>r.left>=0&&r.right<=innerWidth+.5&&r.height>0);
    const overlap=boxes.some((a,i)=>boxes.slice(i+1).some(b=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1));
    const clipped=nodes.some(n=>n.scrollWidth>n.clientWidth+1||n.scrollHeight>n.clientHeight+1);
    const labels=[...filters.children].map(label=>({label:rect(label),box:rect(label.querySelector('input')),text:rect(label.querySelector('span'))}));
    return {button:style(button),date:style(date),status:style(status),tier:style(document.querySelector('.model-relative')),ui:getComputedStyle(document.body).fontFamily,
      bounds:rect(button),dateBounds:rect(date),filters:rect(filters),labels,fits,overlap,clipped,overflow:document.documentElement.scrollWidth>innerWidth,
      pressed:button.hasAttribute('aria-pressed'),text:date.textContent,statusText:status.textContent};
  })()`);
  try {
    for (const width of [360,800,1280,1366,1920]) for (const theme of ['classic','light','dark']) for (const scale of [1,1.25,1.5,2]) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:false},id);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'},
        {name:'prefers-reduced-motion',value:'reduce'}]},id);
      await evaluate(id,`document.documentElement.dataset.theme=${JSON.stringify(theme==='classic'?'classic':'web')};document.documentElement.style.fontSize='${15*scale}px'`);
      for (const state of ['normal','refreshing','failure','unavailable']) {
        const date=state==='unavailable'?'Last fetched: Unavailable':state==='failure'?
          'Last fetched: Wednesday, 30 September 2026 at 23:59:59 Central European Summer Time':original.date;
        const status=state==='refreshing'?'Refreshing…':state==='failure'?
          'Price list refresh failed; previous prices retained. '+ 'upstream-unavailable-'.repeat(18):'';
        await evaluate(id,`(()=>{const p=document.querySelector('.model-price-controls');p.children[3].textContent=${JSON.stringify(date)};p.children[4].textContent=${JSON.stringify(status)};})()`);
        await evaluate(id,`document.querySelectorAll('.model-tools:not(.benchmark-tools) .model-filters label span').forEach((n,i)=>n.textContent=${JSON.stringify(original.labels)}[i]+${JSON.stringify(state==='failure'?' — extended localized filter label':'')})`);
        const layout=await measure(), context=JSON.stringify({width,theme,scale,state,layout});
        assert.equal(layout.button.font,layout.ui,context);
        assert.equal(layout.date.font,layout.ui,context); assert.equal(layout.status.font,layout.ui,context);
        assert.match(layout.tier.font,/monospace/,context);
        assert.equal(layout.button.size,`${12*scale}px`,context);
        assert.equal(layout.date.size,layout.button.size,context);
        assert.equal(layout.bounds.height,30*scale,context);
        assert.equal(layout.pressed,false,context); assert.equal(layout.text,date,context); assert.equal(layout.statusText,status,context);
        assert.equal(layout.fits,true,context); assert.equal(layout.clipped,false,context);
        assert.equal(layout.overlap,false,context); assert.equal(layout.overflow,false,context);
        for (const label of layout.labels) assert.ok(Math.abs(label.box.center-label.text.center)<1,context);
        if (width>=1280&&scale===1&&state==='normal') {
          assert.ok(Math.abs(layout.bounds.center-layout.dateBounds.center)<1,context);
          for (const label of layout.labels) assert.ok(Math.abs(label.label.center-layout.bounds.center)<1,context);
        }
        layouts.push({width,theme,fontScale:scale,state,...layout});
      }
    }
    await evaluate(id,`document.documentElement.style.fontSize='15px'`);
    await command('Emulation.setDeviceMetricsOverride',{width:360,height:1100,deviceScaleFactor:1,mobile:false},id);
    await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
    const coarse=await evaluate(id,`({coarse:matchMedia('(pointer: coarse)').matches,height:document.querySelector('.model-price-controls button').getBoundingClientRect().height,labels:[...document.querySelectorAll('.model-tools:not(.benchmark-tools) .model-filters label')].map(n=>n.getBoundingClientRect().height)})`);
    assert.equal(coarse.coarse,true); assert.ok(coarse.height>=44);
    assert.ok(coarse.labels.every(height=>height>=44)); layouts.push({coarse});
  } finally {
    await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
    await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},id);
    await evaluate(id,`(()=>{document.documentElement.style.removeProperty('font-size');const p=document.querySelector('.model-price-controls');p.children[3].textContent=${JSON.stringify(original.date)};p.children[4].textContent=${JSON.stringify(original.status)};})()`);
    await evaluate(id,`document.querySelectorAll('.model-tools:not(.benchmark-tools) .model-filters label span').forEach((n,i)=>n.textContent=${JSON.stringify(original.labels)}[i])`);
  }
  return layouts;
}
module.exports = {probeToolbar};
