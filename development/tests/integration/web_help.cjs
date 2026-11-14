// Deterministic event/clock contract; rendered-browser proof is a separate probe.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
class Node {
  constructor(doc, tag) { this.ownerDocument=doc;this.tag=tag;this.children=[];this.attributes={};this.events={};this.style={};this.textContent=''; }
  get isConnected() { return this===this.ownerDocument.body || !!this.parentNode?.isConnected; }
  append(node) {node.remove();this.children.push(node);node.parentNode=this;}
  remove() {if(this.parentNode)this.parentNode.children.splice(this.parentNode.children.indexOf(this),1);this.parentNode=null;}
  contains(node) {return this===node || this.children.some(child=>child.contains(node));}
  setAttribute(key,value) {this.attributes[key]=String(value);}
  getAttribute(key) {return this.attributes[key]??null;}
  removeAttribute(key) {delete this.attributes[key];}
  addEventListener(kind,fn) {(this.events[kind]||=[]).push(fn);}
  fire(kind,event={}) {
    if (kind==='pointerenter') this.hover=true;
    if (kind==='pointerleave') this.hover=false;
    for(const fn of this.events[kind]||[])fn({target:this,isTrusted:true,pointerType:'mouse',preventDefault(){},...event});
  }
  getBoundingClientRect() {return {left:20,top:20,bottom:40,width:100,height:20};}
  showPopover() {this.open=true;}
  hidePopover() {this.open=false;}
  matches(selector) {return selector===':hover'?!!this.hover:selector===':popover-open'&&this.open;}
  focus() {this.ownerDocument.activeElement=this;this.ownerDocument.fire('focusin',{target:this});this.fire('focus');}
  blur() {this.ownerDocument.activeElement=null;this.fire('blur');}
}
function document() {
  const doc={events:{},visibilityState:'visible',addEventListener:Node.prototype.addEventListener,fire:Node.prototype.fire,
    createElement(tag){return new Node(doc,tag);}};
  const timers=new Map();let sequence=0,now=0;
  doc.defaultView={innerWidth:560,innerHeight:250,performance:{now:()=>now},events:{},addEventListener:Node.prototype.addEventListener,fire:Node.prototype.fire,
    setTimeout(fn,delay){timers.set(++sequence,{fn,at:now+delay});return sequence;},clearTimeout(id){timers.delete(id);}};
  doc.tick=ms=>{const end=now+ms;while(true){const next=[...timers].sort((a,b)=>a[1].at-b[1].at)[0];
    if(!next||next[1].at>end)break;now=next[1].at;timers.delete(next[0]);next[1].fn();}now=end;};
  doc.flush=()=>doc.tick(600);
  doc.timerCount=()=>timers.size;doc.callbacks=()=>[...timers.values()].map(value=>value.fn);
  doc.body=doc.createElement('body');return doc;
}
const main=document(),mini=document(),context=vm.createContext({document:main,window:main.defaultView,mini});
vm.runInContext(fs.readFileSync('src/web/assets/help.js','utf8'),context);
const help=vm.runInContext('ContextHelp',context);
let value='First line\n\nN/A — Unknown, not zero.';
const first=help.button('CCost',()=>value),second=help.button('Other','Other explanation');
first.setAttribute('aria-describedby','existing-status');main.body.append(first);main.body.append(second);
first.focus();const panel=main.body.children.at(-1);
assert.equal(panel.textContent,value);assert.equal(panel.getAttribute('role'),'tooltip');assert.equal(panel.getAttribute('popover'),'manual');
assert.equal(first.getAttribute('aria-describedby'),'existing-status context-help');
main.fire('keydown',{key:'Escape'});
assert.equal(panel.hidden,true);assert.equal(main.activeElement,first);assert.equal(first.getAttribute('aria-describedby'),'existing-status');
value='Updated USD value';help.attach(first,()=>value,true);help.refresh(first);first.fire('pointerenter');
assert.equal(panel.hidden,true,'updates and stationary focus do not reopen Escape-dismissed help');
first.blur();first.fire('pointerleave');main.flush();first.fire('pointerenter');
assert.equal(panel.hidden,true);main.tick(599);assert.equal(panel.hidden,true);main.tick(1);
assert.equal(panel.textContent,value);assert.equal(panel.open,true);
first.fire('pointerleave');panel.fire('pointerenter');main.flush();assert.equal(panel.open,true,'pointer transfer');
panel.fire('pointerleave');main.flush();assert.equal(panel.hidden,true,'unfocused exit closes');
first.fire('click');assert.equal(panel.open,true);first.fire('pointerleave');main.flush();assert.equal(panel.open,true,'tap pins');
first.fire('click');assert.equal(panel.hidden,true,'repeat tap closes');
main.fire('keydown',{key:'Tab'});second.focus();assert.equal(panel.textContent,'Other explanation');assert.equal(first.getAttribute('aria-describedby'),'existing-status');
assert.equal(main.body.children.filter(node=>node.getAttribute('role')==='tooltip').length,1,'one surface per document');
main.fire('pointerdown',{target:main.body});assert.equal(panel.hidden,true,'outside tap closes');
const action=main.createElement('button');let clicks=0;action.addEventListener('click',()=>clicks++);main.body.append(action);
help.attach(action,'Sort help');action.fire('pointerenter');main.tick(600);assert.equal(panel.textContent,'Sort help');
action.fire('click');assert.equal(clicks,1);assert.equal(panel.hidden,true,'actions dismiss rather than pin');
help.refresh(action);action.fire('focus');main.defaultView.fire('focus');assert.equal(panel.hidden,true,'stationary focus and rerenders cannot reopen action help');
action.fire('pointerleave');action.fire('pointerenter');main.tick(600);assert.equal(panel.hidden,false,'new hover rearms action help');
main.fire('pointerdown',{target:action});action.focus();action.fire('pointerleave');main.flush();
assert.equal(panel.hidden,true,'mouse-owned focus cannot strand hover help');assert.equal(main.activeElement,action);
action.fire('pointerenter');main.fire('pointerout',{relatedTarget:null});main.flush();assert.equal(panel.hidden,true,'missed trigger leave closes at document boundary');
action.fire('pointerenter');main.tick(600);main.fire('pointermove',{target:main.body});main.fire('pointermove',{target:main.body});
assert.equal(main.timerCount(),2,'one watchdog and one bounded exit, never renewed by outside movement');main.flush();assert.equal(panel.hidden,true);
action.fire('pointerenter');main.defaultView.fire('blur');assert.equal(panel.hidden,true,'window exit dismisses hover');assert.equal(main.timerCount(),0);
action.blur();main.fire('keydown',{key:'Tab'});action.focus();action.fire('pointerleave');main.fire('pointerout',{relatedTarget:null});main.flush();
assert.equal(panel.hidden,false,'keyboard ownership survives unrelated pointer exit');
action.fire('click');assert.equal(panel.hidden,true);action.blur();action.focus();assert.equal(panel.hidden,false,'new intentional focus rearms help');
action.blur();first.fire('click');main.fire('pointerout',{relatedTarget:null});main.defaultView.fire('blur');main.flush();
assert.equal(panel.hidden,false,'passive pinned help survives hover/window exit');
main.visibilityState='hidden';main.fire('visibilitychange');assert.equal(panel.hidden,true);main.visibilityState='visible';
const child=help.button('Ctx','Mini context',mini);mini.body.append(child);child.focus();const childPanel=mini.body.children.at(-1);
assert.notEqual(childPanel,panel);assert.equal(childPanel.textContent,'Mini context');
assert.equal(child.ownerDocument,mini);assert.equal(mini.activeElement,child);
second.focus();second.remove();help.refresh(main.body);assert.equal(panel.hidden,true,'removed trigger closes without reopening');
action.fire('pointerenter');action.fire('pointerleave');main.defaultView.fire('pagehide');main.flush();
assert.equal(panel.hidden,true);assert.equal(main.timerCount(),0,'teardown cancels pending exits');
action.fire('pointerleave');action.fire('pointerenter');main.tick(300);help.dismiss(action);main.tick(600);
assert.equal(panel.hidden,true,'disabling a settings subtree cancels its pending help');
action.fire('pointerleave');action.fire('pointerenter');main.tick(600);help.dismiss(second);
assert.equal(panel.hidden,false,'unrelated subtree does not dismiss active help');
help.dismiss(main.body);assert.equal(panel.hidden,true,'save closes help without stealing focus');
const sort=main.createElement('button');sort.textContent='Model';main.body.append(sort);
const label=help.heading(sort,'Sort models');let sorts=0;sort.addEventListener('click',()=>sorts++);
sort.fire('pointerenter');main.fire('pointermove',{target:sort});
assert.equal(panel.hidden,true,'action padding is not a help target');
label.fire('pointerenter');main.tick(600);assert.equal(panel.textContent,'Sort models');
label.fire('pointerleave');main.fire('pointermove',{target:sort});main.flush();
assert.equal(panel.hidden,true,'text to same-action whitespace closes hover help');
label.fire('pointerenter');main.tick(600);main.fire('pointermove',{target:sort});main.fire('pointermove',{target:sort});
assert.equal(main.timerCount(),2,'missed text leave still gets one watchdog and one bounded exit');main.flush();
assert.equal(panel.hidden,true);
main.fire('keydown',{key:'Tab'});sort.focus();main.fire('pointermove',{target:sort});main.flush();
assert.equal(panel.hidden,false,'keyboard help belongs to the actual action');
assert.equal(sort.getAttribute('aria-describedby'),'context-help');
assert.equal(label.getAttribute('aria-describedby'),null,'nonfocusable label does not steal ARIA description');
sort.fire('click');assert.equal(sorts,1);assert.equal(panel.hidden,true,'normal sort action preserved');
sort.blur();label.fire('pointerleave');label.fire('pointerenter');main.tick(600);panel.fire('pointerenter');main.flush();
assert.equal(panel.hidden,false,'text-only action still transfers to panel');
main.defaultView.fire('pagehide');
// Opening and closing clocks are independent; a flyover never gets a popup.
main.body.append(second);
first.fire('pointerenter');main.tick(400);first.fire('pointerleave');main.tick(600);
assert.equal(panel.hidden,true);assert.equal(main.timerCount(),0);
first.fire('pointerenter');main.tick(400);second.fire('pointerenter');main.tick(200);
assert.equal(panel.hidden,true,'changing targets starts a fresh delay');main.tick(400);
assert.equal(panel.textContent,'Other explanation');assert.equal(panel.hidden,false);
second.fire('pointerleave');main.tick(150);
first.fire('pointerenter');main.tick(400);main.fire('pointerout',{relatedTarget:null});main.tick(600);
assert.equal(panel.hidden,true,'document exit cancels pending opening');
first.fire('pointerenter');main.defaultView.fire('blur');main.tick(600);assert.equal(panel.hidden,true);
first.fire('pointerenter');first.remove();main.tick(600);assert.equal(panel.hidden,true,'removed pending target cannot open');
child.blur();child.fire('pointerenter');mini.tick(599);assert.equal(childPanel.hidden,true);mini.tick(1);
assert.equal(childPanel.hidden,false,'separate document shares the 600ms policy');
const metric=help.value(main.createElement('span'),'Exact metric facts');metric.textContent='12';main.body.append(metric);
main.fire('keydown',{key:'Tab'});metric.focus();assert.equal(panel.hidden,false,'passive text focus opens promptly');
assert.equal(metric.tabIndex,0);assert.match(metric.className,/help-value/);
metric.fire('keydown',{key:'Escape'});main.fire('keydown',{key:'Escape'});metric.fire('click');
assert.equal(panel.hidden,false,'explicit text tap opens promptly');
panel.currentCSSZoom=1.5;help.refresh(metric);
assert.equal(panel.style.left,(20/1.5)+'px','viewport coordinates convert to zoomed CSS coordinates');
assert.equal(panel.style.maxWidth,'min(34rem, '+(544/1.5)+'px)');
assert.equal(panel.style.maxHeight,(234/1.5)+'px','long help remains scrollable within the zoomed viewport');
// No event reaches the controller after opening: browser hover truth alone changes.
help.dismiss(main.body);main.body.append(first);first.fire('pointerleave');first.fire('pointerenter');main.tick(600);
assert.equal(main.timerCount(),1,'only one active hover watchdog');
first.hover=false;panel.hover=false;
main.tick(1000);assert.equal(panel.hidden,false,'watchdog preserves the transfer grace');main.tick(150);
assert.equal(panel.hidden,true);assert.equal(panel.open,false);assert.equal(main.timerCount(),0);
assert.equal(first.getAttribute('aria-describedby'),'existing-status','watchdog restores prior ARIA');
help.refresh(first);main.tick(5000);assert.equal(panel.hidden,true,'refresh cannot resurrect an expired hover');
first.fire('pointerenter');main.tick(300);first.hover=false;main.tick(300);
assert.equal(panel.hidden,true,'silent exit during opening is revalidated');assert.equal(main.timerCount(),0);
// A confirmed stationary hover survives refresh without an input-idle cutoff.
first.fire('pointerenter');main.tick(600);
first.focus();assert.equal(main.timerCount(),1,'pointer-owned focus does not claim keyboard ownership');
for(let i=0;i<120;i++) {
  help.attach(first,()=>value,true);help.refresh(main.body);main.fire('pointermove',{target:first,isTrusted:false});main.tick(1000);
  assert.equal(panel.hidden,false,'stationary reading survives beyond 30/60/90 seconds');
  assert.equal(main.timerCount(),1,'Live redraw and synthetic motion cannot accumulate watchdogs');
}
main.fire('pointerout',{relatedTarget:null});main.tick(150);
assert.equal(panel.hidden,true,'a browser exit still retires even stale positive hover');
assert.equal(main.timerCount(),0);first.blur();
const matches=first.matches;first.matches=selector=>selector===':hover'?undefined:matches.call(first,selector);
first.fire('pointerenter');main.tick(600);assert.equal(panel.hidden,false,'inconclusive hover still allows bounded help');
main.tick(30000);assert.equal(panel.hidden,true,'unsupported hover querying cannot retain help indefinitely');
assert.equal(main.timerCount(),0);first.matches=matches;
// Actual pointer presence renews; polling/CSS/focus did not. Panel transfer counts too.
first.fire('pointerenter');main.tick(600);
for(let i=0;i<4;i++){main.tick(10000);main.fire('pointermove',{target:first});}
assert.equal(panel.hidden,false,'genuine input keeps long reading usable');
first.fire('pointerleave');main.tick(100);panel.fire('pointerenter');main.tick(2000);
assert.equal(panel.hidden,false,'panel presence survives watchdog and trigger-panel gap');
main.tick(90000);assert.equal(panel.hidden,false,'intentional stationary popup reading has no idle cutoff');
panel.hover=false;main.tick(1150);assert.equal(panel.hidden,true);assert.equal(main.timerCount(),0);
// Native CSS may remain positive after layout moves away from the remembered
// input point. A real hit-test contradiction is actionable, null is not.
main.elementFromPoint=()=>null;first.fire('pointerenter',{clientX:25,clientY:25});main.tick(600);
main.tick(60000);assert.equal(panel.hidden,false,'null hit test is inconclusive, not departure');
main.elementFromPoint=()=>main.body;main.tick(1150);assert.equal(panel.hidden,true,'revealed occlusion retires help');
delete main.elementFromPoint;
// Exact label, not its surrounding action, owns the revalidation.
label.fire('pointerenter');main.tick(600);label.hover=false;sort.hover=true;main.tick(1150);
assert.equal(panel.hidden,true,'enclosing button hover is not label hover evidence');
// Timer tickets cannot affect a replacement target or a later re-entry.
first.fire('pointerenter');const oldOpening=main.callbacks()[0];main.tick(300);
second.fire('pointerenter');oldOpening();main.tick(600);
assert.equal(panel.textContent,'Other explanation');assert.equal(main.timerCount(),1);
const oldWatchdog=main.callbacks()[0];first.fire('pointerenter');main.tick(600);oldWatchdog();
assert.equal(panel.textContent,value);assert.equal(panel.hidden,false);assert.equal(main.timerCount(),1);
first.fire('pointerleave');main.tick(150);first.fire('pointerenter');main.tick(600);oldWatchdog();
assert.equal(panel.hidden,false,'old tick cannot close a re-entered target');assert.equal(main.timerCount(),1);
main.fire('keydown',{key:'Tab'});first.focus();
panel.fire('pointerenter');first.fire('pointerenter');
assert.equal(main.timerCount(),0,'transition to keyboard ownership immediately cancels watchdog');main.tick(60000);
assert.equal(panel.hidden,false,'focus help has no hover lease');first.blur();
first.fire('pointerenter');main.tick(600);first.fire('click');assert.equal(main.timerCount(),0);
main.tick(60000);assert.equal(panel.hidden,false,'explicit passive pin has no idle cap');
main.fire('keydown',{key:'Escape'});assert.equal(main.timerCount(),0);
// Document isolation, visibility/teardown, removed labels, and PiP-like reopen.
child.fire('pointerleave');child.fire('pointerenter');mini.tick(600);
first.fire('pointerleave');first.fire('pointerenter');main.tick(600);
assert.equal(main.timerCount(),1);assert.equal(mini.timerCount(),1);
mini.defaultView.fire('pagehide');assert.equal(mini.timerCount(),0);assert.equal(childPanel.hidden,true);
assert.equal(main.timerCount(),1,'closing PiP cannot cancel main document watchdog');
main.visibilityState='hidden';main.tick(1000);assert.equal(main.timerCount(),0);main.visibilityState='visible';
label.fire('pointerenter');main.tick(600);label.remove();main.tick(1000);
assert.equal(panel.hidden,true);assert.equal(main.timerCount(),0,'removed pointerTarget closes even if its action survives');
const reopened=document(),again=help.button('Mini again','New document',reopened);reopened.body.append(again);
again.fire('pointerenter');reopened.tick(600);assert.equal(reopened.timerCount(),1);
reopened.defaultView.closed=true;reopened.tick(1000);assert.equal(reopened.timerCount(),0);
assert.equal(reopened.body.children.at(-1).hidden,true);assert.equal(mini.timerCount(),0);
first.fire('pointerenter');main.tick(600);main.fire('keydown',{key:'Escape'});assert.equal(main.timerCount(),0);
action.fire('pointerenter');main.tick(600);action.fire('click');assert.equal(main.timerCount(),0,'action stops watchdog');
child.fire('pointerenter');mini.visibilityState='hidden';mini.fire('visibilitychange');assert.equal(mini.timerCount(),0);
console.log('shared Web/Mini help events passed');
