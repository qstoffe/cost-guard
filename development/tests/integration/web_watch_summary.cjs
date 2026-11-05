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
for (const name of ['render', 'watch']) vm.runInContext(fs.readFileSync(`src/web/assets/${name}.js`, 'utf8'), context);
vm.runInContext("globalThis.state = {connection:'Live connected.'}; ReportView.renderLive(parent, input, state)", context);
const watch = context.state.watch, card = [...watch.cards.values()][0];
assert.equal(watch.root.style['--watch-account-width'],'298px');
window.devicePixelRatio=1.875;
media.at(-1).callback();
assert.equal(watch.root.style['--watch-account-width'],'238px');
assert.equal(media[0].callback,null,'obsolete resolution listener is removed');
window.visualViewport.scale=1.25;viewportEvents.resize();
assert.equal(watch.root.style['--watch-account-width'],'191px','pinch factor applies once');
window.devicePixelRatio=1;window.visualViewport.scale=1;windowEvents.resize();
assert.equal(watch.root.style['--watch-account-width'],'448px');
const row = card.body.children[0], prompt = context.input.view.active_cards[0].rows[0].prompt;
assert.equal(card.body.children.length, 1);
assert.equal(row.children[0].textContent, prompt.display.clock);
assert.equal(row.children[2].textContent, '#37' + prompt.preview);
assert.equal(helpText(row.children[2].children[0].children[2]), prompt.preview);
assert.equal(row.attributes['aria-label'], 'Prompt 37 · Running');
assert.match(helpText(row.children[3].children[0].children[0]), /Other models also contributed/);
assert.equal(card.title.className, 'watch-running-title');
assert.ok(!/Session Total|provisional|Loading/.test(card.root.textContent));
assert.equal(card.running.textContent, 'Running: shell 41s');
assert.equal(card.background.textContent, 'Running: subagent 55s');
assert.equal(card.tools.summary.children.at(-1).className, 'watch-activity-error');
assert.match(card.tools.summary.children.at(-1).textContent, /1 failed/);
assert.equal(card.skills.summary.children.at(-1).className, 'watch-activity-error');
assert.equal(card.skills.list.children[0].children.at(-1).className, 'watch-activity-error');
const earlier = [...watch.cards.values()][1];
assert.equal(earlier.title.className, '');
assert.equal(earlier.body.children[0].children[0].textContent,
   context.input.view.history_cards[0].rows[0].prompt.display.finished_clock);
assert.equal(helpText(earlier.body.children[0].children[0].children[0].children[0]),
   context.input.view.history_cards[0].rows[0].prompt.display.finished_date_time);
assert.equal(earlier.root.querySelectorAll('th')[0].children[0].textContent, 'Finished');
assert.equal(card.root.querySelectorAll('th')[0].children[0].textContent, 'Started');
assert.equal(earlier.root.querySelectorAll('th')[1].children[0].textContent, 'Duration');
assert.match(helpText(earlier.root.querySelectorAll('th')[0].children[0]), /including stopped or failed work/);
const saved = card.body.children[0];
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.body.children[0], saved, 'unchanged refresh retains row and valid metrics');
context.input.view.active_cards[0].rows[0].prompt.in_progress = false;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.title.className, '', 'terminal title stops looking running');
assert.equal(watch.daily.attributes['aria-label'], 'CCost Today');
assert.deepEqual(watch.daily.children.map(node => node.textContent), ['CCost Today', '34', '37 prompts', 'Token Mix %',
  'Input: 50% (15)', 'Cached input: 30% (3)', 'Cache write: 10% (4)', 'Output: 10% (12)']);
assert.equal(watch.root.children.at(-2), watch.daily);
assert.match(watch.accounts.textContent, /5-hour · 25% used/);
assert.match(watch.accounts.textContent, /Weekly · 100% used/);
assert.match(watch.accounts.textContent, /<100% used/);
assert.match(watch.accounts.textContent, /Usage unavailable/);
assert.match(watch.accounts.textContent, /CCost Today: 13/);
assert.ok(!/\(estimated\)|Rolling|Fixed window|rolling window/.test(watch.accounts.textContent));
const monthlyCard = watch.accounts.children[0].children[0];
assert.equal(monthlyCard.children[2].textContent, 'Monthly · 8.4% used (1814)');
assert.equal(monthlyCard.children[3].textContent, 'Capacity: 25000');
assert.equal(monthlyCard.children[4].children[0].value, '0.08352');
const periodCost = monthlyCard.children[2].children[1];
assert.equal(periodCost.title, undefined);
assert.match(helpText(monthlyCard.children[2].children[2]), /provider’s reported included AI-credit limit[\s\S]*Used \+ Remaining need not equal Capacity/);
assert.match(helpText(monthlyCard.children[2].children[2]), /Native Used: 2088\/25000 AI credits/);
assert.equal(monthlyCard.children[5].children.length, 3, 'reset and two pace rows; no period cost row');
assert.match(monthlyCard.children[5].children[0].textContent, /^Reset/);
assert.match(monthlyCard.children[5].children[1].textContent, /^Remaining: .*\/day$/);
assert.match(monthlyCard.children[5].children[2].textContent, /^Remaining: .*\/workday$/);
assert.equal(monthlyCard.children.length, 6, 'monthly-only has no secondary section or divider');
const fiveCard = watch.accounts.children[0].children[1];
assert.equal(fiveCard.children[2].textContent, '5-hour · 25% used (420)');
assert.equal(fiveCard.children[3].textContent, 'Capacity: 1680');
assert.match(fiveCard.children[5].textContent, /Reset/);
assert.equal(fiveCard.children[6].children[0].className, 'watch-account-details');
assert.match(fiveCard.children[6].textContent, /Weekly · 100% used \(840\)Capacity: 840Reset/);
const weeklyCard = watch.accounts.children[0].children.at(-1);
assert.equal(weeklyCard.children[2].textContent, 'weekly · 42% used (?)');
assert.match(weeklyCard.children[5].children[0].textContent, /^Reset/);
assert.ok(!/5-hour|Usage unavailable/.test(weeklyCard.textContent));
assert.equal(weeklyCard.children[5].children.length, 1, 'primary reset only');
assert.equal(weeklyCard.children.length, 6, 'weekly-only has no secondary section or divider');
assert.ok(!/BLOCKED|Unknown|Available|Observation details|Unaccounted usage/.test(watch.accounts.textContent));
assert.equal(card.summary.textContent, 'Session Context / CCost: 120k / 4583 (Price threshold >100.0K exceeded; 2.4x more expensive)');
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
assert.match(earlier.summary.textContent, /^Session Context \/ CCost: 120k \/ 4583 \(Approaching price threshold/);
const guidance = context.input.view.active_cards[0].session_summary.context.warning;
const savedGuidance = structuredClone(guidance);
guidance.severity = 'exceeded'; guidance.multiplier = null;
guidance.display.warning_cost = '(Next Ictx CCost 0.3–3)';
guidance.display_units = {usd: {warning_cost: '(Next Ictx CCost $0.003–$0.03)'}};
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.summary.textContent, /4583 \(Price threshold >100k exceeded; Next Ictx CCost 0.3–3\)$/);
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
const nativePace = monthlyCard.children[5].children.slice(1).map(node => node.textContent).join('');
vm.runInContext('ReportView.setUnit("usd", parent)', context);
assert.match(watch.daily.textContent, /\$/);
assert.equal(monthlyCard.children[2].textContent, 'Monthly · 8.4% used ($18.14)');
assert.equal(monthlyCard.children[3].textContent, 'Capacity: $250.00');
assert.match(monthlyCard.children[1].textContent, /\$/);
assert.equal(monthlyCard.children[5].children.slice(1).map(node => node.textContent).join(''), nativePace,
  'CCost unit does not convert native pace');
vm.runInContext('ReportView.setUnit("credits", parent)', context);
assert.equal(totals, watch.daily.textContent);
assert.equal(monthlyCard.children[2].textContent, nativeSummary);
assert.equal(periodCost.textContent, ' (1814)');
const retainedBar = monthlyCard.children[4].children[0];
const beforeSwitch = JSON.stringify(context.input);
vm.runInContext('ReportView.setQuotaMode("remaining"); ReportView.syncUnits(parent)', context);
assert.equal(monthlyCard.children[2].textContent, 'Monthly · 91.6% remaining (22912)');
assert.equal(retainedBar.value, '0.91648');
assert.equal(retainedBar.attributes['aria-label'], 'Monthly remaining');
assert.equal(monthlyCard.children[4].children[0], retainedBar, 'mode switches keep the existing bar and cost/focus owner');
assert.equal(monthlyCard.children[2].children[1], periodCost);
assert.equal(monthlyCard.children[5].children.slice(1).map(node => node.textContent).join(''), nativePace);
assert.match(fiveCard.children[6].textContent, /Weekly · 0% remaining \(0\)/);
const exhausted = fiveCard.children[6].querySelectorAll('progress')[0];
assert.equal(exhausted.value, '0'); assert.match(exhausted.className, /exhausted/);
assert.match(exhausted.attributes['aria-valuetext'], /exhausted/);
vm.runInContext('ReportView.setUnit("usd", parent)', context);
assert.equal(periodCost.textContent, ' ($229.12)');
vm.runInContext('ReportView.setQuotaMode("used"); ReportView.setUnit("credits", parent)', context);
assert.equal(monthlyCard.children[2].textContent, nativeSummary);
assert.equal(JSON.stringify(context.input), beforeSwitch, 'switching never mutates frozen native source values');
const monthly = context.input.view.accounts.accounts[0];
monthly.primary.pace.workdays = 0; monthly.primary.pace.per_workday = null;
monthly.primary.quota.window_active = false; monthly.primary.quota.reset_at_ms = null;
monthly.primary.display.watch_reset = 'Window not started';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
const inactiveCard = watch.accounts.children[0].children[0];
assert.equal(inactiveCard.children[5].children[0].textContent, 'Window not started');
assert.equal(inactiveCard.children[5].children[2].textContent, 'Remaining: no workdays left');
context.input.view.active_cards[0].session_summary.context = null;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.warningIcon.hidden, true);
assert.equal(card.warningText.textContent, '');
assert.match(card.summary.textContent, /^Session Context \/ CCost: N\/A \/ /);
const summaryValue = context.input.view.active_cards[0].session_summary;
const savedCost = summaryValue.cost;
summaryValue.state = 'refreshing';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.summary.textContent, /4583$/);
assert.doesNotMatch(card.summary.textContent, /refreshing|retained total/i);
assert.match(helpText(card.costHelp), /updating; retained observation, not current/);
assert.ok(!card.summary.textContent.includes('Loading'));
summaryValue.cost = null; summaryValue.state = 'loading';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.summary.textContent, /Session Context \/ CCost: N\/A \/ Loading…/);
summaryValue.state = 'unavailable';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.summary.textContent, /Session Context \/ CCost: N\/A \/ N\/A.*unavailable/);
summaryValue.cost = {...savedCost, priced_requests:0, complete:false}; summaryValue.state = 'partial';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.summary.textContent, /Session Context \/ CCost: N\/A \/ N\/A.*partial source evidence/);
summaryValue.cost = savedCost; summaryValue.state = 'observed';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
for (const complete of [true, false]) {
  context.input.view.daily_usage.prompt_count = 181;
  context.input.view.daily_usage.prompt_count_complete = complete;
  vm.runInContext('ReportView.renderLive(parent, input, state)', context);
  assert.equal(watch.daily.children[2].textContent, '181 prompts');
  assert.ok(!/≥|>=|partial attribution|at least/i.test(watch.daily.textContent));
  assert.equal(context.input.view.daily_usage.prompt_count_complete, complete);
}
const retainedDaily = watch.daily.children[1], retainedText = watch.daily.textContent;
const dailyCategories = watch.daily.children.slice(3).map(node => node.textContent);
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
assert.match(watch.daily.textContent, /Source unavailable · retained daily observation/);
assert.match(watch.daily.textContent, /182 prompts/);
assert.equal(watch.daily.children[0].textContent, 'CCost Today');
assert.deepEqual(watch.daily.children.slice(3, 8).map(node => node.textContent), dailyCategories);
context.input.view.daily_usage.total.complete = false;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(watch.daily.children[0].textContent, 'CCost Today');
assert.equal(watch.daily.children[1].textContent, '34');
assert.deepEqual(watch.daily.children.slice(3, 8).map(node => node.textContent), dailyCategories);
assert.match(watch.daily.textContent, /Partial pricing \/ token data/);
context.input.view.daily_usage.total.complete = true;
context.input.view.daily_state = 'retrying';
context.input.view.active_cards[0].state = 'retrying';
context.input.state = 'retrying';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(watch.daily.textContent, /Retrying daily refresh.*not current/);
assert.equal(card.message.textContent, '');
assert.equal(card.message.hidden, true);
assert.doesNotMatch(watch.empty.textContent, /Retrying|delayed/);
assert.match(helpText(card.costHelp), /Prompt source is retrying.*not current/);
now += 29999;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.message.textContent, '');
now++;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.message.textContent, /Prompt updates delayed.*not current/);
assert.match(watch.empty.textContent, /Source updates delayed.*not current/);
context.input.view.active_cards[0].state = 'observed';
summaryValue.state = 'refreshing';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.message.hidden, true);
now += 30000;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(card.costStatus.textContent, /session total updates delayed.*not current/);
summaryValue.state = 'observed';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.costStatus.textContent, '');
assert.ok(!/Source unavailable/.test(watch.root.textContent));
context.input.state = 'running';
vm.runInContext("state.connection = 'RECONNECTING'; ReportView.renderLive(parent, input, state)", context);
assert.match(watch.empty.textContent, /Live connection interrupted/);
assert.ok(!/Source unavailable/.test(watch.empty.textContent));
context.input.view.daily_usage = null;
context.input.view.daily_state = 'loading';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(watch.daily.textContent, /Loading daily activity/);
assert.equal(watch.daily.children[0].textContent, 'CCost Today');
assert.equal(watch.daily.attributes['aria-label'], 'CCost Today');
assert.ok(!/0 prompts/.test(watch.daily.textContent));
context.input.view.daily_state = 'unavailable';
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.deepEqual(watch.daily.children.map(node => node.textContent), ['CCost Today', 'Daily activity unavailable']);
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
    observation: {...monthly.observation, availability: 'stale'}}];
  vm.runInContext('ReportView.renderLive(parent, input, state)', context);
  const account = watch.accounts.children[0].children[0], label = account.children[2].textContent;
  const expected = fixture.percent === '—' ? '—' : fixture.percent + ' used';
  assert.ok(label.includes(fixture.value.quota.unlimited ? 'Unlimited' : expected), fixture.name);
  assert.ok(!label.includes('/'), 'native ratios belong in accessible help, not the headline');
  assert.ok(helpText(account.children[2].children[2]).includes(fixture.native), fixture.name);
  assert.ok(!/CCost:|estimated|partial|[~≈]/.test(label), 'compact value has no visible provenance marker');
  assert.equal(account.children[5].children[0].textContent, 'Reset unknown');
  assert.match(account.textContent, /Stale.*not current/);
  assert.equal(account.querySelectorAll('progress').length,
    fixture.value.used_fraction == null || fixture.value.quota.unlimited ? 0 : 1, fixture.name);
  assert.equal(account.dataset.exhausted, String(fixture.value.exhausted), fixture.name);
  assert.equal(account.children[2].className.includes('watch-quota-exhausted'), fixture.value.exhausted, fixture.name);
  for (const bar of account.querySelectorAll('progress'))
    assert.equal(bar.className === 'watch-quota-exhausted', fixture.value.exhausted, fixture.name);
  if (fixture.name === 'empty period') assert.ok(label.includes('used (0)'));
  if (['unknown cost', 'unpriced period'].includes(fixture.name))
    assert.match(label, /\(\?\)/);
  if (fixture.name === 'partial period') assert.match(helpText(account.children[2].children[2]), /partial attribution/);
  if (fixture.name === 'estimated period') assert.match(helpText(account.children[2].children[2]), /estimated attribution/);
  if (fixture.name === 'owner example') assert.equal(label, '5 hours · 16% used (94)');
  vm.runInContext('ReportView.setQuotaMode("remaining"); ReportView.syncUnits(parent)', context);
  const shown = fixture.value.quota.quota_display.remaining;
  if (fixture.name === 'native money') {
    assert.match(helpText(account.children[2].children[2]), /Native money remaining: \$91.65 \/ \$100.00/);
    vm.runInContext('ReportView.setUnit("usd", parent)', context);
    assert.equal(account.children[2].textContent.includes('CCost used:'), false);
    assert.match(helpText(account.children[2].children[2]), /Native money remaining: \$91.65 \/ \$100.00/);
  }
  if (shown.mode === 'remaining') {
    assert.match(account.children[2].textContent, /remaining/);
    for (const bar of account.querySelectorAll('progress')) assert.equal(bar.value, shown.fraction);
  } else assert.equal(account.children[2].textContent, label, 'unknown/unlimited retains Used');
  vm.runInContext('ReportView.setQuotaMode("used"); ReportView.setUnit("credits", parent)', context);
}
console.log('watch summary passed');
