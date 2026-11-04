'use strict';
// One text-only, noninteractive help surface per document, including Document PiP.
const ContextHelp = (() => {
  const entries = new WeakMap(), documents = new WeakMap();
  function controller(doc) {
    if (documents.has(doc)) return documents.get(doc);
    const win = doc.defaultView || window, panel = doc.createElement('div');
    panel.id = 'context-help'; panel.className = 'context-help'; panel.hidden = true;
    panel.setAttribute('role', 'tooltip'); panel.setAttribute('popover', 'manual');
    let active = null, blocked = null, timer, pinned = false, overPanel = false;
    const cancel = () => win.clearTimeout(timer);
    function position() {
      if (!active) return;
      if (!active.isConnected) { close(); return; }
      const rect = active.getBoundingClientRect(), box = panel.getBoundingClientRect();
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
      active = null; pinned = overPanel = false;
      panel.hidePopover?.(); panel.hidden = true;
    }
    function show(target, pin = false) {
      cancel();
      if (target === blocked || !target.isConnected) return;
      if (active !== target) { close(); active = target; }
      pinned ||= pin;
      if (panel.parentNode !== doc.body) doc.body.append(panel);
      panel.hidden = false;
      const ids = new Set((target.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
      ids.add(panel.id); target.setAttribute('aria-describedby', [...ids].join(' '));
      // Manual Popover avoids browser focus restoration and automatic reopening.
      if (panel.showPopover && !panel.matches(':popover-open')) panel.showPopover();
      refresh();
    }
    function leave(target) {
      if (blocked === target && doc.activeElement !== target) blocked = null;
      cancel(); timer = win.setTimeout(() => {
        if (active === target && !pinned && !overPanel && doc.activeElement !== target) close();
      }, 150); // Lets the pointer cross the small gap into the help surface.
    }
    panel.addEventListener('pointerenter', () => { overPanel = true; cancel(); });
    panel.addEventListener('pointerleave', () => { overPanel = false; if (active) leave(active); });
    doc.addEventListener?.('keydown', event => {
      if (event.key === 'Escape' && active) { close(true); event.preventDefault(); }
    }, true);
    doc.addEventListener?.('pointerdown', event => {
      if (active && !active.contains(event.target) && !panel.contains(event.target)) close(true);
      if (blocked && !blocked.contains(event.target)) blocked = null;
    }, true);
    doc.addEventListener?.('focusin', event => {
      if (active && event.target !== active && !panel.contains(event.target)) close();
      if (blocked && event.target !== blocked) blocked = null;
    });
    win.addEventListener?.('resize', position);
    doc.addEventListener?.('scroll', position, true);
    // A route/row replacement may remove a hovered trigger without pointerleave.
    if (win.MutationObserver) new win.MutationObserver(() => {
      if (active && !active.isConnected) close();
    }).observe(doc.body, {childList: true, subtree: true});
    const value = {show, close, leave, refresh, click(target) {
      if (active === target && pinned) close(true);
      else { blocked = null; show(target, true); }
    }, enter(target) { if (blocked === target && doc.activeElement !== target) blocked = null; show(target); },
    blur(target) { if (blocked === target) blocked = null; pinned = false; leave(target); }};
    documents.set(doc, value); return value;
  }
  function attach(target, content, passive = false) {
    const entry = entries.get(target);
    if (entry) { entry.content = content; refresh(target); return target; }
    entries.set(target, {content}); target.removeAttribute('title');
    const owner = () => controller(target.ownerDocument);
    target.addEventListener('pointerenter', () => owner().enter(target));
    target.addEventListener('pointerleave', () => owner().leave(target));
    target.addEventListener('focus', () => owner().show(target));
    target.addEventListener('blur', () => owner().blur(target));
    target.addEventListener('click', () => passive ? owner().click(target) : owner().show(target));
    return target;
  }
  function button(label, content, doc = document) {
    const target = doc.createElement('button'); target.type = 'button';
    target.className = 'help-trigger'; target.textContent = label;
    return attach(target, content, true);
  }
  function beside(parent, content, label = 'About this value') {
    const target = button('', content, parent.ownerDocument);
    target.className += ' help-cue'; target.setAttribute('aria-label', label);
    parent.append(target); return target;
  }
  function refresh(target) { documents.get(target.ownerDocument)?.refresh(target); }
  return {attach, button, beside, refresh};
})();
