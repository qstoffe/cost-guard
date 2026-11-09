'use strict';
// Equal-treatment cards over server-prepared values; no numerical accounting here.
const AIStatsView = (() => {
  const idleRateHelp = 'Calendar average: The robot keeps a budget even while you sleep. (Total CCost ÷ (calendar days × 24))\n\n' +
    "Workday average: The robot's office calendar is taking a nap. (Total CCost ÷ (workdays × 8))\n\n" +
    "Active AI average: The silicon's hourly snack break hasn't started. (Total CCost ÷ active AI hours)";
  const definitions = [
    ['hourly-rate', '💸', 'AI Hourly Rate', idleRateHelp],
    ['total-cost', '💰', 'Total AI Cost', 'Your token bonfire. Bring marshmallows.'],
    ['working-time', '⏱️', 'AI Working Time', 'Time on the robot clock. Coffee breaks excluded.'],
    ['average-cost', '📊', 'Average Cost per Session', 'The cover charge for a typical robot adventure.'],
    ['expensive-session', '🏆', 'Most Expensive Session', 'The quest with the biggest token tab.'],
    ['longest-session', '🔥', 'Longest Session', 'The longest robot marathon in this period.'],
    ['busiest-day', '📅', 'Busiest Day', 'The calendar’s boss level.'],
    ['night-owl', '🦉', 'Night Owl', 'The share of robot work between 10 pm and 6 am. Hoot hoot.'],
    ['streak', '⚡', 'Coding Streak', 'Your longest chain of days with robot adventures.'],
    ['parallel', '🔀', 'Peak Parallel Sessions', 'The biggest robot party running at once.']
  ];
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'], ['month', 'This month'], ['all', 'All time']];
  const rateRows = [['calendar_rate', 'Calendar average'], ['workday_rate', 'Workday average'], ['active_rate', 'Active AI average']];
  function valid(result) {
    const rows = result?.view?.ai_stats;
    return result?.view?.kind === 'ai-stats' && result.view.ai_stats_policy === 'fun-1' &&
      Array.isArray(rows) && rows.length > 0 && rows.every(row =>
      periods.some(([id]) => id === row.period) && row.metrics?.length === 10 && definitions.every(([key]) =>
        row.metrics.filter(metric => metric.metric === key && metric.value !== null && Number.isFinite(Number(metric.value)) &&
          typeof metric.display?.value === 'string' && typeof metric.display?.trait === 'string' &&
          ['usd', 'credits'].every(unit => typeof (metric.display_units?.[unit]?.value ?? metric.display.value) === 'string' &&
            (key !== 'hourly-rate' || [...rateRows.map(([id]) => id), 'rate_help'].every(id =>
              typeof (metric.display_units?.[unit]?.[id] ?? metric.display[id]) === 'string')))).length === 1));
  }
  function remember(state, result) {
    if (!valid(result)) return;
    state.statsResults ||= new Map();
    for (const row of result.view.ai_stats) {
      const old = state.statsResults.get(row.period);
      if (!old || CachedReports.observation(old) <= CachedReports.observation(result))
        state.statsResults.set(row.period, result);
    }
    state.result = state.statsResults.get(state.period) || null;
  }
  function observe(state, job) {
    if (job.result) remember(state, job.result);
    const scope = job.result?.view?.ai_stats_work?.scopes?.[state.period];
    if (scope) state.percent = Math.max(state.percent || 0, scope.ready && valid(job.result) ? 100 :
      Math.min(99, Math.floor(95 * scope.completed / Math.max(1, scope.total))));
    state.stage = state.stageLabel = 'The robots are counting their adventures…';
    return true;
  }
  async function prioritize(state, api, managed = false) {
    if (state.priorityUpdate || !state.active) return;
    state.priorityUpdate = true;
    try {
      let sent;
      do {
        sent = state.request.stats_scope;
        const request = {kind: 'ai-stats', stats_scope: sent};
        await api(managed ? '/api/data' : '/api/reports', managed ? {request, retry: false} : request);
      } while (state.loading && state.active && sent !== state.request.stats_scope);
    } catch (_) { /* The normal polling/admission path reports authoritative errors. */ }
    finally { state.priorityUpdate = false; }
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
        ContextHelp.heading(button, {today: 'Today’s robot adventures.', '7-days': 'A week of silicon shenanigans.',
          '30-days': 'Thirty days of robot quests.', month: 'This calendar month’s adventures.', all: 'The whole robot saga.'}[id], true);
        button.addEventListener('click', () => select(id));
        this.buttons.set(id, button); this.selector.append(button);
      }
      this.content = e('div');
      this.loading = e('p', 'The robots are counting their adventures…'); this.loading.setAttribute('role', 'status');
      this.grid = e('div', undefined, 'ai-stats-groups');
      for (const [name, items] of [['Overview', definitions.slice(0, 4)], ['Fun Facts', definitions.slice(4)]]) {
        const section = e('section', undefined, 'ai-stats-section'), grid = e('div', undefined, 'ai-stats-grid');
        section.append(e('h3', name), grid); this.grid.append(section);
        for (const [key, icon, title, help] of items) {
          const card = e('article', undefined, 'ai-stat'), heading = e('h4');
          const symbol = e('span', icon, 'ai-stat-icon'); symbol.setAttribute('aria-hidden', 'true');
          const retained = {metric: null, rates: new Map()};
          const helpButton = ContextHelp.button(title, () => key === 'hourly-rate' && retained.metric ?
            ReportView.display(retained.metric, 'rate_help') : help);
          heading.append(symbol, helpButton);
          const value = e(key === 'hourly-rate' ? 'div' : 'p', '', 'ai-stat-value'), detail = e('p', '', 'ai-stat-detail');
          if (key === 'hourly-rate') {
            value.classList.add('ai-stat-rates');
            for (const [id, label] of rateRows) {
              const row = e('div', undefined, 'ai-stat-rate'), amount = e('span', '', 'ai-stat-rate-value');
              row.setAttribute('role', 'group'); row.setAttribute('aria-label', label);
              row.append(e('span', label, 'ai-stat-rate-label'), amount); value.append(row);
              retained.rates.set(id, amount);
            }
          }
          const trait = e('p', '', 'ai-stat-trait');
          card.append(heading, value, detail, trait); grid.append(card);
          this.cards.set(key, Object.assign(retained, {value, detail, trait}));
        }
      }
      this.root.append(this.selector, this.content);
      this.extra = e('article', undefined, 'ai-stat');
      const title = e('h4'), symbol = e('span', '🏁', 'ai-stat-icon'); symbol.setAttribute('aria-hidden', 'true');
      this.extraHeading = ContextHelp.button('Biggest AI Speed Gap',
        'Same opening move. Who crossed the finish line first?');
      title.append(symbol, this.extraHeading);
      this.extraValue = e('p', '', 'ai-stat-value'); this.extraDetail = e('p', '', 'ai-stat-detail'); this.extraTrait = e('p', '', 'ai-stat-trait');
      const link = e('a', 'Comparisons'); link.href = '#/comparisons';
      this.extra.append(title, this.extraValue, this.extraDetail, this.extraTrait, link);
    }
    update(state) {
      const e = ReportView.element;
      for (const [id, button] of this.buttons) button.setAttribute('aria-pressed', String(id === state.period));
      const row = valid(state.result) && state.result.view.ai_stats.find(item => item.period === state.period) ||
        (state.failed || state.interrupted ? empty() : null);
      if (!row) {
        if (this.content.firstChild !== this.loading) this.content.replaceChildren(this.loading);
        return;
      }
      // Mutate the ten retained cards in one synchronous commit; never touch focus/scroll.
      for (const metric of row.metrics) {
        const card = this.cards.get(metric.metric);
        card.metric = metric;
        if (card.rates.size) {
          for (const [id, node] of card.rates) ReportView.text(node, () => ReportView.display(metric, id));
        } else ReportView.text(card.value, () => ReportView.display(metric, 'value'));
        ReportView.text(card.trait, metric.display.trait);
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
  function empty() {
    const traits = ['Budget build. Dangerous potential.', 'The token furnace is on vacation.', 'The silicon crew took a nap.',
      'Tiny adventures. Tiny tab.', 'A boss fight on a budget.', 'A quick quest. Refreshing.', 'A perfectly peaceful calendar.',
      'Day-shift citizen. Suspiciously responsible.', 'The calendar awaits its first quest.', 'The parallel universe is on vacation.'];
    return {metrics: definitions.map(([metric], index) => {
      const suffix = index === 0 ? '/h' : '';
      const value = index < 2 || index === 3 || index === 4 ? '0 CCost' + suffix :
        [2, 5, 6].includes(index) ? '0s' : index === 7 ? '0%' : index === 8 ? '0 days' : '0';
      const display = {value, trait: traits[index], ...(index === 0 ? {
        calendar_rate: '0 CCost/h', workday_rate: 'No workdays', active_rate: '0 CCost/h',
        rate_help: idleRateHelp} : {})};
      return {metric, value: 0, display, display_units: {credits: display,
        usd: {...display, value: index < 2 || index === 3 || index === 4 ? '$0.00' + suffix : value,
          ...(index === 0 ? {calendar_rate: '$0.00/h', active_rate: '$0.00/h'} : {})}}};
    })};
  }
  return {View, valid, remember, observe, prioritize};
})();
