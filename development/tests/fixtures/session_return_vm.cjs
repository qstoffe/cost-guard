'use strict';
// Execute the shipped route controller; no replacement implementation in this test.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const app = fs.readFileSync('src/web/assets/app.js', 'utf8');
const nav = ['sessions','watch','accounts','ai-stats'].map(name => ({
  attributes: {href:'#/'+name}, getAttribute(key) {return this.attributes[key];},
  setAttribute(key,value) {this.attributes[key]=value;}, removeAttribute(key) {delete this.attributes[key];}
}));
const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id,{textContent:'',value:'',disabled:false});
  return elements.get(id);
};
const context = vm.createContext({
  location:{hash:'#/sessions'}, history:{replaceState(){}}, document:{
    title:'',body:{dataset:{}},activeElement:null,getElementById:element,querySelectorAll:()=>nav
  },sessionsNav:nav[0],rememberedSession:null,views:new Map(),current:null,heading:element('heading'),
  csrf:'synthetic',hostState:{terminal:false},sessionDetailAvailable:true,output:{},demand:null,
  show(){},enterCachedReport(){},scheduleCachedReport(){},firstReport(){},focusReport(){},
  window:{scrollY:250,scrollTo(){}},api(){},
  SessionDetail:{View:class {
    constructor(_,id){this.id=id;this.root={contains:()=>false};this.detaches=0;}
    detach(){this.detaches++;}
  }},
  SessionsCatalog:{View:class {configure(){} detach(){}}},
  settingsView:{read(){}},URLSearchParams
});
vm.runInContext(fs.readFileSync('src/web/assets/reports.js','utf8'),context);
const start=app.indexOf('function navigate() {'), end=app.indexOf('\nasync function connect()',start);
vm.runInContext(app.slice(start,end),context);
vm.runInContext('ReportRoutes.controls = () => {}',context); // Controls are outside this test's route seam.
const route = hash => {context.location.hash=hash;context.navigate();};
route('#/sessions');
assert.equal(nav[0].attributes.href,'#/sessions');
route('#/sessions/detail-A');const first=context.current.detail;
assert.equal(nav[0].attributes.href,'#/sessions/detail-A');
assert.equal(nav[0].attributes['aria-current'],'page');
for (const page of ['accounts','watch','ai-stats']) {
  route('#/'+page);assert.equal(nav[0].attributes['aria-current'],undefined);
  route(nav[0].attributes.href);
  assert.equal(context.current.detail,first,'return reuses one bounded detail view');
}
assert.equal(first.detaches,3);
route('#/sessions/detail-B');
assert.equal(nav[0].attributes.href,'#/sessions/detail-B');
route('#/sessions'); // Show all sessions, direct URL and Back to a catalog all use this route.
assert.equal(context.rememberedSession,null);
assert.equal(nav[0].attributes.href,'#/sessions');
route('#/watch');route(nav[0].attributes.href);
assert.ok(context.current.catalog);
route('#/sessions/detail-A'); // Forward/deep-link is honored, not redirected by memory.
assert.equal(context.current.detail,first);
console.log('PASS shipped route memory, list clearing, deep-link/history, aria-current and lease detach');
