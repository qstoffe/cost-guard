// Watch-only dashboard and shared compact subscriptions, over source-prepared DTOs.
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const pending = require('../fixtures/pending_value.cjs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) { this.tag=tag;this.children=[];this.text='';this.dataset={};this.attributes={};this.events={};this.style={setProperty(name,value){this[name]=value;}}; }
  set textContent(value) { this.text=String(value);this.children=[]; }
  get textContent() { return this.text+this.children.map(c=>c.textContent).join(''); }
  append(...items) { for(const item of items){item.remove();this.children.push(item);item.parentNode=this;} }
  replaceChildren(...items) { for(const child of this.children)child.parentNode=null;this.children=[];this.text='';this.append(...items); }
  insertBefore(child,before) { child.remove();this.children.splice(before?this.children.indexOf(before):this.children.length,0,child);child.parentNode=this; }
  remove() { if(this.parentNode)this.parentNode.children.splice(this.parentNode.children.indexOf(this),1);this.parentNode=null; }
  contains(node) { return node===this||this.children.some(c=>c.contains(node)); }
  querySelectorAll(tag) { return this.children.flatMap(c=>[...(c.tag===tag?[c]:[]),...c.querySelectorAll(tag)]); }
  setAttribute(name,value) { this.attributes[name]=value; }
  addEventListener(kind,handler) { this.events[kind]=handler; }
}
let now=1000;
class Clock extends Date { static now(){return now;} }
const controls=new Node('div'), toggle=new Node('button');controls.append(toggle);
const context=vm.createContext({document:{createElement:tag=>new Node(tag),
  createElementNS:(namespaceURI,tag)=>Object.assign(new Node(tag),{namespaceURI}),
  getElementById:id=>id==='mini-watch-controls'?controls:null},
  window:{addEventListener(){},matchMedia:()=>({addEventListener(){},removeEventListener(){}})},
  input,Date:Clock,parent:new Node('div'),console});
const helpText=require('../fixtures/web_help_vm.cjs')(vm,context);
for(const name of ['render','account-cards','watch'])vm.runInContext(fs.readFileSync(`src/web/assets/${name}.js`,'utf8'),context);
const render=()=>vm.runInContext('ReportView.renderLive(parent,input,state)',context);
vm.runInContext('globalThis.state={connection:"Live connected."}',context);render();
const watch=context.state.watch,card=[...watch.cards.values()][0],row=card.body.children[0];
assert.equal(watch.history,undefined);assert.equal(watch.earlier,undefined);
assert.equal(watch.cards.size,input.view.active_cards.length);
assert.equal(watch.root.children[0],watch.band);
assert.deepEqual(watch.band.children,[watch.daily,watch.accounts,controls]);
assert.equal(controls.children[0],toggle);
assert.equal(watch.root.children.at(-1),watch.active);
assert.equal(watch.accounts.className,'mini-accounts');
assert.equal(row.children[2].textContent,'#37'+input.view.active_cards[0].rows[0].prompt.preview);
assert.equal(row.attributes['aria-label'],'Prompt 37 · Running');
assert.equal(card.title.className,'watch-running-title');
const headers=card.root.querySelectorAll('th');
assert.equal(helpText(headers[1].children[0]),'Time spent on this prompt.');
const definition = require('../fixtures/ccost_definition.cjs');
definition(helpText(headers[5].children[0]), /this prompt.*linked subagent/);
assert.doesNotMatch(helpText(headers[7].children[0]),/N\/A or running|No reliable/);
assert.match(helpText(row.children[5].children[0]),/Session Models:\n• [\s\S]*Sub Agents:\n• /);
assert.doesNotMatch(helpText(row.children[5].children[0]),/Duration: N\/A/);
assert.doesNotMatch(helpText(row.children[5].children[0]),/Incoming Context CCost|Extra CCost|Total CCost/);
assert.match(helpText(row.children[6].children[0]),/fixture\/main-model \(High\): 2 calls/);
assert.match(helpText(row.children[6].children[0]),/fixture\/child-model \(Low\): 2 calls/);
assert.doesNotMatch(helpText(row.children[6].children[0]),/Subagent|Main prompt|Total Calls|prompts|tier/);
assert.deepEqual(watch.daily.children.map(n=>n.textContent),['CCost Today','34','37 prompts']);
definition(helpText(watch.daily.children[0]), /local calendar day/);
for(const node of watch.daily.children.slice(1))assert.equal(node.events.focus,undefined);
// Exact shared compact list, including quota modes, unit changes and edge cases.
vm.runInContext('globalThis.compact=new AccountCards.CompactView();compact.update(input.view)',context);
assert.equal(watch.accounts.textContent,context.compact.root.textContent);
assert.deepEqual(watch.accounts.children.map(line=>line.helpText),context.compact.root.children.map(line=>line.helpText));
const monthly=structuredClone(input.view.accounts.accounts[0]);
const capacitySample=structuredClone(input.view.accounts.accounts[1]);
for(const fixture of input.quota_cases||[]) {
  input.view.accounts.accounts=[{...monthly,primary:fixture.value,secondary:[],
    observation:{...monthly.observation,id:'case-'+fixture.name}}];
  render();
  const line=watch.accounts.children[0],bar=line.children[1];
  const capacity=fixture.value.quota.display.capacity_amount;
  const summary=`Capacity: ${capacity==='?'?'N/A':capacity}\nNext reset: ${fixture.value.display.mini_reset}`;
  const help=helpText(line.children[0].children[0]);
  assert.equal(help.split('\n\n')[0],summary);
  if (!fixture.value.quota.ccost_pace) assert.equal(help,summary);
  assert.equal(bar.hidden,fixture.value.used_fraction==null||fixture.value.quota.unlimited);
  assert.equal(line.children[0].querySelectorAll('button').length,0);
  assert.ok(line.textContent.includes(fixture.value.quota.unlimited?'Unlimited':
    fixture.percent==='—'?'Usage unavailable':fixture.percent+' used'),fixture.name);
  vm.runInContext('ReportView.setQuotaMode("remaining");ReportView.syncUnits(parent)',context);
  const shown=fixture.value.quota.quota_display.remaining;
  if(shown.mode==='remaining') {
    assert.match(line.textContent,/remaining/);
    assert.equal(Number(bar.value),Number(shown.fraction));
  }
  vm.runInContext('ReportView.setQuotaMode("used");ReportView.setUnit("credits",parent)',context);
}
// Pending token mix retains only within one source/epoch/prompt; corrections clear.
const live=input.view.active_cards[0],prompt=live.rows[0].prompt;
prompt.token_mix_percent=null;prompt.display.token_mix_percent='running';render();
pending(row.children[7].children[0],'token mix');
prompt.token_mix_percent=[10,20,30,40];prompt.display.token_mix_percent='10/20/30/40';render();
const cells=[...row.children];live.state='partial';prompt.token_mix_percent=null;prompt.display.token_mix_percent='running';render();
assert.equal(row.children[7].textContent,'10/20/30/40');
assert.ok(cells.every((cell,i)=>cell===row.children[i]));
prompt.token_mix_percent=[20,20,20,40];prompt.display.token_mix_percent='20/20/20/40';render();
assert.equal(row.children[7].textContent,'20/20/20/40');
live.session_summary.context={...live.session_summary.context,context_scope:'another-source'};
prompt.token_mix_percent=null;render();const pendingMix=pending(row.children[7].children[0],'token mix');
live.state='observed';render();assert.equal(pending(row.children[7].children[0],'token mix'),pendingMix);
// Terminal rows leave Watch, without modifying the independent Mini history DTOs.
const history=JSON.stringify(input.view.history_cards);
prompt.in_progress=false;render();assert.equal(watch.cards.size,0);
assert.equal(JSON.stringify(input.view.history_cards),history);
prompt.in_progress=true;render();
// The one existing control survives detachment and another Watch view.
context.parent.replaceChildren(new Node('div'));
vm.runInContext('globalThis.reopened=new WatchView.View({miniControls:state.miniControls||document.getElementById("mini-watch-controls")});reopened.attach(parent)',context);
assert.equal(context.reopened.band.children.at(-1),controls);
assert.equal(controls.children[0],toggle);
// Accounts route still uses full native cards, capacity, reset, pace and details.
context.shared={...input.view,accounts:{accounts:[monthly]},quota_stale:false,quota_recovering_count:0};
vm.runInContext('globalThis.accountsPage=new AccountCards.View(true)',context);
const page=context.accountsPage;assert.equal(page.root.textContent,'Loading…');
vm.runInContext('accountsPage.update(shared)',context);
const account=page.grid.children[0],label=account.children[2];
assert.equal(label.textContent,'Monthly · 8.4% used (2088)');
assert.equal(account.children[3].textContent,'Monthly Capacity: 25000');
assert.match(account.textContent,/Reset/);
context.shared.accounts.accounts[0].primary.display.watch_reset='Reset in 15m';
vm.runInContext('accountsPage.update(shared)',context);
assert.equal(page.grid.children[0],account);assert.equal(account.children[2],label);
assert.match(account.textContent,/Reset in 15m/);
vm.runInContext('ReportView.setQuotaMode("remaining");ReportView.setUnit("usd",accountsPage.root)',context);
assert.match(label.textContent,/remaining.*\$/);
vm.runInContext('ReportView.setQuotaMode("used");ReportView.setUnit("credits",accountsPage.root)',context);
require('../fixtures/account_links.cjs')(vm,context,monthly);
require('../fixtures/account_today.cjs')(vm,context,monthly,helpText);
require('../fixtures/account_capacity.cjs')(vm,context,capacitySample,helpText);
require('../fixtures/ccost_refresh.cjs')(vm,context);
require('../fixtures/live_status.cjs')(vm,context,value=>value===undefined?now:(now=value));
require('../fixtures/watch_refresh.cjs')(vm,context);
console.log('watch summary passed');
