'use strict';
// Historical-report display policy only; never used by live views.
const CachedReports = (() => {
  const cadences = {models: 3600000, 'token-mix': 300000, 'ai-stats': 900000, comparisons: 300000};
  const observation = result => result?.source ? result.source.observed_at_ms : result?.observed_at_ms;
  function entry(result, section, now = Date.now()) {
    if (!result) return 'missing';
    const seen = observation(result);
    if (!Number.isSafeInteger(seen) || seen < 0 || now < seen || result.error) return 'withhold';
    return now - seen > cadences[section] ? 'quiet' : 'fresh';
  }
  function interval(result, period) {
    const row = result?.view?.ai_stats?.find(value => value.period === period);
    const zone = result?.scope?.timezone_id;
    if (!row || typeof zone !== 'string' || !Number.isSafeInteger(row.end_ms) || row.end_ms < 0 ||
        !(period === 'all' && row.start_ms === null ||
          Number.isSafeInteger(row.start_ms) && row.start_ms >= 0 && row.start_ms <= row.end_ms)) return null;
    try {
      const format = value => new Intl.DateTimeFormat('sv-SE', {timeZone: zone,
        dateStyle: 'short', timeStyle: 'short'}).format(value);
      return `${row.start_ms === null ? 'All available history' : format(row.start_ms)} → ${format(row.end_ms)} (${zone})`;
    } catch (_) { return null; }
  }
  function summary(state, writable, managed) {
    if (state.section === 'ai-stats') return '';
    if (!state.result || state.withheld) return '';
    const observed = observation(state.result);
    if (entry(state.result, state.section) === 'withhold') return '';
    const refresh = !writable ? 'Not updating.' : managed ? ({running: 'Updating…', queued: 'Refresh queued.',
      scheduled: 'Refresh scheduled.', delayed: 'Update delayed; automatic retry scheduled.',
      waiting: 'Waiting for source recovery.', stopped: 'Not updating; see source error.'}[state.dispatchRefresh] ||
      'Checking refresh status…') : state.failed ? 'Update delayed; last completed report retained.' :
      state.loading ? 'Updating…' : 'Refresh scheduled.';
    return `Historical snapshot as of ${new Date(observed).toLocaleString()}. ${refresh}`;
  }
  return {cadences, observation, entry, interval, summary};
})();
