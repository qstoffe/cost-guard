'use strict';
// Historical-report display policy only; never used by live views.
const CachedReports = (() => {
  const cadences = {'token-mix': 300000, 'ai-stats': 900000, comparisons: 300000};
  const observation = result => result?.source?.observed_at_ms ?? result?.observed_at_ms;
  function entry(result, section, now = Date.now()) {
    if (!result) return 'missing';
    const seen = observation(result);
    if (!Number.isFinite(seen) || now - seen > 3600000) return 'withhold';
    return now - seen > cadences[section] ? 'quiet' : 'fresh';
  }
  return {cadences, observation, entry};
})();
