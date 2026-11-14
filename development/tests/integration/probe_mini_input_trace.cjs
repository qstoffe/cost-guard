// Diagnostic-only native selector pass-through; never changes a selector result.
module.exports=async ({evaluate,control=false})=>{
  await evaluate(`(()=>{
    const cell=miniWatch.view.body.parentNode.tHead.rows[0].cells[3];
    if(${control})cell.replaceChildren(cell.firstChild.cloneNode(true));
    const target=cell.firstChild,native=target.matches,events=[];
    let arrival;
    const record=(kind,details={})=>{
      if(events.length===100)events.shift();
      events.push({kind,elapsed:arrival?performance.now()-arrival.at:null,
        same:cell.firstChild===target,connected:target.isConnected,
        focus:target.ownerDocument.hasFocus(),active:target.ownerDocument.activeElement===target,...details});
    };
    target.matches=function(query){
      const result=native.call(this,query);
      if(query===':hover'){
        const stack=new Error().stack;
        record('selector',{result,guard:stack.includes('at hovered')&&!stack.includes('at hoverState')});
      }
      return result;
    };
    const event=e=>{
      if(e.pointerType==='mouse'&&target.contains(e.target)&&
          ['pointerenter','pointermove'].includes(e.type))arrival={at:performance.now(),x:e.clientX,y:e.clientY};
      record(e.type,{trusted:e.isTrusted,mouse:e.pointerType==='mouse',
        onTarget:target.contains(e.target),related:!!e.relatedTarget});
    };
    const types=['pointerenter','pointermove','pointerleave','pointerout','pointerdown','focus','blur'];
    for(const type of types)target.ownerDocument.addEventListener(type,event,true);
    const win=target.ownerDocument.defaultView;
    win.addEventListener('blur',event,true);
    window.durationInputTrace={target,events,read(){
      // Native selector is observed before any diagnostic layout/hit-test read.
      const hovered=native.call(target,':hover'),panel=target.ownerDocument.getElementById('context-help');
      const result={hovered,events:events.slice(),same:cell.firstChild===target,connected:target.isConnected,
        focus:target.ownerDocument.hasFocus(),active:target.ownerDocument.activeElement===target,
        open:!!panel?.matches(':popover-open')};
      if(arrival){const r=target.getBoundingClientRect();
        result.hit=target.contains(target.ownerDocument.elementFromPoint(arrival.x,arrival.y));
        result.bounds=[r.x,r.y,r.width,r.height];}
      return result;
    },restore(){
      delete target.matches;
      for(const type of types)target.ownerDocument.removeEventListener(type,event,true);
      win.removeEventListener('blur',event,true);
    }};
  })()`);
};
