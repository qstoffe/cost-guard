"""Fair shared detail acquisition and immutable revision-aware 50-row pages.

HTTP callers only read detached pages/enqueue captures; the host's detail lane alone
touches the existing service. Leases bound admission, never logical history.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import logging
from threading import Lock
import time
from uuid import uuid4

from src.pricing.base import PricingUnavailableError
from src.sources.errors import SourceError, SessionExportError

from .detail_archive import DOMAIN as ARCHIVE_DOMAIN, archived_page, refresh_detail, save_detail
from .projection import identity, project
from .session_activity import ActivityHistory, activity_page, activity_summary
from .session_export_archive import analysis_filename, build_analysis_zip
from .session_values import INVALID_REASONS, value_authority
from .session_quota import session_quota_evidence, session_quota_usage


LOG = logging.getLogger(__name__)
RECOVERABLE = frozenset({
    'detail_not_admitted', 'detail_no_progress', 'detail_worker_failed', 'detail_internal_error',
    'source_unavailable', 'concurrent_source_change', 'connection_timeout', 'connection_reset',
    'connection_refused', 'connection_disconnected', 'endpoint_unresponsive', 'registration_missing',
    'pricing_unavailable', 'v1_database_missing',
})


def prompt_activity(rows):
    # Exclude compaction, clocks, prices, tokens and text. This is presentation
    # evidence, never authority to synthesize or amend a canonical prompt row.
    return {row.event_id: (row.in_progress, row.execution_unverified,
        row.completed_at_ms, row.aborted, row.watch_error, row.completed_successfully)
        for row in rows if not row.is_compaction}


class SessionDetails:
    def __init__(self, *, clock=time.monotonic, archive=None):
        self.clock = clock
        self.lock = Lock()
        self.histories = OrderedDict()
        self.leases = OrderedDict()
        self.quota_context = None
        self.quota_capacities = {}
        self.archive = archive
        self.partition = None
        self.archive_target = None
        self.cache_reader = (ThreadPoolExecutor(max_workers=1, thread_name_prefix='cost-guard-detail-restore')
                             if archive else None)

    def bind_archive(self, partition, target):
        with self.lock:
            if self.archive_target is not None and target != self.archive_target:
                for entry in self.histories.values():
                    # Keep archived reads and transport leases across source changes.
                    entry.update(history=ActivityHistory(), result=None, revision=None, due=0,
                                 state='loading', activity=None, attempt=None, retry_at=None,
                                 source_signal=None, activity_signal=None, quota_evidence=None,
                                 export_identity=None, saved_revision=None, source_unavailable=True)
                    entry['acquisition'].update(phase='queued', reason=None, attempts=0, changed_at=self.clock())
                for lease in self.leases.values():
                    lease.pop('reading', None)
                    lease['frozen'] = None
                self.quota_context = None
                self.quota_capacities.clear()
            self.partition = partition
            self.archive_target = target

    def close_archive(self):
        if self.cache_reader:
            self.cache_reader.shutdown(wait=True, cancel_futures=True)

    def observe_accounts(self, accounts, source, now_ms, *, stale=False):
        # One shared Live observation; no IO and no table/history revaluation.
        with self.lock:
            self.quota_context = accounts, source, now_ms, stale

    def observe_source(self, observation, cards=None, *, unavailable=False):
        """Reuse selected-root revisions and proven Watch rows; no source reads."""
        with self.lock:
            for key, entry in self.histories.items():
                if not self._active(key):
                    continue
                revision = observation.revisions.get(key) if observation is not None else None
                entry['source_unavailable'] = unavailable or (observation is not None and revision is None)
                if entry['source_unavailable']:
                    entry['export_identity'] = None
                if unavailable or observation is None:
                    continue
                if revision is None:
                    continue
                signal = observation.source_epoch, revision
                previous = entry.get('source_signal')
                if previous != signal:
                    entry['source_signal'] = signal
                    if previous is not None:
                        self._wake(entry)
                if entry.get('activity_signal') and entry['activity_signal'][0] != signal[0]:
                    entry['activity_signal'] = None
                if cards is not None:
                    self._observe_watch(entry, key, signal, cards.get(key))

    def _observe_watch(self, entry, key, signal, card):
        if (not entry['activity'] or card is None or card.snapshot is None or card.capture is None
                or card.verified_generation != card.generation or card.source_status.failed_at is not None
                or not card.capture.authoritative or card.capture.retained
                or card.snapshot.source_revision != signal[1]
                or card.capture.observed_at_ms < entry['observed_at_ms']):
            return
        provenance = card.snapshot.root.provenance
        scope = identity((provenance.source_type, provenance.source_generation, provenance.source_instance,
            signal[0], key))
        if scope != entry['activity']['scope']:
            entry['activity_signal'] = None
            return
        # A capture for the already-reconciled source revision is not new work.
        # Compare once per Watch observation and canonical activity version.
        if signal[1] == entry.get('captured_source_revision'):
            return
        observed = (signal, card.capture.observed_at_ms, entry.get('activity_revision'))
        if observed == entry.get('watch_activity_observation'):
            return
        entry['watch_activity_observation'] = observed
        current = prompt_activity(row for row in card.capture.rows if row.event_id in card.capture.observed_ids)
        previous = entry.get('prompt_activity', {})
        if any(event not in previous or (
                previous[event] != state and not state[1] and (state[0] or state[2] is not None))
                for event, state in current.items()):
            if entry.get('activity_signal') != signal:
                if not entry.get('activity_signal'):
                    entry['activity_queued_at'] = self.clock()
                entry['activity_signal'] = signal
                if entry['attempt'] is None or entry.get('attempt_signal') != signal:
                    self._wake(entry)
        else:
            entry['activity_signal'] = None

    def _wake(self, entry):
        # Hints never reset retry budgets, cooldowns or terminal errors.
        if entry['acquisition']['reason'] is not None or entry['acquisition']['phase'] in {'failed', 'retrying'}:
            return
        entry['wake'] = True
        entry['due'] = min(entry['due'], self.clock())

    def wake(self, token):
        with self.lock:
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError('detail_expired')
            lease['touched'] = self.clock()
            if lease['mode'] == 'live':
                entry = self.histories[lease['session_id']]
                if self.clock() - entry.get('requested_at', -float('inf')) >= 1:
                    entry['requested_at'] = self.clock()
                    self._wake(entry)

    def live_hints(self):
        with self.lock:
            return [dict(session_id=key, hint=identity((entry.get('source_signal'), entry['generation'],
                entry.get('activity_signal'), entry.get('source_unavailable'))))
                for key, entry in self.histories.items() if self._active(key)]

    def archive_hints(self):
        changes = self.archive.generation(ARCHIVE_DOMAIN) if self.archive is not None else 0
        return [{**item, 'hint': identity((item['hint'], changes))} for item in self.live_hints()]

    def open(self, session_id, mode):
        with self.lock:
            # Reclaim abandoned transport handles, not observed history/rows.
            for token, lease in tuple(self.leases.items()):
                if self.clock() - lease["touched"] > 300:
                    del self.leases[token]
            if session_id not in self.histories:
                leased = {lease['session_id'] for lease in self.leases.values()}
                while len(self.histories) >= 16:
                    victim = next((key for key in self.histories if key not in leased), None)
                    if victim is None:
                        break
                    del self.histories[victim]
            if len(self.leases) >= 32 or (session_id not in self.histories and len(self.histories) >= 16):
                raise RuntimeError("detail_busy")
            entry = self.histories.setdefault(session_id, dict(history=ActivityHistory(), result=None, activity=None,
                revision=None, due=0, state="loading", observed_at_ms=None, generation=0, timezone_id="UTC",
                value_authority=None, quota_evidence=None,
                row_observations={}, omitted_ids=frozenset(), ccost_display_unit="credits",
                 acquisition=dict(phase='queued', reason=None, attempts=0, completed=0, percent=0,
                    queued_at=self.clock(), changed_at=self.clock(), started_at=None), attempt=None,
                retry_windows=0, retry_at=None, attempt_leases=()))
            if entry['acquisition']['phase'] not in {'failed', 'retrying'}:
                entry["due"] = 0
            token = uuid4().hex
            self.leases[token] = dict(session_id=session_id, mode=mode, frozen=None,
                after=entry['generation'] - 1 if entry.get('validated') is not None and
                     0 <= self.clock() - entry['validated'] <= 3600 else entry['generation'], touched=self.clock())
            self._cache_read(entry, session_id)
            return token

    def _cache_read(self, entry, key):
        if not self.cache_reader:
            return None
        stamp = self.archive.generation(ARCHIVE_DOMAIN)
        saved = entry.get('cache_job')
        if saved is None or (saved[1].done() and self.clock() >= saved[2] and
                             (saved[0] != stamp or saved[1].result()[1] is None)):
            previous = saved[1].result() if saved is not None else (0, None)
            saved = (stamp, self.cache_reader.submit(refresh_detail, self.archive, key, previous),
                       self.clock() + 1)
            entry['cache_job'] = saved
            return previous[1]
        job = saved[1]
        return job.result()[1] if job.done() else None

    def invalidate(self):
        with self.lock:
            self.leases.clear()
            self.histories.clear()
            self.quota_context = None
            self.quota_capacities.clear()

    def freeze(self, token):
        with self.lock:
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError("detail_expired")
            entry = self.histories[lease["session_id"]]
            if entry["result"] is None:
                raise RuntimeError("detail_pending")
            lease["mode"] = "snapshot"
            lease["frozen"] = self._capture(entry)

    def close(self, token):
        with self.lock:
            self.leases.pop(token, None)

    def retry(self, token):
        """Explicit intent resets only the failure budget, never a valid snapshot."""
        with self.lock:
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError('detail_expired')
            entry = self.histories[lease['session_id']]
            entry['attempt'] = None
            entry['retry_windows'] = 0
            entry['retry_at'] = None
            entry['due'] = 0
            entry['acquisition'] = dict(phase='queued', reason=None, attempts=0, completed=0, percent=0,
                queued_at=self.clock(), changed_at=self.clock(), started_at=None)
            lease['touched'] = self.clock()

    def _active(self, key):
        return any(lease['session_id'] == key and self.clock() - lease['touched'] <= 300
                   and (lease['mode'] == 'live' or lease['frozen'] is None)
                   for lease in self.leases.values())

    def _attempt_active(self, key, entry):
        return any(token in self.leases and self.clock() - self.leases[token]['touched'] <= 300
                   for token in entry['attempt_leases'])

    def _schedule(self, entry):
        if entry['acquisition']['reason'] not in RECOVERABLE and not entry['acquisition'].get('recoverable'):
            entry['retry_at'] = None
            return
        entry['retry_windows'] = min(5, entry['retry_windows'] + 1)
        entry['retry_at'] = self.clock() + min(300, 30 * 2 ** (entry['retry_windows'] - 1))
        entry['due'] = entry['retry_at']
        LOG.info("detail_retry_scheduled reason=%s window=%s cooldown=%s",
            entry['acquisition']['reason'], entry['retry_windows'], entry['retry_at'] - self.clock())

    def claim(self, *, unavailable=False):
        with self.lock:
            # Re-arm only on the existing owner lane, after cooldown and while a
            # live lease still wants this source. HTTP reads cannot reset budgets.
            for key, entry in self.histories.items():
                if (not unavailable and self._active(key) and entry['attempt'] is None
                        and entry['acquisition']['phase'] == 'failed' and entry['retry_at'] is not None
                        and self.clock() >= entry['retry_at']):
                    entry['acquisition'] = dict(phase='queued', reason=None, attempts=0, completed=0, percent=0,
                        queued_at=self.clock(), changed_at=self.clock(), started_at=None)
                    entry['retry_at'] = None
            candidate = next(((key, entry) for key, entry in self.histories.items()
                if self._active(key) and self.clock() >= entry['due'] and entry['attempt'] is None
                and entry['acquisition']['phase'] != 'failed'), None)
            if candidate is None:
                return None
            key, entry = candidate
            self.histories.move_to_end(key)
            attempt = uuid4().hex
            entry['attempt'] = attempt
            entry['attempt_signal'] = entry.get('source_signal')
            entry['attempt_partition'] = self.partition
            entry['wake'] = False
            entry['attempt_leases'] = tuple(token for token, lease in self.leases.items()
                if lease['session_id'] == key and self.clock() - lease['touched'] <= 300)
            entry['acquisition'] = dict(phase='selecting', reason=None, percent=3, attempt_id=attempt,
                attempts=entry['acquisition']['attempts'] + 1, completed=0,
                queued_at=self.clock(), changed_at=self.clock(), started_at=self.clock())
            return key, attempt, entry['history']

    def current(self, key, attempt):
        with self.lock:
            entry = self.histories.get(key)
            return entry is not None and entry['attempt'] == attempt and self._attempt_active(key, entry)

    def progress(self, key, attempt, phase, completed, *, percent=0, phase_completed=-1, phase_total=-1):
        with self.lock:
            entry = self.histories.get(key)
            if entry is not None and entry['attempt'] == attempt:
                status = entry['acquisition']
                if completed > status['completed']:
                    status['changed_at'] = self.clock()
                    status['completed'] = completed
                status['phase'] = phase
                status['percent'] = max(status['percent'], min(69, max(0, percent)))
                measured = 0 <= phase_completed <= phase_total and phase_total > 0
                status['phase_completed'] = phase_completed if measured else None
                status['phase_total'] = phase_total if measured else None

    def finish(self, key, attempt, outcome):
        save = None
        with self.lock:
            entry = self.histories.get(key)
            if entry is None or entry['attempt'] != attempt:
                return
            entry['attempt'] = None
            if not self._attempt_active(key, entry):
                entry['acquisition']['phase'] = 'queued'
                entry['acquisition']['changed_at'] = self.clock()
                return
            reason = outcome.get('error')
            status = entry['acquisition']
            if reason:
                if reason in {"source_identity_changed", "session_missing"}:
                    entry["activity"] = None
                    for lease in self.leases.values():
                        if lease["session_id"] == key:
                            for name in ("reading", "frozen"):
                                if lease.get(name) is not None:
                                    lease[name] = {**lease[name], "activity": None}
                status['reason'] = reason
                status['recoverable'] = outcome.get('recoverable', False)
                status['phase'] = 'failed' if outcome.get('terminal') or status['attempts'] >= 3 else 'retrying'
                entry['due'] = self.clock() + 5 * status['attempts']
                if status['phase'] == 'failed':
                    self._schedule(entry)
                entry['state'] = outcome.get('state', 'source_unavailable')
                entry['export_identity'] = None
            else:
                report = outcome['report']
                previous_scope = (entry['activity'] or {}).get('scope')
                entry['history'] = outcome['history']
                entry['captured_source_revision'] = entry['history'].revision
                if outcome['changed']:
                    entry['result'] = report
                    entry['revision'] = uuid4().hex
                    activity = prompt_activity(report.prompt_blocks[0].rows)
                    if entry.get('prompt_activity') != activity:
                        entry['prompt_activity'] = activity
                        entry['activity_revision'] = entry['revision']
                entry.update(outcome['metadata'])
                if (self.archive and self.partition and self.partition == entry['attempt_partition']
                        and not entry['history'].retained and outcome['state'] == 'observed'
                        and entry['history'].revision != entry.get('saved_revision')):
                    save = self.partition, entry['history'].revision, report, outcome['metadata']
                signal = entry.get('activity_signal')
                if signal and (signal[1] == entry['captured_source_revision']
                        or previous_scope != (entry['activity'] or {}).get('scope')):
                    entry['activity_signal'] = None
                entry['validated'] = self.clock()
                if entry['retry_windows']:
                    LOG.info("detail_recovered windows=%s", entry['retry_windows'])
                entry['retry_windows'] = 0
                entry['retry_at'] = None
                entry['state'] = outcome['state']
                status.update(phase='ready', reason=None, attempts=0, percent=70,
                    phase_completed=None, phase_total=None)
                entry['due'] = self.clock() + (0 if entry.get('wake') else 5)
            entry['generation'] += 1
        if save is not None:
            partition, revision, report, metadata = save
            if save_detail(self.archive, partition, key, revision, report, metadata):
                with self.lock:
                    if (self.histories.get(key) is entry and self.partition == partition
                            and entry['history'].revision == revision):
                        entry['saved_revision'] = revision

    def acquisition_status(self, entry):
        status = entry['acquisition']
        age = max(0, self.clock() - status['changed_at'])
        # A stopped/uninitialized owner must not leave an eternal unadmitted bar.
        if (entry['attempt'] is None and ((status['phase'] == 'queued' and age >= 120)
                or (entry.get('activity_signal') and status['phase'] == 'ready'
                    and self.clock() - entry['activity_queued_at'] >= 120))):
            status.update(phase='failed', reason='detail_not_admitted')
            self._schedule(entry)
        return dict(phase=status['phase'], reason=status['reason'], attempts=status['attempts'],
            attempt_id=status.get('attempt_id'), percent=status['percent'],
            phase_completed=status.get('phase_completed'), phase_total=status.get('phase_total'),
            completed=status['completed'], progress_age_seconds=int(age),
            attempt_age_seconds=int(max(0, self.clock() - (status['started_at'] or self.clock()))),
            retry_available=status['phase'] == 'failed',
            retry_after_seconds=max(0, int(entry['retry_at'] - self.clock())) if entry['retry_at'] is not None else None)

    def failed(self, reason):
        with self.lock:
            for key, entry in self.histories.items():
                if self._active(key):
                    entry['attempt'] = None
                    entry['acquisition'].update(phase='failed', reason=reason)
                    self._schedule(entry)

    def export_identity(self, token):
        """Only a freshly observed canonical selection may authorize transfer."""
        with self.lock:
            lease = self.leases.get(token)
            if lease is None or self.clock() - lease['touched'] > 300:
                raise KeyError('detail_expired')
            entry = self.histories[lease['session_id']]
            validated = entry.get('validated')
            if entry.get('source_unavailable') or validated is None or self.clock() - validated > 3600:
                return None
            return entry.get('export_identity')

    def export(self, token, source, cancelled):
        identity = self.export_identity(token)
        capability = getattr(source, 'export_session_tree', None)
        if not identity or not callable(capability):
            raise SessionExportError('export_unavailable')
        source_id, instance, epoch, session_id = identity
        if (source_id, instance) != (source.source_id, source.source_instance):
            raise SessionExportError('export_source_changed')
        def retired():
            try:
                return cancelled() or self.export_identity(token) != identity
            except KeyError:
                return True
        payload = build_analysis_zip(lambda cancelled: capability(session_id, epoch, cancelled), retired)
        if retired():
            raise SessionExportError('export_cancelled')
        return payload, f'opencode-{session_id}-analysis.zip'

    @staticmethod
    def _capture(entry):
        return {name: entry[name] for name in ("result", "revision", "state", "observed_at_ms",
                                              "row_observations", "omitted_ids", "timezone_id", "ccost_display_unit", "activity",
                                              "value_authority", "quota_evidence")} | {
            'activity_revision': entry.get('activity_revision')}

    def activity_page(self, token, revision, offset):
        with self.lock:
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError("detail_expired")
            saved = lease.get('cached_reading')
            if saved and revision == identity(('durable-history', saved.revision, saved.observed_ms)):
                lease['touched'] = self.clock()
                activity = saved.value.get('activity')
                if activity is None:
                    raise KeyError('detail_expired')
                return dict(revision=revision, **activity_page(activity, offset))
            capture = lease.get("reading") or lease["frozen"]
            if capture is None or capture["revision"] != revision or capture["activity"] is None:
                raise KeyError("detail_expired")
            lease["touched"] = self.clock()
            return dict(revision=revision, **activity_page(capture["activity"], offset))

    def page(self, token, offset, revision=None, anchor=None, *, begin=False, chunk=False):
        if self.archive:
            with self.lock:
                lease = self.leases.get(token)
                if lease is None:
                    raise KeyError('detail_expired')
                key = lease['session_id']
                entry = self.histories[key]
                saved = (lease.get('cached_reading') if chunk else None) or lease.get('cached_frozen')
                cache = self._cache_read(entry, key) if not chunk and not saved else None
                current = entry['result'] is not None and not entry.get('source_unavailable') and (
                    entry['acquisition']['reason'] not in INVALID_REASONS)
                reconciled = (current and cache is not None and cache.partition == self.partition
                              and cache.observed_ms >= (entry['observed_at_ms'] or 0))
                use_cache = (entry['result'] is None or entry.get('source_unavailable') or
                             entry['acquisition']['reason'] in INVALID_REASONS or reconciled) and lease['frozen'] is None
                mode = lease['mode']
                if use_cache or saved:
                    lease['touched'] = self.clock()
                    status = self.acquisition_status(entry)
                if use_cache and not chunk and not saved:
                    saved = cache
                    if saved:
                        if begin:
                            lease['cached_reading'] = saved
                            lease.pop('reading', None)
                        if mode == 'snapshot':
                            lease['cached_frozen'] = saved
                    elif begin:
                        lease.pop('cached_reading', None)
                elif begin and not saved:
                    lease.pop('cached_reading', None)
            if saved:
                response = archived_page(saved, revision, offset, anchor, mode=mode, begin=begin, chunk=chunk,
                                         acquisition=status if status['phase'] == 'failed' else None)
                if reconciled and begin and mode == 'live':
                    response['export_available'] = self.export_identity(token) is not None
                    if response['export_available']:
                        block, = response['result']['view']['prompt_blocks']
                        response['export_name'] = analysis_filename(block.get('title'), key)
                return response
        with self.lock:
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError("detail_expired")
            lease["touched"] = self.clock()
            entry = self.histories[lease["session_id"]]
            if (lease["mode"] == "snapshot" and lease["frozen"] is None and entry['result'] is not None
                    and entry["generation"] > lease["after"]):
                lease["frozen"] = self._capture(entry)
            if begin:
                lease["reading"] = lease["frozen"] or self._capture(entry)
            capture = lease.get("reading") if chunk else lease["frozen"] or self._capture(entry)
            if begin:
                capture = lease["reading"]
            if chunk and (capture is None or capture["revision"] != revision):
                raise KeyError("detail_expired")
            pending = lease["frozen"] is None and entry["generation"] <= lease["after"]
            expired = entry.get('validated') is None or not 0 <= self.clock() - entry['validated'] <= 3600
            pending = pending or expired
            acquisition = self.acquisition_status(entry)
            export_available = bool(entry.get('export_identity'))
            invalidated = acquisition["reason"] in INVALID_REASONS
            if self.archive and entry.get('source_unavailable') and lease['frozen'] is None:
                pending = True  # Do not show old Running while the cache read catches up.
            activity_refresh = None
            if begin and not pending and lease['mode'] == 'live' and entry.get('activity_signal'):
                if entry.get('source_unavailable') or acquisition['reason']:
                    activity_refresh = 'unavailable'
                else:
                    activity_refresh = 'pending'
            quota_context = self.quota_context
        report = capture["result"]
        if pending or report is None:
            return dict(state=capture["state"], pending=pending, result=None, acquisition=acquisition,
                        values_invalidated=invalidated, activity_refresh=activity_refresh)
        block = report.prompt_blocks[0]
        rows = block.rows
        stale = revision is not None and revision != capture["revision"]
        if stale and anchor:
            offset = next((i for i, row in enumerate(rows) if
                identity((block.session_id, row.event_id, row.is_compaction)) == anchor), offset)
        offset = (max(0, len(rows) - 50) if offset >= 2**52 else
                  max(0, min(offset, max(0, len(rows) - 1))))
        size = 25 if begin or chunk else 50
        page = replace(report, prompt_blocks=(replace(block, rows=rows[offset:offset + size]),))
        view = project(page, capture["timezone_id"], capture["ccost_display_unit"], prompt_details=begin or chunk).to_json()
        for row in view["prompt_blocks"][0]["rows"]:
            row["id"] = identity((block.session_id, row["event_id"], row["is_compaction"]))
            row["last_observed_at_ms"] = capture["row_observations"].get(row["event_id"])
            row["retained"] = row["event_id"] in capture["omitted_ids"]
        authority = capture["value_authority"]
        if authority is not None:
            authority = {**authority, "rows": {row["event_id"]: authority["rows"].get(row["event_id"])
                for row in view["prompt_blocks"][0]["rows"]}}
        usage = None
        if quota_context is not None and not invalidated and not chunk:
            accounts, source, now_ms, quota_stale = quota_context
            with self.lock:
                usage = session_quota_usage(capture.get("quota_evidence"), accounts, source, now_ms,
                    stale=quota_stale or acquisition['phase'] == 'failed', capacity_cache=self.quota_capacities)
        return dict(state=capture["state"], revision=capture["revision"], stale_cursor=stale,
             **(dict(activity_refresh=activity_refresh, activity_revision=capture['activity_revision']) if begin else {}),
            **(dict(quota_usage=usage) if not chunk else {}),
            values_invalidated=invalidated,
            value_authority=authority,
            **(dict(activity=activity_summary(capture["activity"])) if not chunk else {}),
            offset=offset, total=len(rows), pending=False, mode=lease["mode"],
            **(dict(acquisition=acquisition) if acquisition['phase'] == 'failed' and lease['frozen'] is None else {}),
             export_available=export_available,
             **(dict(export_name=analysis_filename(block.title, block.session_id)) if export_available and not chunk else {}),
            result=dict(observed_at_ms=capture["observed_at_ms"], view=view,
                        source=dict(status="partial" if capture["state"] != "observed" else "acquired",
                                    atomicity="per_root_snapshot")))

    def tick(self, service, *, unavailable=False):
        claimed = self.claim(unavailable=unavailable)
        if claimed is not None:
            key, attempt, history = claimed
            self.finish(key, attempt, acquire_detail(service, history, key, unavailable=unavailable))


def acquire_detail(service, history, key, *, unavailable=False):
    """Private execution result; only the parent owner can publish its attempt."""
    if unavailable or service is None:
        return dict(error='source_unavailable')
    try:
        previous = history.report
        report, state = history.acquire(service, key)
        if report is None:
            return dict(error=state, state=state, terminal=True)
        source = service.source
        export_identity = ((source.source_id, source.source_instance,
            getattr(source, 'observation_epoch', None), report.prompt_blocks[0].session_id)
             if state == 'observed' and callable(getattr(source, 'export_session_tree', None)) else None)
        return dict(history=history, report=report, state=state, changed=report is not previous,
            metadata=dict(timezone_id=service.timezone_id,
                ccost_display_unit=service.config.get('ccostDisplayUnit', 'credits'),
                activity=history.activity_for(source, report.prompt_blocks[0].rows),
                 value_authority=value_authority(history, source),
                 quota_evidence=session_quota_evidence(history, service),
                observed_at_ms=service.now_ms, row_observations=history.row_observations,
                omitted_ids=history.omitted_ids, export_identity=export_identity))
    except SourceError as error:
        return dict(error=error.code.value, terminal=error.terminal,
            recoverable=not error.terminal and error.readiness_retryable)
    except PricingUnavailableError:
        return dict(error='pricing_unavailable')
    except Exception:
        return dict(error='detail_internal_error', terminal=True)
