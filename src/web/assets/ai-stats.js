'use strict';
// Equal-treatment cards over server-prepared values; no numerical accounting here.
const AIStatsView = (() => {
  const definitions = [
    ['hourly-rate', '💸', 'AI Hourly Rate', 'Selected-period reference CCost per unioned AI execution hour. Not actual billing, worker-hours, salary or human time saved. Unknown pricing or time cannot produce an exact rate.'],
    ['total-cost', '💰', 'Total AI Cost', 'Deduplicated reference token valuation attributed by request event/completion time to this period. Not subscription charges. Missing prices are not free usage.'],
    ['working-time', '⏱️', 'AI Working Time', 'Unioned observed execution inside this period, including attributable agents, tests, tools and compaction. Overlaps count once; idle gaps between executions do not count. Not session age or human working time.'],
    ['average-cost', '📊', 'Average Cost per Session', 'Period reference CCost divided by distinct root sessions with attributable requests in this period. Each root counts once, even across periods. No sessions means no average.'],
    ['expensive-session', '🏆', 'Most Expensive Session', 'Root with highest selected-period reference CCost, not necessarily its lifetime cost. Requests outside the window are excluded, never split across dates. Equal values use a stable session tie-break.'],
    ['longest-session', '🔥', 'Longest Session', 'Root with longest qualified unioned execution inside the period, clipped at the boundaries. Not lifetime age, idle time or summed concurrent child-worker time.'],
    ['busiest-day', '📅', 'Busiest Day', 'Configured-local date with most overlap-safe AI execution in the selected period. Two sessions running for the same real hour count as one hour, not two. Boundary dates are clipped; equal days use the earliest date.'],
    ['night-owl', '🦉', 'Night Owl', 'Share of unioned AI execution between 22:00 and 06:00 in the configured timezone, including daylight-saving transitions. Includes qualified tool/test/child work; not proof the human was awake. No measured time means unavailable.'],
    ['streak', '⚡', 'Coding Streak', 'Longest consecutive run of configured-local dates with positive qualified AI execution in this period. Cross-midnight activity may touch two dates. Not a current streak, Git commits or proof of human coding.'],
    ['parallel', '🔀', 'Peak Parallel Sessions', 'Maximum distinct root sessions executing at the same instant in this period. Child agents within one root count only once. Inactive session ages, prompts and model-call counts do not count.']
  ];
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'], ['month', 'This month'], ['all', 'All time']];
  function valid(result) {
    const rows = result?.view?.ai_stats;
    return result?.view?.kind === 'ai-stats' && Array.isArray(rows) && rows.length > 0 && rows.every(row =>
      periods.some(([id]) => id === row.period) && row.metrics?.length === 10 && definitions.every(([key]) =>
        row.metrics.filter(metric => metric.metric === key && typeof metric.display?.value === 'string' &&
          typeof metric.display?.trait === 'string').length === 1));
  }
  class View {
    constructor(select) {
      const e = ReportView.element;
      this.root = e('div', undefined, 'ai-stats-view');
      this.selector = e('div', undefined, 'ai-stats-periods');
      this.selector.setAttribute('role', 'group'); this.selector.setAttribute('aria-label', 'AI Stats period');
      this.buttons = new Map(); this.cards = new Map();
      for (const [id, label] of periods) {
        const button = e('button', label); button.type = 'button';
        if (id === 'month' || id === 'all') ContextHelp.heading(button, id === 'month' ?
          'From the first day of the current configured-local calendar month until the observation time.' :
          'All available recorded sessions, including archived roots. Deleted/pruned history cannot be recovered.');
        button.addEventListener('click', () => select(id));
        this.buttons.set(id, button); this.selector.append(button);
      }
      this.content = e('div'); this.status = e('p', '', 'ai-stats-status'); this.status.setAttribute('role', 'status');
      this.grid = e('div', undefined, 'ai-stats-groups');
      for (const [name, items] of [['Overview', definitions.slice(0, 4)], ['Fun Facts', definitions.slice(4)]]) {
        const section = e('section', undefined, 'ai-stats-section'), grid = e('div', undefined, 'ai-stats-grid');
        section.append(e('h3', name), grid); this.grid.append(section);
        for (const [key, icon, title, help] of items) {
          const card = e('article', undefined, 'ai-stat'), heading = e('h4');
          const symbol = e('span', icon, 'ai-stat-icon'); symbol.setAttribute('aria-hidden', 'true');
          heading.append(symbol, ContextHelp.button(title, help));
          const value = e('p', '', 'ai-stat-value'), detail = e('p', '', 'ai-stat-detail');
          const trait = e('p', '', 'ai-stat-trait'), status = e('span', '', 'ai-stat-state');
          card.append(heading, value, detail, trait, status); grid.append(card);
          this.cards.set(key, {value, detail, trait, status});
        }
      }
      this.root.append(this.selector, this.status, this.content);
      this.extra = e('article', undefined, 'ai-stat');
      const title = e('h4'), symbol = e('span', '🏁', 'ai-stat-icon'); symbol.setAttribute('aria-hidden', 'true');
      this.extraHeading = ContextHelp.button('Biggest AI Speed Gap',
        'Optional matched first-input observation within this period. Only fully finished, reliably bounded runs qualify. Repeats of one model count too. Not a controlled benchmark or answer-quality score. Unavailable/partial match coverage omits this card.');
      title.append(symbol, this.extraHeading);
      this.extraValue = e('p', '', 'ai-stat-value'); this.extraDetail = e('p', '', 'ai-stat-detail'); this.extraTrait = e('p', '', 'ai-stat-trait');
      const link = e('a', 'Comparisons'); link.href = '#/comparisons';
      this.extra.append(title, this.extraValue, this.extraDetail, this.extraTrait, link);
    }
    update(state) {
      const e = ReportView.element;
      for (const [id, button] of this.buttons) button.setAttribute('aria-pressed', String(id === state.period));
      const row = state.result?.view.ai_stats.find(item => item.period === state.period);
      if (!row || state.withheld) {
        if (this.content.contains(this.grid)) this.grid.remove();
        this.status.textContent = state.failed ? state.message + (state.result ?
          ` Last successful observation: ${new Date(CachedReports.observation(state.result)).toLocaleString()}. Retained data are stale and withheld.` : '') :
          state.loading ? (state.lastWork || 'Acquiring available AI history…') : 'Waiting to acquire AI history…';
        if (state.loading && !this.content.querySelector('progress')) {
          const bar = e('progress'); bar.setAttribute('aria-label', 'Acquiring AI Stats'); this.content.replaceChildren(bar);
        } else if (!state.loading) this.content.replaceChildren();
        return;
      }
      this.status.textContent = state.failed ? state.message : '';
      // Mutate the ten retained cards in one synchronous commit; never touch focus/scroll.
      for (const metric of row.metrics) {
        const card = this.cards.get(metric.metric);
        ReportView.text(card.value, () => ReportView.display(metric, 'value'));
        ReportView.text(card.trait, metric.display.trait);
        ReportView.text(card.status, metric.status === 'complete' ? '' : metric.status);
        const target = card.detail.querySelector('a');
        if (metric.session_title && /^[A-Za-z0-9_-]{1,200}$/.test(metric.session_id)) {
          const link = target || e('a'); ReportView.text(link, metric.session_title);
          link.href = '#/sessions/' + metric.session_id;
          if (!target) card.detail.replaceChildren(link);
        } else ReportView.text(card.detail, metric.detail || '');
      }
      if (!this.content.contains(this.grid)) this.content.replaceChildren(this.grid);
      if (row.matched) {
        ReportView.text(this.extraHeading, row.matched.metric === 'original-thinker' ? 'Original Thinker' : 'Biggest AI Speed Gap');
        ReportView.text(this.extraValue, () => ReportView.display(row.matched, 'value'));
        ReportView.text(this.extraTrait, row.matched.display.trait); ReportView.text(this.extraDetail, row.matched.detail);
        const grid = this.grid.querySelectorAll('.ai-stats-grid')[1];
        if (!grid.contains(this.extra)) grid.append(this.extra);
      } else this.extra.remove();
      ContextHelp.refresh(this.root);
    }
    attach(parent) { if (parent.firstChild !== this.root) parent.replaceChildren(this.root); }
  }
  return {View, valid};
})();
