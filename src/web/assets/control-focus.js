'use strict';
// One event-driven modality owner per document, including Document PiP. Native
// focus remains intact; only a pointer-owned control's extra focus ring is gated.
const ControlFocus = (() => {
  const documents = new WeakMap();
  const selector = 'button, a[href], [role="button"], summary, input[type="checkbox"], input[type="radio"], .help-value';
  function install(doc) {
    if (documents.has(doc)) return;
    const state = {pointer: false};
    documents.set(doc, state);
    const control = target => target?.closest?.(selector);
    doc.addEventListener('pointerdown', event => {
      state.pointer = true;
      control(event.target)?.setAttribute('data-pointer-focus', '');
    }, true);
    doc.addEventListener('keydown', event => {
      if (['Shift', 'Control', 'Alt', 'Meta'].includes(event.key) || event.altKey || event.ctrlKey || event.metaKey) return;
      state.pointer = false;
      control(doc.activeElement)?.removeAttribute('data-pointer-focus');
    }, true);
    doc.addEventListener('focusin', event => {
      const node = control(event.target);
      if (state.pointer) node?.setAttribute('data-pointer-focus', '');
      else node?.removeAttribute('data-pointer-focus');
    }, true);
  }
  function keyboard(doc) { return !documents.get(doc)?.pointer; }
  function retain(node) {
    const doc = node.ownerDocument;
    let restore = doc.activeElement === node && keyboard(doc);
    const moved = event => { if (event.target !== node) restore = false; };
    const events = ['focusin', 'pointerdown', 'keydown'];
    for (const event of events) doc.addEventListener(event, moved, true);
    return () => {
      for (const event of events) doc.removeEventListener(event, moved, true);
      if (restore && node.isConnected && !node.disabled && doc.activeElement === doc.body) node.focus({preventScroll:true});
      restore = false;
    };
  }
  return {install, keyboard, retain};
})();
ControlFocus.install(document);
