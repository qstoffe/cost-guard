"""Web history membership and prompt-card lifecycle; no CLI retention changes."""
from dataclasses import dataclass, field, replace

from .models import WatchCard, WatchRow
from .tools import RUNNING_VISIBLE_AFTER_MS, without_live_activity


@dataclass(slots=True)
class CardSession:
    root: object
    revision: object
    generation: int
    capture: object = None
    snapshot: object = None
    tools: dict = field(default_factory=dict)
    terminals: dict = field(default_factory=dict)
    last_ms: int = -1
    state: str = "loading"
    latest_ms: int | None = None
    refresh_requested: bool = True


class WatchCards:
    def __init__(self, workers, recent_seconds=30, on_duration=None):
        self.workers = workers
        self.recent_ms = int(recent_seconds * 1000)
        self.sessions = {}
        self.active_candidates = frozenset()
        self.generation = 0
        self.turn = 0
        self.on_duration = on_duration

    def catalog(self, observation):
        self.active_candidates = observation.active_candidates | observation.live_candidates
        roots = {root.session_id: root for root in observation.roots}
        for key in set(self.sessions) - roots.keys():
            del self.sessions[key]
        for key, root in roots.items():
            revision = observation.revisions.get(key)
            entry = self.sessions.get(key)
            if entry is None:
                self.generation += 1
                self.sessions[key] = CardSession(root, revision, self.generation)
            else:
                entry.root = root
                if entry.revision != revision:
                    self.generation += 1
                    entry.revision, entry.generation = revision, self.generation
                    entry.last_ms = -1
                    # Keep visible history and its coherent metrics during refresh.
                    # Evicted captures still need fresh ranking before selection.
                    if entry.capture is None:
                        entry.latest_ms = None
                    entry.refresh_requested = True
                elif (entry.capture is not None and any(row.in_progress for row in entry.capture.rows)) or entry.state == "unavailable":
                    entry.refresh_requested = True

    def accept(self, result, now_ms):
        entry = self.sessions.get(result.session_id)
        if entry is None or entry.generation != result.generation:
            return
        if (entry.capture is not None and result.captured_at_ms is not None
                and result.captured_at_ms < entry.capture.observed_at_ms):
            return
        if result.phase == "rows":
            capture, tools, snapshot = result.value
            if entry.capture is not None and capture.observed_at_ms < entry.capture.observed_at_ms:
                return
            previous = {row.event_id: row for row in entry.capture.rows} if entry.capture else {}
            if capture.retained and not capture.authoritative:
                current_rows = {row.event_id: row for row in capture.rows}
                current_rows.update((key, row) for key, row in previous.items() if key not in capture.observed_ids)
                capture = replace(capture, rows=tuple(sorted(current_rows.values(), key=lambda row: (row.at_ms, row.event_id))))
            elif capture.authoritative:
                current_rows = {row.event_id: row for row in capture.rows}
                for key, old in previous.items():
                    row = current_rows.get(key)
                    if row is None and (old.in_progress or key in entry.terminals or not capture.rows):
                        # Complete analysis reclassified the prompt; retain its
                        # observed history, not a made-up successful outcome.
                        current_rows[key] = (replace(old, in_progress=False,
                            duration_ms=max(old.duration_ms or 0, now_ms - old.at_ms),
                            completed_at_ms=None, completed_successfully=False,
                            aborted=False, watch_error=False, abort_reason="",
                            abort_at_ms=0, ended_after_tool_calls=False, running_cost_warning=False,
                            background_kinds=(), background_started_ms=0, background_only=False)
                            if old.in_progress else old)
                    elif row is not None and not row.in_progress and row.completed_at_ms is None and not old.in_progress:
                        current_rows[key] = replace(row, duration_ms=old.duration_ms)
                capture = replace(capture, rows=tuple(sorted(current_rows.values(), key=lambda row: (row.at_ms, row.event_id))),
                    latest_ms=capture.latest_ms or entry.latest_ms or 0)
            current = {row.event_id: row for row in capture.rows}
            for key, old in previous.items():
                row = current.get(key)
                # A missing source row is not completion evidence.
                if old.in_progress and row is not None and not row.in_progress:
                    entry.terminals[key] = now_ms
                if row is not None and row.in_progress:
                    entry.terminals.pop(key, None)
            newly_running = [row for key, row in current.items() if row.in_progress and key not in previous]
            for row in newly_running:
                for key in tuple(entry.terminals):
                    old = current.get(key)
                    if old is not None and ((key in previous and not previous[key].in_progress)
                            or (old.completed_at_ms is not None and old.completed_at_ms <= row.at_ms)):
                        entry.terminals.pop(key, None)
            entry.capture, entry.tools, entry.snapshot = capture, dict(tools), snapshot
            entry.latest_ms = capture.latest_ms
            entry.last_ms = now_ms
            entry.state = "partial" if capture.retained else "observed"
        else:
            entry.state = "unavailable"
            entry.last_ms = now_ms

    def _focals(self, entry, now_ms):
        if entry.capture is None:
            return ()
        running = [row for row in entry.capture.rows if row.in_progress]
        recent = [row for row in entry.capture.rows if not row.in_progress and
            row.event_id in entry.terminals and
            0 <= now_ms - entry.terminals[row.event_id] < self.recent_ms]
        return tuple(running + recent)

    def historical_ids(self, now_ms):
        eligible = [(entry.latest_ms, key) for key, entry in self.sessions.items()
            if entry.latest_ms and not self._focals(entry, now_ms)]
        return tuple(key for _, key in sorted(eligible, key=lambda pair: (-pair[0], pair[1]))[:5])

    def tick(self, now_ms):
        for result in self.workers.drain():
            if result.phase == "timing":
                if self.on_duration is not None:
                    self.on_duration(result.value)
            else:
                self.accept(result, now_ms)
        for entry in self.sessions.values():
            entry.terminals = {key: seen for key, seen in entry.terminals.items()
                if 0 <= now_ms - seen < self.recent_ms}
        historical = set(self.historical_ids(now_ms))
        active, history = [], []
        for key, entry in self.sessions.items():
            busy = bool(self._focals(entry, now_ms)) or (key in self.active_candidates and entry.latest_ms is None)
            due = entry.refresh_requested or (key in historical and entry.capture is None)
            needed = busy or entry.latest_ms is None or key in historical
            if due and needed and key not in self.workers.jobs:
                (active if busy else history).append((entry.last_ms, key, entry))
        active.sort(key=lambda item: (item[0], item[1]))
        history.sort(key=lambda item: (item[0], item[1]))
        while (active or history) and len(self.workers.jobs) < self.workers.limit:
            # Reserve recurring admission for history even with 100 busy roots.
            candidates = history if history and (not active or self.turn % 4 == 3) else active
            _, _, entry = candidates.pop(0)
            if self.workers.submit(entry.root, entry.generation, now_ms, entry.snapshot,
                    tuple(row.event_id for row in self._focals(entry, now_ms))):
                entry.refresh_requested = False
                self.turn += 1
        # Retain full source captures only for cards that can currently appear.
        for key, entry in self.sessions.items():
            if key not in historical and not self._focals(entry, now_ms):
                entry.snapshot = None
                if key not in self.workers.jobs:
                    entry.capture = None

    def _card(self, entry, focal, now_ms):
        capture = entry.capture
        if capture is None:
            return WatchCard(entry.root.session_id, entry.root.title or entry.root.session_id,
                "", (), state=entry.state)
        rows = (focal,) if focal is not None else capture.rows[-1:]
        projected = []
        for row in rows:
            duration = (max(row.duration_ms or 0, now_ms - row.at_ms)
                if row.in_progress and row.event_id in capture.observed_ids else row.duration_ms)
            row = replace(row, duration_ms=duration)
            is_focal = focal is not None and row.event_id == focal.event_id
            marker = ("▶" if row.in_progress else "!" if row.aborted or row.watch_error else "✓") if is_focal else ""
            tool = entry.tools.get(row.event_id) if is_focal else None
            if tool is not None:
                if not row.in_progress:
                    tool = without_live_activity(tool)
                elapsed = max(0, tool.running_ms - RUNNING_VISIBLE_AFTER_MS + now_ms - capture.observed_at_ms)
                show_running = row.in_progress and elapsed >= RUNNING_VISIBLE_AFTER_MS
                tool = replace(tool, running_tool=tool.running_tool if show_running else "",
                    running_ms=elapsed if show_running else 0,
                    background_kinds=row.background_kinds if row.in_progress else (),
                    background_ms=max(0, now_ms - row.background_started_ms)
                        if row.in_progress and row.background_kinds else 0)
            projected.append(WatchRow(capture.session_id, capture.title, row, marker, tool))
        return WatchCard(capture.session_id, capture.title, focal.event_id if focal else "",
            tuple(projected), entry.state,
            capture.context if (capture.context is not None and entry.state != "unavailable"
                and (focal is None or capture.context.owner_id == focal.event_id)) else None)

    def project(self, now_ms):
        active = []
        for key, entry in self.sessions.items():
            focals = self._focals(entry, now_ms)
            for focal in focals:
                active.append((focal.at_ms, key, focal.event_id, self._card(entry, focal, now_ms)))
            if not focals and key in self.active_candidates and entry.capture is None and entry.latest_ms is None:
                active.append((entry.root.created_at_ms, key, "", self._card(entry, None, now_ms)))
        history = tuple(self._card(self.sessions[key], None, now_ms) for key in self.historical_ids(now_ms))
        pending = any(key in self.active_candidates and entry.latest_ms is None for key, entry in self.sessions.items())
        visible = [entry for key, entry in self.sessions.items()
            if key in self.active_candidates or self._focals(entry, now_ms)]
        failed = any(entry.state == "unavailable" for entry in visible)
        partial = any(entry.state == "partial" for entry in visible)
        state = "unavailable" if failed else "loading" if pending else "partial" if partial else "observed"
        return tuple(item[-1] for item in sorted(active, key=lambda item: item[:3])), history, state
