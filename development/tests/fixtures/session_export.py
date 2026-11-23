"""Synthetic paged V2 catalog and native transfers; no installed sessions or credentials."""
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Event, Thread
from urllib.parse import parse_qs, urlsplit

from src.sources.opencode_v2 import OpenCodeV2Source

SESSION = 'ses_export_test'
ROUTE = '/api/experimental/session/{sessionID}/export'
SPECIFICATION = {'paths': {ROUTE: {'get': {'parameters': [
    {'name': 'sanitize', 'in': 'query', 'schema': {'enum': ['true', 'false']}}]}}},
    'components': {'schemas': {'SessionTransfer.Data': {'type': 'object', 'required': ['info', 'messages'],
        'properties': {'info': {'type': 'object'}, 'messages': {'type': 'array'}}}}}}
CHILD, SIBLING, GRANDCHILD, LEAF, OTHER = ('ses_a', 'ses_b', 'ses_c', 'ses_leaf', 'ses_other')
TRANSFER = {'info': {'id': SESSION, 'title': 'Unicode å 日本語', 'note': 'Quotes "🚀"\n  next\tline', 'time': {'created': 1},
    'metadata': {'outcome': 'succeeded'}}, 'messages': [
    {'id': 'msg_first', 'type': 'user', 'text': 'Inspect the cache.', 'time': {'created': 1}},
    {'id': 'msg_idle', 'type': 'idle', 'outcome': 'succeeded', 'time': {'created': 2}},
    {'id': 'msg_later', 'type': 'user', 'text': 'Check the retry.', 'time': {'created': 3}}]}


def transfers():
    tree = {SESSION: deepcopy(TRANSFER)}
    for member, parent, title in [(CHILD, SESSION, 'Unicode: å 日本語'), (SIBLING, SESSION, 'unicode å 日本語'),
            (GRANDCHILD, CHILD, 'CON'), (LEAF, GRANDCHILD, 'Deep 🚀'), (OTHER, None, 'Unicode å 日本語')]:
        info = {'id': member, 'title': title}
        if parent:
            info['parentID'] = parent
        tree[member] = {'info': info, 'messages': []}
    return tree


@contextmanager
def export_source():
    class State:
        status = 200
        content_type = 'application/json'
        length = None
        body = None
        specification = deepcopy(SPECIFICATION)
        tree = transfers()
        before_export = None
        requests = []
        entered = Event()
        release = Event()
        hold = False
    state = State()
    # Cross-page, out-of-order ancestry; the matching unrelated title is a decoy.
    state.pages = {cursor: {'data': [state.tree[key]['info'] for key in ids], 'cursor': {'next': after}}
        for cursor, ids, after in [(None, (LEAF, OTHER, SESSION), 'page 2'), ('page 2', (GRANDCHILD, SIBLING, CHILD), None)]}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state.requests.append(self.path)
            route = urlsplit(self.path)
            query = parse_qs(route.query)
            body, status = b'{"error":"unexpected fixture route"}', 404
            if route.path == '/openapi.json':
                body, status = json.dumps(state.specification).encode(), 200
            elif route.path == '/api/session':
                page = state.pages.get(query.get('cursor', [None])[0])
                if page is not None:
                    body, status = json.dumps(page).encode(), 200
            elif (len(route.path.split('/')) == 6 and route.path.startswith('/api/experimental/session/')
                    and route.path.endswith('/export') and query == {'sanitize': ['false']}):
                member = route.path.split('/')[-2]
                if state.before_export:
                    state.before_export(member)
                state.entered.set()
                if state.hold:
                    state.release.wait(3)
                if member in state.tree:
                    body = state.body if state.body is not None else json.dumps({'data': state.tree[member]}, ensure_ascii=False).encode()
                    status = state.status
            self.send_response(status)
            is_transfer = route.path.endswith('/export')
            self.send_header('Content-Type', state.content_type if is_transfer else 'application/json')
            length = state.length if is_transfer else None
            if length != 'omit':
                self.send_header('Content-Length', str(len(body)) if length is None else length)
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
