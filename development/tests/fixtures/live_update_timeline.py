"""Opt-in known synthetic update/owner-stage observation, not scheduling or proof.

Only numeric timestamps, ordinals and stage labels survive calls. The deadline
observer reads the existing runtime caller's loop-local numeric publication_due;
missing evidence stays None. No frame, payload, session or service is retained.
"""
from functools import wraps
import sys
from threading import Lock
import time


def field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return next((item for key, item in getattr(value, 'fields', ()) if key == name), default)


def ordinal(event_id):
    prefix = 'ses_fixture_00000_live_update_u'
    if isinstance(event_id, str) and event_id.startswith(prefix) and event_id[len(prefix):].isdigit():
        return int(event_id[len(prefix):])
    return 0


class LiveUpdateTimeline:
    def __init__(self, *, clock=time.monotonic, cpu_clock=time.thread_time):
        self.clock = clock
        self.cpu_clock = cpu_clock
        self.lock = Lock()
        self.accepted, self.published = {}, {}
        self.spans, self.turns = [], []

    def attach_cards(self, cards):
        original = cards.accept

        def accept(result, now_ms):
            value = original(result, now_ms)
            entry = cards.sessions.get(result.session_id)
            if (result.phase == 'rows' and entry is not None and entry.generation == result.generation
                    and entry.verified_generation == entry.generation and entry.capture is not None):
                for row in entry.capture.rows:
                    update = ordinal(row.event_id)
                    if update and row.in_progress:
                        with self.lock:
                            self.accepted.setdefault(update, self.clock())
            return value

        cards.accept = accept

    def _span(self, owner, name, stage):
        original = getattr(owner, name, None)
        if not callable(original):
            return

        @wraps(original)
        def measured(*args, **kwargs):
            started = self.clock()
            cpu = self.cpu_clock()
            try:
                return original(*args, **kwargs)
            finally:
                with self.lock:
                    self.spans.append(dict(stage=stage, started=started, seconds=self.clock() - started,
                        thread_cpu_seconds=self.cpu_clock() - cpu))

        setattr(owner, name, measured)

    def attach_runtime(self, runtime, driver):
        owner = driver.coordinator
        for name, stage in (('service_completed', 'completion_turn'), ('_build_projection', 'projection'),
                ('tick_catalog', 'session_catalog_turn'), ('tick_details', 'session_detail_turn'),
                ('_account_history', 'account_history')):
            self._span(owner, name, stage)
        self._span(owner.source, '_list_native_sessions', 'source_catalog')
        self._span(runtime, '_publish_frame', 'export_and_publication')
        original = driver.tick

        def tick():
            started = self.clock()
            due = sys._getframe(1).f_locals.get('publication_due')
            try:
                return original()
            finally:
                with self.lock:
                    seconds = self.clock() - started
                    self.turns.append(dict(started=started, seconds=seconds,
                        deadline_lateness_seconds=max(0, started - due) if type(due) in (int, float) else None))
                    self.spans.append(dict(stage='driver_tick', started=started, seconds=seconds))

        driver.tick = tick

    def publication(self, value):
        cards = field(field(value, 'view'), 'active_cards', ())
        for card in cards:
            for row in field(card, 'rows', ()):
                prompt = field(row, 'prompt')
                update = ordinal(field(prompt, 'event_id'))
                if update and field(prompt, 'in_progress'):
                    with self.lock:
                        self.published.setdefault(update, self.clock())

    def summary(self):
        with self.lock:
            return dict(accepted=dict(self.accepted), published=dict(self.published),
                spans=[dict(row) for row in self.spans], publication_turns=[dict(row) for row in self.turns],
                limitation='Opt-in observer overhead; overlapping stage wall times are not additive CPU. '
                    'Active-content owner acceptance and server publication, not native UI paint. '
                    'Cross-process monotonic timestamps apply only on this same local machine.')

    def progress(self):
        with self.lock:
            return dict(self.published)
