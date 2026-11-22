'use strict';
// AI Stats = BEST EFFORT / NEVER Unavailable, for every present and future card.
// Sparse/partial/estimated ready observations show fun values; pending metrics and real
// page-level operational failures are distinct. See architecture/modules/reports.md.
// Equal-treatment cards over server-prepared values; no numerical accounting here.
const AIStatsView = (() => {
  const idleRateHelp = 'Average cost across all AI work: total CCost for every model ÷ total active AI hours. ' +
    'Overlapping work counts once. Individual models can have higher or lower hourly rates.';
  const definitions = [
    ['hourly-rate', '💸', 'AI Hourly Rate', idleRateHelp],
    ['total-cost', '💰', 'Total AI Cost', 'Your token bonfire. Bring marshmallows.'],
    ['subagent-cost', '🦾', 'Subagent Cost', 'The boss delegated. The bots sent the bill.'],
    ['total-tokens', '🍿', 'Total Tokens', 'The robots have eaten the entire context buffet.'],
    ['token-rate', '🍽️', 'Token Consumption Rate', 'The silicon sprinters are racing for snacks.'],
    ['working-time', '⏱️', 'AI Working Time', 'Time on the robot clock.\n\nOverlapping calls share the same clock time.'],
    ['average-cost', '📊', 'Average Cost per Session', 'The cover charge for a typical robot adventure.'],
    ['expensive-session', '🏆', 'Most Expensive Session', 'The quest with the biggest token tab.'],
    ['longest-session', '🔥', 'Longest Session', 'The longest robot marathon in this period.'],
    ['busiest-day', '📅', 'Busiest Day', 'The calendar’s boss level.'],
    ['night-owl', '🦉', 'Night Owl', 'The robots brought night-vision goggles.\n\nWork between 10 pm and 6 am.'],
    ['streak', '⚡', 'Coding Streak', 'Your longest chain of days with robot adventures.'],
    ['parallel', '🔀', 'Peak Parallel Sessions', 'The biggest robot party running at once.']
  ];
  const periods = [['today', 'Today'], ['7-days', '7 days'], ['30-days', '30 days'], ['month', 'This month'], ['all', 'All time']];
  const costMetrics = new Set(['hourly-rate', 'total-cost', 'subagent-cost', 'average-cost', 'expensive-session']);
  const podiumMetrics = new Set(['hourly-rate', 'token-rate', 'total-tokens', 'total-cost', 'subagent-cost', 'working-time', 'average-cost']);
  const face = value => typeof value === 'string' ? value.replace(/\b(?:N\/A|Not Applicable)\b/gi, '—') : value;
  const mainFileHelp = '\n\nMeasures only the main database file, excluding auxiliary files such as the SQLite WAL.';
  const databaseRows = [
    ['opencode_bytes', 'OpenCode DB',
      'OpenCode stores the source sessions used for CostGuard’s session-based statistics. In OpenCode v2, a deleted session ' +
      'stops contributing to refreshed source-backed results. Old derived cache entries may remain on disk for a while.'],
    ['cache_bytes', 'CostGuard Cache DB',
      'CostGuard keeps a disposable SQLite cache to speed up repeated analysis. Eligible old session-cache entries can be ' +
      'cleaned up when neither session activity nor meaningful use has occurred for at least 30 days. Cleanup runs while the ' +
      'host is idle, after at least 60 minutes of uptime—not immediately or on a fixed schedule. Removing entries may not ' +
      'shrink the database file straight away. Cleanup never deletes OpenCode source data.']
  ];
  const sizeUnits = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const sizeNumber = new Intl.NumberFormat('en', {maximumFractionDigits: 1});
  function formatFileSize(bytes) {
    if (!Number.isSafeInteger(bytes) || bytes < 0) return 'Size unavailable';
    let unit = 0;
    while (unit < sizeUnits.length - 1 && Math.round(bytes * 10) >= 10000) {
      bytes /= 1000; unit++;
    }
    return `${sizeNumber.format(bytes)} ${sizeUnits[unit]}`;
  }
  function valid(result) {
    const rows = result?.view?.ai_stats;
    return !result?.error && result?.view?.kind === 'ai-stats' && result.view.ai_stats_policy === 'fun-5-buckets' &&
      Array.isArray(rows) && rows.length > 0 && rows.every(row =>
      periods.some(([id]) => id === row.period) && row.metrics?.length === definitions.length && definitions.every(([key]) =>
        row.metrics.filter(metric => metric.metric === key && metric.value !== null && Number.isFinite(Number(metric.value)) &&
          typeof metric.display?.value === 'string' && typeof metric.display?.trait === 'string' &&
          (key !== 'total-tokens' || /^\d+$/.test(metric.exact_value) && typeof metric.display.token_help === 'string') &&
          ['usd', 'credits'].every(unit => typeof (metric.display_units?.[unit]?.value ?? metric.display.value) === 'string' &&
             (key !== 'hourly-rate' ||
               typeof (metric.display_units?.[unit]?.rate_help ?? metric.display.rate_help) === 'string')) &&
           (!podiumMetrics.has(key) || Array.isArray(metric.podium) && metric.podium.length <= 3 &&
             metric.podium.every(row => typeof row.label === 'string' && typeof row.model_help === 'string' &&
                (key === 'token-rate' || Number.isFinite(Number(row.podium_value)) &&
                  (key === 'hourly-rate' ? Number(row.podium_value) >= 0 : Number(row.podium_value) > 0)) &&
               ['usd', 'credits'].every(unit => typeof (row.display_units?.[unit]?.amount ?? row.display?.amount ?? row.speed) === 'string'))) &&
           (key !== 'token-rate' ||
              typeof metric.display.response_help === 'string' &&
              (metric.podium.length ? Number(metric.value) > 0 : Number(metric.value) === 0) && metric.podium.every(row =>
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
      state.statsAcquisitionFailed = false;
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
    if (state.result) state.statsAcquisitionFailed = false;
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
      this.databaseValues = new Map();
      this.databaseRefresh = 0;
      this.hasOpenCodeSize = false;
      for (const [name, items] of [['Overview', definitions.slice(0, 7)], ['Fun Facts', definitions.slice(7)]]) {
        const section = e('section', undefined, 'ai-stats-section'), grid = e('div', undefined, 'ai-stats-grid');
        section.append(e('h3', name), grid); this.grid.append(section);
        for (const [key, icon, title, help] of items) {
          const card = e('article', undefined, 'ai-stat'), heading = e('h4');
          card.dataset.metric = key;
          const symbol = e('span', icon, 'ai-stat-icon'); symbol.setAttribute('aria-hidden', 'true');
          const retained = {metric: null, podium: []};
          const hourly = key === 'hourly-rate', hasPodium = podiumMetrics.has(key), response = key === 'token-rate';
          const helpButton = ContextHelp.button(title, () => retained.metric && (hourly || response || key === 'total-tokens') ?
            ReportView.display(retained.metric, hourly ? 'rate_help' : response ? 'response_help' : 'token_help') : help);
          heading.append(symbol, helpButton);
          const value = e('p', '', 'ai-stat-value'), detail = e('p', '', 'ai-stat-detail');
          const podium = e('div', undefined, 'ai-stat-podium');
          if (hasPodium) {
            if (response) card.classList.add('ai-stat-response');
            for (const medal of ['🥇', '🥈', '🥉']) {
              const row = e('div', undefined, 'ai-stat-racer'), label = e('span', '', 'ai-stat-model');
              ContextHelp.value(label, () => {
                const row = retained.metric?.podium[retained.podium.findIndex(item => item.label === label)];
                return row ? ReportView.aiStatsModelHelp(row) : '';
              });
              const icon = e('span', medal); icon.setAttribute('aria-hidden', 'true');
              const speed = e('span', '', 'ai-stat-speed');
              row.append(icon, label, speed); row.setAttribute('role', 'group');
              retained.podium.push({row, label, speed});
            }
          }
          const trait = e('p', '', 'ai-stat-trait');
          grid.append(card);
          this.cards.set(key, Object.assign(retained, {card, title, nodes: [heading, value, podium, detail, trait], value, podiumNode: podium, detail, trait}));
          card.append(heading, value, podium, detail, trait);
        }
        if (name === 'Fun Facts') {
          this.funFacts = grid;
          this.databaseCard = e('article', undefined, 'ai-stat ai-stat-databases');
          const rows = e('dl');
          for (const [key, label, help] of databaseRows) {
            const row = e('div', undefined, 'ai-stat-size-row'), term = e('dt');
            term.append(ContextHelp.button(label, help + mainFileHelp));
            const value = e('dd', formatFileSize(null));
            row.append(term, value); rows.append(row);
            this.databaseValues.set(key, value);
          }
          this.databaseCard.append(e('h4', 'Database Sizes'), rows);
          grid.append(this.databaseCard);
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
    async refreshDatabaseSizes() {
      // Optional local facts never share the report request or its error state.
      const request = ++this.databaseRefresh;
      let sizes;
      try {
        const response = await fetch('/api/database-sizes', {credentials: 'same-origin', cache: 'no-store',
          signal: AbortSignal.timeout(5000)});
        if (response.ok) sizes = await response.json();
      } catch (_) { /* A failed read only affects this card. */ }
      if (request !== this.databaseRefresh) return;
      const openCodeSize = formatFileSize(sizes?.opencode_bytes);
      this.hasOpenCodeSize = openCodeSize !== 'Size unavailable';
      ReportView.text(this.databaseValues.get('opencode_bytes'), openCodeSize);
      ReportView.text(this.databaseValues.get('cache_bytes'), formatFileSize(sizes?.cache_bytes));
    }
    update(state, sourceBlocked) {
      // Every card has its shell from first render. Only a complete compatible
      // period observation replaces the last-good cards, including their details.
      const e = ReportView.element;
      if (state.result?.source) {
        this.sourceIdentity = JSON.stringify([
          state.result.source.identity, state.result.source.generation, state.result.view.timezone_id]);
        this.timezone = state.result.view.timezone_id;
      }
      const identity = state.statsIdentity ?? this.sourceIdentity;
      const day = ReportView.formatDateTime(Date.now(), ReportView.DateTimeMode.DATE,
        state.result?.view.timezone_id ?? this.timezone ?? ReportView.configuredTimezone());
      const scope = JSON.stringify([identity, state.period,
        state.period === 'all' ? null : state.period === 'month' ? day.slice(0, 7) : day]);
      for (const [id, button] of this.buttons) button.setAttribute('aria-pressed', String(id === state.period));
      const ready = state.result?.view?.ai_stats_work?.scopes?.[state.period]?.ready === true;
      const row = ready && valid(state.result) && state.result.view.ai_stats.find(item => item.period === state.period);
      if (!row) {
        if (this.readyScope === scope) return;
        this.readyScope = null;
        const pending = !sourceBlocked && !state.interrupted && !state.statsAcquisitionFailed;
        for (const [key, item] of this.cards) {
          item.metric = null;
          ReportView.valueSlot(item.value, key === 'token-rate' ? '' : '—', {pending, field: item.title});
          ReportView.text(item.detail, ''); ReportView.text(item.trait, '');
          if (item.podiumNode.firstChild) item.podiumNode.replaceChildren();
        }
        this.extra.remove();
        return;
      }
      // Reveal each complete card in this synchronous commit; retain nodes on quiet refresh.
      this.readyScope = scope;
      this.costs ||= new ReportView.CostDisplay();
      for (let metric of row.metrics) {
        if (costMetrics.has(metric.metric)) {
          metric = this.costs.select(metric, [state.result.source?.identity, state.result.source?.generation,
            row.period, row.start_ms, metric.metric,
            metric.metric === 'expensive-session' ? metric.session_id : null], 'value',
            metric.metric === 'subagent-cost' || !metric.reasons?.length, metric.value,
            ['value', 'rate_help']);
        }
        const card = this.cards.get(metric.metric);
        if (costMetrics.has(metric.metric)) card.costScope = scope;
        card.metric = metric;
        ReportView.valueSlot(card.value, () => face(ReportView.display(metric, 'value')));
        if (card.podium.length) {
          if (metric.podium.length) {
            for (const [index, item] of card.podium.entries()) {
              const racer = metric.podium[index];
              if (!racer) { item.row.remove(); continue; }
              ReportView.text(item.label, racer.label);
              ReportView.text(item.speed, () => face(racer.speed ?? ReportView.display(racer, 'amount')));
              item.row.setAttribute('aria-label', `Rank ${index + 1}: ${racer.label}`);
            }
            const nodes = card.podium.slice(0, metric.podium.length).map(item => item.row);
            if (nodes.some((node, index) => card.podiumNode.children[index] !== node) || card.podiumNode.children.length !== nodes.length)
              card.podiumNode.replaceChildren(...nodes);
          } else if (card.podiumNode.firstChild) card.podiumNode.replaceChildren();
        }
        ReportView.text(card.trait, face(metric.display.trait));
        const target = card.detail.querySelector('a');
        if (metric.session_title && /^[A-Za-z0-9_-]{1,200}$/.test(metric.session_id)) {
          const link = target || e('a'); ReportView.text(link, metric.session_title);
          link.href = '#/sessions/' + metric.session_id;
          if (!target) card.detail.replaceChildren(link);
        } else ReportView.text(card.detail, metric.metric === 'token-rate' ? '' : face(metric.detail || ''));
      }
      if (!this.content.contains(this.grid)) this.content.replaceChildren(this.grid);
      if (row.matched) {
        ReportView.text(this.extraHeading, row.matched.metric === 'original-thinker' ? 'Original Thinker' : 'Biggest AI Speed Gap');
        ReportView.text(this.extraValue, () => face(ReportView.display(row.matched, 'value')));
        ReportView.text(this.extraTrait, face(row.matched.display.trait)); ReportView.text(this.extraDetail, face(row.matched.detail));
        if (!this.funFacts.contains(this.extra)) this.funFacts.insertBefore(this.extra, this.databaseCard);
      } else this.extra.remove();
      ContextHelp.refresh(this.root);
    }
    attach(parent) { if (parent.firstChild !== this.root) parent.replaceChildren(this.root); }
  }
  return {View, valid, remember, observe, prioritize};
})();
