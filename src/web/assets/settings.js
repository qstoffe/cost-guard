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
      explanation: 'Credits and USD show the same estimated reference cost, not your bill. Terminal display is unchanged.'},
    {key: 'miniWatchPlacement', id: 'mini-placement', label: 'Mini Watch position', endpoint: 'mini-placement',
      choices: [['remember-last', 'Remember last'], ['standard', 'Standard position']],
       explanation: 'Applies on the next opening. Remember last asks for the browser’s last position in this live tab; Standard asks for initial browser placement, not exact coordinates. Browser placement and size are coupled: Fit on open prioritizes fit and may reset position. Reload or host restart starts fresh.'},
    {key: 'miniWatchSize', id: 'mini-size', label: 'Mini Watch size', endpoint: 'mini-size',
      choices: [['fit-on-open', 'Fit on open'], ['remember-last', 'Remember last size']],
       explanation: 'Fit on open requests about 650 outer DIPs wide and measured content height with room for two running prompts. Remember last size lets the browser reuse manual dimensions in this live tab; Standard position can reset them. Earlier Sessions clicks can grow/shrink; passive updates never resize. Screen limits may require scrolling. No pixel geometry is saved.'},
    {key: 'quotaDisplayMode', id: 'quota-display', label: 'Quota display', endpoint: 'quota-display',
      choices: [['used', 'Used'], ['remaining', 'Remaining']],
       explanation: 'Remaining needs a known quota limit; unlimited plans still show Used.\nCCost used and the daily remaining allowance are unchanged.'}
  ];
  function apply(value, root) {
    const settings = value?.webSettings, choices = value?.webSettingsChoices, defaults = value?.webSettingsDefaults;
    if (fields.some(field => {
      const valid = item => field.choices.some(([choice]) => choice === item);
      return !valid(settings?.[field.key]) || !valid(defaults?.[field.key]) ||
        !(choices?.[field.key] === 'default' || valid(choices?.[field.key])) ||
        settings[field.key] !== (choices[field.key] === 'default' ? defaults[field.key] : choices[field.key]);
    })) {
      throw new Error('settings_unavailable');
    }
    document.documentElement.dataset.theme = settings.theme;
    ReportView.setQuotaMode(settings.quotaDisplayMode);
    ReportView.setUnit(settings.ccostDisplayUnit, root);
    return {values: {...settings}, choices: {...choices}, defaults: {...defaults}};
  }
  class View {
    constructor(api, applySettings = apply) {
      this.api = api; this.applySettings = applySettings;
      const e = ReportView.element;
      this.root = e('section'); this.root.className = 'web-settings';
      this.root.append(e('h3', 'Web settings'), e('p', 'Changes save immediately and apply only to Web.'));
      this.controls = new Map();
      this.confirmed = Object.fromEntries(fields.map(field => [field.key, 'default']));
      for (const field of fields) {
        const select = e('select'); select.id = field.id;
        const inherited = e('option', 'Default'); inherited.value = 'default'; select.append(inherited);
        for (const [value, text] of field.choices) {
          const option = e('option', text); option.value = value; select.append(option);
        }
        const label = e('label', field.label); label.htmlFor = select.id;
        const explanation = e('p', field.explanation, 'help-copy'); explanation.id = field.id + '-explanation';
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
        select.disabled = busy || !this.loaded; select.value = this.confirmed[key];
      }
    }
    confirm(value) {
      const state = this.applySettings(value);
      this.confirmed = state.choices; this.loaded = true;
      for (const field of fields) {
        const label = field.choices.find(([choice]) => choice === state.defaults[field.key])[1];
        this.controls.get(field.key).firstChild.textContent = `Default (${label})`;
      }
    }
    async read() {
      if (this.busy) return;
      this.lock(true);
      this.feedback.className = ''; this.feedback.textContent = 'Reading saved Web settings…';
      try {
        this.confirm(await this.api('/api/settings'));
        this.feedback.textContent = '';
      } catch (error) { this.error(error); }
      finally { this.lock(false); }
    }
    async save(field) {
      const select = this.controls.get(field.key), value = select.value;
      if (this.busy || !this.loaded || value === this.confirmed[field.key]) return;
      const focused = document.activeElement === select;
      this.lock(true);
      this.feedback.className = ''; this.feedback.textContent = 'Saving ' + field.label.toLowerCase() + '…';
      try {
        this.confirm(await this.api('/api/settings/' + field.endpoint, {[field.key]: value}));
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
