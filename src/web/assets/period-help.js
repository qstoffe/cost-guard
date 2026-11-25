'use strict';
// Shared server calendar starts and a live end. Only visible help renews its read.
const PeriodHelp = (() => {
  let read, ranges, pending, lastRead = -Infinity, retryAt = -Infinity;
  const clock = () => performance.now();
  function load() {
    if (!read || pending || clock() < retryAt) return;
    pending = read().then(value => {
      ranges = value;
      lastRead = clock();
    }).catch(() => { retryAt = clock() + 5000; })
      .finally(() => { pending = null; });
  }
  function range(period) {
    const now = Date.now();
    const current = ranges && now < ranges.valid_until;
    if (!current || period === 'all' && clock() - lastRead >= 5000) load();
    const zone = ranges?.timezone_id || ReportView.configuredTimezone();
    const format = ms => ReportView.formatDateTime(ms, ReportView.DateTimeMode.DATE_TIME_SECONDS, zone);
    const first = period === 'all' ? ranges?.first_prompt_ms : current ? ranges.starts[period] : null;
    const known = Number.isSafeInteger(first) && first <= now;
    const start = known ? format(first) : period === 'all' && ranges?.history_complete && first === null
      ? 'No recorded prompts' : 'Start not yet known';
    const qualifier = known && period === 'all' && !ranges.history_complete ? 'Earliest recorded so far: ' : '';
    return `${qualifier}${start} – ${format(now)}`;
  }
  return {
    configure(reader) { read = reader; },
    attach(button, period) {
      if (!ranges) load();
      ContextHelp.timedAction(button, () => range(period));
    },
    range,
  };
})();
