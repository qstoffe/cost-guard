// Real rendered header fit, not merely request arguments or a nowrap assertion.
const assert = require('node:assert/strict');
function inspect(view) {
  const w=view.doc.defaultView, header=view.root.firstElementChild, bounds=header.getBoundingClientRect();
  const parts=[view.summary.querySelector('.mini-brand'),view.earlierToggle,view.dailyText].map(node=>{
    const range=view.doc.createRange();range.selectNodeContents(node);
    // Split value/help spans can yield duplicate or adjacent rects on one line.
    // Group their actual vertical bands; wrapping must still create another line.
    const lines=[];
    for(const rect of [...range.getClientRects()].filter(r=>r.width>0 && r.height>0)) {
      const line=lines.find(r=>Math.abs(r.top-rect.top)<.5 && Math.abs(r.bottom-rect.bottom)<.5);
      if(line){line.left=Math.min(line.left,rect.left);line.right=Math.max(line.right,rect.right);}
      else lines.push({left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom});
    }
    const r=node.getBoundingClientRect(),style=w.getComputedStyle(node);
    return {text:node.textContent,box:{left:r.left,right:r.right,top:r.top,bottom:r.bottom},lines:lines.map(r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom})),
      font:style.fontFamily,size:style.fontSize,lineHeight:style.lineHeight,
      overflow:node.scrollWidth>node.clientWidth+1 && w.getComputedStyle(node).overflowX==='hidden'};
  });
  const fits=parts.every(p=>p.lines.length===1 && !p.overflow && p.box.left>=bounds.left-1 && p.box.right<=bounds.right+1 &&
      p.lines[0].left>=p.box.left-1 && p.lines[0].right<=p.box.right+1) &&
    parts.slice(1).every((p,i)=>p.lines[0].left>=parts[i].lines[0].right &&
      p.lines[0].top<parts[i].lines[0].bottom && p.lines[0].bottom>parts[i].lines[0].top);
  const marker=w.getComputedStyle(view.earlierToggle,'::before'),button=w.getComputedStyle(view.earlierToggle);
  const luminance=color=>{const rgb=color.match(/[\d.]+/g).slice(0,3).map(n=>{const c=Number(n)/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;});return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
  const light=luminance(button.color),background=luminance(button.backgroundColor);
  return {fits,width:bounds.width,parts,marker:{content:marker.content,width:marker.width},
    button:{border:button.borderWidth,outline:button.outlineWidth,focused:view.doc.activeElement===view.earlierToggle,
      pressed:view.earlierToggle.getAttribute('aria-pressed'),expanded:view.earlierToggle.getAttribute('aria-expanded'),
      controls:view.earlierToggle.getAttribute('aria-controls'),hidden:view.earlier.hidden,data:view.prompts.dataset.expanded,
      background:button.backgroundColor,color:button.color,contrast:(Math.max(light,background)+.05)/(Math.min(light,background)+.05)},
    documentOverflow:view.doc.documentElement.scrollWidth>w.innerWidth+1};
}
async function pipSession({evaluate,command,targetId}) {
  let pip;
  for(const target of (await command('Target.getTargets')).targetInfos.filter(t=>t.targetId!==targetId&&t.type==='page')) {
    const attached=await command('Target.attachToTarget',{targetId:target.targetId,flatten:true});
    if(await evaluate('!!document.querySelector(".mini-watch")',false,attached.sessionId)){pip=attached.sessionId;break;}
  }
  assert.ok(pip);return pip;
}
async function disclosure({evaluate,command,pip,read,layouts,label,required,capture}) {
  await command('Page.bringToFront',{},pip);
  await evaluate(`(()=>{const w=miniWatch.window;w.headerResizes=[];for(const name of ['resizeBy','resizeTo']) {
    const native=w[name].bind(w);w[name]=(...args)=>{w.headerResizes.push({name,args,before:[w.outerWidth,w.outerHeight]});return native(...args);};}})()`);
  const settle=()=>evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
  const initial=await read();
  for(const key of [null,'Enter',' '])for(const expanded of [true,false]) {
    if(key) {
      await evaluate('miniWatch.view.earlierToggle.focus()');
      for(const type of ['keyDown','keyUp'])await command('Input.dispatchKeyEvent',{type,key,code:key===' '?'Space':key,windowsVirtualKeyCode:key===' '?32:13,...(type==='keyDown'?{text:key===' '?' ':'\r'}:{})},pip);
    } else {
      const point=await evaluate(`(()=>{const r=miniWatch.view.earlierToggle.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
      await command('Input.dispatchMouseEvent',{type:'mouseMoved',...point},pip);
      await command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point},pip);
      const active=await read();
      if(active.header.width>=required-1)assert.equal(active.header.fits,true,JSON.stringify(active));
      else {assert.equal(active.header.documentOverflow,false);assert.ok(active.header.parts.every(p=>!p.overflow));}
      await command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point},pip);
    }
    await settle();const value=await read();assert.equal(value.expanded,expanded);
    const b=value.header.button;
    assert.equal(b.pressed,String(expanded));assert.equal(b.expanded,String(expanded));assert.equal(b.data,String(expanded));
    assert.equal(b.hidden,!expanded);assert.equal(b.controls,'mini-earlier-sessions');
    assert.equal(value.header.parts[1].text,'Earlier Sessions');
    assert.ok(['none','normal','""'].includes(value.header.marker.content),'no disclosure chevron');
    if(expanded){assert.notEqual(b.background,initial.header.button.background);assert.ok(b.contrast>=4.5,JSON.stringify(b));}
    await command('Input.dispatchMouseEvent',{type:'mouseMoved',x:0,y:0},pip);
    const resting=await read();
    if(expanded)assert.equal(resting.header.button.background,b.background,'pressed fill persists without hover');
    else assert.equal(resting.header.button.background,initial.header.button.background);
    if(expanded && !key && label.theme==='classic' && label.color==='light' && label.font==='system-ui')await capture('expanded');
    value.resizeRequests=await evaluate('miniWatch.window.headerResizes');
    for(const request of value.resizeRequests)assert.ok(request.name==='resizeBy'?Math.abs(request.args[0])<=1:
      Math.abs(request.args[0]-request.before[0])<=1,'only height and permitted one-DIP rounding correction');
    assert.equal(value.header.documentOverflow,false);
    assert.ok(value.header.parts.every(p=>!p.overflow && p.lines.length>0));
    assert.equal(value.header.marker.width,initial.header.marker.width,'markers must not move header contents');
    assert.equal(value.header.parts[1].box.right-value.header.parts[1].box.left,
      initial.header.parts[1].box.right-initial.header.parts[1].box.left);
    if(key){assert.equal(value.header.button.focused,true);assert.ok(parseFloat(value.header.button.outline)>0);}
    // Native clamps may change the achieved width, not the header's intrinsic need.
    if(value.header.width>=required-1)assert.equal(value.header.fits,true,JSON.stringify({label,key,value}));
    else value.nativeDisclosureClamp=true;
    if(Math.abs(value.outer[0]-initial.outer[0])<=1) {
      assert.equal(value.header.fits,true,JSON.stringify({label,key,value}));
      initial.header.parts.forEach((p,i)=>assert.ok(Math.abs(p.lines[0].left-value.header.parts[i].lines[0].left)<=1.5));
    }
    layouts.push({case:'reference-disclosure',label,key,...value});
  }
}
async function probe({evaluate,command,sessionId,targetId,open,close,read,capture,layouts,checks}) {
  const widths=[];
  const inspectSource=inspect.toString();
  for(const theme of ['classic','web'])for(const color of ['light','dark'])for(const font of ['system-ui','serif']) {
    await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},sessionId);
    await evaluate(`(async()=>applySettings(await api('/api/settings/mini-size',{miniWatchSize:'${theme==='classic'?'default':'fit-on-open'}'})))()`);
    await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'${theme}'})))()`);
    await evaluate(`window.probeFont='${font}';miniWatch.measure.body.style.fontFamily='${font}'`);
    for(const [unit,cost,count,state] of [['credits','6 152',106,'observed'],['credits','90 000',999,'observed'],
        ['credits','9 000 000 000',99999999,'observed'],['usd','$123456.78',99999999,'observed'],['usd','123.456,78 $',999,'observed'],
        ['credits','',0,'loading'],['credits','',0,'unavailable']]) {
      await evaluate(`(()=>{ReportView.setUnit('${unit}');const p=structuredClone(liveValue);p.view.now_ms++;
        if('${state}'!=='observed')p.view.daily_usage=null;
        else {p.view.daily_usage.prompt_count=${count};p.view.daily_usage.display_units={${unit}:{daily_ccost:'${cost}'}};
          p.view.daily_usage.total.complete=false;p.view.daily_usage.total.display_units={${unit}:{known_ccost:'?${cost}'}};
          p.view.daily_usage.mix.cost_complete=false;p.view.daily_usage.prompt_count_complete=false;}
        p.view.daily_state='${state}';miniWatch.observations.view=null;miniWatch.update(p);})()`);
      await open();
      const pip=await pipSession({evaluate,command,targetId});
      await command('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:color}]},pip);
      await evaluate('new Promise(resolve=>miniWatch.window.requestAnimationFrame(()=>miniWatch.window.requestAnimationFrame(resolve)))');
      assert.equal(await evaluate(`miniWatch.window.matchMedia('(prefers-color-scheme: ${color})').matches`),true);
      const value=await read();
      value.measurement=await evaluate(`(()=>{const v=miniWatch.measure.view,h=v.root.firstElementChild.cloneNode(true);h.classList.add('mini-header-measuring');v.root.append(h);
        const actual=h.querySelector('.mini-daily > span'),toggle=h.querySelector('.mini-earlier-toggle'),real=actual.textContent,widths=[];
        for(const text of [real,'CCost Today 90 000 · 999 prompts'])for(const expanded of ['false','true']) {
          actual.textContent=text;toggle.setAttribute('aria-expanded',expanded);toggle.setAttribute('aria-pressed',expanded);widths.push({text,expanded,width:h.getBoundingClientRect().width});}
        const s=getComputedStyle(miniWatch.measure.body),w=miniWatch.window,d=w.document;
        const result={widths,real,maximum:Math.max(...widths.map(n=>n.width)),horizontal:parseFloat(s.paddingLeft)+parseFloat(s.paddingRight),
          gutter:w.innerWidth-d.documentElement.getBoundingClientRect().width,scale:(outerWidth-16)/innerWidth};h.remove();return result;})()`);
      const m=value.measurement;
      assert.equal(value.header.parts[2].text,m.real,'synthetic reserve must never replace actual UI data');
      if(state==='observed')assert.equal(value.header.parts[2].text,`CCost Today ${cost} · ${count} prompts`);
      assert.equal(await evaluate('miniWatch.view.dailyNote.textContent'),'');
      assert.equal(await evaluate('miniWatch.measure.view.earlier.hidden'),true);
      const slack=value.request.width/m.scale-m.horizontal-m.gutter-m.maximum;
      assert.ok(slack>=7 && slack<10,JSON.stringify({slack,value}));
      if(cost==='9 000 000 000')assert.ok(m.widths[0].width>m.widths[2].width,'larger real content must win');
      assert.equal(value.header.documentOverflow,false);
      const limited=value.outer[0]+2<value.request.width+16;
      value.requestClamped=limited;
      if(limited && (value.header.width+1<m.maximum || value.desired>value.outer[1]+2)) {
        assert.match(await evaluate('miniWatch.feedback.textContent'),/Browser size limits/,JSON.stringify(value));
        assert.ok(value.header.parts.every(p=>!p.overflow),'native limits must not hide header text');
        layouts.push({case:'intrinsic-width-native-clamp',theme,color,font,unit,state,...value});
        widths.push(value.request.width);await close();continue;
      }
      assert.equal(value.header.fits,true,JSON.stringify({theme,font,unit,state,value}));
      assert.equal(new Set(value.header.parts.map(p=>p.size)).size,1,'shared header type size');
      assert.equal(new Set(value.header.parts.map(p=>p.font)).size,1,'shared header font');
      assert.equal(new Set(value.header.parts.map(p=>p.lineHeight)).size,1,'shared line height');
      const centers=value.header.parts.map(p=>(p.lines[0].top+p.lines[0].bottom)/2);
      assert.ok(Math.max(...centers)-Math.min(...centers)<=1.5,JSON.stringify(value.header));
      if(theme==='classic' && color==='light' && font==='system-ui' && cost==='90 000')await capture();
      // Lower real openings must also contain the reference without requesting a resize.
      const reference=await evaluate(`(()=>{const v=miniWatch.view,children=[...v.dailyText.childNodes];v.dailyText.textContent='CCost Today 90 000 · 999 prompts';
        try{return (${inspectSource})(v);}finally{v.dailyText.replaceChildren(...children);}})()`);
      assert.equal(reference.fits,true,JSON.stringify({value,reference}));
      const narrower=await evaluate(`(()=>{const v=miniWatch.view,r=v.root,old=r.style.width;
        r.style.width=(${m.maximum}-2)+'px';
        const children=[...v.dailyText.childNodes];if(${JSON.stringify(m.widths[2].width>=m.widths[0].width)})v.dailyText.textContent='CCost Today 90 000 · 999 prompts';
        try{return (${inspectSource})(v);}finally{r.style.width=old;v.dailyText.replaceChildren(...children);}})()`);
      assert.equal(narrower.fits,false,JSON.stringify({value,narrower}));
      assert.equal(narrower.documentOverflow,false);
      assert.ok(Math.abs(narrower.parts[0].lines[0].top-narrower.parts[1].lines[0].top)<=1.5,'actions stay grouped');
      assert.ok(narrower.parts[2].lines[0].top>=narrower.parts[1].lines[0].bottom,'whole readout uses the secondary row');
      layouts.push({case:'intrinsic-width',theme,color,font,unit,state,...value,narrower});
      if(cost==='90 000')await disclosure({evaluate,command,pip,read,layouts,label:{theme,color,font},required:m.maximum,capture});
      widths.push(value.request.width);
      await close();
    }
  }
  assert.ok(Math.max(...widths)-Math.min(...widths)>30,'snapshot/fonts must change the measured width');
  await evaluate(`window.probeFont='';miniWatch.measure.body.style.fontFamily='';ReportView.setUnit('credits');miniWatch.update(liveValue)`);
  await evaluate(`(async()=>applySettings(await api('/api/settings/theme',{theme:'default'})))()`);
  await evaluate(`(async()=>applySettings(await api('/api/settings/mini-size',{miniWatchSize:'default'})))()`);
  checks.push('56 header snapshots: light/dark themes, fonts, exact reference/lower/larger/locale Credits/USD/loading/unavailable; bounded 8px slack excluding measured gutter; achieved text-range fit, pointer active/hover and repeated Enter/Space disclosure; native clamps separately recorded');
}
module.exports=probe;
module.exports.inspect=inspect;
