'use strict';
// Native Save As is requested synchronously from the click, before source work.
const SessionExport = (() => {
  const help = 'Exports this session as native OpenCode JSON using sanitized mode.\nOpenCode redacts sensitive transcript and file data. Review the file before sharing.\nRunning sessions are saved as a point-in-time snapshot.\nSupported browsers open Save As; otherwise your browser handles the download.';
  const messages = {
    export_unavailable: 'Export unavailable for this source/version. CLI alternative: opencode session export <session-id> --sanitize.',
    export_source_changed: 'Source changed. Reopen this session before exporting.',
    export_source_denied: 'The selected OpenCode source denied export.',
    export_source_unavailable: 'The selected OpenCode source is unavailable. Retry when it is ready.',
    export_invalid_response: 'OpenCode returned an unsupported or incomplete export; no file was saved.',
    export_too_large: 'Export exceeds the 16 MiB limit; use the native CLI instead.',
    export_busy: 'Another session export is in progress. Try again.',
    detail_expired: 'Session selection expired. Reopen this session before exporting.'
  };
  function filename(title, id) {
    // Keep Unicode (including joined emoji), but never paths or invisible direction controls.
    const clean = typeof title === 'string' ? title.replace(/[<>:"/\\|?*\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b\u200e\u200f\u2028-\u202e\u2060-\u206f\ufeff\ud800-\udfff]/gu, '') : '';
    const encoder = new TextEncoder();
    let stem = '', bytes = 0;
    for (const character of clean) {
      bytes += encoder.encode(character).length;
      if (bytes > 200) break; // Conservative UTF-8 and UTF-16 component budget, including room for .json.
      stem += character;
    }
    stem = stem.replace(/[. ]+$/u, '');
    if (!stem.trim() || /^(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³]|conin\$|conout\$)(?: *\.|$)/i.test(stem)) {
      stem = /^ses_[A-Za-z0-9_-]{1,160}$/.test(id) ? `session-${id}` : 'session';
    }
    return `${stem}.json`;
  }
  class Action {
    constructor(api, id) {
      Object.assign(this, {api, id, token: null, available: false, operation: null, filename: filename(null, id)});
      this.root = ReportView.element('div', undefined, 'session-export');
      this.button = ReportView.element('button', 'Export Sanitized JSON'); this.button.type = 'button'; this.button.disabled = true;
      this.notice = ReportView.element('span', 'Export unavailable until the selected session is observed.');
      this.notice.setAttribute('role', 'status');
      this.root.append(this.button, this.notice);
      ContextHelp.attach(this.button, help);
      this.button.addEventListener('click', () => this.save());
    }
    update(token, available, title) {
      const changed = this.token !== token || this.available !== available;
      if (this.token !== token || !available) this.operation?.abort();
      this.token = token; this.available = available;
      this.filename = filename(token && available ? title : null, this.id);
      this.button.disabled = !token || !available || !!this.operation;
      if (changed && !this.operation) this.notice.textContent = available && token ? '' : messages.export_unavailable;
    }
    close() {
      this.token = null; this.available = false; this.filename = filename(null, this.id); this.operation?.abort();
      if (this.url) { URL.revokeObjectURL(this.url); this.url = null; }
      clearTimeout(this.revokeTimer);
      this.button.disabled = true;
    }
    async save() {
      if (this.operation || !this.token || !this.available) return;
      const operation = new AbortController(), token = this.token, name = this.filename;
      const focused = window.document?.activeElement === this.button;
      this.operation = operation; this.button.disabled = true;
      let writable;
      try {
        const handle = typeof window.showSaveFilePicker === 'function' ? await window.showSaveFilePicker({
          suggestedName: name,
          types: [{description: 'JSON session export', accept: {'application/json': ['.json']}}]
        }) : null;
        if (operation.signal.aborted || token !== this.token) return;
        this.notice.textContent = 'Exporting sanitized session…';
        const {blob} = await this.api('/api/detail/export', {token}, operation.signal, true);
        if (operation.signal.aborted || token !== this.token) return;
        if (handle) {
          writable = await handle.createWritable();
          if (operation.signal.aborted) { await writable.abort(); writable = null; return; }
          await writable.write(blob);
          if (operation.signal.aborted) { await writable.abort(); writable = null; return; }
          await writable.close(); writable = null;
          this.notice.textContent = 'Sanitized JSON saved. Review before sharing.';
        } else {
          const link = ReportView.element('a');
          this.url = URL.createObjectURL(blob); link.href = this.url; link.download = name;
          link.hidden = true; this.root.append(link); link.click(); link.remove();
          const url = this.url;
          this.revokeTimer = setTimeout(() => { URL.revokeObjectURL(url); if (this.url === url) this.url = null; }, 1000);
          this.notice.textContent = 'Sanitized download requested; your browser controls the save location. Review before sharing.';
        }
      } catch (error) {
        if (writable) await writable.abort().catch(() => {});
        if (!operation.signal.aborted) this.notice.textContent = error.name === 'AbortError' ? 'Export cancelled.' :
          messages[error.message] || 'Export failed; no completed export is claimed. Check the source and browser permissions.';
      } finally {
        if (this.operation === operation) this.operation = null;
        this.button.disabled = !this.token || !this.available;
        if (focused && token === this.token && window.document.activeElement === window.document.body) {
          this.button.focus({preventScroll: true});
          // Restoring picker focus is not a new request for keyboard help.
          ContextHelp.dismiss(this.button);
        }
      }
    }
  }
  return {Action};
})();
