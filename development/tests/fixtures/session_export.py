"""Content-free local export service; no installed sessions or credentials."""
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Event, Thread

from src.sources.opencode_v2 import OpenCodeV2Source

SESSION = 'ses_export_test'
ROUTE = '/api/experimental/session/{sessionID}/export'
SPECIFICATION = {'paths': {ROUTE: {'get': {'parameters': [
    {'name': 'sanitize', 'in': 'query', 'schema': {'enum': ['true', 'false']}}]}}},
    'components': {'schemas': {'SessionTransfer.Data': {'type': 'object', 'required': ['info', 'messages'],
        'properties': {'info': {'type': 'object'}, 'messages': {'type': 'array'}}}}}}
TRANSFER = {'info': {'id': SESSION, 'title': 'Unicode å 日本語', 'note': 'Quotes "🚀"\n  next\tline', 'time': {'created': 1},
    'metadata': {'outcome': 'succeeded'}}, 'messages': [
    {'id': 'msg_first', 'type': 'user', 'text': '[REDACTED]', 'time': {'created': 1}},
    {'id': 'msg_idle', 'type': 'idle', 'outcome': 'succeeded', 'time': {'created': 2}},
    {'id': 'msg_later', 'type': 'user', 'text': '[REDACTED]', 'time': {'created': 3}}]}


@contextmanager
def export_source():
    class State:
        status = 200
        content_type = 'application/json'
        length = None
        body = None
        specification = deepcopy(SPECIFICATION)
        transfer = deepcopy(TRANSFER)
        before_export = None
        requests = []
        entered = Event()
        release = Event()
        hold = False
    state = State()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state.requests.append(self.path)
            if self.path == '/openapi.json':
                body, status = json.dumps(state.specification).encode(), 200
            else:
                if state.before_export:
                    state.before_export()
                state.entered.set()
                if state.hold:
                    state.release.wait(3)
                body = state.body if state.body is not None else json.dumps({'data': state.transfer}, ensure_ascii=False).encode()
                status = state.status
            self.send_response(status)
            self.send_header('Content-Type', state.content_type)
            if state.length != 'omit':
                self.send_header('Content-Length', str(len(body)) if state.length is None else state.length)
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, args=(0.02,))
    thread.start()
    with tempfile.TemporaryDirectory() as temp:
        registration = Path(temp) / 'service.json'
        registration.write_text(json.dumps({'url': f'http://127.0.0.1:{server.server_port}',
            'pid': 5252, 'version': '2.2.6'}), encoding='utf-8')
        source = OpenCodeV2Source(registration)
        source.refresh_observation_epoch()
        try:
            yield source, state, registration
        finally:
            state.release.set()
            source.close_reads()
            server.shutdown()
            thread.join(3)
            server.server_close()
