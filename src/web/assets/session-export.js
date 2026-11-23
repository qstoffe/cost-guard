'use strict';
const SessionExport = (() => {
  const help = 'Export this session and all nested sub-agents as JSON in one ZIP file.\n\n' +
    'We attempt to mask secrets in the exported files, but this is a best-effort process and there is no guarantee that all secrets will be masked. Review it before sharing.';
  const readyLifetime = 60000;
  const messages = {
    export_unavailable: 'Analysis ZIP export is unavailable for this source or OpenCode version.',
    export_source_changed: 'Source changed. Reopen this session before exporting.',
    export_source_denied: 'The selected OpenCode source denied export.',
    export_source_unavailable: 'The selected OpenCode source is unavailable. Retry when it is ready.',
    export_invalid_response: 'The export response was invalid or incomplete; no complete ZIP was saved.',
    export_descendant_unavailable: 'A subagent session could not be retrieved; no complete ZIP was saved.',
    export_timed_out: 'Session export timed out; no complete ZIP was saved.',
    export_cancelled: 'Export cancelled.',
    export_too_large: 'This session tree exceeds the export size limit; no complete ZIP was saved.',
    export_busy: 'Another session export is in progress. Try again.',
    detail_expired: 'Session selection expired. Reopen this session before exporting.'
  };
  function fallbackName(id) {
    return /^ses_[A-Za-z0-9_-]{1,160}$/.test(id) ? `session-${id}.zip` : 'session.zip';
  }
  class Action {
    constructor(api, id) {
      Object.assign(this, {api, id, token: null, available: false, operation: null, prepared: null,
        url: null, filename: fallbackName(id)});
      this.root = ReportView.element('div', undefined, 'session-export');
      this.button = ReportView.element('button', 'Export Session Analysis ZIP'); this.button.type = 'button'; this.button.disabled = true;
      this.spinner = ReportView.element('span', undefined, 'metric-spinner');
      this.spinner.hidden = true;
      this.spinner.setAttribute('aria-hidden', 'true');
      this.notice = ReportView.element('span', '');
      this.notice.setAttribute('role', 'status');
      this.root.append(this.button, this.spinner, this.notice);
      ContextHelp.attach(this.button, help);
      this.button.addEventListener('click', () => this.activate());
    }
    update(token, available, exportName) {
      const changed = this.token !== token || this.available !== available;
      if (changed) {
        this.operation?.abort();
        this.clearPrepared();
        this.clearDownload();
        this.notice.textContent = '';
        this.spinner.hidden = true;
      }
      this.token = token; this.available = available;
      this.filename = token && available && typeof exportName === 'string' && exportName.endsWith('.zip')
        ? exportName : fallbackName(this.id);
      this.renderButton();
    }
    close() {
      this.update(null, false);
    }
    renderButton() {
      this.button.textContent = this.prepared ? 'Save ZIP' : 'Export Session Analysis ZIP';
      this.button.disabled = !this.token || !this.available || !!this.operation;
    }
    clearPrepared() {
      clearTimeout(this.expiryTimer);
      this.prepared = null;
    }
    clearDownload() {
      clearTimeout(this.revokeTimer);
      if (this.url) { URL.revokeObjectURL(this.url); this.url = null; }
    }
    async activate() {
      if (this.operation || !this.token || !this.available) return;
      const operation = new AbortController(), token = this.token, name = this.filename;
      const saving = this.prepared !== null;
      const focused = window.document?.activeElement === this.button;
      this.operation = operation; this.button.disabled = true;
      try {
        if (saving) {
          clearTimeout(this.expiryTimer);
          this.notice.textContent = '';
          await this.save(operation.signal);
        } else await this.prepare(token, name, operation.signal);
      } catch (error) {
        if (!operation.signal.aborted) this.notice.textContent = error.name === 'AbortError' ? 'Export cancelled.' :
          messages[error.message] || 'Export failed; no completed export is claimed. Check the source and browser permissions.';
      } finally {
        if (saving) this.clearPrepared();
        this.operation = null;
        this.spinner.hidden = true;
        this.renderButton();
        if (focused && !operation.signal.aborted && window.document.activeElement === window.document.body) {
          this.button.focus({preventScroll: true});
          // Restoring picker focus is not a new request for keyboard help.
          ContextHelp.dismiss(this.button);
        }
      }
    }
    async prepare(token, name, signal) {
      this.spinner.hidden = false;
      this.notice.textContent = 'Preparing session analysis ZIP…';
      const {blob, filename} = await this.api('/api/detail/export', {token}, signal, true);
      if (signal.aborted) return;
      if (filename !== `opencode-${this.id}-analysis.zip`) throw new Error('export_invalid_response');
      this.prepared = {blob, name};
      this.notice.textContent = 'Analysis ZIP ready to save.';
      this.expiryTimer = setTimeout(() => {
        this.clearPrepared();
        this.renderButton();
        this.notice.textContent = 'Prepared ZIP expired. Export again to save a new ZIP.';
      }, readyLifetime);
    }
    async save(signal) {
      const {name} = this.prepared;
      if (typeof window.showSaveFilePicker !== 'function') {
        this.clearDownload();
        const link = ReportView.element('a');
        this.url = URL.createObjectURL(this.prepared.blob); link.href = this.url; link.download = name;
        this.revokeTimer = setTimeout(() => this.clearDownload(), 1000);
        link.hidden = true; this.root.append(link);
        try { link.click(); } finally { link.remove(); }
        this.notice.textContent = 'Analysis ZIP download requested; your browser controls the save location. Review before sharing.';
        return;
      }
      // The Save ZIP click supplies fresh activation. No source request follows it.
      const handle = await window.showSaveFilePicker({
        suggestedName: name,
        types: [{description: 'Session analysis ZIP', accept: {'application/zip': ['.zip']}}]
      });
      if (signal.aborted) return;
      const writable = await handle.createWritable();
      let committed = false;
      try {
        if (signal.aborted) return;
        await writable.write(this.prepared.blob);
        if (signal.aborted) return;
        await writable.close();
        committed = true;
        if (!signal.aborted) this.notice.textContent = 'Analysis ZIP saved. Review before sharing.';
      } finally {
        if (!committed) await writable.abort().catch(() => {});
      }
    }
  }
  return {Action};
})();
