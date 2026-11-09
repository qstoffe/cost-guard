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
  class Action {
    constructor(api, id) {
      Object.assign(this, {api, id, token: null, available: false, operation: null});
      this.root = ReportView.element('div', undefined, 'session-export');
      this.button = ReportView.element('button', 'Export Sanitized JSON'); this.button.type = 'button'; this.button.disabled = true;
      this.notice = ReportView.element('span', 'Export unavailable until the selected session is observed.');
      this.notice.setAttribute('role', 'status');
      this.root.append(this.button, this.notice);
      ContextHelp.attach(this.button, help);
      this.button.addEventListener('click', () => this.save());
    }
    update(token, available) {
      const changed = this.token !== token || this.available !== available;
      this.token = token; this.available = available;
      this.button.disabled = !token || !available || !!this.operation;
      if (changed && !this.operation) this.notice.textContent = available && token ? '' : messages.export_unavailable;
    }
    close() {
      this.token = null; this.operation?.abort();
      if (this.url) { URL.revokeObjectURL(this.url); this.url = null; }
      clearTimeout(this.revokeTimer);
      this.button.disabled = true;
    }
    async save() {
      if (this.operation || !this.token || !this.available) return;
      const operation = new AbortController(), token = this.token;
      const focused = window.document?.activeElement === this.button;
      this.operation = operation; this.button.disabled = true;
      let writable;
      try {
        const handle = typeof window.showSaveFilePicker === 'function' ? await window.showSaveFilePicker({
          suggestedName: `opencode-${this.id}-sanitized.json`,
          types: [{description: 'JSON session export', accept: {'application/json': ['.json']}}]
        }) : null;
        if (operation.signal.aborted) return;
        this.notice.textContent = 'Exporting sanitized session…';
        const {blob, filename} = await this.api('/api/detail/export', {token}, operation.signal, true);
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
          this.url = URL.createObjectURL(blob); link.href = this.url; link.download = filename;
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
