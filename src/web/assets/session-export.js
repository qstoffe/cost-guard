'use strict';
// Native Save As is requested synchronously from the click, before source work.
const SessionExport = (() => {
  const help = 'Export this session and all nested subagents as JSON in one ZIP. Secret masking is best effort: ' +
    'the ZIP is not guaranteed secret-free or anonymous. Review it before sharing.';
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
      Object.assign(this, {api, id, token: null, available: false, operation: null, filename: fallbackName(id)});
      this.root = ReportView.element('div', undefined, 'session-export');
      this.button = ReportView.element('button', 'Export Session Analysis ZIP'); this.button.type = 'button'; this.button.disabled = true;
      this.notice = ReportView.element('span', '');
      this.notice.setAttribute('role', 'status');
      this.root.append(this.button, this.notice);
      ContextHelp.attach(this.button, help);
      this.button.addEventListener('click', () => this.save());
    }
    update(token, available, exportName) {
      const changed = this.token !== token || this.available !== available;
      if (this.token !== token || !available) this.operation?.abort();
      this.token = token; this.available = available;
      this.filename = token && available && typeof exportName === 'string' && exportName.endsWith('.zip')
        ? exportName : fallbackName(this.id);
      this.button.disabled = !token || !available || !!this.operation;
      if (changed && !this.operation) this.notice.textContent = '';
    }
    close() {
      this.token = null; this.available = false; this.filename = fallbackName(this.id); this.operation?.abort();
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
          types: [{description: 'Session analysis ZIP', accept: {'application/zip': ['.zip']}}]
        }) : null;
        if (operation.signal.aborted || token !== this.token) return;
        this.notice.textContent = 'Exporting session tree…';
        const {blob, filename} = await this.api('/api/detail/export', {token}, operation.signal, true);
        if (operation.signal.aborted || token !== this.token) return;
        if (filename !== `opencode-${this.id}-analysis.zip`) throw new Error('export_invalid_response');
        if (handle) {
          writable = await handle.createWritable();
          if (operation.signal.aborted) { await writable.abort(); writable = null; return; }
          await writable.write(blob);
          if (operation.signal.aborted) { await writable.abort(); writable = null; return; }
          await writable.close(); writable = null;
          if (!operation.signal.aborted) this.notice.textContent = 'Analysis ZIP saved. Review before sharing.';
        } else {
          const link = ReportView.element('a');
          this.url = URL.createObjectURL(blob); link.href = this.url; link.download = name;
          link.hidden = true; this.root.append(link); link.click(); link.remove();
          const url = this.url;
          this.revokeTimer = setTimeout(() => { URL.revokeObjectURL(url); if (this.url === url) this.url = null; }, 1000);
          this.notice.textContent = 'Analysis ZIP download requested; your browser controls the save location. Review before sharing.';
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
