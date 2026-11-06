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
      explanation: 'Appearance of Web and Mini Watch. Terminal colors are unchanged.',
      help: {classic: 'Use the dark, CLI-inspired palette, independent of system appearance.',
        web: 'Follow your system’s light or dark appearance.'}},
    {key: 'ccostDisplayUnit', id: 'ccost-unit', label: 'CCost display', endpoint: 'ccost', choices: [['credits', 'Credits'], ['usd', 'USD']],
      explanation: 'Units for estimated reference cost in Web and Mini Watch, not your bill. Terminal display is unchanged.',
      help: {credits: 'Show estimated reference cost in Credits; the underlying cost is unchanged.',
        usd: 'Show the same estimated reference cost in US dollars, not actual charges.'}},
    {key: 'miniWatchPlacement', id: 'mini-placement', label: 'Mini Watch position', endpoint: 'mini-placement',
      choices: [['remember-last', 'Remember last'], ['standard', 'Standard position']],
      explanation: 'Position requested on the next Mini Watch opening. The browser couples position and size; exact coordinates are not guaranteed.',
      help: {'remember-last': 'Ask for the browser’s last position in this live tab. Fit on open may reset it. Reload or host restart starts fresh.',
        standard: 'Ask for initial browser placement, not exact coordinates. This can also reset remembered size.'}},
    {key: 'miniWatchSize', id: 'mini-size', label: 'Mini Watch size', endpoint: 'mini-size',
      choices: [['fit-on-open', 'Fit on open'], ['remember-last', 'Remember last size']],
      explanation: 'Size requested on the next Mini Watch opening. Earlier Sessions clicks can resize it; passive Live updates never do. No pixel geometry is saved.',
      help: {'fit-on-open': 'Open about 650 outer DIPs wide, fitted to content with room for two running prompts. Earlier Sessions clicks can grow or shrink it; Live updates never resize. Screen limits may require scrolling.',
        'remember-last': 'Let the browser reuse manual size in this live tab. Standard position can reset it. Reload or host restart starts fresh; Earlier Sessions clicks can still resize.'}},
    {key: 'quotaDisplayMode', id: 'quota-display', label: 'Quota display', endpoint: 'quota-display',
      choices: [['used', 'Used'], ['remaining', 'Remaining']],
      explanation: 'Orientation of provider-native quotas in Web and Mini Watch. CCost used and the daily remaining allowance are unchanged.',
      help: {used: 'Show how much of each provider-native quota has been used.',
        remaining: 'Show the amount left when a quota limit is known. Unlimited plans still show Used.'}}
  ];
  function choiceHelp(field, choice, defaults) {
    if (choice !== 'default') return field.help[choice];
    const value = defaults?.[field.key], label = field.choices.find(([key]) => key === value)?.[1];
    return label ? `Follow the shipped default, currently ${label}; do not pin this value. ${field.help[value]}` :
      'Follow the shipped default, rather than pinning an explicit value. Reading the current default…';
  }
  function enhancedPicker() {
    return typeof CSS !== 'undefined' && CSS.supports('appearance', 'base-select') &&
      CSS.supports('selector(select::picker(select))') && CSS.supports('max-width', 'stretch') &&
      typeof HTMLSelectedContentElement !== 'undefined';
  }
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
      this.root = e('section'); this.root.className = 'web-settings'; this.root.setAttribute('aria-label', 'Settings');
      this.enhanced = enhancedPicker();
      const grid = e('div', undefined, 'settings-grid');
      const name = e('span', 'Setting', 'settings-column'), value = e('span', 'Value', 'settings-column');
      name.setAttribute('aria-hidden', 'true'); value.setAttribute('aria-hidden', 'true'); grid.append(name, value);
      this.root.append(grid);
      this.controls = new Map();
      this.defaultHelp = new Map();
      this.confirmed = Object.fromEntries(fields.map(field => [field.key, 'default']));
      for (const field of fields) {
        const select = e('select'); select.id = field.id;
        select.className = this.enhanced ? 'settings-picker' : '';
        select.addEventListener('keydown', () => { select.dataset.helpInput = 'keyboard'; });
        select.addEventListener('pointermove', () => { select.dataset.helpInput = 'pointer'; });
        if (this.enhanced) {
          const button = e('button'); button.type = 'button'; button.append(e('selectedcontent')); select.append(button);
        }
        const label = e('label', field.label); label.htmlFor = select.id;
        ContextHelp.value(label, field.explanation + ' Changes save immediately and apply only to Web.');
        ContextHelp.attach(select, () => choiceHelp(field, this.confirmed[field.key], this.defaults));
        const cell = e('div', undefined, 'settings-value'); cell.append(select);
        const reference = e('dl', undefined, 'settings-choice-reference');
        for (const [value, text] of [['default', 'Default'], ...field.choices]) {
          const option = e('option'); option.value = value; option.setAttribute('aria-label', text);
          const description = e(this.enhanced ? 'span' : 'dd', choiceHelp(field, value, this.defaults), 'settings-choice-help');
          // selectedcontent clones option children: keep description IDs outside that clone.
          const accessible = this.enhanced ? e('span', description.textContent) : description;
          accessible.id = `${field.id}-${value}-help`;
          if (this.enhanced) { accessible.hidden = true; cell.append(accessible); }
          if (value === 'default') this.defaultHelp.set(field.key, this.enhanced ? [description, accessible] : [description]);
          option.setAttribute('aria-describedby', accessible.id);
          if (this.enhanced) {
            option.append(e('span', text, 'settings-choice-label'), description);
          } else { option.textContent = text; reference.append(e('dt', text), description); }
          select.append(option);
        }
        if (!this.enhanced) {
          const details = e('details', undefined, 'settings-choice-fallback');
          details.append(e('summary', 'Choice help'), reference); cell.append(details);
        }
        select.setAttribute('aria-describedby', 'settings-feedback');
        select.value = this.confirmed[field.key]; select.disabled = true;
        select.addEventListener('change', () => this.save(field));
        grid.append(label, cell);
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
      ContextHelp.dismiss(this.root);
      for (const [key, select] of this.controls) {
        select.disabled = busy || !this.loaded; select.value = this.confirmed[key];
      }
    }
    confirm(value) {
      const state = this.applySettings(value);
      this.confirmed = state.choices; this.defaults = state.defaults; this.loaded = true;
      for (const field of fields) {
        const select = this.controls.get(field.key);
        const label = `Default (${field.choices.find(([choice]) => choice === state.defaults[field.key])[1]})`;
        select.querySelector('option').setAttribute('aria-label', label);
        if (this.enhanced) {
          const option = select.querySelector('option'); option.firstChild.textContent = label; option.setAttribute('aria-label', label);
        } else { select.firstChild.textContent = label; }
        for (const description of this.defaultHelp.get(field.key)) description.textContent = choiceHelp(field, 'default', this.defaults);
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
