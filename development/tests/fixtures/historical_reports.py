"""Controlled many-root current V2 wire history; no transport latency is implied."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import json
import tempfile
from threading import Event

from development.tests.fixtures.opencode_v2_service import CurrentV2Service
from src.reports import ReportRequest

DAY = 1_792_886_400_000  # 2026-10-25 UTC


@dataclass(frozen=True, slots=True)
class HeldDateReport(ReportRequest):
    release: object = None


class HistoricalWire:
    def __init__(self, count=872):
        template = CurrentV2Service()
        self.sessions, self.messages = [], {}
        self.calls = Counter()
        for index in range(count):
            key = f'root-{index:04d}'
            session = deepcopy(template.sessions[0])
            session.update(id=key, time=dict(created=DAY, updated=DAY + 9000))
            self.sessions.append(session)
            messages = deepcopy(template.messages['ses_current'])
            for item in messages:
                item['id'] += f'-{index}'
                item['time'] = {name: DAY + index * 10_000 + value for name, value in item['time'].items()}
                if item['type'] == 'assistant':
                    item['model'] = dict(providerID='github-copilot', id='gpt-test')
                    item['tokens'] = dict(input=100, output=10, reasoning=0, cache=dict(read=0, write=0))
            self.messages[key] = messages

    def json(self, path, *, query=None, **kwargs):
        if path == '/api/info':
            return {'version': '2.1.0'}
        if path == '/api/session':
            self.calls['catalog'] += 1
            return {'data': self.sessions, 'cursor': {}}
        if path == '/api/session/active':
            return {'data': {}}
        if path.endswith('/context') or path.endswith('/message'):
            self.calls['context' if path.endswith('/context') else 'messages'] += 1
            return {'data': self.messages[path.split('/')[3]], 'cursor': {}}
        raise AssertionError('Unexpected controlled V2 route')


def blocked_date_report(sender, request):
    """Spawnable real report/V2 HTTP path, held after four of eight trees."""
    from development.tests.fixtures.opencode_v2_service import source_with_current_service
    from development.tests.fixtures.watch_runtime import make_service
    from src.application import ReportApplication

    wire = HistoricalWire(8)
    with source_with_current_service() as (source, remote, _), tempfile.TemporaryDirectory() as directory:
        remote.sessions, remote.messages = wire.sessions, wire.messages
        remote.session_page_size = 100
        release = request.release if isinstance(request, HeldDateReport) else Event()

        def hold(key):
            if key < 'root-0004':
                release.wait(60)

        remote.before_message = hold

        def factory(now, observe):
            service = make_service(directory, source, now_ms=now)[2]
            service.progress = observe
            return service

        try:
            result = ReportApplication(factory, clock=lambda: DAY + 86_400_000).execute(request,
                progress=lambda event: sender.send(('progress', event.to_json())))
            sender.send(('result', json.dumps(result.to_json()).encode('ascii')))
        finally:
            release.set()
            sender.close()
