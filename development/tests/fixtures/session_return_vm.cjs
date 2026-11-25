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
  location:{hash:'#/sessions'}, history:{state:null,replaceState(){},
    pushState(state,_,hash){this.state=state;context.location.hash=hash;}}, document:{
    title:'',body:{dataset:{}},activeElement:null,getElementById:element,querySelectorAll:()=>nav
  },sessionsNav:nav[0],rememberedSession:null,views:new Map(),current:null,heading:element('heading'),
  csrf:'synthetic',archiveHistory:true,hostState:{terminal:false},historyBlocked:()=>false,sessionDetailAvailable:true,
  output:{addEventListener(_,handler){this.click=handler;}},demand:null,
  show(){},enterCachedReport(){},scheduleCachedReport(){},firstReport(){},focusReport(){},
  window:{scrollY:250,scrollTo(){}},api(){},
  SessionDetail:{View:class {
    constructor(_,id){this.id=id;this.root={contains:()=>false};this.back={href:'#/sessions'};this.detaches=0;}
    detach(){this.detaches++;}
  }},
  SessionsCatalog:{View:class {configure(){} detach(){} sourceHealth(){}}},
  settingsView:{read(){}},URLSearchParams
});
vm.runInContext(fs.readFileSync('src/web/assets/reports.js','utf8'),context);
const start=app.indexOf('function navigate() {'), end=app.indexOf('\nasync function connect()',start);
vm.runInContext(app.slice(start,end),context);
vm.runInContext('ReportRoutes.controls = () => {}',context); // Controls are outside this test's route seam.
const route = (hash, state=null) => {context.history.state=state;context.location.hash=hash;context.navigate();};
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
const clickStart=app.indexOf("output.addEventListener('click',");
vm.runInContext(app.slice(clickStart,app.indexOf("\nwindow.addEventListener('hashchange'",clickStart)),context);
route('#/sessions?period=all&sort=name&direction=1&offset=25&epoch=old');
context.current.catalog.firstPageDestination=()=>'#/sessions?period=all&sort=name&direction=1';
const link={getAttribute:()=> '#/sessions/detail-A',hasAttribute:()=>false};
const click = changes => {
  let prevented=false;
  context.output.click({target:{closest:()=>link},button:0,preventDefault(){prevented=true;},...changes});
  return prevented;
};
for(const modifiers of [{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true},{button:1},{defaultPrevented:true}]) {
  assert.equal(click(modifiers),false,'native modified/new-tab activation remains native');
  assert.equal(context.current.section,'sessions');
  assert.equal(context.history.state,null);
}
assert.equal(click(),true);
assert.equal(context.current.detail,first);
assert.equal(first.back.href,'#/sessions?period=all&sort=name&direction=1');
const origin=context.history.state;
context.navigate(); // Same entry, including a repeated connection/route notification.
assert.equal(first.back.href,origin.sessionsReturn.list);
route('#/sessions/detail-B',origin);
assert.equal(context.current.detail.back.href,'#/sessions','history context is bound to its exact detail');
route('#/sessions/detail-A');
assert.equal(first.back.href,'#/sessions','cached detail from Watch/deep link cannot leak earlier filters');
route('#/sessions/detail-A',origin);
assert.equal(first.back.href,origin.sessionsReturn.list,'Back/Forward restores per-entry context');
console.log('PASS shipped route memory, list clearing, origin isolation, native modified links, per-entry filters and lease detach');
