// Deterministic event/lifetime contract; native CSS/focus is checked by browser probes.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Doc extends EventTarget {
  constructor() { super();this.body={};this.activeElement=this.body; }
  emit(type,target,properties={}) { const event=new Event(type);Object.defineProperty(event,'target',{value:target});
    Object.assign(event,properties);this.dispatchEvent(event); }
}
const document=new Doc(),pip=new Doc();
const context=vm.createContext({document});
const focus=vm.runInContext(fs.readFileSync('src/web/assets/control-focus.js','utf8')+'\nControlFocus',context);
function node(doc) {
  return {ownerDocument:doc,attrs:new Set(),isConnected:true,disabled:false,
    closest(){return this;},setAttribute(key){this.attrs.add(key);},removeAttribute(key){this.attrs.delete(key);},
    focus(){doc.activeElement=this;doc.emit('focusin',this);}};
}
const button=node(document),other=node(document),mini=node(pip);
focus.install(document);focus.install(pip);button.focus();
document.emit('pointerdown',button);
assert.equal(focus.keyboard(document),false);
assert.equal(button.attrs.has('data-pointer-focus'),true,'same focused element is marked without needing focusin');
assert.equal(focus.keyboard(pip),true,'documents do not share modality');
document.emit('keydown',button,{key:'Shift'});
assert.equal(button.attrs.has('data-pointer-focus'),true,'modifier alone is not keyboard navigation');
document.emit('keydown',button,{key:'Tab'});
assert.equal(button.attrs.size,0);
const restore=focus.retain(button);document.activeElement=document.body;restore();
assert.equal(document.activeElement,button,'disabled keyboard control can regain focus');
const cancelled=focus.retain(button);other.focus();document.activeElement=document.body;cancelled();
assert.equal(document.activeElement,document.body,'completion never steals deliberately moved focus');
document.emit('pointerdown',button);button.focus();
const pointer=focus.retain(button);document.activeElement=document.body;pointer();
assert.equal(document.activeElement,document.body,'no synthetic pointer refocus');
pip.emit('pointerdown',mini);mini.focus();
assert.equal(mini.attrs.has('data-pointer-focus'),true);
pip.emit('keydown',mini,{key:'Enter'});
assert.equal(mini.attrs.size,0,'keyboard activation restores PiP indicator');
console.log('PASS: per-document modality, same-node pointer ownership, keyboard-only restoration and no focus theft');
