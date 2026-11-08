// Per-document demand ownership. No source, second stream or real OS input.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
function events(value = {}) {
  const handlers = new Map();
  return Object.assign(value, {
    addEventListener(name, callback) { const list = handlers.get(name) || []; list.push(callback); handlers.set(name, list); },
    removeEventListener(name, callback) { handlers.set(name, (handlers.get(name) || []).filter(item => item !== callback)); },
    fire(name) { for (const callback of [...(handlers.get(name) || [])]) callback(); }
  });
}
function owner(hidden = false) {
  const timers = new Map(); let id = 0;
  return events({document: events({hidden}), timers,
    setTimeout(callback, milliseconds) { assert.equal(milliseconds, 30000); timers.set(++id, callback); return id; },
    clearTimeout(key) { timers.delete(key); }});
}
const main = owner(), mini = owner(); let serial = 0, writable = true;
const context = vm.createContext({window: main, crypto: {randomUUID: () => String(++serial).padStart(32, 'a')}});
vm.runInContext(fs.readFileSync('src/web/assets/data-demand.js', 'utf8'), context);
const Controller = vm.runInContext('DataDemand.Controller', context), sent = [];
const api = (path, value) => { assert.equal(path, '/api/interest'); sent.push(structuredClone(value)); return Promise.resolve({}); };
const state = {section: 'watch', history: true};
const legacy = new Controller(api, () => state, () => writable);
legacy.update(); assert.equal('history' in sent.at(-1), false, 'capability required'); legacy.close();
const full = new Controller(api, () => state, () => writable, {history: true});
full.update(); assert.equal(sent.at(-1).history, true);
state.history = false; full.update(); assert.equal(sent.at(-1).history, false, 'collapse withdraws history');
main.document.hidden = true; main.document.fire('visibilitychange');
assert.equal(sent.at(-1).visible, false); assert.equal(main.timers.size, 0);
const pip = new Controller(api, () => ({section: 'watch', history: true}), () => writable, {owner: mini, history: true});
pip.update(); assert.equal(sent.at(-1).visible, true); assert.equal(sent.at(-1).history, true);
assert.notEqual(pip.tab, full.tab); assert.equal(mini.timers.size, 1); assert.equal(main.timers.size, 0);
const late = [...mini.timers.values()][0]; late();
assert.equal(sent.at(-1).visible, true, 'hidden opener cannot suppress PiP renewal');
writable = false; pip.update(); assert.equal(mini.timers.size, 0);
const before = sent.length; late(); assert.equal(sent.length, before, 'nonwritable callbacks cannot renew');
writable = true; pip.update(); mini.document.hidden = true; mini.document.fire('visibilitychange');
assert.equal(sent.at(-1).visible, false);
mini.document.hidden = false; mini.document.fire('visibilitychange');
const stale = [...mini.timers.values()][0]; mini.fire('pagehide');
assert.equal(sent.at(-1).visible, false); assert.equal(mini.timers.size, 0);
const closed = sent.length; stale(); pip.update(); assert.equal(sent.length, closed, 'closed controller never rearms');
full.close(false); main.document.fire('visibilitychange'); assert.equal(sent.length, closed, 'changed instance does not write');
console.log('PASS independent Full/Mini history leases, visibility, expiry fallback and stale callbacks');
