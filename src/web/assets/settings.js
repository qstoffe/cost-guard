'use strict';
// File-backed only. No browser persistence, report acquisition or reload.
const ThemeSettings = (() => {
  const messages = {
    settings_invalid_config: 'Configuration is invalid or cannot be safely edited. Correct the user configuration and retry.',
    settings_not_writable: 'Cannot write the user configuration. Check file permissions and retry.',
    settings_unsafe_path: 'Configuration location is unsafe (linked or non-owned file). Correct it before retrying.',
    settings_config_too_large: 'User configuration exceeds the safe size limit.',
    settings_conflict: 'Configuration changed while saving. Select the theme again to retry.',
    instance_stopping: 'Host is stopping. Open Cost Guard again before retrying.',
    authentication_required: 'Authorization expired. Use a fresh launcher link.',
    csrf_required: 'Authorization expired. Use a fresh launcher link.',
    host_identity_changed: 'Host changed. Use a fresh launcher link.'
  };
  function apply(value) {
    if (!['classic', 'web'].includes(value?.webTheme)) throw new Error('settings_unavailable');
    document.documentElement.dataset.theme = value.webTheme;
    return value.webTheme;
  }
  class View {
    constructor(api) {
      this.api = api;
      const e = ReportView.element;
      this.root = e('section'); this.root.className = 'theme-settings';
      this.select = e('select'); this.select.id = 'web-theme';
      for (const [value, text] of [['classic', 'Classic'], ['web', 'Web']]) {
        const option = e('option', text); option.value = value; this.select.append(option);
      }
      const label = e('label', 'Theme'); label.htmlFor = this.select.id;
      this.feedback = e('p'); this.feedback.id = 'theme-feedback'; this.feedback.setAttribute('role', 'status');
      this.select.setAttribute('aria-describedby', 'theme-explanation theme-feedback');
      const explanation = e('p', 'Classic uses a dark CLI-inspired palette. Web follows your system appearance. Changes save immediately; terminal colors are unchanged.');
      explanation.id = 'theme-explanation';
      label.append(this.select); this.root.append(label, explanation, this.feedback);
      this.confirmed = document.documentElement.dataset.theme;
      this.select.value = this.confirmed;
      this.select.disabled = true;
      this.select.addEventListener('change', () => this.save());
    }
    attach(output) {
      if (output.firstChild !== this.root) output.replaceChildren(this.root);
    }
    error(error) {
      this.feedback.className = 'error';
      this.feedback.textContent = messages[error.message] || 'Theme could not be confirmed. Check the host connection and retry; no save is claimed.';
    }
    async read() {
      if (this.busy) return;
      this.busy = true; this.select.disabled = true;
      this.feedback.className = ''; this.feedback.textContent = 'Reading saved theme…';
      try {
        this.confirmed = apply(await this.api('/api/settings/theme'));
        this.feedback.textContent = '';
      } catch (error) { this.error(error); }
      finally { this.select.value = this.confirmed; this.select.disabled = false; this.busy = false; }
    }
    async save() {
      const theme = this.select.value;
      if (this.busy || theme === this.confirmed) return;
      const focused = document.activeElement === this.select;
      this.busy = true; this.select.disabled = true;
      this.feedback.className = ''; this.feedback.textContent = 'Saving theme…';
      try {
        this.confirmed = apply(await this.api('/api/settings/theme', {webTheme: theme}));
        this.feedback.className = 'success'; this.feedback.textContent = 'Theme saved.';
      } catch (error) { this.error(error); }
      finally {
        this.select.value = this.confirmed; this.select.disabled = false; this.busy = false;
        // Disabling a native select blurs it. Restore keyboard focus only if the
        // user has not moved elsewhere (including to another route) while saving.
        if (focused && this.root.isConnected && document.activeElement === document.body) this.select.focus();
      }
    }
  }
  return {apply, View};
})();
