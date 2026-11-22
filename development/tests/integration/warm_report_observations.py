"""Passive, opt-in warm-entry checkpoints for the historical Web journey.

One owned sequence-specific file pair bridges the host sampler and Node driver.
No report lookup, demand, acquisition or result payload crosses this boundary.
"""
import hashlib
import json
import os
from pathlib import Path
import time


def publication(key, result):
    if not key or not result:
        return None
    fields = [key, result.get('instance_id'), result.get('sequence'),
        (result.get('source') or {}).get('observed_at_ms')]
    return hashlib.sha256(json.dumps(fields, separators=(',', ':')).encode()).hexdigest()


class WarmReportObservations:
    def __init__(self, jobs, dispatcher, directory, usable):
        self.jobs, self.dispatcher, self.usable = jobs, dispatcher, usable
        self.directory = Path(directory)
        self.previous_request = 0
        self.ordinals, self.calls = {}, []
        self.dropped = 0
        self.sharing_retries = 0  # Retained evidence field; immutable publication never retries permission errors.
        self.protocol_stage, self.current_sequence = 'not-started', None
        self.original_submit = jobs.submit
        jobs.submit = self.submit

    @staticmethod
    def scope(request):
        from src.reports import ReportRequest
        default = ReportRequest(request.kind)
        return dict(kind=request.kind.value, stats_scope=getattr(request, 'stats_scope', None),
            comparison_offset=getattr(request, 'comparison_offset', 0),
            default_scope=all(getattr(request, name) == getattr(default, name)
                for name in ReportRequest.__dataclass_fields__))

    def submit(self, request):
        started = int(time.time() * 1000)
        # Preserve native synchronization, including reentrant submit. Never take
        # a dispatcher lock here: normal callers already hold it in that order.
        with self.jobs._lock:
            row = dict(started_wall_ms=started, scope=self.scope(request))
            try:
                key = self.original_submit(request)
            except BaseException as error:
                row.update(outcome='rejected', error_class=type(error).__name__)
                raise
            else:
                first = key not in self.ordinals
                ordinal = self.ordinals.setdefault(key, len(self.ordinals) + 1)
                row.update(outcome='returned', job=ordinal, first_seen=first)
                return key
            finally:
                row['finished_wall_ms'] = int(time.time() * 1000)
                if len(self.calls) < 1000:
                    self.calls.append(row)
                else:
                    self.dropped += 1

    def snapshot(self):
        values = []
        dispatcher = self.dispatcher
        now = None
        if dispatcher is not None:
            # Native lock order; copy only small immutable/scalar facts. A partial
            # publication with an unfinished producer is not warm-complete.
            with dispatcher.lock:
                with self.jobs._lock:
                    now = int(time.time() * 1000)
                    for request, entry in dispatcher.entries.items():
                        result, key = entry.get('result'), entry.get('job')
                        job = self.jobs._jobs.get(key) if key else None
                        status = job.get('status') if job else None
                        deliverable = bool(self.usable(result, now))
                        source = (result or {}).get('source') or {}
                        view = (result or {}).get('view') or {}
                        scope_ready = (request.kind.value != 'ai-stats' or any(
                            row.get('period') == getattr(request, 'stats_scope', '30-days')
                            for row in view.get('ai_stats', ())))
                        values.append(dict(scope=self.scope(request), deliverable=deliverable,
                            scope_ready=scope_ready, active_status=status,
                            warm_complete=deliverable and scope_ready and status not in ('queued', 'running')
                                and not entry.get('terminal') and not entry.get('failures')
                                and not getattr(dispatcher, 'source_error', None)
                                and not getattr(dispatcher, 'source_terminal', False),
                            observed_at_ms=source.get('observed_at_ms'),
                            publication=publication(entry.get('result_id'), result),
                            due_in_seconds=entry.get('due', 0) - dispatcher.clock(),
                            failures=entry.get('failures', 0), terminal=bool(entry.get('terminal'))))
        with self.jobs._lock:
            if now is None:
                now = int(time.time() * 1000)
            admitted = len(self.ordinals)
            calls = len(self.calls)
        return dict(captured_wall_ms=now, dispatcher=dispatcher is not None,
            entries=values, submit_calls=calls, first_seen_jobs=admitted)

    def poll(self, boundary):
        self.protocol_stage, self.current_sequence = 'request-read', None
        expected = self.previous_request + 1
        request_path = self.directory / f'warm-request-{expected}.json'
        try:
            request = json.loads(request_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return
        self.protocol_stage = 'request-validate'
        if type(request.get('sequence')) is not int or request['sequence'] != expected:
            raise RuntimeError('fixture_warm_checkpoint_invalid')
        self.current_sequence = request['sequence']
        self.protocol_stage = 'snapshot'
        snapshot = self.snapshot()
        # Resource reads and serialization/file writes stay outside product locks.
        self.protocol_stage = 'boundary'
        snapshot.update(sequence=request['sequence'], label=request.get('label'), boundary=boundary())
        temporary = self.directory / f'warm-ack-{expected}.tmp'
        self.protocol_stage = 'acknowledgement-write'
        with temporary.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(snapshot))
        self.protocol_stage = 'acknowledgement-publish'
        # Atomic no-overwrite publication of already-closed bytes. Neither peer
        # replaces/deletes any published file while readers are alive. Keep the
        # temporary hard link too: cleanup belongs after both participants stop.
        # Fixture lifetime and the existing sampler cadence bound accumulation.
        os.link(temporary, self.directory / f'warm-ack-{expected}.json')
        self.previous_request = request['sequence']
        self.protocol_stage = 'acknowledged'

    def error_details(self, error):
        return dict(stage=self.protocol_stage, current_sequence=self.current_sequence,
            last_acknowledged_sequence=self.previous_request, error_class=type(error).__name__,
            errno=getattr(error, 'errno', None), winerror=getattr(error, 'winerror', None))

    def close(self):
        self.jobs.submit = self.original_submit

    def summary(self):
        return dict(calls=self.calls, dropped=self.dropped, checkpoint_sharing_retries=self.sharing_retries,
            limitation='Submit calls may reuse identities; new identities alone do not prove heavy reads. '
                'Check active/due state and original report acquisition records; Live source traffic is not report attribution.')
