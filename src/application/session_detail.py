"""Fair shared detail acquisition and immutable revision-aware 50-row pages.

HTTP callers only read detached pages/enqueue captures; the host's detail lane alone
touches the existing service. Leases bound admission, never logical history.
"""
from collections import OrderedDict
from dataclasses import replace
from threading import Lock
import time
from uuid import uuid4

from src.pricing.base import PricingUnavailableError
from src.reports.session_history import SessionHistory
from src.sources.errors import SourceError, SessionExportError

from .projection import identity, project


class SessionDetails:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self.lock = Lock()
        self.histories = OrderedDict()
        self.leases = OrderedDict()

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
            entry = self.histories.setdefault(session_id, dict(history=SessionHistory(), result=None,
                revision=None, due=0, state="loading", observed_at_ms=None, generation=0, timezone_id="UTC",
                row_observations={}, omitted_ids=frozenset(), ccost_display_unit="credits",
                acquisition=dict(phase='queued', reason=None, attempts=0, completed=0,
                    queued_at=self.clock(), changed_at=self.clock(), started_at=None), attempt=None))
            if entry['acquisition']['phase'] != 'failed':
                entry["due"] = 0
            token = uuid4().hex
            self.leases[token] = dict(session_id=session_id, mode=mode, frozen=None,
                after=entry['generation'] - 1 if entry.get('validated') is not None and
                    0 <= self.clock() - entry['validated'] <= 3600 else entry['generation'], touched=self.clock())
            return token

    def invalidate(self):
        with self.lock:
            self.leases.clear()
            self.histories.clear()

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
            entry['due'] = 0
            entry['acquisition'] = dict(phase='queued', reason=None, attempts=0, completed=0,
                queued_at=self.clock(), changed_at=self.clock(), started_at=None)
            lease['touched'] = self.clock()

    def _active(self, key):
        return any(lease['session_id'] == key and self.clock() - lease['touched'] <= 300
                   and (lease['mode'] == 'live' or lease['frozen'] is None)
                   for lease in self.leases.values())

    def claim(self):
        with self.lock:
            candidate = next(((key, entry) for key, entry in self.histories.items()
                if self._active(key) and self.clock() >= entry['due'] and entry['attempt'] is None
                and entry['acquisition']['phase'] != 'failed'), None)
            if candidate is None:
                return None
            key, entry = candidate
            self.histories.move_to_end(key)
            attempt = uuid4().hex
            entry['attempt'] = attempt
            entry['acquisition'] = dict(phase='reading', reason=None,
                attempts=entry['acquisition']['attempts'] + 1, completed=0,
                queued_at=self.clock(), changed_at=self.clock(), started_at=self.clock())
            return key, attempt, entry['history']

    def current(self, key, attempt):
        with self.lock:
            entry = self.histories.get(key)
            return entry is not None and entry['attempt'] == attempt and self._active(key)

    def progress(self, key, attempt, phase, completed):
        with self.lock:
            entry = self.histories.get(key)
            if entry is not None and entry['attempt'] == attempt:
                status = entry['acquisition']
                if completed > status['completed']:
                    status['changed_at'] = self.clock()
                    status['completed'] = completed
                status['phase'] = phase

    def finish(self, key, attempt, outcome):
        with self.lock:
            entry = self.histories.get(key)
            if entry is None or entry['attempt'] != attempt:
                return
            entry['attempt'] = None
            if not self._active(key):
                entry['acquisition']['phase'] = 'queued'
                return
            reason = outcome.get('error')
            status = entry['acquisition']
            if reason:
                status['reason'] = reason
                status['phase'] = 'failed' if outcome.get('terminal') or status['attempts'] >= 3 else 'retrying'
                entry['due'] = self.clock() + 5 * status['attempts']
                entry['state'] = outcome.get('state', 'source_unavailable')
                entry['export_identity'] = None
            else:
                report = outcome['report']
                entry['history'] = outcome['history']
                if outcome['changed']:
                    entry['result'] = report
                    entry['revision'] = uuid4().hex
                entry.update(outcome['metadata'])
                entry['validated'] = self.clock()
                entry['state'] = outcome['state']
                status.update(phase='ready', reason=None, attempts=0)
                entry['due'] = self.clock() + 5
            entry['generation'] += 1

    def acquisition_status(self, entry):
        status = entry['acquisition']
        age = max(0, self.clock() - status['changed_at'])
        # A stopped/uninitialized owner must not leave an eternal unadmitted bar.
        if status['phase'] == 'queued' and age >= 120:
            status.update(phase='failed', reason='detail_not_admitted')
        return dict(phase=status['phase'], reason=status['reason'], attempts=status['attempts'],
            completed=status['completed'], progress_age_seconds=int(age),
            attempt_age_seconds=int(max(0, self.clock() - (status['started_at'] or self.clock()))),
            retry_available=status['phase'] == 'failed')

    def failed(self, reason):
        with self.lock:
            for key, entry in self.histories.items():
                if self._active(key):
                    entry['attempt'] = None
                    entry['acquisition'].update(phase='failed', reason=reason)

    def export_identity(self, token):
        """Only a freshly observed canonical selection may authorize transfer."""
        with self.lock:
            lease = self.leases.get(token)
            if lease is None or self.clock() - lease['touched'] > 300:
                raise KeyError('detail_expired')
            entry = self.histories[lease['session_id']]
            if self.clock() - entry.get('validated', -float('inf')) > 3600:
                return None
            return entry.get('export_identity')

    def export(self, token, source, cancelled):
        identity = self.export_identity(token)
        capability = getattr(source, 'export_session', None)
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
        payload = capability(session_id, epoch, retired)
        if retired():
            raise SessionExportError('export_cancelled')
        return payload, f'opencode-{session_id}-sanitized.json'

    @staticmethod
    def _capture(entry):
        return {name: entry[name] for name in ("result", "revision", "state", "observed_at_ms",
                                              "row_observations", "omitted_ids", "timezone_id", "ccost_display_unit")}

    def page(self, token, offset, revision=None, anchor=None, *, begin=False, chunk=False):
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
        report = capture["result"]
        if pending or report is None:
            return dict(state=capture["state"], pending=pending, result=None, acquisition=acquisition)
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
        return dict(state=capture["state"], revision=capture["revision"], stale_cursor=stale,
            offset=offset, total=len(rows), pending=False, mode=lease["mode"],
            **(dict(acquisition=acquisition) if acquisition['phase'] == 'failed' and lease['frozen'] is None else {}),
            export_available=bool(entry.get('export_identity')),
            result=dict(observed_at_ms=capture["observed_at_ms"], view=view,
                        source=dict(status="partial" if capture["state"] != "observed" else "acquired",
                                    atomicity="per_root_snapshot")))

    def tick(self, service, *, unavailable=False):
        claimed = self.claim()
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
            if state == 'observed' and callable(getattr(source, 'export_session', None)) else None)
        return dict(history=history, report=report, state=state, changed=report is not previous,
            metadata=dict(timezone_id=service.timezone_id,
                ccost_display_unit=service.config.get('ccostDisplayUnit', 'credits'),
                observed_at_ms=service.now_ms, row_observations=history.row_observations,
                omitted_ids=history.omitted_ids, export_identity=export_identity))
    except SourceError as error:
        return dict(error=error.code.value, terminal=error.terminal)
    except PricingUnavailableError:
        return dict(error='pricing_unavailable')
    except Exception:
        return dict(error='detail_internal_error', terminal=True)
