'use strict';
const SessionExport = (() => {
  const help = 'Export this session and all nested sub-agents as JSON in one ZIP file.\n\n' +
    'We attempt to mask secrets in the exported files, but this is a best-effort process and there is no guarantee that all secrets will be masked. Review it before sharing.';
  const chunkBytes = 1024 * 1024;
  const messages = {
    export_unavailable: 'Analysis ZIP export is unavailable for this source or OpenCode version.',
    export_source_changed: 'Source changed. Reopen this session before exporting.',
    export_source_denied: 'The selected OpenCode source denied export.',
    export_source_unavailable: 'The selected OpenCode source is unavailable. Retry when it is ready.',
    export_invalid_response: 'The export response was invalid or incomplete; no complete ZIP was saved.',
    export_descendant_unavailable: 'A subagent session could not be retrieved; no complete ZIP was saved.',
    export_timed_out: 'An export transfer timed out; no complete ZIP was saved.',
    export_cancelled: 'Export cancelled.',
    export_too_large: 'This session tree exceeds the export size limit; no complete ZIP was saved.',
    export_busy: 'Another session export is in progress. Try again.',
    export_retiring: 'The previous export is still cancelling. Try again.',
    detail_expired: 'Session selection expired. Try again after the session has reconnected.'
  };
  const el = (...args) => ReportView.element(...args);

  function wait(ms, signal) {
    signal.throwIfAborted();
    return new Promise((resolve, reject) => {
      const abort = () => { clearTimeout(timer); reject(signal.reason); };
      const timer = setTimeout(() => {
        signal.removeEventListener('abort', abort); resolve();
      }, ms);
      signal.addEventListener('abort', abort, {once: true});
    });
  }

  class Action {
    constructor(api, id) {
      Object.assign(this, {api, id, token: null, state: 'pending', operation: null,
        filename: null, feedback: 'Checking export availability…'});
      this.root = el('div', undefined, 'session-export');
      this.button = el('button', 'Export Session Analysis ZIP');
      this.button.type = 'button'; this.button.disabled = true;
      this.spinner = el('span', undefined, 'metric-spinner');
      this.spinner.hidden = true;
      this.spinner.setAttribute('aria-hidden', 'true');
      this.button.append(this.spinner);
      this.cancel = el('button', 'Cancel export'); this.cancel.type = 'button'; this.cancel.hidden = true;
      this.notice = el('span', this.feedback);
      this.notice.setAttribute('role', 'status');
      this.root.append(this.button, this.cancel, this.notice);
      ContextHelp.attach(this.button, help);
      this.button.addEventListener('click', () => this.activate());
      this.cancel.addEventListener('click', () => this.operation?.controller.abort());
    }
    update(token, state, scope, exportName, nameState) {
      this.token = token;
      this.state = state;
      this.scope = scope;
      this.filename = state === 'ready' && typeof exportName === 'string' && exportName.endsWith('.zip')
        ? exportName : null;
      this.nameState = state === 'ready' && !this.filename ? nameState || 'pending' : null;
      const feedback = this.availabilityFeedback();
      if (this.feedback !== feedback && !this.operation) this.notice.textContent = feedback;
      this.feedback = feedback;
      this.renderButton();
    }
    availabilityFeedback() {
      if (this.state === 'pending') return 'Checking export availability…';
      if (this.state === 'unavailable') return messages.export_unavailable;
      if (this.nameState === 'unavailable') return 'Could not resolve the session title for export.';
      return this.nameState === 'pending' ? 'Waiting for the session title before export…' : '';
    }
    close() {
      this.operation?.controller.abort();
      if (this.operation) this.operation.detached = true;
      this.update(null, 'pending');
    }
    renderButton() {
      this.button.disabled = !this.token || this.state !== 'ready' || !this.scope || !this.filename || !!this.operation;
      this.spinner.hidden = !this.operation;
    }
    async activate() {
      if (this.operation || this.button.disabled) return;
      const operation = {controller: new AbortController(), id: crypto.randomUUID().replaceAll('-', '')};
      const {signal} = operation.controller;
      const name = this.filename, scope = this.scope, token = this.token;
      const focused = document.activeElement === this.button;
      this.operation = operation;
      ContextHelp.dismiss(this.button);
      this.renderButton();
      let requested = false;
      try {
        let handle;
        if (typeof window.showSaveFilePicker === 'function') {
          this.notice.textContent = 'Choose where to save the analysis ZIP…';
          handle = await window.showSaveFilePicker({
            suggestedName: name,
            types: [{description: 'Session analysis ZIP', accept: {'application/zip': ['.zip']}}]
          });
        }
        signal.throwIfAborted();
        this.cancel.hidden = false;
        this.notice.textContent = 'Preparing session analysis ZIP…';
        requested = true;
        // Await admission before requesting cancellation, even if the user cancels first.
        await this.start(operation, scope, token);
        signal.throwIfAborted();
        const size = await this.ready(operation);
        this.notice.textContent = 'Transferring session analysis ZIP…';
        const blob = await this.transfer(operation, size);
        signal.throwIfAborted();
        if (handle) await this.save(handle, blob, signal);
        else this.download(blob, name);
      } catch (error) {
        if (!operation.detached) this.notice.textContent = signal.aborted || error.name === 'AbortError' ?
          messages.export_cancelled : messages[error.message] ||
          'Export failed; no completed export is claimed. Check the source and browser permissions.';
      } finally {
        this.cancel.hidden = true;
        if (requested) await this.request(operation, 'cancel').catch(() => {});
        this.operation = null;
        if (!operation.detached && this.feedback) this.notice.textContent = this.feedback;
        this.renderButton();
        if (focused && !operation.detached && document.activeElement === document.body && !this.button.disabled) {
          this.button.focus({preventScroll: true});
          ContextHelp.dismiss(this.button);
        }
      }
    }
    request(operation, action, value = {}, signal) {
      return this.api('/api/detail/export', {action, id: operation.id, ...value}, signal, action === 'chunk');
    }
    async start(operation, scope, token) {
      const {signal} = operation.controller;
      const admit = async token => {
        for (let attempt = 0; ; attempt++) {
          signal.throwIfAborted();
          try { return await this.request(operation, 'start', {token, scope}); }
          catch (error) {
            // The server explicitly declined admission while releasing our last job.
            if (error.message !== 'export_retiring' || attempt >= 4) throw error;
            await wait(150 * 2 ** attempt, signal);
          }
        }
      };
      try {
        await admit(this.scope === scope ? this.token || token : token);
      } catch (error) {
        if (error.message !== 'detail_expired') throw error;
        // A native picker can remain open beyond an ordinary detail lease.
        signal.throwIfAborted();
        const fresh = await this.api('/api/detail', {action: 'open', session_id: this.id, mode: 'live'});
        try {
          signal.throwIfAborted();
          if (fresh.export_scope !== scope) throw new Error('export_source_changed');
          await admit(fresh.token);
        } finally {
          this.api('/api/detail', {action: 'close', token: fresh.token}).catch(() => {});
        }
      }
    }
    async read(operation, action, value) {
      const {signal} = operation.controller;
      for (let attempt = 0; ; attempt++) {
        signal.throwIfAborted();
        try { return await this.request(operation, action, value, signal); }
        catch (error) {
          if (error.retryable !== true || attempt >= 3) throw error;
          await wait(500 * 2 ** attempt, signal);
        }
      }
    }
    async ready(operation) {
      const {signal} = operation.controller;
      while (true) {
        const status = await this.read(operation, 'status');
        if (status.state === 'ready' && Number.isInteger(status.size) && status.size > 0 &&
            status.size <= 64 * chunkBytes) return status.size;
        if (status.state !== 'preparing') throw new Error('export_invalid_response');
        await wait(750, signal);
      }
    }
    async transfer(operation, size) {
      const chunks = [];
      for (let offset = 0; offset < size; offset += chunkBytes) {
        const {blob, filename} = await this.read(operation, 'chunk', {offset});
        if (filename !== `opencode-${this.id}-analysis.zip` || blob.size !== Math.min(chunkBytes, size - offset))
          throw new Error('export_invalid_response');
        chunks.push(blob);
      }
      return new Blob(chunks, {type: 'application/zip'});
    }
    async save(handle, blob, signal) {
      const writable = await handle.createWritable();
      const abort = () => { writable.abort().catch(() => {}); };
      signal.addEventListener('abort', abort, {once: true});
      let committed = false;
      try {
        signal.throwIfAborted();
        await writable.write(blob);
        signal.throwIfAborted();
        this.cancel.hidden = true;
        signal.removeEventListener('abort', abort);
        await writable.close();
        committed = true;
        this.notice.textContent = 'Analysis ZIP saved. Review before sharing.';
      } finally {
        signal.removeEventListener('abort', abort);
        if (!committed) await writable.abort().catch(() => {});
      }
    }
    download(blob, name) {
      const link = el('a');
      const url = URL.createObjectURL(blob);
      link.href = url; link.download = name; link.hidden = true;
      this.root.append(link);
      try { link.click(); } finally {
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      }
      this.notice.textContent = 'Analysis ZIP download requested; your browser controls the save location. Review before sharing.';
    }
  }
  return {Action};
})();
