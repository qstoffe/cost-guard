"""Opt-in numeric observation of owned card futures; never a scheduling owner."""
from threading import Lock, local
import time


class CardServiceTimeline:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.lock = Lock()
        self.current = local()
        self.records = []
        self.turns = []
        self.attached = False

    def attach(self, cards):
        if self.attached:
            raise RuntimeError('card_timeline_already_attached')
        self.attached = True
        workers = cards.workers
        original_submit = workers.pool.submit
        original_publish = workers._publish
        original_drain = workers.drain
        original_tick = cards.tick
        futures = {}
        now_ms = None

        original_factory = getattr(workers, 'factory', None)
        if callable(original_factory):
            def factory(*args, **kwargs):
                started = self.clock()
                try:
                    service = original_factory(*args, **kwargs)
                    self.current.resources = (service.metrics,
                        getattr(service.source, '_diagnostics', {}).get('transport', {}))
                    return service
                finally:
                    record = getattr(self.current, 'record', None)
                    if record is not None:
                        with self.lock:
                            record['factory_seconds'] = self.clock() - started

            workers.factory = factory

        def submit(function, *args, **kwargs):
            with self.lock:
                record = dict(ordinal=len(self.records), submitted=self.clock() - self.started,
                    role='guidance' if function.__name__ != '_capture' and function.__name__ != '_capture_batch' else 'card',
                    members=len(args[0]) if function.__name__ == '_capture_batch' else 1,
                    outcomes={})
                self.records.append(record)

            def execute():
                self.current.record = record
                self.current.resources = None
                with self.lock:
                    record['execution_started'] = self.clock() - self.started
                cpu = time.thread_time()
                try:
                    return function(*args, **kwargs)
                finally:
                    with self.lock:
                        record['execution_returned'] = self.clock() - self.started
                        record['thread_cpu_seconds'] = time.thread_time() - cpu
                        resources = self.current.resources
                        if resources is not None:
                            metrics, transport = resources
                            record['acquisition'] = metrics.snapshot()
                            record['transport'] = {key: transport[key] for key in
                                ('requests', 'connections_opened', 'stale_retries', 'request_ms')
                                if type(transport.get(key)) in (int, float)}
                    self.current.resources = None
                    self.current.record = None

            future = original_submit(execute)
            futures[future] = record

            def completed(_future):
                with self.lock:
                    record['future_completed'] = self.clock() - self.started

            future.add_done_callback(completed)
            return future

        def publish(root, generation, phase, value=None, captured_at_ms=None):
            record = getattr(self.current, 'record', None)
            if record is not None:
                with self.lock:
                    record.setdefault('first_result_queued', self.clock() - self.started)
                    bucket = phase
                    if phase == 'unavailable':
                        code = getattr(value, 'code', None)
                        bucket += ':' + str(getattr(code, 'value', 'unknown'))
                    record['outcomes'][bucket] = record['outcomes'].get(bucket, 0) + 1
            return original_publish(root, generation, phase, value, captured_at_ms)

        def drain():
            occupied = set(workers.jobs.values())
            with self.lock:
                for future in occupied:
                    record = futures[future]
                    if record['role'] == 'card':
                        record['role'] = ('history' if any(key in workers.history_jobs
                            for key, value in workers.jobs.items() if value is future) else 'active')
            # A conservative ready backlog, sufficient for the healthy controlled
            # fixture. This is not another production eligibility/proof oracle.
            ready = sum(entry.refresh_requested and entry.verified_generation != entry.generation
                and key not in workers.jobs and key not in cards.active_candidates
                and not cards._focals(entry, now_ms)
                for key, entry in cards.sessions.items())
            try:
                return original_drain()
            finally:
                reaped = occupied - set(workers.jobs.values())
                with self.lock:
                    for future in reaped:
                        record = futures[future]
                        record['owner_reaped'] = self.clock() - self.started
                        record['ready_history_at_reap'] = ready
                        completed = record.get('future_completed')
                        if completed is not None:
                            record['completed_slot_wait_seconds'] = record['owner_reaped'] - completed

        def tick(current_ms, **kwargs):
            nonlocal now_ms
            now_ms = current_ms
            started = self.clock()
            try:
                return original_tick(current_ms, **kwargs)
            finally:
                with self.lock:
                    self.turns.append(dict(at=started - self.started, seconds=self.clock() - started,
                        completion_only=bool(kwargs.get('completed_only'))))

        workers.pool.submit = submit
        workers._publish = publish
        workers.drain = drain
        cards.tick = tick

    def summary(self):
        with self.lock:
            records = [dict(record, outcomes=dict(record['outcomes'])) for record in self.records]
            turns = [dict(turn) for turn in self.turns]
        waits = [record for record in records if record.get('ready_history_at_reap', 0) > 0]
        return dict(unique_futures=len(records), futures=records, card_service_turns=turns,
            completed_permit_wait_with_ready_history_seconds=sum(
                record.get('completed_slot_wait_seconds', 0) * record['members'] for record in waits),
            limitation='Opt-in scheduling/resource diagnostic adds observation overhead. Acquisition/transport counters '
                'are per completed capture service, not a complete host or guidance accounting. Ready backlog is conservative; '
                'permit-weighted completed wait is not CPU time. Callback timing may follow actual Future completion.')
