// Pure DOM VM regression; no browser process, dependencies or source access.
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ''; this.dataset = {}; this.attributes = {}; this.events = {}; this.style = {setProperty(name, value) {this[name] = value;}}; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(''); }
  append(...items) { for (const item of items) { item.remove(); this.children.push(item); item.parentNode = this; } }
  replaceChildren(...items) { for (const child of this.children) child.parentNode = null; this.children = []; this.text = ''; this.append(...items); }
  insertBefore(child, before) { child.remove(); this.children.splice(before ? this.children.indexOf(before) : this.children.length, 0, child); child.parentNode = this; }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  contains(node) { return node === this || this.children.some(child => child.contains(node)); }
  querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(kind, handler) { this.events[kind] = handler; }
}
const media = [], windowEvents = {}, viewportEvents = {};
const window = {devicePixelRatio:1.5,visualViewport:{scale:1,addEventListener(kind, fn) {viewportEvents[kind]=fn;}},
  addEventListener(kind, fn) {windowEvents[kind]=fn;},matchMedia(query) {
    const value={query,addEventListener(kind,fn) {this.callback=fn;},removeEventListener() {this.callback=null;}};
    media.push(value);return value;
  }};
let now = 1000;
class Clock extends Date { static now() { return now; } }
const context = vm.createContext({document: {createElement: tag => new Node(tag),
  createElementNS: (namespaceURI, tag) => Object.assign(new Node(tag), {namespaceURI})}, window, console,
  input, Date: Clock, parent: new Node('div')});
const helpText = require('../fixtures/web_help_vm.cjs')(vm, context);
for (const name of ['render', 'account-cards', 'watch']) vm.runInContext(fs.readFileSync(`src/web/assets/${name}.js`, 'utf8'), context);
vm.runInContext("globalThis.state = {connection:'Live connected.'}; ReportView.renderLive(parent, input, state)", context);
const watch = context.state.watch, card = [...watch.cards.values()][0];
const primaryDetails = card => card.children.find(node => node.className === 'watch-primary-details');
const primaryTrack = card => card.children.find(node => node.className === 'watch-quota-track');
const footer = card => card.children.find(node => node.className === 'watch-account-footer');
assert.equal(watch.accounts.style['--watch-account-width'],'298px');
window.devicePixelRatio=1.875;
media.at(-1).callback();
assert.equal(watch.accounts.style['--watch-account-width'],'238px');
assert.equal(media[0].callback,null,'obsolete resolution listener is removed');
window.visualViewport.scale=1.25;viewportEvents.resize();
assert.equal(watch.accounts.style['--watch-account-width'],'191px','pinch factor applies once');
window.devicePixelRatio=1;window.visualViewport.scale=1;windowEvents.resize();
assert.equal(watch.accounts.style['--watch-account-width'],'448px');
const row = card.body.children[0], prompt = context.input.view.active_cards[0].rows[0].prompt;
assert.equal(card.body.children.length, 1);
assert.equal(row.children[0].textContent, prompt.display.clock);
assert.equal(row.children[2].textContent, '#37' + prompt.preview);
assert.equal(row.children[2].querySelectorAll('button').length,0,'no full-preview cue on running rows');
assert.equal(row.attributes['aria-label'], 'Prompt 37 · Running');
assert.equal(row.children[3].textContent, 'Model*');
assert.match(helpText(row.children[3].children[0]), /Linked subagents participated[\s\S]*fixture\/main-model[\s\S]*fixture\/child-model/);
assert.match(helpText(row.children[5].children[0]), /Main prompt — fixture\/main-model · High\n• Input: 8[\s\S]*Subagents — fixture\/child-model · Low \(2 agents\)[\s\S]*Subtotal: 8[\s\S]*Total CCost: 33/);
assert.match(helpText(row.children[6].children[0]), /Subagents — fixture\/child-model · Low \(2 agents\): 2\nTotal Calls: 4/);
assert.equal(row.children[7].children[0].events.focus, undefined, 'Token Mix remains header-only help');
assert.equal(card.title.className, 'watch-running-title');
assert.ok(!/Session Total|provisional|Loading/.test(card.root.textContent));
assert.equal(card.runningDetail.summary.textContent, 'Running: shell 41s');
assert.equal(card.backgroundDetail.summary.textContent, 'Running: subagent 55s');
assert.match(card.runningDetail.note.textContent, /Command not recorded in the current tool event/);
assert.match(card.backgroundDetail.note.textContent, /Original call links missing/);
const activityTool = context.input.view.active_cards[0].rows[0].tool;
const oldActivity = structuredClone(activityTool);
activityTool.background_kinds = ['shell', 'shell'];
activityTool.background_invocations = [1, 2].map(i => ({identity:'job-'+i,revision:'r1',kind:'shell',
  text:'command:\npython task'+i+'.py',qualification:'',mode:'background'}));
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.backgroundDetail.jobs.size, 2);
assert.match(card.background.textContent, /python task1\.py[\s\S]*python task2\.py/);
const backgroundJobs = [...card.backgroundDetail.jobs.values()];
card.background.open = true;
for (let i=0;i<4;i++) {
  activityTool.display.background_ms = (20+i)+'s';
  vm.runInContext('ReportView.renderLive(parent, input, state)', context);
  assert.equal(card.background.open, true);
  assert.equal(card.backgroundDetail.jobs.get('job-2'), backgroundJobs[1]);
}
activityTool.background_invocations[0].revision = 'corrected';
activityTool.background_invocations[0].text = 'command:\npython corrected.py';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(backgroundJobs[0].node.open, false);
assert.equal(backgroundJobs[1].node.open, true, 'unrelated job stays expanded');
context.input.view.active_cards[0].state = 'unavailable';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.backgroundDetail.jobs.size, 0);
assert.doesNotMatch(card.background.textContent, /python/);
assert.match(card.background.textContent, /Awaiting verified live source/);
context.input.view.active_cards[0].state = 'observed';
Object.assign(activityTool, oldActivity, {background_invocations:[]});
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.tools.summary.children.at(-1).className, 'watch-activity-error');
assert.match(card.tools.summary.children.at(-1).textContent, /1 failed/);
assert.equal(card.skills.summary.children.at(-1).className, 'watch-activity-error');
assert.equal(card.skills.list.children[0].children.at(-1).className, 'watch-activity-error');
const earlier = [...watch.cards.values()][1];
assert.equal(earlier.body.children[0].children[2].querySelectorAll('button').length,0,'no full-preview cue on earlier rows');
assert.equal(earlier.title.className, '');
assert.equal(earlier.body.children[0].children[0].textContent,
   context.input.view.history_cards[0].rows[0].prompt.display.finished_clock);
assert.equal(helpText(earlier.body.children[0].children[0].children[0]),
   context.input.view.history_cards[0].rows[0].prompt.display.finished_date_time);
assert.equal(earlier.root.querySelectorAll('th')[0].children[0].textContent, 'Finished');
assert.equal(card.root.querySelectorAll('th')[0].children[0].textContent, 'Started');
assert.equal(earlier.root.querySelectorAll('th')[1].children[0].textContent, 'Duration');
assert.match(helpText(earlier.root.querySelectorAll('th')[0].children[0]), /including stopped or failed work/);
const saved = card.body.children[0];
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.body.children[0], saved, 'unchanged refresh retains row and valid metrics');
const savedTargets = [3,5,6].map(index => saved.children[index].children[0]);
context.input.view.active_cards[0].rows[0].watch_duration_ms++;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.deepEqual([3,5,6].map(index => saved.children[index].children[0]), savedTargets,
  'advancing prompt publications retain value-help target identity');
context.input.view.active_cards[0].rows[0].prompt.in_progress = false;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.title.className, '', 'terminal title stops looking running');
assert.equal(watch.daily.attributes['aria-label'], 'CCost Today');
assert.deepEqual(watch.daily.children.map(node => node.textContent), ['CCost Today', '34', '37 prompts']);
assert.equal(watch.daily.querySelectorAll('button').length,0);
for (const node of watch.daily.children) {
  assert.equal(node.events.focus, undefined, 'daily label, amount and count have no help target');
  assert.equal(node.attributes['aria-describedby'], undefined);
  assert.equal(node.attributes.title, undefined);
}
assert.doesNotMatch(watch.daily.textContent,/Token Mix|Cached input|Cache write|Output/);
for (const table of [card, earlier]) {
  const headers = table.root.querySelectorAll('th');
  assert.match(helpText(headers[3].children[0]),/• Main prompt[\s\S]*• Linked subagents[\s\S]*hover, focus or tap the Model value/);
  assert.doesNotMatch(helpText(headers[5].children[0]),/displayed zero|N\/A|Part of the cost|Input token share/);
  assert.match(helpText(headers[5].children[0]),/value for Incoming\/Extra CCost and model\/subagent details/);
}
assert.equal(watch.root.children.at(-2), watch.daily);
assert.match(watch.accounts.textContent, /5-hour · 25% used/);
assert.match(watch.accounts.textContent, /Weekly · 100% used/);
assert.match(watch.accounts.textContent, /<100% used/);
assert.match(watch.accounts.textContent, /Usage unavailable/);
assert.match(watch.accounts.textContent, /CCost Today: 13/);
assert.ok(!/\(estimated\)|Rolling|Fixed window|rolling window/.test(watch.accounts.textContent));
const monthlyCard = watch.accounts.children[0].children[0];
assert.equal(monthlyCard.children[2].textContent, 'Monthly · 8.4% used (2088)');
assert.equal(monthlyCard.children[3].textContent, 'Monthly Capacity: 25000');
assert.equal(primaryTrack(monthlyCard).children[0].value, '0.08352');
assert.equal(monthlyCard.children[4].className, 'watch-capacity-spacer');
assert.equal(monthlyCard.children[4].attributes['aria-hidden'], 'true');
assert.equal(monthlyCard.children[4].textContent, '');
assert.equal(monthlyCard.children[4].tabIndex, undefined);
const periodCost = monthlyCard.children[2].children[1];
assert.equal(periodCost.title, undefined);
assert.equal(periodCost.tabIndex,0,'numeric Used help is focusable');
assert.equal(monthlyCard.children[2].querySelectorAll('button').length,0,'quota and capacity share one explanation');
assert.equal(helpText(monthlyCard.children[3].children[0]), 'Capacity: 25000 Credits');
assert.doesNotMatch(helpText(monthlyCard.children[3].children[0]), /Native Used|Native Remaining|÷|estimate/i);
assert.match(helpText(monthlyCard.children[2].children[0]), /Used: 2088\/25000 AI credits/);
assert.doesNotMatch(helpText(monthlyCard.children[2].children[0]), /Capacity|CCost|rolling|scope|pricing/);
assert.equal(primaryDetails(monthlyCard).children.length, 3, 'reset and two pace rows; no period cost row');
assert.match(primaryDetails(monthlyCard).children[0].textContent, /^Reset/);
assert.match(primaryDetails(monthlyCard).children[1].textContent, /^Remaining: .*\/day$/);
assert.match(primaryDetails(monthlyCard).children[2].textContent, /^Remaining: .*\/workday$/);
assert.equal(monthlyCard.children.length, 7, 'monthly peer has only an empty alignment row, no fake secondary quota');
const fiveCard = watch.accounts.children[0].children[1];
const capacitySample = structuredClone(context.input.view.accounts.accounts[1]);
assert.equal(fiveCard.children[2].textContent, '5-hour · 25% used (420)');
assert.equal(fiveCard.children[3].textContent, '5-hour Capacity: ~1700');
assert.equal(fiveCard.children[4].textContent, 'Monthly Capacity: ~240000');
assert.equal(helpText(fiveCard.children[3].children[0]), 'Capacity: ~1680 Credits');
assert.equal(helpText(fiveCard.children[4].children[0]), 'Monthly Capacity: ~241920 Credits');
assert.doesNotMatch(helpText(fiveCard.children[3].children[0]),/241920|Native Used|Native Remaining|rolling|scope/);
assert.equal(fiveCard.children[4].children[0].tabIndex,0);
assert.equal(fiveCard.children[2].children[1].tabIndex,0,'observed Used has concise numeric help, not estimate prose');
assert.equal(helpText(fiveCard.children[2].children[1]), 'Used: 420 Credits');
assert.match(primaryDetails(fiveCard).textContent, /Reset/);
assert.equal(footer(fiveCard).children[0].className, 'watch-account-details');
assert.match(footer(fiveCard).textContent, /Weekly · 100% used \(840\)Weekly Capacity: ~800Monthly Capacity: ~3600Reset/);
const weeklyCard = watch.accounts.children[0].children.at(-1);
assert.equal(weeklyCard.children[2].textContent, 'Weekly · 42% used (?)');
assert.match(primaryDetails(weeklyCard).children[0].textContent, /^Reset/);
assert.ok(!/5-hour|Usage unavailable/.test(weeklyCard.textContent));
assert.equal(primaryDetails(weeklyCard).children.length, 1, 'primary reset only');
assert.equal(weeklyCard.children.length, 7, 'unknown weekly keeps both permanent capacity rows');
assert.equal(weeklyCard.children[3].textContent, 'Weekly Capacity: ?');
assert.equal(weeklyCard.children[4].textContent, 'Monthly Capacity: ?');
assert.ok(!/BLOCKED|Unknown|Available|Observation details|Unaccounted usage/.test(watch.accounts.textContent));
assert.deepEqual(card.summary.children.map(line=>line.textContent), ['Context: 120k (Price threshold >100.0K exceeded; 2.4x more expensive)', 'Total CCost: 4583']);
assert.equal(card.warningIcon.className, 'watch-warning-icon');
for (const severity of ['none', 'approaching', 'exceeded', 'none']) {
  const warning = context.input.view.active_cards[0].session_summary.context.warning;
  warning.severity = severity;
  warning.text = severity === 'approaching' ? '[Approaching price threshold >100k]' : '[Price threshold >100k exceeded]';
  vm.runInContext('ReportView.renderLive(parent, input, state)', context);
  assert.equal(card.summary.dataset.severity, severity);
  const cell = card.body.children[0].children[8], icon = card.warningIcon;
  assert.equal(icon.hidden, severity === 'none');
  assert.equal(icon.textContent, '', 'SVG supplies shape without an OS-colored emoji');
  assert.ok(!/[~≈]/.test(cell.textContent));
  if (severity !== 'none') {
    assert.equal(icon.tabIndex, 0);
    assert.match(icon.attributes['aria-label'], severity === 'exceeded' ? /^Stop:/ : /^Caution:/);
    assert.equal(icon.title, undefined, 'no repeated explanation in a tooltip');
    assert.equal(card.warningOutline.attributes.points.split(' ').length, severity === 'exceeded' ? 8 : 3);
    assert.equal((card.warningText.textContent.match(/price threshold/gi) || []).length, 1);
    assert.equal((card.warningText.textContent.match(/\(/g) || []).length, 1);
    assert.equal(card.warningImpact.className, 'watch-price-multiplier');
  }
}
assert.match(earlier.summary.children[0].textContent, /^Context: 120k \(Approaching price threshold/);
assert.equal(earlier.summary.children[1].textContent, 'Total CCost: 4583');
const guidance = context.input.view.active_cards[0].session_summary.context.warning;
const savedGuidance = structuredClone(guidance);
guidance.severity = 'exceeded'; guidance.multiplier = null;
guidance.display.warning_cost = '(Next Ictx CCost 0.3–3)';
guidance.display_units = {usd: {warning_cost: '(Next Ictx CCost $0.003–$0.03)'}};
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.summary.children[0].textContent, /120k \(Price threshold >100k exceeded; Next Ictx CCost 0.3–3\)$/);
assert.equal(card.warningImpact.className, '', 'alternate price range stays neutral');
vm.runInContext('ReportView.setUnit("usd", parent)', context);
assert.match(card.warningText.textContent, /Next Ictx CCost \$0.003–\$0.03/);
vm.runInContext('ReportView.setUnit("credits", parent)', context);
guidance.display.warning_cost = ''; guidance.display_units = {};
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.warningText.textContent, ' (Price threshold >100k exceeded)', 'no invented impact or dangling separator');
Object.assign(guidance, savedGuidance);
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.ok(!/[~≈]/.test(earlier.body.children[0].children[8].textContent));
assert.equal(card.root.children.indexOf(card.summary), card.root.children.indexOf(card.activity) - 1);
assert.equal(card.root.children[card.root.children.indexOf(card.summary) - 1].className, 'watch-table-scroll');
assert.equal(earlier.root.children[earlier.root.children.indexOf(earlier.summary) - 1].className, 'watch-table-scroll');
assert.ok(!/threshold|\*1|\*2/.test(card.body.textContent));
const totals = watch.daily.textContent;
const nativeSummary = monthlyCard.children[2].textContent;
const creditPace = primaryDetails(monthlyCard).children.slice(1).map(node => node.textContent).join('');
const paceNodes = primaryDetails(monthlyCard).children.slice(1);
vm.runInContext('ReportView.setUnit("usd", parent)', context);
assert.match(watch.daily.textContent, /\$/);
assert.equal(monthlyCard.children[2].textContent, 'Monthly · 8.4% used ($20.88)');
assert.equal(monthlyCard.children[3].textContent, 'Monthly Capacity: $250.00');
assert.match(monthlyCard.children[1].textContent, /\$/);
assert.deepEqual(primaryDetails(monthlyCard).children.slice(1), paceNodes, 'unit changes retain pace DOM');
assert.deepEqual(paceNodes.map(node => node.textContent), ['Remaining: $38.19/day', 'Remaining: $45.82/workday']);
vm.runInContext('ReportView.setUnit("credits", parent)', context);
assert.equal(totals, watch.daily.textContent);
assert.equal(monthlyCard.children[2].textContent, nativeSummary);
assert.equal(periodCost.textContent, ' (2088)');
const retainedBar = primaryTrack(monthlyCard).children[0];
const beforeSwitch = JSON.stringify(context.input);
vm.runInContext('ReportView.setQuotaMode("remaining"); ReportView.syncUnits(parent)', context);
assert.equal(monthlyCard.children[2].textContent, 'Monthly · 91.6% remaining (22912)');
assert.equal(retainedBar.value, '0.91648');
assert.equal(retainedBar.attributes['aria-label'], 'Monthly remaining');
assert.equal(primaryTrack(monthlyCard).children[0], retainedBar, 'mode switches keep the existing bar and cost/focus owner');
assert.equal(monthlyCard.children[2].children[1], periodCost);
assert.equal(primaryDetails(monthlyCard).children.slice(1).map(node => node.textContent).join(''), creditPace);
assert.match(footer(fiveCard).textContent, /Weekly · 0% remaining \(0\)/);
const exhausted = footer(fiveCard).querySelectorAll('progress')[0];
assert.equal(exhausted.value, '0'); assert.match(exhausted.className, /exhausted/);
assert.match(exhausted.attributes['aria-valuetext'], /exhausted/);
vm.runInContext('ReportView.setUnit("usd", parent)', context);
assert.equal(periodCost.textContent, ' ($229.12)');
vm.runInContext('ReportView.setQuotaMode("used"); ReportView.setUnit("credits", parent)', context);
assert.equal(monthlyCard.children[2].textContent, nativeSummary);
assert.equal(JSON.stringify(context.input), beforeSwitch, 'switching never mutates frozen native source values');
const monthly = context.input.view.accounts.accounts[0];
monthly.primary.pace.workdays = 0; monthly.primary.pace.per_workday = null;
monthly.primary.quota.ccost_pace.workdays = 0; monthly.primary.quota.ccost_pace.ccost_per_workday = null;
monthly.primary.quota.window_active = false; monthly.primary.quota.reset_at_ms = null;
monthly.primary.display.watch_reset = 'Window not started';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
const inactiveCard = watch.accounts.children[0].children[0];
assert.equal(primaryDetails(inactiveCard).children[0].textContent, 'Window not started');
assert.equal(primaryDetails(inactiveCard).children[2].textContent, 'Remaining: no workdays left');
context.input.view.active_cards[0].session_summary.context = null;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.warningIcon.hidden, true);
assert.equal(card.warningText.textContent, '');
assert.equal(card.summary.children[0].textContent, 'Context: N/A');
const summaryValue = context.input.view.active_cards[0].session_summary;
const savedCost = summaryValue.cost;
summaryValue.state = 'refreshing';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.summary.textContent, /4583$/);
assert.doesNotMatch(card.summary.textContent, /refreshing|retained total/i);
assert.doesNotMatch(helpText(card.costHelp), /updating|Cache unavailable|source is retrying/);
assert.ok(!card.summary.textContent.includes('Loading'));
summaryValue.cost = null; summaryValue.state = 'loading';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.summary.children[1].textContent, 'Total CCost: 4583');
summaryValue.state = 'unavailable';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.summary.children[1].textContent, /^Total CCost: N\/A.*unavailable/);
summaryValue.cost = {...savedCost, priced_requests:0, complete:false}; summaryValue.state = 'partial';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.summary.children[1].textContent, 'Total CCost: N/A');
assert.match(helpText(card.costHelp), /Partial pricing or source data/);
assert.doesNotMatch(helpText(card.costHelp), /Source evidence:/);
summaryValue.cost = savedCost; summaryValue.state = 'observed';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
for (const complete of [true, false]) {
  context.input.view.daily_usage.prompt_count = 181;
  context.input.view.daily_usage.prompt_count_complete = complete;
  vm.runInContext('ReportView.renderLive(parent, input, state)', context);
  assert.equal(watch.daily.children[2].textContent, '181 prompts');
  assert.doesNotMatch(watch.daily.textContent, /Prompt count incomplete/);
  assert.equal(context.input.view.daily_usage.prompt_count_complete, complete);
}
const retainedDaily = watch.daily.children[1], retainedText = watch.daily.textContent;
const dailyValues = watch.daily.children.slice(0,3).map(node => node.textContent);
for (const state of ['refreshing', 'observed', 'refreshing']) {
  context.input.view.daily_state = state;
  vm.runInContext('ReportView.renderLive(parent, input, state)', context);
  assert.equal(watch.daily.children[1], retainedDaily, 'routine state changes do not replace valid daily DOM');
  assert.equal(watch.daily.textContent, retainedText);
  assert.ok(!/Refreshing|Loading/.test(watch.daily.textContent));
}
context.input.view.daily_usage.prompt_count = 182;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(watch.daily.children[2].textContent, '182 prompts');
context.input.view.daily_state = 'unavailable';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.doesNotMatch(watch.daily.textContent, /Source unavailable|retained/i);
assert.equal(watch.daily.attributes['aria-description'], undefined);
assert.match(watch.daily.textContent, /182 prompts/);
assert.equal(watch.daily.children[0].textContent, 'CCost Today');
assert.deepEqual(watch.daily.children.slice(0,2).map(node => node.textContent), dailyValues.slice(0,2));
context.input.view.daily_usage.total.complete = false;
context.input.view.daily_usage.total.priced_requests = 99;
context.input.view.daily_usage.total.display.known_ccost = '?34';
context.input.view.daily_usage.total.display_units.usd.known_ccost = '?$0.34';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(watch.daily.children[0].textContent, 'CCost Today');
assert.equal(watch.daily.children[1].textContent, '34');
assert.doesNotMatch(watch.daily.textContent,/Token Mix|Cached input|Cache write|Output/);
assert.doesNotMatch(watch.daily.textContent, /Partial|[?≥~]/);
assert.equal(watch.daily.children[1].events.focus, undefined, 'daily amount has no help interaction');
assert.equal(context.input.view.daily_usage.total.complete, false);
vm.runInContext('ReportView.setUnit("usd", parent)', context);
assert.equal(watch.daily.children[1].textContent, '$0.34');
vm.runInContext('ReportView.setUnit("credits", parent)', context);
assert.equal(watch.daily.children[1].textContent, '34');
context.input.view.daily_usage.total.complete = true;
context.input.view.daily_state = 'retrying';
context.input.view.active_cards[0].state = 'retrying';
context.input.state = 'retrying';
context.state.connection = 'Retrying source read — last observation retained, not current.';
context.state.connectionKind = 'source_retrying';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.doesNotMatch(watch.daily.textContent, /Retrying|delayed/);
assert.equal(card.message.textContent, '');
assert.equal(card.message.hidden, true);
assert.doesNotMatch(watch.empty.textContent, /Retrying|delayed/);
assert.doesNotMatch(watch.empty.textContent, /connection interrupted/i);
assert.match(helpText(card.costHelp), /Reference cost of the entire session/);
now += 29999;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.message.textContent, '');
now++;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.message.textContent, '', 'host owns source retry notice, never duplicate it in each card');
assert.equal(watch.empty.textContent, '');
assert.doesNotMatch(watch.daily.textContent, /delayed/i);
context.input.view.active_cards[0].state = 'observed';
context.input.view.active_cards[0].observed_at_ms++;
summaryValue.state = 'refreshing';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.message.hidden, true);
now += 240000;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.costStatus.textContent, '', 'ordinary pending checks never turn a known total into a delayed warning');
assert.equal(earlier.costStatus.textContent, '');
summaryValue.state = 'observed';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.costStatus.textContent, '');
assert.ok(!/Source unavailable/.test(watch.root.textContent));
context.input.state = 'running';
context.input.view.daily_state = 'observed';
context.state.connectionKind = 'reconnecting';
vm.runInContext("state.connection = 'RECONNECTING'; ReportView.renderLive(parent, input, state)", context);
assert.doesNotMatch(watch.empty.textContent, /Live connection interrupted/);
assert.ok(!/Source unavailable/.test(watch.empty.textContent));
context.input.view.daily_usage = null;
context.input.view.daily_state = 'loading';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(watch.daily.textContent, /182 prompts/);
assert.doesNotMatch(watch.daily.textContent, /Loading|delayed/);
assert.equal(watch.daily.children[0].textContent, 'CCost Today');
assert.equal(watch.daily.attributes['aria-label'], 'CCost Today');
assert.ok(!/0 prompts/.test(watch.daily.textContent));
context.input.view.daily_state = 'unavailable';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(watch.daily.textContent, /182 prompts/);
for (const node of [watch.daily, ...watch.daily.children]) {
  assert.equal(node.attributes.title, undefined);
  assert.equal(node.attributes['aria-describedby'], undefined);
  assert.equal(node.attributes['aria-description'], undefined);
  assert.equal(node.attributes.tabindex, undefined);
  assert.ok(!node.className?.includes('help-value'));
}
// A fresh initial acquisition stays neutral, never an observed empty/zero state.
const initial = structuredClone(context.input);
Object.assign(initial.view, {active_cards:[], history_cards:[], cards_state:'loading', history_state:'loading',
  daily_usage:null, daily_state:'loading', accounts:null});
initial.view.active_cards = [{...context.input.view.active_cards[0],rows:[],state:'loading',
  session_summary:{cost:null,context:null,state:'loading'}}];
context.initial = initial;
vm.runInContext('globalThis.fresh = new WatchView.View({connection:"Live connected."}); fresh.update(initial)', context);
assert.equal(context.fresh.empty.textContent, '');
assert.equal(context.fresh.history.textContent, 'Loading earlier sessions…');
assert.equal(context.fresh.daily.textContent, 'CCost Today—');
assert.equal(context.fresh.accounts.textContent, '');
const initialCard = [...context.fresh.cards.values()][0];
assert.equal(initialCard.message.textContent, '');
assert.equal(initialCard.body.children.length, 0);
assert.equal(initialCard.costLabel.textContent, 'Loading…');
now += 29999;
vm.runInContext('fresh.update(initial)', context);
assert.equal(initialCard.costLabel.textContent, 'Loading…');
assert.doesNotMatch(context.fresh.root.textContent, /delayed/i);
now++;
vm.runInContext('fresh.update(initial)', context);
assert.equal(context.fresh.empty.textContent, '', 'elapsed startup time is not a global failure');
assert.equal(context.fresh.daily.textContent, 'CCost Today—');
assert.match(initialCard.message.textContent, /Prompt updates delayed/);
Object.assign(initial.view, {cards_state:'observed', history_state:'observed', daily_state:'unavailable', accounts:{accounts:[]}});
initial.view.active_cards = [];
vm.runInContext('fresh.update(initial)', context);
assert.equal(context.fresh.empty.textContent, 'No running prompts');
assert.equal(context.fresh.history.textContent, 'No earlier sessions');
assert.equal(context.fresh.daily.textContent, 'CCost TodayUnavailable');
// Independent sublanes cannot turn advancing prompt observations into a global delay.
const advancing = structuredClone(input);
advancing.view.active_cards[0].rows[0].prompt.in_progress = true;
context.advancing = advancing;
vm.runInContext('globalThis.healthy = new WatchView.View({connection:"Live connected."}); healthy.update(advancing)', context);
const healthy = context.healthy, anchored = healthy.active.children[0];
for (const lane of ['history', 'accounts', 'daily', 'partial']) {
  Object.assign(advancing.view, {history_state:'observed', accounts:input.view.accounts,
    daily_state:'observed', cards_state:'observed'});
  if (lane === 'history') advancing.view.history_state = 'loading';
  if (lane === 'accounts') advancing.view.accounts = null;
  if (lane === 'daily') advancing.view.daily_state = 'loading';
  if (lane === 'partial') advancing.view.cards_state = 'partial';
  for (let seconds = 0; seconds <= 180; seconds += 10) {
    now += 10000;
    advancing.view.active_cards[0].rows[0].prompt.calls = seconds + 1;
    vm.runInContext('healthy.update(advancing)', context);
    assert.equal(healthy.empty.textContent, '', lane + ' must not gate running prompts');
    assert.equal(healthy.active.children[0], anchored);
    assert.equal(anchored.querySelectorAll('tr')[1].children[6].textContent, String(seconds + 1));
  }
}
// Only confirmed healthy observations establish an empty running population.
advancing.view.active_cards = [];
for (const cardsState of [null, 'loading', 'partial', 'retrying', 'unavailable', 'observed']) {
  advancing.view.cards_state = cardsState;
  vm.runInContext('healthy.update(advancing)', context);
  assert.equal(healthy.empty.textContent === 'No running prompts', cardsState === 'observed');
}
for (const sourceState of ['retrying', 'unavailable', 'failed']) {
  advancing.state = sourceState;
  vm.runInContext('healthy.update(advancing)', context);
  now += 180000;
  vm.runInContext('healthy.update(advancing)', context);
  assert.doesNotMatch(healthy.empty.textContent, /not current|Source updates delayed/);
  assert.doesNotMatch(healthy.empty.textContent, /No running prompts|Still loading Watch data/);
}
advancing.state = 'running';
vm.runInContext('healthy.state.connection="RECONNECTING"; healthy.state.connectionKind="reconnecting"; healthy.update(advancing)', context);
assert.equal(healthy.empty.textContent, '');
vm.runInContext('healthy.state.connection="Live connected."; healthy.state.connectionKind="connected"; healthy.update(advancing)', context);
assert.equal(healthy.empty.textContent, 'No running prompts');
const baseHistory = context.input.view.history_cards[0];
const historyCard = id => ({...baseHistory, session_id: id});
context.input.view.history_cards = ['oldest', 'middle', 'newest'].map(historyCard);
for (const open of [false, true, false]) {
  watch.earlier.open = open;
  vm.runInContext('ReportView.renderLive(parent, input, state)', context);
  assert.deepEqual([...watch.history.children].map(node => node.dataset.session), ['oldest', 'middle', 'newest']);
  assert.equal(watch.earlier.open, open);
}
context.input.view.history_cards = ['middle', 'newest', 'newly-eligible'].map(historyCard);
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.deepEqual([...watch.history.children].map(node => node.dataset.session), ['middle', 'newest', 'newly-eligible']);
for (const fixture of context.input.quota_cases || []) {
  context.input.view.accounts.accounts = [{...monthly, primary: fixture.value, secondary: [],
    observation: {...monthly.observation, id:'quota-case-'+fixture.name, availability: 'stale'}}];
  vm.runInContext('ReportView.renderLive(parent, input, state)', context);
  const account = watch.accounts.children[0].children[0], label = account.children[2].textContent;
  const expected = fixture.percent === '—' ? '—' : fixture.percent + ' used';
  assert.ok(label.includes(fixture.value.quota.unlimited ? 'Unlimited' : expected), fixture.name);
  assert.ok(!label.includes('/'), 'native ratios belong in accessible help, not the headline');
  assert.ok(helpText(account.children[2].children[0]).includes(fixture.native), fixture.name);
  assert.ok(!/CCost:|estimated|partial|[~≈]/.test(label), 'compact value has no visible provenance marker');
  assert.equal(primaryDetails(account).children[0].textContent, 'Reset unknown');
  assert.equal(account.attributes['aria-description'], undefined);
  assert.equal(account.querySelectorAll('progress').length,
    fixture.value.used_fraction == null || fixture.value.quota.unlimited ? 0 : 1, fixture.name);
  assert.equal(account.dataset.exhausted, String(fixture.value.exhausted), fixture.name);
  assert.equal(account.children[2].className.includes('watch-quota-exhausted'), fixture.value.exhausted, fixture.name);
  for (const bar of account.querySelectorAll('progress'))
    assert.equal(bar.className === 'watch-quota-exhausted', fixture.value.exhausted, fixture.name);
  if (fixture.name === 'empty period') assert.ok(label.includes('used (0)'));
  if (['unknown cost', 'unpriced period'].includes(fixture.name))
    assert.match(label, /\(\?\)/);
  assert.doesNotMatch(helpText(account.children[2].children[0]), /Capacity|CCost|÷|pricing/);
  if (fixture.name === 'partial period') assert.match(helpText(account.children[2].children[1]), /Partial pricing \/ attribution/);
  if (fixture.name === 'estimated period') assert.match(helpText(account.children[2].children[1]), /Account attribution uncertain/);
  if (fixture.name === 'owner example') assert.equal(label, '5 hours · 16% used (94)');
  vm.runInContext('ReportView.setQuotaMode("remaining"); ReportView.syncUnits(parent)', context);
  const shown = fixture.value.quota.quota_display.remaining;
  if (fixture.name === 'native money') {
    assert.match(helpText(account.children[2].children[0]), /Native money remaining: \$91.65 \/ \$100.00/);
    vm.runInContext('ReportView.setUnit("usd", parent)', context);
    assert.equal(account.children[2].textContent.includes('CCost used:'), false);
    assert.match(helpText(account.children[2].children[0]), /Native money remaining: \$91.65 \/ \$100.00/);
  }
  if (shown.mode === 'remaining') {
    assert.match(account.children[2].textContent, /remaining/);
    for (const bar of account.querySelectorAll('progress')) assert.equal(bar.value, shown.fraction);
  } else assert.equal(account.children[2].textContent, label, 'unknown/unlimited retains Used');
  vm.runInContext('ReportView.setQuotaMode("used"); ReportView.setUnit("credits", parent)', context);
}
// Accounts can start before any Watch DOM and consumes exactly the same cards.
context.shared = structuredClone(input.view);
context.shared.accounts = {accounts:[structuredClone(monthly)]};
context.shared.quota_stale = false; context.shared.quota_recovering_count = 0;
vm.runInContext('globalThis.accountsPage = new AccountCards.View(true)', context);
const page = context.accountsPage;
assert.equal(page.root.textContent, 'Loading accounts…');
vm.runInContext('accountsPage.update(shared)', context);
const sharedCard = page.grid.children[0], sharedLabel = sharedCard.children[2], sharedBar = primaryTrack(sharedCard).children[0];
assert.equal(sharedCard.children.some(n => n.className === 'watch-capacity-spacer'), false, 'single monthly card stays compact');
assert.equal(sharedCard.children.length, 6);
vm.runInContext('globalThis.parity = new WatchView.View({connection:"Live connected."}); parity.update({state:"running",view:shared})', context);
assert.equal(page.root.textContent, context.parity.accounts.textContent);
assert.equal(page.root.children.length, 1, 'healthy Accounts contains only the shared grid');
context.shared.accounts.now_ms = 999999;
vm.runInContext('accountsPage.update(shared)', context);
assert.equal(page.grid.children[0], sharedCard, 'publication clock alone does not rebuild accounts');
context.shared.accounts.accounts[0].primary.display.watch_reset = 'Reset in 15m';
context.shared.accounts.accounts[0].observation.availability = 'stale';
vm.runInContext('accountsPage.update(shared)', context);
assert.equal(page.grid.children[0], sharedCard);
assert.equal(sharedCard.children[2], sharedLabel, 'changed clocks and warnings preserve metric/help targets');
assert.equal(primaryTrack(sharedCard).children[0], sharedBar);
assert.match(sharedCard.textContent, /Reset in 15m/);
assert.doesNotMatch(sharedCard.textContent, /Stale|not current/);
assert.equal(sharedCard.attributes['aria-description'], undefined);
vm.runInContext('ReportView.setQuotaMode("remaining"); ReportView.setUnit("usd", accountsPage.root)', context);
assert.match(sharedLabel.textContent, /remaining.*\$/);
const other = structuredClone(context.shared.accounts.accounts[0]); other.observation.id = 'another-account';
context.shared.accounts.accounts.push(other);
vm.runInContext('accountsPage.update(shared)', context);
assert.equal(page.grid.children.length, 2);
context.shared.accounts.accounts.reverse();
vm.runInContext('accountsPage.update(shared)', context);
assert.equal(page.grid.children[1], sharedCard, 'reordering retains the correct account identity');
context.shared.accounts = {accounts:[]}; context.shared.quota_stale = true;
vm.runInContext('accountsPage.update(shared)', context);
assert.equal(page.grid.children.length, 2, 'failed empty read retains usable accounts');
assert.doesNotMatch(page.message.textContent, /retained|delayed/i);
now += 60000;
vm.runInContext('accountsPage.update(shared)', context);
assert.equal(page.message.textContent, '', 'do not duplicate a card-owned source warning as a global retained warning');
assert.doesNotMatch(page.grid.textContent, /Stale|Updates delayed/);
context.shared.quota_stale = false;
vm.runInContext('accountsPage.update(shared)', context);
assert.equal(page.root.textContent, 'No configured accounts detected.', 'observed empty actually removes cards');
assert.equal(page.cards.size, 0);
require('../fixtures/live_status.cjs')(vm, context, value => value == null ? now : (now = value));
require('../fixtures/account_links.cjs')(vm, context, monthly);
require('../fixtures/account_today.cjs')(vm, context, monthly, helpText);
require('../fixtures/account_capacity.cjs')(vm,context,capacitySample,helpText);
console.log('watch summary passed');
