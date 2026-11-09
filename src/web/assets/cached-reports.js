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
    const end = ReportView.timestamp(row.end_ms, zone);
    const start = row.start_ms === null ? 'All available history' : ReportView.timestamp(row.start_ms, zone);
    return start === 'N/A' || end === 'N/A' ? null : `${start} → ${end} (${zone})`;
  }
  return {cadences, observation, entry, interval};
})();
