// Minimal existing VM DOM adaptation. Real interaction/layout proof is browser-owned.
const fs = require('node:fs');
module.exports = function loadHelp(vm, context) {
  const doc = context.document, sample = doc.createElement('div'), proto = Object.getPrototypeOf(sample);
  // VM nodes have no layout; a browser probe checks actual resize and scroll geometry.
  context.ResizeObserver ||= class { observe() {} disconnect() {} };
  if (!('classList' in sample)) Object.defineProperty(proto, 'classList', {get() {
    const toggle = (name, enabled) => {
      const names = new Set((this.className || '').split(' ').filter(Boolean));
      if (enabled) names.add(name); else names.delete(name); this.className = [...names].join(' ');
    };
    return {toggle, add: (...names) => names.forEach(name => toggle(name, true))};
  }});
  proto.getAttribute ||= function(name) { return this.attributes?.[name] ?? this[name] ?? null; };
  proto.removeAttribute ||= function(name) { if (this.attributes) delete this.attributes[name]; delete this[name]; };
  proto.getBoundingClientRect ||= () => ({left:20,top:20,bottom:40,width:100,height:20});
  proto.contains ||= function(node) { return this === node || this.children.some(child => child.contains(node)); };
  if (!Object.getOwnPropertyDescriptor(proto,'isConnected')) Object.defineProperty(proto,'isConnected',{get:()=>true});
  if (!proto.helpEventsInstalled) {
    // Browser append() converts literal separators/copy into text nodes.
    const append = proto.append;
    proto.append = function(...items) {
      return append.call(this, ...items.map(item => typeof item === 'string' ?
        Object.assign(new this.constructor('#text'), {textContent: item}) : item));
    };
    const add = proto.addEventListener || function(kind, callback) { (this.events ||= {})[kind] = callback; };
    proto.addEventListener = function(kind, callback) {
      const old = this.events?.[kind];
      add.call(this, kind, typeof old === 'function' ? event => { old(event); callback(event); } : callback);
    };
    proto.removeEventListener ||= function(kind, callback) {
      if (this.events?.[kind] === callback) delete this.events[kind];
    };
    proto.helpEventsInstalled = true;
  }
  const original = doc.createElement;
  doc.createElement = tag => { const node = original(tag); node.ownerDocument = doc; node.style ||= {setProperty() {}}; return node; };
  doc.body ||= doc.createElement('body');
  context.window ||= {}; context.window.clearTimeout ||= clearTimeout; context.window.setTimeout ||= setTimeout;
  context.window.addEventListener ||= () => {};
  context.window.matchMedia ||= () => ({addEventListener(){},removeEventListener(){}});
  vm.runInContext(fs.readFileSync('src/web/assets/help.js','utf8'), context);
  return target => {
    const focus = target.events?.focus || target.listeners?.focus;
    for (const callback of Array.isArray(focus) ? focus : [focus]) callback();
    return (target.ownerDocument || doc).body.children.at(-1).textContent;
  };
};
