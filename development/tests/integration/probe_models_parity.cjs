// Same-page computed design contract; synthetic source data in the shipped application.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');

async function probeModelsParity({command, evaluate, id, output}) {
  const layouts = [];
  try {
    await evaluate(id, `window.parityOriginal={data:current.benchmark.data,efforts:current.benchmark.choice.efforts};
      current.benchmark.choice.efforts=null;current.benchmark.draw();`);
    for (const width of [360, 768, 1366, 1920]) for (const theme of ['classic', 'light', 'dark']) for (const scale of [1, 1.25, 1.5]) {
      await command('Emulation.setDeviceMetricsOverride', {width, height:1100, deviceScaleFactor:1, mobile:false}, id);
      await command('Emulation.setEmulatedMedia', {features:[{name:'prefers-color-scheme', value:theme==='dark'?'dark':'light'},
        {name:'prefers-reduced-motion',value:'reduce'}]}, id);
      await evaluate(id, `document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';
        document.documentElement.style.fontSize='${15*scale}px';current.benchmark.picker.open=true;`);
      const layout = await evaluate(id, `(()=>{
        const rect=n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};};
        const style=n=>{const s=getComputedStyle(n);return Object.fromEntries(['fontFamily','fontSize','fontWeight','lineHeight','color',
          'backgroundColor','padding','borderTop','borderRight','borderBottom','borderRadius','overflowX','scrollbarColor'].map(k=>[k,s[k]]));};
        const pair=(a,b)=>[style(document.querySelector(a)),style(document.querySelector(b))];
        const tools=[...document.querySelectorAll('.model-tools')].map(n=>{
          const left=n.querySelector('.model-price-controls'),right=n.querySelector('.model-filters');
          const children=[...left.children].filter(n=>n.textContent);
          return {row:rect(n),left:rect(left),right:rect(right),button:rect(children[0]),date:rect(children[1]),
            noLink:!left.querySelector('a'),direction:getComputedStyle(n).flexDirection,
            fits:[...children,...right.children].every(n=>{const r=rect(n);return r.left>=0&&r.right<=innerWidth+1;})};
        });
        const picker=current.benchmark, options=rect(picker.options), labels=[...picker.options.children].map(rect);
        return {overflow:document.documentElement.scrollWidth>innerWidth,tools,
          heading:pair('.model-section-heading','.benchmark-section .model-section-heading'),
          source:pair('.model-source a','.benchmark-section .model-source a'),
          shell:pair('.overview-models','.benchmark-scroll'),
          header:pair('.overview-model-table th','.benchmark-table th'),
          cell:pair('.overview-model-table tbody td','.benchmark-table tbody td'),
          sort:pair('.overview-model-table th button','.benchmark-table th button'),
          refresh:pair('[data-model-control="refresh"]','[data-benchmark-control="refresh"]'),
          status:pair('.model-tools [role="status"]','.benchmark-tools [role="status"]'),
          sourceSizes:[...document.querySelectorAll('.model-source, .model-source *')].map(n=>getComputedStyle(n).fontSize),
          solved:[...document.querySelectorAll('.benchmark-table :is(th,td):nth-child(5)')].map(n=>getComputedStyle(n).textAlign),
          cost:[...document.querySelectorAll('.benchmark-table :is(th,td):nth-child(4)')].map(n=>getComputedStyle(n).textAlign),
          section:style(document.querySelector('.benchmark-section')),options,labels,
          popupFits:options.left>=0&&options.right<=innerWidth+1&&picker.options.scrollWidth<=picker.options.clientWidth+1,
          grid:getComputedStyle(picker.options).gridTemplateColumns,
          pickerHeight:rect(picker.summary).height,refreshHeight:rect(document.querySelector('[data-model-control="refresh"]')).height,
          sourceSmaller:parseFloat(getComputedStyle(document.querySelector('.model-source')).fontSize)<parseFloat(getComputedStyle(document.querySelector('h2')).fontSize)
        };
      })()`);
      const context = JSON.stringify({width, theme, scale, layout});
      for (const key of ['heading','source','shell','header','cell','sort','refresh','status']) assert.deepEqual(layout[key][0], layout[key][1], key+' '+context);
      assert.equal(layout.overflow, false, context); assert.equal(layout.popupFits, true, context);
      assert.equal(new Set(layout.sourceSizes).size, 1, context); assert.equal(layout.sourceSmaller, true, context);
      assert.ok(layout.solved.every(value=>value==='left'), context); assert.ok(layout.cost.every(value=>value==='right'), context);
      assert.match(layout.section.borderTop, /^0px none /, context);
      assert.equal(layout.section.backgroundColor, 'rgba(0, 0, 0, 0)', context);
      assert.equal(layout.pickerHeight, layout.refreshHeight, context);
      assert.equal(layout.grid.split(' ').length, 1, context);
      layout.labels.forEach((label,index)=>{
        assert.ok(label.left>=layout.options.left && label.right<=layout.options.right, context);
        if (index) assert.ok(label.top>=layout.labels[index-1].bottom, context);
      });
      for (const tools of layout.tools) {
        assert.equal(tools.direction,'row',context); assert.equal(tools.noLink,true,context); assert.equal(tools.fits,true,context);
        assert.ok(Math.abs(tools.button.left-tools.left.left)<1,context);
        assert.ok(Math.abs(tools.right.right-tools.row.right)<1,context);
        if (width>=1366 && scale===1) assert.ok(Math.abs(tools.button.top-tools.right.top)<1,context);
      }
      layouts.push({kind:'models-parity',width,theme,fontScale:scale,...layout});
      if ((width===1366 || width===360) && scale===1) {
        await evaluate(id, 'window.scrollTo(0,0)');
        const metrics = await command('Page.getLayoutMetrics',{},id);
        const image = await command('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,
          clip:{x:0,y:0,width,height:Math.ceil(metrics.cssContentSize.height),scale:1}},id);
        await fs.writeFile(output.replace(/\.json$/,'')+'-parity-'+width+'-'+theme+'.png',Buffer.from(image.data,'base64'));
      }
    }
    // Stress a long source-provided list without inventing any production choices.
    await evaluate(id, `window.savedBenchmark=current.benchmark.data;current.benchmark.data={...savedBenchmark,
      efforts:[...savedBenchmark.efforts,...Array.from({length:30},(_,i)=>'source extra '+i)]};current.benchmark.draw();
      current.benchmark.picker.open=true;current.benchmark.summary.scrollIntoView({block:'start'});`);
    const point = await evaluate(id, `(()=>{const n=current.benchmark.options,r=n.getBoundingClientRect();return {
      x:r.left+r.width/2,y:Math.min(innerHeight-10,r.top+r.height/2),scrolls:n.scrollHeight>n.clientHeight};})()`);
    assert.equal(point.scrolls,true);
    await command('Input.dispatchMouseEvent',{type:'mouseWheel',x:point.x,y:point.y,deltaX:0,deltaY:200},id);
    await evaluate(id, 'new Promise(requestAnimationFrame)');
    assert.equal(await evaluate(id, 'current.benchmark.options.scrollTop>0'),true);
    await evaluate(id, 'current.benchmark.data=savedBenchmark;current.benchmark.draw();current.benchmark.picker.open=false');
    await command('Page.bringToFront',{},id);
    await command('Emulation.setDeviceMetricsOverride',{width:360,height:1100,deviceScaleFactor:1,mobile:false},id);
    await evaluate(id, "document.documentElement.style.fontSize='15px'");
    await command('Emulation.setTouchEmulationEnabled',{enabled:true},id);
    const touch = async selector=>{
      const point=await evaluate(id, `(()=>{const n=document.querySelector(${JSON.stringify(selector)});n.scrollIntoView({block:'center'});
        const r=n.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
      try {
        await command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{...point,radiusX:1,radiusY:1}]},id);
        await command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]},id);
      } catch (error) { throw new Error('Touch '+selector+' at '+JSON.stringify(point),{cause:error}); }
    };
    await touch('.effort-picker summary');
    assert.equal(await evaluate(id, 'current.benchmark.picker.open && current.benchmark.summary.getBoundingClientRect().height>=44'),true);
    await touch('.effort-options input');
    assert.equal(await evaluate(id, 'current.benchmark.picker.open && current.benchmark.choice.efforts.size===2'),true);
    layouts.push({kind:'models-parity-input',verticalWheel:true,touchOpenAndToggle:true});
  } finally {
    await command('Emulation.setTouchEmulationEnabled',{enabled:false},id);
    await command('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},id);
    await evaluate(id, `document.documentElement.style.removeProperty('font-size');current.benchmark.picker.open=false;
      current.benchmark.data=parityOriginal.data;current.benchmark.choice.efforts=parityOriginal.efforts;
      current.benchmark.draw();window.scrollTo(0,0);`);
  }
  return layouts;
}
module.exports = {probeModelsParity};
