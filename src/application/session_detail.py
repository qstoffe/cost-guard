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
                row_observations={}, omitted_ids=frozenset(), ccost_display_unit="credits"))
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
            if lease["mode"] == "snapshot" and lease["frozen"] is None and entry["generation"] > lease["after"]:
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
        report = capture["result"]
        if pending or report is None:
            return dict(state=capture["state"], pending=pending, result=None)
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
            export_available=bool(entry.get('export_identity')),
            result=dict(observed_at_ms=capture["observed_at_ms"], view=view,
                        source=dict(status="partial" if capture["state"] != "observed" else "acquired",
                                    atomicity="per_root_snapshot")))

    def tick(self, service, *, unavailable=False):
        with self.lock:
            active = {lease["session_id"] for lease in self.leases.values()
                      if self.clock() - lease["touched"] <= 300 and
                      (lease["mode"] == "live" or lease["frozen"] is None)}
            candidate = next(((key, value) for key, value in self.histories.items()
                              if key in active and self.clock() >= value["due"]), None)
            if candidate is None:
                return
            key, entry = candidate
            self.histories.move_to_end(key)
            entry["due"] = self.clock() + 5
        report = None
        state = "source_unavailable"
        if not unavailable:
            try:
                report, state = entry["history"].acquire(service, key)
            except (SourceError, PricingUnavailableError):
                pass
        with self.lock:
            if report is not None and report is not entry["result"]:
                entry["result"] = report
                entry["revision"] = uuid4().hex
            if report is not None:
                entry["timezone_id"] = service.timezone_id
                entry["ccost_display_unit"] = service.config.get("ccostDisplayUnit", "credits")
                entry["observed_at_ms"] = service.now_ms
                entry["row_observations"] = entry["history"].row_observations
                entry["omitted_ids"] = entry["history"].omitted_ids
                entry['validated'] = self.clock()
            source = service.source
            entry['export_identity'] = ((source.source_id, source.source_instance,
                getattr(source, 'observation_epoch', None), report.prompt_blocks[0].session_id)
                if report is not None and state == 'observed' and
                callable(getattr(source, 'export_session', None)) else None)
            entry["state"] = state
            entry["generation"] += 1
