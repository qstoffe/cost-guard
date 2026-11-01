'use strict';
// File-backed only. No browser persistence, report acquisition or reload.
const WebSettings = (() => {
  const messages = {
    settings_invalid_config: 'Configuration is invalid or cannot be safely edited. Correct the user configuration and retry.',
    settings_not_writable: 'Cannot write the user configuration. Check file permissions and retry.',
    settings_unsafe_path: 'Configuration location is unsafe (linked or non-owned file). Correct it before retrying.',
    settings_config_too_large: 'User configuration exceeds the safe size limit.',
    settings_conflict: 'Configuration changed while saving. Select the preference again to retry.',
    instance_stopping: 'Host is stopping. Open Cost Guard again before retrying.',
    authentication_required: 'Authorization expired. Use a fresh launcher link.',
    csrf_required: 'Authorization expired. Use a fresh launcher link.',
    host_identity_changed: 'Host changed. Use a fresh launcher link.'
  };
  const fields = [
    {key: 'theme', id: 'web-theme', label: 'Theme', endpoint: 'theme', choices: [['classic', 'Classic'], ['web', 'Web']],
      explanation: 'Classic uses a dark CLI-inspired palette. Web follows your system appearance. Terminal colors are unchanged.'},
    {key: 'ccostDisplayUnit', id: 'ccost-unit', label: 'CCost display', endpoint: 'ccost', choices: [['credits', 'Credits'], ['usd', 'USD']],
      explanation: 'USD is reference token valuation, not billed spending. CLI display is unchanged.'}
  ];
  function apply(value, root) {
    const settings = value?.webSettings;
    if (fields.some(field => !field.choices.some(([choice]) => choice === settings?.[field.key]))) {
      throw new Error('settings_unavailable');
    }
    document.documentElement.dataset.theme = settings.theme;
    ReportView.setUnit(settings.ccostDisplayUnit, root);
    return {...settings};
  }
  class View {
    constructor(api, applySettings = apply) {
      this.api = api; this.applySettings = applySettings;
      const e = ReportView.element;
      this.root = e('section'); this.root.className = 'web-settings';
      this.root.append(e('h3', 'Web settings'), e('p', 'Changes save immediately and apply only to Web.'));
      this.controls = new Map();
      this.confirmed = {theme: document.documentElement.dataset.theme, ccostDisplayUnit: 'credits'};
      for (const field of fields) {
        const select = e('select'); select.id = field.id;
        for (const [value, text] of field.choices) {
          const option = e('option', text); option.value = value; select.append(option);
        }
        const label = e('label', field.label); label.htmlFor = select.id;
        const explanation = e('p', field.explanation); explanation.id = field.id + '-explanation';
        select.setAttribute('aria-describedby', explanation.id + ' settings-feedback');
        select.value = this.confirmed[field.key]; select.disabled = true;
        select.addEventListener('change', () => this.save(field));
        label.append(select); this.root.append(label, explanation);
        this.controls.set(field.key, select);
      }
      this.feedback = e('p'); this.feedback.id = 'settings-feedback'; this.feedback.setAttribute('role', 'status');
      this.root.append(this.feedback);
    }
    attach(output) {
      if (output.firstChild !== this.root) output.replaceChildren(this.root);
    }
    error(error) {
      this.feedback.className = 'error';
      this.feedback.textContent = messages[error.message] || 'Web settings could not be confirmed. Check the host connection and retry; no save is claimed.';
    }
    lock(busy) {
      this.busy = busy;
      for (const [key, select] of this.controls) {
        select.disabled = busy; select.value = this.confirmed[key];
      }
    }
    async read() {
      if (this.busy) return;
      this.lock(true);
      this.feedback.className = ''; this.feedback.textContent = 'Reading saved Web settings…';
      try {
        this.confirmed = this.applySettings(await this.api('/api/settings'));
        this.feedback.textContent = '';
      } catch (error) { this.error(error); }
      finally { this.lock(false); }
    }
    async save(field) {
      const select = this.controls.get(field.key), value = select.value;
      if (this.busy || value === this.confirmed[field.key]) return;
      const focused = document.activeElement === select;
      this.lock(true);
      this.feedback.className = ''; this.feedback.textContent = 'Saving ' + field.label.toLowerCase() + '…';
      try {
        this.confirmed = this.applySettings(await this.api('/api/settings/' + field.endpoint, {[field.key]: value}));
        this.feedback.className = 'success'; this.feedback.textContent = field.label + ' saved.';
      } catch (error) { this.error(error); }
      finally {
        this.lock(false);
        // Restore native-select focus only if the user has not moved elsewhere.
        if (focused && this.root.isConnected && document.activeElement === document.body) select.focus();
      }
    }
  }
  return {apply, View};
})();
