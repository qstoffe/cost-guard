'use strict';
// One noninteractive text surface per document; only live Duration has a safe span.
const ContextHelp = (() => {
  const entries = new WeakMap(), documents = new WeakMap();
  const durations = new WeakSet();
  function runningDuration(before, duration, after) {
    const value = {before, duration, after}; durations.add(value); return value;
  }
  function fragmentText(node, text) {
    if (node.textContent === text) return;
    const leaf = node.nodeType === 3 ? node : node.firstChild;
    if (leaf?.nodeType !== 3) { node.textContent = text; return; }
    const selection = node.ownerDocument.getSelection?.(), length = leaf.length;
    const anchor = selection?.anchorNode, focus = selection?.focusNode;
    const start = selection?.anchorOffset, end = selection?.focusOffset;
    leaf.data = text;
    if (anchor === leaf || focus === leaf) {
      const offset = value => value === length ? text.length : Math.min(value, text.length);
      selection.setBaseAndExtent(anchor, anchor === leaf ? offset(start) : start,
        focus, focus === leaf ? offset(end) : end);
    }
  }
  const HOVER_DELAY = 600, HOVER_CHECK = 1000, HOVER_IDLE = 30000;
  function controller(doc) {
    if (documents.has(doc)) return documents.get(doc);
    const win = doc.defaultView || window, panel = doc.createElement('div');
    panel.id = 'context-help'; panel.className = 'context-help'; panel.hidden = true;
    panel.setAttribute('role', 'tooltip'); panel.setAttribute('popover', 'manual');
    let active = null, blocked = null, timer, opening, pending = null, origin = null, keyboard = true, fragments = null;
    let watchdog, hoverDeadline = 0, pointer = null;
    const now = () => win.performance?.now() ?? Date.now();
    const cancel = () => { win.clearTimeout(timer); timer = undefined; };
    const cancelOpening = () => { win.clearTimeout(opening); opening = undefined; pending = null; };
    const cancelWatchdog = () => { win.clearTimeout(watchdog); watchdog = undefined; };
    const hovered = node => node.matches?.(':hover');
    const valid = target => target?.ownerDocument === doc && target.isConnected &&
      entries.get(target).pointerTarget.ownerDocument === doc && entries.get(target).pointerTarget.isConnected &&
      doc.visibilityState !== 'hidden' && !win.closed;
    function pointerInteraction(event) {
      if (!event?.isTrusted || event.pointerType === 'touch') return;
      hoverDeadline = now() + HOVER_IDLE;
      pointer = Number.isFinite(event.clientX) && Number.isFinite(event.clientY) ?
        {x: event.clientX, y: event.clientY} : null;
    }
    function hoverState(pointerTarget) {
      const trigger = hovered(pointerTarget), surface = hovered(panel);
      // A remembered point is not a current OS cursor position. Use hit testing
      // only to detect layout/occlusion contradictions, never to override a
      // genuine negative hover state or invent presence from stale coordinates.
      if (trigger === false && surface === false) return false;
      if (trigger !== true && surface !== true) return null;
      const hit = pointer && doc.elementFromPoint?.(pointer.x, pointer.y);
      if (hit && !pointerTarget.contains(hit) && !panel.contains(hit)) return false;
      return true;
    }
    function watchHover() {
      if (origin !== 'hover') { cancelWatchdog(); return; }
      if (watchdog !== undefined) return;
      const target = active, pointerTarget = entries.get(target).pointerTarget;
      const ticket = win.setTimeout(() => {
        if (watchdog !== ticket) return;
        watchdog = undefined;
        if (active !== target || origin !== 'hover') return;
        if (!valid(target) || entries.get(target).pointerTarget !== pointerTarget ||
            panel.hidden || !panel.isConnected) { close(); return; }
        const state = hoverState(pointerTarget);
        // Stationary native hover is not abandonment. Only an inconclusive
        // browser query uses the bounded fallback. Stale positive CSS + no OS
        // exit is fundamentally indistinguishable from real stationary reading.
        if (state === false) exit(target);
        else if (state === null && now() >= hoverDeadline) { close(); return; }
        watchHover();
      }, HOVER_CHECK);
      watchdog = ticket;
    }
    function position() {
      if (!active) return;
      if (!active.isConnected) { close(); return; }
      const width = win.innerWidth, height = win.innerHeight;
      // Top-layer help inherits CSS zoom; geometry is in viewport pixels, styles are not.
      const zoom = panel.currentCSSZoom || 1;
      panel.style.maxWidth = 'min(34rem, ' + (width - 16) / zoom + 'px)';
      panel.style.maxHeight = (height - 16) / zoom + 'px';
      const rect = entries.get(active).pointerTarget.getBoundingClientRect(), box = panel.getBoundingClientRect();
      const top = rect.bottom + box.height + 8 <= height ? rect.bottom + 4 : rect.top - box.height - 4;
      panel.style.left = Math.max(8, Math.min(rect.left, width - box.width - 8)) / zoom + 'px';
      panel.style.top = Math.max(8, Math.min(top, height - box.height - 8)) / zoom + 'px';
    }
    function refresh(target) {
      if (!active) return;
      if (!active.isConnected) { close(); return; }
      if (target && target !== active && !target.contains(active)) return;
      const content = entries.get(active).content;
      const value = typeof content === 'function' ? content() : content;
      if (durations.has(value)) {
        if (!fragments) {
          const before = doc.createTextNode(''), duration = doc.createElement('span'), after = doc.createTextNode('');
          duration.className = 'context-help-running-duration';
          panel.replaceChildren(before, duration, after); fragments = [before, duration, after];
        }
        [value.before, value.duration, value.after].forEach((text, index) => {
          fragmentText(fragments[index], text);
        });
      } else {
        const text = String(value);
        if (!text) { close(); return; }
        if (fragments || panel.textContent !== text) panel.textContent = text;
        fragments = null;
      }
      position();
    }
    function close(suppress = false) {
      cancel();
      cancelWatchdog();
      if (suppress && pending) blocked = pending;
      cancelOpening();
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
      cancelOpening();
      if (target === blocked || !valid(target)) return;
      const content = entries.get(target).content;
      if (!(typeof content === 'function' ? content() : content)) return;
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
      if (active) watchHover();
    }
    function leave(target) {
      if (pending === target) cancelOpening();
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
    panel.addEventListener('pointerenter', event => { pointerInteraction(event); cancel(); });
    panel.addEventListener('pointerleave', () => { if (active) exit(); });
    doc.addEventListener?.('keydown', event => {
      if (!['Shift', 'Control', 'Alt', 'Meta'].includes(event.key)) keyboard = true;
      if (event.key === 'Escape' && (active || pending)) { close(true); event.preventDefault(); }
    }, true);
    doc.addEventListener?.('pointerdown', event => {
      keyboard = false;
      if (active && (entries.get(active).pointerTarget.contains(event.target) || panel.contains(event.target))) pointerInteraction(event);
      cancelOpening();
      if (active && !active.contains(event.target) && !panel.contains(event.target)) close(true);
      if (blocked && !blocked.contains(event.target)) blocked = null;
    }, true);
    doc.addEventListener?.('focusin', event => {
      if (pending && event.target !== pending) cancelOpening();
      if (active && event.target !== active && !panel.contains(event.target)) close();
      if (blocked && event.target !== blocked) blocked = null;
    });
    // Document exit can arrive without a trigger leave (notably in Document PiP).
    // Pointer focus is NOT evidence of hover. No polling or work while closed.
    doc.addEventListener?.('pointerout', event => { if (!event.relatedTarget) { cancelOpening(); exit(); } }, true);
    doc.addEventListener?.('pointerleave', event => {
      if (event.target === doc || event.target === doc.documentElement) { cancelOpening(); exit(); }
    }, true);
    doc.addEventListener?.('pointermove', event => {
      if (pending && !entries.get(pending).pointerTarget.contains(event.target)) cancelOpening();
      if (!active || origin !== 'hover') return;
      if (entries.get(active).pointerTarget.contains(event.target) || panel.contains(event.target)) {
        pointerInteraction(event); cancel();
      }
      else exit();
    }, true);
    win.addEventListener?.('blur', () => { cancelOpening(); if (origin === 'hover') close(); });
    doc.addEventListener?.('visibilitychange', () => { if (doc.visibilityState === 'hidden') close(true); });
    win.addEventListener?.('pagehide', () => close());
    win.addEventListener?.('resize', position);
    doc.addEventListener?.('scroll', position, true);
    // A route/row replacement may remove a hovered trigger without pointerleave.
    if (win.MutationObserver) new win.MutationObserver(() => {
      if (pending && !valid(pending)) cancelOpening();
      if (active && !valid(active)) close();
    }).observe(doc.body, {childList: true, subtree: true});
    const value = {leave, refresh, dismiss(target) {
      if (active && target.contains(active) || pending && target.contains(pending)) close(true);
    }, click(target, passive) {
      if (!passive || active === target && origin === 'pinned') { close(); blocked = target; }
      else { blocked = null; show(target, 'pinned'); }
    }, enter(target, event) {
      if (event?.pointerType === 'touch' || target === blocked || pending === target) return;
      pointerInteraction(event);
      if (active === target) { cancel(); return; }
      cancelOpening();
      if (origin === 'focus' || origin === 'pinned') return;
      keyboard = false;
      close(); pending = target; hoverDeadline = now() + HOVER_IDLE;
      const ticket = win.setTimeout(() => {
        if (opening !== ticket || pending !== target) return;
        if (!valid(target) || hovered(entries.get(target).pointerTarget) === false) { cancelOpening(); return; }
        show(target, 'hover');
      }, HOVER_DELAY);
      opening = ticket;
    },
    focus(target) { if (keyboard) show(target, 'focus'); },
    blur(target) {
      if (blocked === target && doc.hasFocus?.() !== false) blocked = null;
      if (pending === target) cancelOpening();
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
    target.addEventListener('click', () => {
      const selection = target.ownerDocument.getSelection?.();
      if (passive && selection && !selection.isCollapsed &&
          (target.contains(selection.anchorNode) || target.contains(selection.focusNode))) return;
      owner().click(target, passive);
    });
    return target;
  }
  function button(label, content, doc = document) {
    const target = doc.createElement('button'); target.type = 'button';
    target.className = 'help-trigger'; target.textContent = label;
    return attach(target, content, true);
  }
  // Sorting keeps its original click/focus target; only the visible label owns hover.
  function heading(action, content, passive = false) {
    const label = action.ownerDocument.createElement('span');
    label.className = 'help-label'; label.textContent = action.textContent;
    action.textContent = ''; action.append(label); action.className = 'help-action';
    attach(action, content, passive, label); return label;
  }
  function value(target, content) {
    if (entries.has(target)) return attach(target, content, true);
    target.className = (target.className || '') + ' help-value'; target.tabIndex = 0;
    target.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault(); controller(target.ownerDocument).click(target, true);
      }
    });
    return attach(target, content, true);
  }
  function refresh(target) { documents.get(target.ownerDocument)?.refresh(target); }
  function dismiss(target) { documents.get(target.ownerDocument)?.dismiss(target); }
  return {attach, button, heading, value, refresh, dismiss, runningDuration, HOVER_DELAY};
})();
