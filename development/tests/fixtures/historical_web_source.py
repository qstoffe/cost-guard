"""Version-neutral current V2 wire server for isolated historical Web benchmarks.

Only synthetic JSON crosses this boundary. No production imports, credentials,
session recording or integration calls; SSE remains open until owned shutdown.
"""
import argparse
import faulthandler
from collections import Counter
from copy import deepcopy
import json
import os
import socket
import sys
from threading import Event, Lock, Thread, current_thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from urllib.parse import parse_qs, urlsplit


class WireHistory:
    def __init__(self, roots, prompts, asof, latency_ms, activity_pattern='recent-metadata', *, active_probe=False):
        self.stopping = Event()
        self.lock = Lock()
        self.counts = Counter()
        self.bytes = 0
        self.latency = latency_ms / 1000
        self.cpu_started = time.process_time()
        self.stales_applied = False
        self.active, self.events = {}, []
        self.update_ordinal = -1
        self.sessions, self.messages, finishes = [], {}, []
        for index in range(roots):
            sid = f'ses_fixture_{index:05d}'
            # Deliberately not the same ordering as catalog activity.
            finish_rank = (index * 37) % roots
            finish = asof - 3_600_000 - finish_rank * 60_000
            values = []
            for prompt in range(prompts):
                at = finish - (prompts - prompt) * 10_000
                model = 'gpt-test-1' if index % 2 else 'gpt-test-2'
                values.extend([
                    dict(id=f'{sid}_u{prompt}', type='user', text=f'Synthetic comparison {index % 11}',
                         files=[], agents=[], time=dict(created=at)),
                    dict(id=f'{sid}_a{prompt}', type='assistant', agent='build',
                         model=dict(providerID='openai', id=model, variant='medium'),
                         content=[dict(type='text', id=f'{sid}_t{prompt}', text='Synthetic answer')],
                         finish='stop', cost=0.01,
                         tokens=dict(input=120000, output=100, reasoning=20, cache=dict(read=20000, write=0)),
                         time=dict(created=at + 100, completed=at + 1100)),
                ])
            self.messages[sid] = values
            touched_old = finish_rank >= roots - roots // 10
            updated = (asof - index * 1000 if activity_pattern == 'recent-metadata' or touched_old
                else values[-1]['time']['completed'])
            self.sessions.append(dict(id=sid, projectID='prj_fixture', title=f'Synthetic session {index}',
                location=dict(directory='/fixture/repository'), agent='build',
                model=dict(providerID='openai', id=model, variant='medium'),
                time=dict(created=finish - prompts * 10000, updated=updated)))
            finishes.append((values[-1]['time']['completed'], sid))
        self.winners = [sid for _, sid in sorted(finishes, key=lambda value: (-value[0], value[1]))
            if not active_probe or sid != 'ses_fixture_00000'][:5]
        self.sessions.sort(key=lambda value: (-value['time']['updated'], value['id']))
        if active_probe:
            self.active_update(0)

    def active_update(self, ordinal):
        """Mutate ONLY this owned source; no inference, external source or shared state."""
        with self.lock:
            if ordinal != self.update_ordinal + 1:
                raise RuntimeError('nonsequential_fixture_update')
            sid, now = 'ses_fixture_00000', int(time.time() * 1000)
            messages = deepcopy(self.messages[sid])
            if self.update_ordinal >= 0:
                messages[-1]['finish'] = 'stop'
                messages[-1]['time']['completed'] = now - 1
            messages.extend([
                dict(id=f'{sid}_live_update_u{ordinal}', type='user', text='Synthetic active update',
                    files=[], agents=[], time=dict(created=now)),
                dict(id=f'{sid}_live_update_a{ordinal}', type='assistant', agent='build',
                    model=dict(providerID='openai', id='gpt-test-2', variant='medium'),
                    content=[dict(type='text', text='Synthetic streaming answer')], cost=.01,
                    tokens=dict(input=120000, output=100 + ordinal, reasoning=20, cache=dict(read=20000, write=0)),
                    time=dict(created=now + 1)),
            ])
            sessions = deepcopy(self.sessions)
            next(row for row in sessions if row['id'] == sid)['time']['updated'] = now + 1
            self.sessions = sorted(sessions, key=lambda row: (-row['time']['updated'], row['id']))
            self.messages = {**self.messages, sid: messages}
            self.active = {sid: dict(type='running')}
            self.update_ordinal = ordinal
            changed_at = time.monotonic()
            self.events.append(dict(type='session.updated', data=dict(sessionID=sid)))
            return dict(ordinal=ordinal, changed_at=changed_at)

    def make_sparse_stale(self):
        """One fixed pre-arm change, never a concurrent churn/freshness simulation."""
        with self.lock:
            if self.stales_applied:
                raise RuntimeError('fixture_stales_already_applied')
            order = [row['id'] for row in self.sessions]
            roots = len(self.sessions)
            selected = {f'ses_fixture_{roots * numerator // 4:05d}' for numerator in (1, 2, 3)}
            for row in self.sessions:
                if row['id'] in selected:
                    row['time']['updated'] += 1
                    self.messages[row['id']][-1]['tokens']['output'] += 1
            self.sessions.sort(key=lambda row: (-row['time']['updated'], row['id']))
            if [row['id'] for row in self.sessions] != order:
                raise RuntimeError('fixture_stales_changed_catalog_order')
            self.stales_applied = True
            return dict(changed_roots=len(selected), usage_output_delta=len(selected), ordering_preserved=True)

    def snapshot(self):
        with self.lock:
            return dict(requests=dict(self.counts), bytes=self.bytes,
                cpu_seconds=time.process_time() - self.cpu_started)

    def reply(self, handler, value, bucket, status=200):
        raw = json.dumps(value, separators=(',', ':')).encode()
        with self.lock:
            self.counts[bucket] += 1
            self.bytes += len(raw)
        if self.latency:
            self.stopping.wait(self.latency)
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Content-Length', str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw)

    def handler(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def setup(self):
                super().setup()
                self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # Windows shutdown(SHUT_RDWR) need not release another thread's
                # pending read. Bound idle keep-alive IO, not valid source work.
                self.connection.settimeout(2)

            def log_message(self, *_args):
                pass

            def handle_one_request(self):
                self.response_active = False
                super().handle_one_request()

            def send_response(self, code, message=None):
                self.response_active = True
                super().send_response(code, message)

            def log_error(self, message, *args):
                # BaseHTTPRequestHandler consumes TimeoutError itself. Its normal
                # quiet logging must not conceal a stalled active response/SSE.
                if args and isinstance(args[0], TimeoutError):
                    self.server.record_timeout(self.response_active)
                else:
                    super().log_error(message, *args)

            def do_GET(self):
                route = urlsplit(self.path)
                query = parse_qs(route.query)
                if route.path == '/api/info':
                    owner.reply(self, dict(version='2.1.0'), 'info')
                elif route.path == '/openapi.json':
                    owner.reply(self, {'openapi':'3.1.0', 'paths': {
                        '/api/session': {'get': {'parameters':[{'name':'parentID', 'in':'query'},
                            {'name':'limit', 'in':'query'}, {'name':'cursor', 'in':'query'}]}},
                        '/api/session/{sessionID}': {'get': {}}}}, 'capability')
                elif route.path == '/api/model':
                    owner.reply(self, dict(data=[dict(providerID='openai', id=f'gpt-test-{index}', enabled=True)
                        for index in range(1, 6)]), 'models')
                elif route.path == '/api/session/active':
                    owner.reply(self, dict(data=owner.active), 'active')
                elif route.path in {'/api/skill', '/api/shell'}:
                    owner.reply(self, dict(data=[]), route.path.rsplit('/', 1)[-1])
                elif route.path == '/api/session':
                    cursor = query.get('cursor', ['0'])[0]
                    parent = query.get('parentID', [None])[0]
                    if '|parent=' in cursor:
                        cursor, parent = cursor.split('|parent=', 1)
                    offset = int(cursor)
                    limit = int(query.get('limit', ['50'])[0])
                    if not 1 <= limit <= 500 or ('cursor' in query and 'order' in query):
                        owner.reply(self, dict(error='invalid_fixture_pagination'), 'unsupported', 400)
                        return
                    values = (owner.sessions if parent is None else
                        [value for value in owner.sessions if value.get('parentID') == parent])
                    page = values[offset:offset + limit]
                    following = str(offset + len(page)) + ('|parent=' + parent if parent is not None else '')
                    owner.reply(self, dict(data=page, cursor=dict(next=following) if page else {}),
                        'catalog' if parent is None else 'scoped_children')
                elif route.path.startswith('/api/session/') and route.path.endswith(('/message', '/context')):
                    sid = route.path.split('/')[3]
                    values = owner.messages.get(sid, [])
                    owner.reply(self, dict(data=values, cursor={}),
                        'context' if route.path.endswith('/context') else 'messages')
                elif route.path.startswith('/api/session/') and len(route.path.split('/')) == 4:
                    sid = route.path.split('/')[3]
                    value = next((value for value in owner.sessions if value['id'] == sid), None)
                    owner.reply(self, dict(data=value) if value is not None else dict(error='missing'),
                        'scoped_session', 200 if value is not None else 404)
                elif route.path == '/api/event':
                    with owner.lock:
                        owner.counts['event_connections'] += 1
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    sent = 0
                    try:
                        while not owner.stopping.is_set():
                            with owner.lock:
                                events = tuple(owner.events[sent:])
                                sent = len(owner.events)
                            for event in events:
                                self.wfile.write(b'data: ' + json.dumps(event).encode() + b'\n\n')
                            self.wfile.write(b': fixture heartbeat\n\n')
                            self.wfile.flush()
                            owner.stopping.wait(.1 if owner.active else .5)
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as error:
                        self.server.record_disconnect(error)
                    self.close_connection = True
                else:
                    owner.reply(self, dict(error='fixture_route_not_supported'), 'unsupported', 404)

        return Handler


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, owner):
        super().__init__(('127.0.0.1', 0), owner.handler())
        self.owner = owner
        self.sockets = set()
        self.handlers = set()
        self.socket_lock = Lock()
        self.disconnects = Counter()
        self.unexpected_errors = 0
        self.idle_timeouts = self.transfer_timeouts = 0

    def process_request(self, request, address):
        thread = Thread(target=self.process_request_thread, args=(request, address), daemon=True)
        with self.socket_lock:
            self.sockets.add(request)
            self.handlers.add(thread)
        thread.start()

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            with self.socket_lock:
                self.handlers.discard(current_thread())

    def record_disconnect(self, error):
        with self.socket_lock:
            self.disconnects[type(error).__name__] += 1

    def record_timeout(self, active):
        with self.socket_lock:
            if active:
                self.transfer_timeouts += 1
                self.unexpected_errors += 1
            else:
                self.idle_timeouts += 1
        if active:
            print('fixture_active_transfer_timeout', file=sys.stderr, flush=True)

    def handle_error(self, request, address):
        error = sys.exception()
        if isinstance(error, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            self.record_disconnect(error)
        else:
            with self.socket_lock:
                self.unexpected_errors += 1
            super().handle_error(request, address)

    def shutdown_request(self, request):
        try:
            super().shutdown_request(request)
        finally:
            with self.socket_lock:
                self.sockets.discard(request)

    def close_connections(self):
        with self.socket_lock:
            connections = tuple(self.sockets)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def join_handlers(self, timeout):
        deadline = time.monotonic() + timeout
        with self.socket_lock:
            handlers = tuple(self.handlers)
        for thread in handlers:
            thread.join(max(0, deadline - time.monotonic()))

    def lifetime(self):
        with self.socket_lock:
            return dict(handler_threads_alive=sum(thread.is_alive() for thread in self.handlers),
                open_connections=len(self.sockets), disconnects=dict(self.disconnects),
                idle_keepalive_timeouts=self.idle_timeouts, active_transfer_timeouts=self.transfer_timeouts,
                unexpected_handler_errors=self.unexpected_errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', type=int, required=True)
    parser.add_argument('--prompts', type=int, default=2)
    parser.add_argument('--asof', type=int, required=True)
    parser.add_argument('--latency-ms', type=float, default=0)
    parser.add_argument('--activity-pattern', choices=('recent-metadata', 'cutoff-effective'), default='recent-metadata')
    parser.add_argument('--active-probe', action='store_true')
    args = parser.parse_args()
    if not 6 <= args.roots <= 3000 or not 1 <= args.prompts <= 100 or not 0 <= args.latency_ms <= 100:
        parser.error('fixture requires 6..3000 roots, 1..100 prompts, 0..100ms latency')
    owner = WireHistory(args.roots, args.prompts, args.asof, args.latency_ms, args.activity_pattern,
        active_probe=args.active_probe)
    server = FixtureServer(owner)
    thread = Thread(target=server.serve_forever, kwargs=dict(poll_interval=.05), daemon=True)
    thread.start()
    try:
        print(json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}', pid=os.getpid(),
            roots=args.roots, prompts=args.prompts, asof=args.asof, winners=owner.winners,
            catalog_order=[value['id'] for value in owner.sessions])), flush=True)
        for line in sys.stdin:
            command = json.loads(line)['command']
            if command == 'stop':
                break
            if command == 'snapshot':
                print(json.dumps(dict(**owner.snapshot(), **server.lifetime())), flush=True)
            if command == 'sparse-stale':
                print(json.dumps(owner.make_sparse_stale()), flush=True)
            if command == 'active-update':
                print(json.dumps(owner.active_update(owner.update_ordinal + 1)), flush=True)
    finally:
        owner.stopping.set()
        server.shutdown()
        server.close_connections()
        server.join_handlers(5)
        server.server_close()
        thread.join(5)
        lifetime = dict(**server.lifetime(), server_thread_alive=thread.is_alive())
        print(json.dumps(dict(**owner.snapshot(), **lifetime)), flush=True)
        if (lifetime['server_thread_alive'] or lifetime['handler_threads_alive'] or
                lifetime['open_connections'] or lifetime['unexpected_handler_errors']):
            faulthandler.dump_traceback()
            raise RuntimeError('fixture_source_ownership_failed')


if __name__ == '__main__':
    main()
