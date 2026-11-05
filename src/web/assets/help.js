'use strict';
// One text-only, noninteractive help surface per document, including Document PiP.
const ContextHelp = (() => {
  const entries = new WeakMap(), documents = new WeakMap();
  function controller(doc) {
    if (documents.has(doc)) return documents.get(doc);
    const win = doc.defaultView || window, panel = doc.createElement('div');
    panel.id = 'context-help'; panel.className = 'context-help'; panel.hidden = true;
    panel.setAttribute('role', 'tooltip'); panel.setAttribute('popover', 'manual');
    let active = null, blocked = null, timer, origin = null, keyboard = true;
    const cancel = () => { win.clearTimeout(timer); timer = undefined; };
    function position() {
      if (!active) return;
      if (!active.isConnected) { close(); return; }
      const rect = entries.get(active).pointerTarget.getBoundingClientRect(), box = panel.getBoundingClientRect();
      const width = win.innerWidth, height = win.innerHeight;
      const top = rect.bottom + box.height + 8 <= height ? rect.bottom + 4 : rect.top - box.height - 4;
      panel.style.left = Math.max(8, Math.min(rect.left, width - box.width - 8)) + 'px';
      panel.style.top = Math.max(8, Math.min(top, height - box.height - 8)) + 'px';
    }
    function refresh(target) {
      if (!active) return;
      if (!active.isConnected) { close(); return; }
      if (target && target !== active && !target.contains(active)) return;
      const content = entries.get(active).content;
      const value = String(typeof content === 'function' ? content() : content);
      if (panel.textContent !== value) panel.textContent = value;
      position();
    }
    function close(suppress = false) {
      cancel();
      if (active) {
        if (suppress) blocked = active;
        const ids = (active.getAttribute('aria-describedby') || '').split(/\s+/).filter(id => id && id !== panel.id);
        if (ids.length) active.setAttribute('aria-describedby', ids.join(' '));
        else active.removeAttribute('aria-describedby');
      }
      active = null; origin = null;
      panel.hidePopover?.(); panel.hidden = true;
    }
    function show(target, source) {
      cancel();
      if (target === blocked || !target.isConnected) return;
      if (active !== target) { close(); active = target; }
      // Hover must never take ownership from deliberate keyboard/touch help.
      if (origin !== 'pinned' && (source !== 'hover' || origin !== 'focus')) origin = source;
      if (panel.parentNode !== doc.body) doc.body.append(panel);
      panel.hidden = false;
      const ids = new Set((target.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
      ids.add(panel.id); target.setAttribute('aria-describedby', [...ids].join(' '));
      // Manual Popover avoids browser focus restoration and automatic reopening.
      if (panel.showPopover && !panel.matches(':popover-open')) panel.showPopover();
      refresh();
    }
    function leave(target) {
      if (blocked === target) blocked = null;
      exit(target);
    }
    function exit(target = active) {
      if (timer !== undefined || origin !== 'hover') return;
      timer = win.setTimeout(() => {
        timer = undefined;
        if (active === target && origin === 'hover') close();
      }, 150); // Lets the pointer cross the small gap into the help surface.
    }
    panel.addEventListener('pointerenter', cancel);
    panel.addEventListener('pointerleave', () => { if (active) exit(); });
    doc.addEventListener?.('keydown', event => {
      if (!['Shift', 'Control', 'Alt', 'Meta'].includes(event.key)) keyboard = true;
      if (event.key === 'Escape' && active) { close(true); event.preventDefault(); }
    }, true);
    doc.addEventListener?.('pointerdown', event => {
      keyboard = false;
      if (active && !active.contains(event.target) && !panel.contains(event.target)) close(true);
      if (blocked && !blocked.contains(event.target)) blocked = null;
    }, true);
    doc.addEventListener?.('focusin', event => {
      if (active && event.target !== active && !panel.contains(event.target)) close();
      if (blocked && event.target !== blocked) blocked = null;
    });
    // Document exit can arrive without a trigger leave (notably in Document PiP).
    // Pointer focus is NOT evidence of hover. No polling or work while closed.
    doc.addEventListener?.('pointerout', event => { if (!event.relatedTarget && active) exit(); }, true);
    doc.addEventListener?.('pointerleave', event => {
      if (active && (event.target === doc || event.target === doc.documentElement)) exit();
    }, true);
    doc.addEventListener?.('pointermove', event => {
      if (!active || origin !== 'hover') return;
      if (entries.get(active).pointerTarget.contains(event.target) || panel.contains(event.target)) cancel();
      else exit();
    }, true);
    win.addEventListener?.('blur', () => { if (origin === 'hover') close(); });
    doc.addEventListener?.('visibilitychange', () => { if (doc.visibilityState === 'hidden') close(true); });
    win.addEventListener?.('pagehide', () => close());
    win.addEventListener?.('resize', position);
    doc.addEventListener?.('scroll', position, true);
    // A route/row replacement may remove a hovered trigger without pointerleave.
    if (win.MutationObserver) new win.MutationObserver(() => {
      if (active && !active.isConnected) close();
    }).observe(doc.body, {childList: true, subtree: true});
    const value = {leave, refresh, click(target, passive) {
      if (!passive || active === target && origin === 'pinned') { close(); blocked = target; }
      else { blocked = null; show(target, 'pinned'); }
    }, enter(target, event) { if (event?.pointerType !== 'touch') show(target, 'hover'); },
    focus(target) { if (keyboard) show(target, 'focus'); },
    blur(target) {
      if (blocked === target && doc.hasFocus?.() !== false) blocked = null;
      if (active === target) close();
    }};
    documents.set(doc, value); return value;
  }
  function attach(target, content, passive = false, pointerTarget = target) {
    const entry = entries.get(target);
    if (entry) { entry.content = content; refresh(target); return target; }
    entries.set(target, {content, pointerTarget}); target.removeAttribute('title');
    const owner = () => controller(target.ownerDocument);
    pointerTarget.addEventListener('pointerenter', event => owner().enter(target, event));
    pointerTarget.addEventListener('pointerleave', () => owner().leave(target));
    target.addEventListener('focus', () => owner().focus(target));
    target.addEventListener('blur', () => owner().blur(target));
    target.addEventListener('click', () => owner().click(target, passive));
    return target;
  }
  function button(label, content, doc = document) {
    const target = doc.createElement('button'); target.type = 'button';
    target.className = 'help-trigger'; target.textContent = label;
    return attach(target, content, true);
  }
  // Sorting keeps its original click/focus target; only the visible label owns hover.
  function heading(action, content) {
    const label = action.ownerDocument.createElement('span');
    label.className = 'help-label'; label.textContent = action.textContent;
    action.textContent = ''; action.append(label); action.className = 'help-action';
    attach(action, content, false, label); return label;
  }
  function beside(parent, content, label = 'About this value') {
    const target = button('', content, parent.ownerDocument);
    target.className += ' help-cue'; target.setAttribute('aria-label', label);
    parent.append(target); return target;
  }
  function refresh(target) { documents.get(target.ownerDocument)?.refresh(target); }
  return {attach, button, heading, beside, refresh};
})();
