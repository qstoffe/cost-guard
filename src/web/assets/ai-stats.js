'use strict';
// AI Stats = BEST EFFORT / NEVER Unavailable, for every present and future card.
// Sparse/partial/estimated ready observations show fun values; Loading and real
// page-level operational failures are distinct. See architecture/modules/reports.md.
// Equal-treatment cards over server-prepared values; no numerical accounting here.
const AIStatsView = (() => {
  const idleRateHelp = 'Calendar average: The robot keeps a budget even while you sleep. (Total CCost ÷ (calendar days × 24))\n\n' +
    "Workday average: The robot's office calendar is taking a nap. (Total CCost ÷ (workdays × 8))\n\n" +
    "Active AI average: The silicon's hourly snack break hasn't started. (Total CCost ÷ active AI hours)";
  const definitions = [
    ['hourly-rate', '💸', 'AI Hourly Rate', idleRateHelp],
    ['total-cost', '💰', 'Total AI Cost', 'Your token bonfire. Bring marshmallows.'],
    ['total-tokens', '🍿', 'Total Tokens', 'Observed token traffic, including repeated context reads.'],
    ['token-rate', '🍽️', 'Token Consumption Rate', 'Approximate model output response throughput in tok/s.'],
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
    return !result?.error && result?.view?.kind === 'ai-stats' && result.view.ai_stats_policy === 'fun-3-responses' &&
      Array.isArray(rows) && rows.length > 0 && rows.every(row =>
      periods.some(([id]) => id === row.period) && row.metrics?.length === definitions.length && definitions.every(([key]) =>
        row.metrics.filter(metric => metric.metric === key && metric.value !== null && Number.isFinite(Number(metric.value)) &&
          typeof metric.display?.value === 'string' && typeof metric.display?.trait === 'string' &&
          (key !== 'total-tokens' || /^\d+$/.test(metric.exact_value) && typeof metric.display.token_help === 'string') &&
          ['usd', 'credits'].every(unit => typeof (metric.display_units?.[unit]?.value ?? metric.display.value) === 'string' &&
            (key !== 'hourly-rate' || [...rateRows.map(([id]) => id), 'rate_help'].every(id =>
              typeof (metric.display_units?.[unit]?.[id] ?? metric.display[id]) === 'string'))) &&
          (key !== 'token-rate' || Array.isArray(metric.podium) && metric.podium.length <= 3 &&
            typeof metric.display.response_help === 'string' && metric.podium.every(row =>
              ['label', 'speed', 'sample'].every(id => typeof row[id] === 'string') &&
              Number.isFinite(Number(row.tokens_per_second)) && Number(row.tokens_per_second) > 0 &&
              Number.isInteger(row.sampled_calls) && row.sampled_calls > 0 && row.sampled_calls <= 32))).length === 1));
  }
  function remember(state, result) {
    if (!valid(result)) return;
    state.statsResults ||= new Map();
    const seen = CachedReports.observation(result);
    if (!Number.isSafeInteger(seen) || seen < 0) return;
    const identity = JSON.stringify([result.source?.identity, result.source?.generation, result.scope?.timezone_id]);
    if (state.statsIdentity !== identity) {
      if (state.statsObserved > seen) return;
      state.statsResults.clear(); state.statsIdentity = identity;
    }
    state.statsObserved = Math.max(state.statsObserved || 0, seen || 0);
    for (const row of result.view.ai_stats) {
      const old = state.statsResults.get(row.period);
      const ready = result.view.ai_stats_work?.scopes?.[row.period]?.ready === true;
      const newer = !old || CachedReports.observation(old) < seen || CachedReports.observation(old) === seen &&
        (old.instance_id !== result.instance_id || (old.sequence || 0) <= (result.sequence || 0));
      if (ready && newer)
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
      this.grid = e('div', undefined, 'ai-stats-groups');
      for (const [name, items] of [['Overview', definitions.slice(0, 6)], ['Fun Facts', definitions.slice(6)]]) {
        const section = e('section', undefined, 'ai-stats-section'), grid = e('div', undefined, 'ai-stats-grid');
        section.append(e('h3', name), grid); this.grid.append(section);
        for (const [key, icon, title, help] of items) {
          const card = e('article', undefined, 'ai-stat'), heading = e('h4');
          card.dataset.metric = key;
          const symbol = e('span', icon, 'ai-stat-icon'); symbol.setAttribute('aria-hidden', 'true');
          const retained = {metric: null, rates: new Map(), podium: []};
          const hasRates = key === 'hourly-rate', hasPodium = key === 'token-rate';
          const helpButton = ContextHelp.button(title, () => retained.metric && (hasRates || hasPodium || key === 'total-tokens') ?
            ReportView.display(retained.metric, hasRates ? 'rate_help' : hasPodium ? 'response_help' : 'token_help') : help);
          heading.append(symbol, helpButton);
          const value = e(hasRates ? 'div' : 'p', '', 'ai-stat-value'), detail = e('p', '', 'ai-stat-detail');
          if (hasRates) {
            value.classList.add('ai-stat-rates');
            for (const [id, label] of rateRows) {
              const row = e('div', undefined, 'ai-stat-rate'), amount = e('span', '', 'ai-stat-rate-value');
              row.setAttribute('role', 'group'); row.setAttribute('aria-label', label);
              row.append(e('span', label, 'ai-stat-rate-label'), amount); value.append(row);
              retained.rates.set(id, amount);
            }
          }
          if (hasPodium) {
            value.classList.add('ai-stat-podium');
            for (const medal of ['🥇', '🥈', '🥉']) {
              const row = e('div', undefined, 'ai-stat-racer'), label = e('span', '', 'ai-stat-model');
              ContextHelp.value(label, () => retained.metric?.podium[retained.podium.findIndex(item => item.label === label)]?.model_help || 'Recorded model identity unavailable.');
              const icon = e('span', medal); icon.setAttribute('aria-hidden', 'true');
              const speed = e('span', '', 'ai-stat-speed'), sample = e('span', '', 'ai-stat-sample');
              row.append(icon, label, speed, sample); row.setAttribute('role', 'group');
              retained.podium.push({row, label, speed, sample});
            }
          }
          const trait = e('p', '', 'ai-stat-trait');
          grid.append(card);
          this.cards.set(key, Object.assign(retained, {card, nodes: [heading, value, detail, trait], value, detail, trait}));
        }
      }
      this.root.append(this.selector, this.content);
      this.content.append(this.grid);
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
      const ready = state.result?.view?.ai_stats_work?.scopes?.[state.period]?.ready === true;
      const row = ready && valid(state.result) && state.result.view.ai_stats.find(item => item.period === state.period);
      if (!row) {
        const message = state.failed || state.interrupted ? 'Counting paused.' : 'Loading…';
        for (const item of this.cards.values()) {
          if (item.pending !== message) {
            item.card.replaceChildren(message); item.pending = message;
            item.card.setAttribute('role', 'status'); item.card.setAttribute('aria-live', 'off');
          }
        }
        this.extra.remove();
        return;
      }
      // Reveal each complete card in this synchronous commit; retain nodes on quiet refresh.
      for (const metric of row.metrics) {
        const card = this.cards.get(metric.metric);
        card.metric = metric;
        if (card.podium.length) {
          if (metric.podium.length) {
            for (const [index, item] of card.podium.entries()) {
              const racer = metric.podium[index];
              if (!racer) { item.row.remove(); continue; }
              ReportView.text(item.label, racer.label); ReportView.text(item.speed, racer.speed);
              ReportView.text(item.sample, racer.sample);
              item.row.setAttribute('aria-label', `Rank ${index + 1}: ${racer.label}`);
            }
            const nodes = card.podium.slice(0, metric.podium.length).map(item => item.row);
            if (nodes.some((node, index) => card.value.children[index] !== node) || card.value.children.length !== nodes.length)
              card.value.replaceChildren(...nodes);
          } else ReportView.text(card.value, metric.display.value);
        } else if (card.rates.size) {
          for (const [id, node] of card.rates) ReportView.text(node, () => ReportView.display(metric, id));
        } else ReportView.text(card.value, () => ReportView.display(metric, 'value'));
        ReportView.text(card.trait, metric.display.trait);
        const target = card.detail.querySelector('a');
        if (metric.session_title && /^[A-Za-z0-9_-]{1,200}$/.test(metric.session_id)) {
          const link = target || e('a'); ReportView.text(link, metric.session_title);
          link.href = '#/sessions/' + metric.session_id;
          if (!target) card.detail.replaceChildren(link);
        } else ReportView.text(card.detail, metric.metric === 'token-rate' ? '' : metric.detail || '');
        if (card.pending || !card.card.firstChild) {
          card.card.replaceChildren(...card.nodes); card.pending = null;
          card.card.removeAttribute('role'); card.card.removeAttribute('aria-live');
        }
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
  return {View, valid, remember, observe, prioritize};
})();
