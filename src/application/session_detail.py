"""Fair shared detail acquisition and immutable revision-aware 50-row pages.

HTTP callers only read detached pages/enqueue captures; the live thread alone
touches the existing service. Leases bound admission, never logical history.
"""
from collections import OrderedDict
from dataclasses import replace
from threading import Lock
import time
from uuid import uuid4

from src.pricing.base import PricingUnavailableError
from src.reports.session_history import SessionHistory
from src.sources.errors import SourceError

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
            if len(self.leases) >= 32 or (session_id not in self.histories and len(self.histories) >= 16):
                raise RuntimeError("detail_busy")
            entry = self.histories.setdefault(session_id, dict(history=SessionHistory(), result=None,
                revision=None, due=0, state="loading", observed_at_ms=None, generation=0, timezone_id="UTC",
                row_observations={}, omitted_ids=frozenset()))
            entry["due"] = 0
            token = uuid4().hex
            self.leases[token] = dict(session_id=session_id, mode=mode, frozen=None,
                after=entry["generation"], touched=self.clock())
            return token

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

    @staticmethod
    def _capture(entry):
        return {name: entry[name] for name in ("result", "revision", "state", "observed_at_ms",
                                              "row_observations", "omitted_ids", "timezone_id")}

    def page(self, token, offset, revision=None, anchor=None):
        with self.lock:
            lease = self.leases.get(token)
            if lease is None:
                raise KeyError("detail_expired")
            lease["touched"] = self.clock()
            entry = self.histories[lease["session_id"]]
            if lease["mode"] == "snapshot" and lease["frozen"] is None and entry["generation"] > lease["after"]:
                lease["frozen"] = self._capture(entry)
            capture = lease["frozen"] or self._capture(entry)
            pending = lease["frozen"] is None and entry["generation"] <= lease["after"]
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
        page = replace(report, prompt_blocks=(replace(block, rows=rows[offset:offset + 50]),))
        view = project(page, capture["timezone_id"]).to_json()
        for row in view["prompt_blocks"][0]["rows"]:
            row["id"] = identity((block.session_id, row["event_id"], row["is_compaction"]))
            row["last_observed_at_ms"] = capture["row_observations"].get(row["event_id"])
            row["retained"] = row["event_id"] in capture["omitted_ids"]
        return dict(state=capture["state"], revision=capture["revision"], stale_cursor=stale,
            offset=offset, total=len(rows), pending=False, mode=lease["mode"],
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
                entry["observed_at_ms"] = service.now_ms
                entry["row_observations"] = entry["history"].row_observations
                entry["omitted_ids"] = entry["history"].omitted_ids
            entry["state"] = state
            entry["generation"] += 1
