// Actual shipped assets in a deterministic VM/DOM, never browser automation.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.events = {}; this.text = ''; }
  set textContent(value) { this.text = String(value); this.replaceChildren(); }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(''); }
  get firstElementChild() { return this.children[0]; }
  get parentNode() { return this.parent; }
  get isConnected() { return Boolean(this.parent); }
  append(...children) { for (const child of children) { child.remove(); this.children.push(child); child.parent = this; } }
  replaceChildren(...children) { for (const child of this.children) child.parent = null; this.children = []; this.append(...children); }
  insertBefore(child, before) { child.remove(); const index = before ? this.children.indexOf(before) : this.children.length; this.children.splice(index, 0, child); child.parent = this; }
  remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
  contains(child) { return child === this || this.children.some(c => c.contains(child)); }
  setAttribute() {}
  addEventListener(key, fn) { this.events[key] = fn; }
  getBoundingClientRect() { return {top: this.top || 100}; }
}
async function main() {
  let selected = null, offline = false, page = input.first, opens = 0;
  const calls = [], scrolls = [];
  let duringPage = () => {};
  const document = {createElement: tag => new Node(tag), activeElement: null, documentElement: {scrollHeight: 1000}};
  const context = vm.createContext({document, console, Date, setTimeout: () => 1, clearTimeout: () => {},
    window: {innerHeight: 500, scrollY: 0, addEventListener() {}, removeEventListener() {},
      getSelection: () => ({isCollapsed: !selected, anchorNode: selected}), scrollBy: (...args) => scrolls.push(args)},
    api: async (path, value) => {
      assert.equal(path, '/api/detail'); calls.push(value);
      if (offline) throw new Error('offline');
      if (value.action === 'open') { opens++; return {token: 'owned'}; }
      if (value.action === 'freeze' || value.action === 'close') return {};
      duringPage();
      return JSON.parse(JSON.stringify(page));
    }});
  for (const path of ['render', 'session']) vm.runInContext(fs.readFileSync(`src/web/assets/${path}.js`, 'utf8'), context);
  vm.runInContext("globalThis.view = new SessionDetail.View(api, 'root-0000', 'live')", context);
  const view = context.view;
  view.attached = true;
  const parent = new Node('main');
  parent.append(view.root);
  const replace = parent.replaceChildren.bind(parent);
  let replacements = 0;
  parent.replaceChildren = (...children) => { replacements++; replace(...children); };
  view.attach(parent);
  assert.equal(replacements, 0, 'a health check must not detach the connected detail tree');
  await view.load();
  assert.equal(view.body.children.length, 50);
  assert.equal(view.offset, 0);
  assert.match(view.summary.textContent, /100 rows/);
  const total = input.first.result.view.prompt_blocks[0];
  assert.ok(view.summary.textContent.includes('CCost ' + total.display.total_ccost));
  assert.ok(view.summary.textContent.includes('Billed ' + total.display.billed_cost));
  assert.ok(view.summary.textContent.includes('Duration ' + total.display.duration_ms));
  assert.ok(view.context.textContent.includes(total.display.next_context));
  assert.equal(view.toggle.textContent, 'Freeze snapshot');
  assert.equal(view.latest.textContent, 'Jump to latest', 'initial capture is not new activity');
  const row = view.body.children[10], first = view.body.firstElementChild;
  view.follow = false;
  document.activeElement = view.next;
  page = input.changed;
  await view.load();
  assert.equal(view.body.children[10], row, 'unchanged rows keep canonical DOM identity');
  assert.equal(view.body.firstElementChild, first);
  assert.equal(document.activeElement, view.next, 'background updates never replace focused controls');
  assert.match(view.latest.textContent, /New\/changed activity/);
  assert.match(view.summary.textContent, /101 rows/);
  assert.equal(calls.at(-1).anchor, input.first.result.view.prompt_blocks[0].rows[0].id);
  // A selected row is never replaced by delayed model/warning/value changes.
  selected = row.children[0];
  const revision = view.revision;
  page = {...input.changed, revision: 'new-selection-revision'};
  page.result.view.prompt_blocks[0].rows[10].model_effort = 'late model / warning';
  await view.load();
  assert.equal(view.revision, revision);
  assert.equal(row.children[0], selected);
  selected = null;
  await view.load();
  assert.match(row.textContent, /late model/);
  offline = true;
  const retained = view.body.textContent;
  await view.load();
  assert.equal(view.body.textContent, retained);
  assert.match(view.status.textContent, /Last known result retained/);
  offline = false;
  await view.switchMode();
  assert.equal(view.mode, 'snapshot');
  assert.equal(view.toggle.textContent, 'Follow live');
  assert.match(view.status.textContent, /Snapshot · frozen until Refresh/);
  assert.ok(calls.some(c => c.action === 'freeze'));
  await view.switchMode();
  assert.equal(view.mode, 'live');
  assert.equal(opens, 2, 'entering Live requests current authoritative state');
  view.onScroll();
  assert.equal(view.follow, false);
  page = input.latest;
  await view.page(2 ** 52, true);
  assert.equal(view.body.children.length, 50);
  assert.equal(view.body.children.at(-1).dataset.id, input.latest.result.view.prompt_blocks[0].rows.at(-1).id);
  assert.ok(calls.at(-1).offset >= 2 ** 52);
  assert.equal(view.toggle, view.controls.children[0]);
  assert.equal(scrolls.length, 0, 'unchanged geometry does not move scroll');
  const scroll = view.root.children.find(node => node.className === 'table-scroll');
  scroll.scrollTop = 200; scroll.scrollLeft = 90;
  scroll.clientHeight = 300; scroll.scrollHeight = 1200;
  scroll.getBoundingClientRect = () => ({top: 100});
  for (const [index, node] of view.body.children.entries()) {
    node.getBoundingClientRect = () => ({top: 100 + index * 20 - scroll.scrollTop,
      bottom: 120 + index * 20 - scroll.scrollTop});
  }
  view.follow = false;
  // Movement while HTTP is in flight belongs to the user, not the old anchor.
  duringPage = () => { scroll.scrollTop = 400; };
  await view.load();
  assert.equal(scroll.scrollTop, 400);
  assert.equal(scrolls.length, 0, 'a delayed response must not undo user scrolling via the page');
  duringPage = () => {};
  const update = view.update.bind(view);
  const visible = view.body.children[20];
  view.update = data => {
    update(data);
    // Rows above the viewport grew; the visible row moved within the table.
    visible.getBoundingClientRect = () => ({top: 160, bottom: 180});
  };
  page = {...page, revision: 'geometry-change'};
  await view.load();
  assert.equal(scroll.scrollTop, 460, 'restore the visible anchor in the inner scroll owner');
  assert.equal(scroll.scrollLeft, 90, 'vertical retention preserves horizontal navigation');
  assert.equal(scrolls.length, 0, 'inner table changes must not move the document');
  view.follow = true;
  scroll.events.scroll();
  assert.equal(view.follow, false, 'browsing older rows in the internal table disables follow');
  console.log('PASS bounded DOM, canonical row identity, anchor, selection/focus, offline, mode transitions and latest');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
