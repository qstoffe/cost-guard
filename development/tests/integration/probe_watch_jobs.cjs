// Authenticated shipped Full Watch; synthetic two-job publications, no real secrets.
const assert=require('node:assert/strict'), fs=require('node:fs/promises'), path=require('node:path');
module.exports=async ({command,evaluate,until,owner,checks,layouts,output})=>{
  for(const theme of ['classic','light','dark']) for(const width of [1366,360]) {
    await command('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false},owner);
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:theme==='dark'?'dark':'light'}]},owner);
    await evaluate(owner,`document.documentElement.dataset.theme='${theme==='classic'?'classic':'web'}';
      globalThis.jobCard=[...current.watch.cards.values()].find(c=>c.backgroundDetail.jobs.size===2);
      globalThis.jobTarget=jobCard.backgroundDetail;jobTarget.summary.scrollIntoView();jobTarget.summary.focus();`);
    await command('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'},owner);
    await command('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13},owner);
    await until(owner,'jobTarget.node.open');
    const facts=await evaluate(owner,`(() => {
      const jobs=[...jobTarget.jobs.values()], node=jobs[1].input.firstChild;
      const range=document.createRange();range.selectNodeContents(node);
      const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
      jobs[1].summary.focus({preventScroll:true});const focus=document.activeElement,y=scrollY,selected=selection.toString();
      for(let i=0;i<8;i++) current.watch.update(liveValue);
      const result={jobs:jobs.length,commands:jobs.map(j=>j.input.textContent.includes('python task')),
        stable:jobTarget.node.open&&jobs.every(j=>j.node.open)&&jobs[1].input.firstChild===node&&
          document.activeElement===focus&&selection.toString()===selected&&scrollY===y,
        literal:jobTarget.list.querySelectorAll('script,img').length===0,
        overflow:document.documentElement.scrollWidth>innerWidth};
      selection.removeAllRanges();document.activeElement?.blur();return result;})()`);
    assert.deepEqual(facts,{jobs:2,commands:[true,true],stable:true,literal:true,overflow:false});
    const image=await command('Page.captureScreenshot',{format:'png'},owner);
    await fs.writeFile(path.join(path.dirname(output),`jobs-${theme}-${width}.png`),Buffer.from(image.data,'base64'));
    await evaluate(owner,'jobTarget.node.open=false');
    layouts.push({theme,width,...facts});
  }
  checks.push('authenticated Full Watch two-job commands; six theme/width cases; stable focus/selection/scroll');
};
