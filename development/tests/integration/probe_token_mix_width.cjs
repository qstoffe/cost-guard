// Compare intrinsic tracks with the same table in its wide container.
const assert = require('node:assert/strict');
module.exports = async function probe({evaluate, command, tab, checks}) {
  for(const theme of ['classic','light','dark']) for(const width of [360,520,1280,2560])
    for(const variant of ['normal','font','zoom']) {
      await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},tab);
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},tab);
      const geometry=await evaluate(`(()=>{
        document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';
        document.documentElement.style.fontSize='${variant==='font'?'20px':''}';
        document.body.style.zoom='${variant==='zoom'?'1.25':'1'}';
        return [...document.querySelectorAll('.token-mix-table')].map(table=>{
          const cells=[...table.tHead.rows[0].cells], pan=table.parentElement;
          const widths=()=>cells.map(cell=>cell.getBoundingClientRect().width);
          const actual=widths(), total=table.getBoundingClientRect().width;
          table.style.width='max-content'; table.style.minWidth='0';
          const intrinsic=widths(); table.style.width='';table.style.minWidth='';
          const last=cells.at(-1), row=table.tBodies[0].rows[0], rect=last.getBoundingClientRect();
          return {actual,intrinsic,total,pan:pan.clientWidth*(document.body.currentCSSZoom||1),
            right:getComputedStyle(last).textAlign==='right' && getComputedStyle(row.cells[row.cells.length-1]).textAlign==='right',
            headerGap:rect.right-last.querySelector('button').getBoundingClientRect().right,
            padding:parseFloat(getComputedStyle(last).paddingRight)*(document.body.currentCSSZoom||1),
            outside:document.documentElement.scrollWidth>innerWidth,
            horizontal:pan.scrollWidth>pan.clientWidth,
            edge:Math.abs(table.getBoundingClientRect().right-last.getBoundingClientRect().right)};
        });
      })()`);
      for(const [index,g] of geometry.entries()) {
        assert.equal(g.actual.length,index===0?10:9);
        assert.equal(g.outside,false);assert.equal(g.right,true);assert.ok(g.edge<1);
        assert.ok(Math.abs(g.headerGap-g.padding)<2,JSON.stringify(g));
        for(let col=0;col<g.actual.length-1;col++)
          assert.ok(Math.abs(g.actual[col]-g.intrinsic[col])<1,JSON.stringify({theme,width,variant,index,col,g}));
        if(width<=520) assert.equal(g.horizontal,true);
        if(g.pan>g.intrinsic.reduce((a,b)=>a+b,0)+2) {
          assert.ok(g.actual.at(-1)>g.intrinsic.at(-1)+1,JSON.stringify(g));
          assert.ok(Math.abs(g.total-g.pan)<2,JSON.stringify(g));
        }
      }
    }
  await evaluate(`document.documentElement.style.fontSize='';document.body.style.zoom=''`);
  checks.push('both 10/9-column grids: intrinsic non-total tracks, sole elastic right-aligned total, no trailing/page overflow, 360/520/1280/2560 × three themes × normal/large-font/125%-zoom');
};
