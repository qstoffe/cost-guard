// Pure DOM VM regression; no browser process, dependencies or source access.
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ''; this.dataset = {}; this.attributes = {}; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(''); }
  append(...items) { for (const item of items) { item.remove(); this.children.push(item); item.parentNode = this; } }
  replaceChildren(...items) { for (const child of this.children) child.parentNode = null; this.children = []; this.text = ''; this.append(...items); }
  insertBefore(child, before) { child.remove(); this.children.splice(before ? this.children.indexOf(before) : this.children.length, 0, child); child.parentNode = this; }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
  contains(node) { return node === this || this.children.some(child => child.contains(node)); }
  querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
  setAttribute(name, value) { this.attributes[name] = value; }
}
const context = vm.createContext({document: {createElement: tag => new Node(tag)}, window: {}, console,
  input, parent: new Node('div')});
for (const name of ['render', 'watch']) vm.runInContext(fs.readFileSync(`src/web/assets/${name}.js`, 'utf8'), context);
vm.runInContext("globalThis.state = {connection:'Live connected.'}; ReportView.renderLive(parent, input, state)", context);
const watch = context.state.watch, card = [...watch.cards.values()][0];
const row = card.body.children[0], prompt = context.input.view.active_cards[0].rows[0].prompt;
assert.equal(card.body.children.length, 1);
assert.equal(row.children[0].textContent, 'Prompt 37 ' + prompt.display.clock);
assert.equal(row.children[1].textContent, prompt.preview);
assert.equal(row.children[1].children[0].title, prompt.preview);
assert.equal(row.attributes['aria-label'], 'Prompt 37 · Running');
assert.match(row.children[2].children[0].title, /Additional model contribution/);
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
  'Prompt 37 ' + context.input.view.history_cards[0].rows[0].prompt.display.date_time);
const saved = card.body.children[0];
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.body.children[0], saved, 'unchanged refresh retains row and valid metrics');
context.input.view.active_cards[0].rows[0].prompt.in_progress = false;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.title.className, '', 'terminal title stops looking running');
assert.match(watch.daily.textContent, /Total Today34.*37 prompts.*Token Mix %.*Input: 50% \(15\).*Cached input: 30% \(3\)/);
assert.equal(watch.root.children.at(-2), watch.daily);
assert.match(watch.accounts.textContent, /5-hour · 25% used/);
assert.match(watch.accounts.textContent, /Weekly · 100% used/);
assert.match(watch.accounts.textContent, /<100% used/);
assert.match(watch.accounts.textContent, /Usage unavailable/);
assert.match(watch.accounts.textContent, /CCost Today: 13 \(estimated\)/);
assert.ok(!/BLOCKED|Unknown|Available|Observation details|Unaccounted usage/.test(watch.accounts.textContent));
assert.match(card.warning.textContent, /⚠ Price threshold.*2.4x more expensive/);
assert.ok(!/threshold|\*1|\*2/.test(card.body.textContent));
const totals = watch.daily.textContent;
vm.runInContext('ReportView.setUnit("usd", parent)', context);
assert.match(watch.daily.textContent, /\$/);
vm.runInContext('ReportView.setUnit("credits", parent)', context);
assert.equal(totals, watch.daily.textContent);
context.input.view.active_cards[0].context_warning = null;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.equal(card.warning.hidden, true);
assert.equal(card.warning.textContent, '');
context.input.view.daily_usage.prompt_count_complete = false;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(watch.daily.textContent, /≥37 prompts · partial attribution/);
context.input.view.daily_usage = null;
vm.runInContext('ReportView.renderLive(parent, input, state)', context);
assert.match(watch.daily.textContent, /Loading daily activity/);
assert.ok(!/0 prompts/.test(watch.daily.textContent));
console.log('watch summary passed');
