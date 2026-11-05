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
  fire(kind,event={}) {for(const fn of this.events[kind]||[])fn({target:this,preventDefault(){},...event});}
  getBoundingClientRect() {return {left:20,top:20,bottom:40,width:100,height:20};}
  showPopover() {this.open=true;}
  hidePopover() {this.open=false;}
  matches(selector) {return selector===':popover-open'&&this.open;}
  focus() {this.ownerDocument.activeElement=this;this.ownerDocument.fire('focusin',{target:this});this.fire('focus');}
  blur() {this.ownerDocument.activeElement=null;this.fire('blur');}
}
function document() {
  const doc={events:{},addEventListener:Node.prototype.addEventListener,fire:Node.prototype.fire,
    createElement(tag){return new Node(doc,tag);}};
  const timers=new Map();let sequence=0;
  doc.defaultView={innerWidth:560,innerHeight:250,events:{},addEventListener:Node.prototype.addEventListener,fire:Node.prototype.fire,
    setTimeout(fn){timers.set(++sequence,fn);return sequence;},clearTimeout(id){timers.delete(id);}};
  doc.flush=()=>{for(const [id,fn]of [...timers]){timers.delete(id);fn();}};
  doc.timerCount=()=>timers.size;doc.body=doc.createElement('body');return doc;
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
assert.equal(panel.textContent,value);assert.equal(panel.open,true);
first.fire('pointerleave');panel.fire('pointerenter');main.flush();assert.equal(panel.open,true,'pointer transfer');
panel.fire('pointerleave');main.flush();assert.equal(panel.hidden,true,'unfocused exit closes');
first.fire('click');assert.equal(panel.open,true);first.fire('pointerleave');main.flush();assert.equal(panel.open,true,'tap pins');
first.fire('click');assert.equal(panel.hidden,true,'repeat tap closes');
second.focus();assert.equal(panel.textContent,'Other explanation');assert.equal(first.getAttribute('aria-describedby'),'existing-status');
assert.equal(main.body.children.filter(node=>node.getAttribute('role')==='tooltip').length,1,'one surface per document');
main.fire('pointerdown',{target:main.body});assert.equal(panel.hidden,true,'outside tap closes');
const action=main.createElement('button');let clicks=0;action.addEventListener('click',()=>clicks++);main.body.append(action);
help.attach(action,'Sort help');action.fire('pointerenter');assert.equal(panel.textContent,'Sort help');
action.fire('click');assert.equal(clicks,1);assert.equal(panel.hidden,true,'actions dismiss rather than pin');
help.refresh(action);action.fire('focus');main.defaultView.fire('focus');assert.equal(panel.hidden,true,'stationary focus and rerenders cannot reopen action help');
action.fire('pointerleave');action.fire('pointerenter');assert.equal(panel.hidden,false,'new hover rearms action help');
main.fire('pointerdown',{target:action});action.focus();action.fire('pointerleave');main.flush();
assert.equal(panel.hidden,true,'mouse-owned focus cannot strand hover help');assert.equal(main.activeElement,action);
action.fire('pointerenter');main.fire('pointerout',{relatedTarget:null});main.flush();assert.equal(panel.hidden,true,'missed trigger leave closes at document boundary');
action.fire('pointerenter');main.fire('pointermove',{target:main.body});main.fire('pointermove',{target:main.body});
assert.equal(main.timerCount(),1,'repeated outside movement cannot defer the bounded exit');main.flush();assert.equal(panel.hidden,true);
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
console.log('shared Web/Mini help events passed');
