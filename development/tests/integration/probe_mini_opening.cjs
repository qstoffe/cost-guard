// Real headless Document PiP timings. Synthetic publication, not OS compositor proof.
const assert=require('node:assert/strict');
module.exports=async({evaluate,until,checks,layouts,baseline=false})=>{
  await evaluate(`window.openingTraces=[];window.openingDelay=0;
    window.openingNative=documentPictureInPicture.requestWindow.bind(documentPictureInPicture);
    documentPictureInPicture.requestWindow=async options=>{
      const trace={click:performance.now(),styles:[]};openingTraces.push(trace);
      const w=await openingNative(options);trace.native=performance.now();window.openingChild=w;
      const d=w.document,append=d.head.append.bind(d.head);
      trace.violations=[];d.addEventListener('securitypolicyviolation',event=>trace.violations.push(event.violatedDirective));
      d.head.append=(...nodes)=>nodes.forEach(node=>{
        if(node.rel!=='stylesheet'){append(node);return;}
        node.addEventListener('load',()=>trace.styles.push(performance.now()),{once:true});
        if(openingDelay)setTimeout(()=>{if(!w.closed)append(node);},openingDelay);else append(node);
      });
      const observer=new MutationObserver(()=>{
        if(d.body.textContent.trim()&&trace.content==null){
          trace.content=performance.now();
          w.requestAnimationFrame(()=>{trace.contentFrame=performance.now();});
        }
        if(d.querySelector('.mini-watch')&&trace.usable==null){
          trace.usable=performance.now();observer.disconnect();
        }
      });observer.observe(d.body,{childList:true,subtree:true});
      return w;
    };`);
  for(const name of ['cold','warm','slow-styles']) {
    if(name==='slow-styles')await evaluate(`openingDelay=650;
      if(miniWatch.measure.styleDocument){
        window.openingStyleDocument=miniWatch.measure.styleDocument.bind(miniWatch.measure);
        miniWatch.measure.styleDocument=doc=>{openingStyleDocument(doc);return false;};
      }`);
    await evaluate('miniWatch.toggle()',true);
    await until('!!miniWatch.view&&openingTraces.at(-1).contentFrame!=null');
    const value=await evaluate(`(()=>{
      const t=openingTraces.at(-1),relative=v=>v==null?null:Math.round((v-t.click)*10)/10;
      const w=miniWatch.window,v=miniWatch.view,copy=v.root.firstElementChild.cloneNode(true);
      copy.classList.add('mini-header-measuring');copy.inert=true;copy.setAttribute('aria-hidden','true');v.root.append(copy);
      const daily=copy.querySelector('.mini-daily > span');
      let headerMinimum=copy.getBoundingClientRect().width;
      daily.textContent='CCost Today 90 000 · 999 prompts';
      headerMinimum=Math.max(headerMinimum,copy.getBoundingClientRect().width);copy.remove();
      const geometry={outer:[w.outerWidth,w.outerHeight],inner:[w.innerWidth,w.innerHeight],
        requested:miniWatch.openingBounds?.requested,desiredHeight:v.fitHeight(),headerMinimum,
        contentWidth:v.root.getBoundingClientRect().width};
      return {native:relative(t.native),content:relative(t.content),contentFrame:relative(t.contentFrame),
        styles:t.styles.map(relative),usable:relative(t.usable),
        blankAfterNative:Math.round((t.content-t.native)*10)/10,
        feedback:miniWatch.feedback.textContent,adopted:miniWatch.window.document.adoptedStyleSheets.length,
        geometry,clamped:geometry.desiredHeight>w.outerHeight+2,
        feedbackHidden:miniWatch.feedback.className==='sr-only',
        violations:t.violations,paints:miniWatch.window.performance.getEntriesByType('paint').map(entry=>({
          name:entry.name,ms:Math.round((entry.startTime+miniWatch.window.performance.timeOrigin-performance.timeOrigin-t.click)*10)/10}))};
    })()`);
    layouts.push({case:'opening-'+name,...value});
    if(!baseline){
      if(value.feedback){
        assert.equal(value.feedback,'Browser size limits prevented the full opening fit. Scroll Mini Watch to reach all content.');
        assert.equal(value.clamped,true,JSON.stringify(value));
      }
      assert.equal(value.feedbackHidden,true,'genuine clamp feedback also reserves no inline status slot');
      assert.deepEqual(value.violations,[],'same-origin cached styles retain shipped CSP');
      assert.ok(value.blankAfterNative<100,JSON.stringify(value));
      if(name!=='slow-styles')assert.ok(value.adopted>=2,'reuse successfully measured same-origin CSS');
      else assert.ok(value.usable-value.content>=500,'shell precedes controlled stylesheet delay');
    }
    await evaluate('miniWatch.close()');
  }
  await evaluate(`if(window.openingStyleDocument)miniWatch.measure.styleDocument=openingStyleDocument;
    documentPictureInPicture.requestWindow=openingNative;openingDelay=0;`);
  checks.push(baseline?'Baseline real native first/repeat/650ms delayed stylesheet timings':
    'Native first/repeat cached styles and early themed shell during 650ms stylesheet delay');
};
