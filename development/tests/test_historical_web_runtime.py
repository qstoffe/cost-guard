"""Independent wire oracle and neutral historical journey admission contracts."""
import http.client
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.historical_web_source import FixtureServer, WireHistory
from development.tests.integration.benchmark_web_runtime import backend_journey, live_semantics


class HistoricalWebRuntimeTests(unittest.TestCase):
    def test_retention_mix_has_real_old_and_recent_execution_not_only_old_metadata(self):
        now = 1_800_000_000_000
        fixture = WireHistory(120, 2, now, 0, 'retention-mix')
        finishes = [messages[-1]['time']['completed'] for messages in fixture.messages.values()]
        cutoff = now - 30 * 86_400_000
        self.assertEqual(60, sum(value < cutoff for value in finishes))
        self.assertEqual(60, sum(value > cutoff for value in finishes))
        self.assertTrue(all(fixture.messages[key][-1]['time']['completed'] > cutoff for key in fixture.winners))

    @unittest.skipUnless(shutil.which('node'), 'optional JS runtime unavailable')
    def test_accounts_paint_requires_visible_matching_fields_not_arbitrary_text_length(self):
        script = r"""
const assert = require('node:assert/strict');
const {connectedUsablePaint} = require('./development/tests/integration/probe_historical_web.cjs');
const card = {connected:true,attached:true,visible:true,height:172,width:448,text_length:100,
  value_present:true,shape_present:true,signature_present:true,
  identity_matches:true,heading_visible:true,heading_matches:true,quota_visible:true,quota_matches:true};
const value = {height:172,text_length:100,section:'accounts',hidden:false,output_connected:true,
  account_root_attached:true,account_root_visible:true,live_accounts:1,account_cards:1,account_nodes:[card]};
for (const section of ['accounts','accounts-switch']) {
  assert.equal(connectedUsablePaint(section,value),true,'100 characters may contain complete useful data');
  for (const field of ['connected','attached','visible','value_present','shape_present','signature_present',
    'identity_matches','heading_visible','heading_matches','quota_visible','quota_matches'])
    assert.equal(connectedUsablePaint(section,{...value,account_nodes:[{...card,[field]:false}]}),false,field);
  for (const [field,replacement] of [['height',0],['width',0],['text_length',0]])
    assert.equal(connectedUsablePaint(section,{...value,account_nodes:[{...card,[field]:replacement}]}),false,field);
  for (const [field,replacement] of [['hidden',true],['output_connected',false],['account_root_attached',false],
    ['account_root_visible',false],['live_accounts',0],['account_cards',0],['section','watch'],['account_nodes',[]]])
    assert.equal(connectedUsablePaint(section,{...value,[field]:replacement}),false,field);
}
assert.equal(connectedUsablePaint('models',{height:172,text_length:100}),false);
assert.equal(connectedUsablePaint('models',{height:172,text_length:101}),true);
assert.equal(connectedUsablePaint('models',{height:0,text_length:101}),false);
"""
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

        self.assertEqual(0, result.returncode, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'optional JS runtime unavailable')
    def test_accounts_capture_matches_observation_identity_independently_of_map_key(self):
        script = r"""
const assert = require('node:assert/strict');
const {captureAccountsPaint,connectedUsablePaint} = require('./development/tests/integration/probe_historical_web.cjs');
global.current={section:'accounts'}; global.document={hidden:false};
global.ReportView={quotaView:()=>({percent:'25%',mode:'used'})};
const node=text=>({isConnected:true,textContent:text,checkVisibility:()=>true,
  getBoundingClientRect:()=>({height:172,width:448})});
const item={observation:{id:'account',provider_id:'provider',label:'Same display label'},primary:{quota:{label:'Primary'}}};
const heading=node('Same display label'), quota=node('Primary · 25% used');
const root={...node('x'.repeat(100)),querySelector:selector=>selector==='h4'?heading:
  selector==='.watch-quota-summary>span'?quota:null};
const card={root,value:item,shape:'shape',signature:'signature'}, parent=node('x'.repeat(100));
const accountRoot={...node(''),parentNode:parent,contains:value=>value===root};
const view={accounts:{accounts:[item]}};
for (const key of ['account',JSON.stringify(['provider','account'])]) {
  const cards={root:accountRoot,cards:new Map([[key,card]])};
  assert.equal(connectedUsablePaint('accounts',captureAccountsPaint(cards,view,parent)),true,key);
  for (const observation of [{...item.observation,id:'other'}, {...item.observation,provider_id:'other'}]) {
    const mismatch={...card,value:{...item,observation}};
    assert.equal(connectedUsablePaint('accounts',captureAccountsPaint(
      {...cards,cards:new Map([[key,mismatch]])},view,parent)),false,'same label cannot disguise identity mismatch');
  }
  assert.equal(connectedUsablePaint('accounts',captureAccountsPaint(cards,
    {accounts:{accounts:[item,item]}},parent)),false,'identity match must be unambiguous');
}
"""
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

        self.assertEqual(0, result.returncode, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'optional JS runtime unavailable')
    def test_untouched_entry_requires_fresh_exact_unvisited_warm_publication(self):
        script = r"""
const assert = require('node:assert/strict');
const {qualifyUntouchedEntry} = require('./development/tests/integration/probe_historical_web.cjs');
const entry = {scope:{kind:'ai-stats',default_scope:true,stats_scope:'30-days',comparison_offset:0},
  warm_complete:true,publication:'fingerprint'};
const input = {section:'ai-stats',navigation:2000,visited:false,
  client:{view_present:false,acquisition_started:false},
  checkpoint:{dispatcher:true,captured_wall_ms:1000,entries:[entry]}};
assert.equal(qualifyUntouchedEntry(input).valid,true);
for (const change of [
  {navigation:2001}, {navigation:999}, {visited:true},
  {client:{view_present:true,acquisition_started:false}},
  {client:{view_present:false,acquisition_started:true}},
  {checkpoint:{...input.checkpoint,captured_wall_ms:null}},
  ...[null,{...entry,warm_complete:false},{...entry,publication:null},
    {...entry,publication:''}, {...entry,scope:{...entry.scope,default_scope:false}},
    {...entry,scope:{...entry.scope,stats_scope:'7-days'}},
    {...entry,scope:{...entry.scope,comparison_offset:1}}]
    .map(value=>({checkpoint:{...input.checkpoint,entries:value?[value]:[]}}))
]) assert.equal(qualifyUntouchedEntry({...input,...change}).valid,false,JSON.stringify(change));
const b0 = qualifyUntouchedEntry({...input,checkpoint:{...input.checkpoint,dispatcher:false,entries:[]}});
assert.equal(b0.valid,true);
assert.equal(b0.classification,'no-dispatcher-on-demand');
assert.equal(qualifyUntouchedEntry({...input,checkpoint:null}).valid,false);
"""
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

        self.assertEqual(0, result.returncode, result.stderr)

    def test_untouched_observation_does_not_implicitly_append_reentry(self):
        from types import SimpleNamespace
        from development.tests.integration.benchmark_web_runtime import warm_options

        for untouched, reentry, expected in ((False, False, (False, False)),
                (True, False, (True, False)), (False, True, (True, True)), (True, True, (True, True))):
            with self.subTest(untouched=untouched, reentry=reentry):
                actual = warm_options(SimpleNamespace(untouched_warm=untouched, warm_reentry=reentry))

                self.assertEqual(expected, (actual['observe_warm'], actual['append_warm_reentry']))

    @unittest.skipUnless(shutil.which('node'), 'optional JS runtime unavailable')
    def test_node_checkpoint_rejects_wrong_ack_and_never_republishes_a_request(self):
        script = r"""
const assert = require('node:assert/strict'), fs = require('node:fs/promises'), path = require('node:path');
const {requestWarmCheckpoint} = require('./development/tests/integration/probe_historical_web.cjs');
(async()=>{
  const directory = process.argv[1];
  await fs.writeFile(path.join(directory,'warm-ack-1.json'),JSON.stringify({sequence:2}));
  const input = {directory,sequence:1,label:'first',deadline:Date.now()+1000,lastAcknowledgedSequence:0};
  await assert.rejects(requestWarmCheckpoint(input),error=>{
    assert.equal(error.protocol.stage,'acknowledgement-read');
    assert.equal(error.protocol.current_sequence,1);
    assert.equal(error.protocol.last_acknowledged_sequence,0);
    assert.equal(JSON.stringify(error.protocol).includes(directory),false);
    return true;
  });
  await assert.rejects(requestWarmCheckpoint({...input,label:'replacement'}),error=>{
    assert.equal(error.protocol.stage,'request-write');
    return true;
  });
  const published = JSON.parse(await fs.readFile(path.join(directory,'warm-request-1.json'),'utf8'));
  assert.equal(published.label,'first');
})();
"""
        with TemporaryDirectory() as directory:
            result = subprocess.run(['node', '-e', script, directory], capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

        self.assertEqual(0, result.returncode, result.stderr)

    def test_warm_observer_preserves_submit_identity_reuse_rejection_and_passive_partial_state(self):
        from threading import RLock
        from types import SimpleNamespace
        from development.tests.integration.warm_report_observations import WarmReportObservations
        from src.reports import ReportKind, ReportRequest
        request = ReportRequest(ReportKind.AI_STATS)
        results = iter(['same', 'same', 'new', RuntimeError('busy')])
        def submit(value):
            self.assertIs(request, value)
            result = next(results)
            if isinstance(result, Exception):
                raise result
            return result
        jobs = SimpleNamespace(_lock=RLock(), _jobs={'same':{'status':'running'}}, submit=submit)
        entry = dict(job='same', result_id='same', due=5, failures=0, terminal=False,
            result=dict(instance_id='not-exported', sequence=1,
                source=dict(status='partial', observed_at_ms=1),
                view=dict(ai_stats=[dict(period='30-days')], private_payload='MUST NOT EXPORT')))
        dispatcher = SimpleNamespace(lock=RLock(), entries={request:entry}, clock=lambda:0)
        observer = WarmReportObservations(jobs, dispatcher, '.', lambda result, now:True)
        try:
            self.assertEqual(['same', 'same', 'new'], [jobs.submit(request) for _ in range(3)])
            with self.assertRaisesRegex(RuntimeError, '^busy$'):
                jobs.submit(request)
            running = observer.snapshot()
            jobs._jobs['same']['status'] = 'complete'
            complete = observer.snapshot()
            entry['terminal'] = True
            terminal = observer.snapshot()
        finally:
            observer.close()

        calls = observer.summary()['calls']
        self.assertEqual([True, False, True], [row['first_seen'] for row in calls[:3]])
        self.assertEqual([1, 1, 2], [row['job'] for row in calls[:3]])
        self.assertEqual('rejected', calls[3]['outcome'])
        self.assertIs(submit, jobs.submit)
        self.assertFalse(running['entries'][0]['warm_complete'])
        self.assertTrue(complete['entries'][0]['warm_complete'])
        self.assertFalse(terminal['entries'][0]['warm_complete'])
        self.assertNotIn('MUST NOT EXPORT', json.dumps(complete))
        self.assertNotIn('not-exported', json.dumps(complete))

    def test_warm_checkpoint_uses_exact_sequence_without_replacing_prior_acknowledgements(self):
        from threading import RLock
        from types import SimpleNamespace
        from development.tests.integration.warm_report_observations import WarmReportObservations
        jobs = SimpleNamespace(_lock=RLock(), submit=lambda request:None)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            observer = WarmReportObservations(jobs, None, root, None)
            try:
                for sequence in (1, 2):
                    request = root / f'warm-request-{sequence}.json'
                    request.write_text(json.dumps(dict(sequence=sequence)), encoding='utf-8')
                    os.utime(request, ns=(1_000_000_000, 1_000_000_000))
                    observer.poll(lambda: dict(cpu_seconds=0))
                    actual = json.loads((root / f'warm-ack-{sequence}.json').read_text())
                    self.assertEqual(sequence, actual['sequence'])
                    self.assertFalse(actual['dispatcher'])
                    self.assertEqual([], actual['entries'])
                self.assertEqual(1, json.loads((root / 'warm-ack-1.json').read_text())['sequence'])
                (root / 'warm-request-3.json').write_text('{"sequence":3}', encoding='utf-8')
                locked = PermissionError('controlled Windows reader sharing violation')
                locked.winerror = 32
                with patch('development.tests.integration.warm_report_observations.os.link', side_effect=locked):
                    with self.assertRaises(PermissionError):
                        observer.poll(lambda: {})
                self.assertEqual(2, observer.previous_request)
                self.assertFalse((root / 'warm-ack-3.json').exists())
                self.assertEqual(0, observer.summary()['checkpoint_sharing_retries'])
            finally:
                observer.close()

    def test_warm_protocol_errors_keep_operation_and_do_not_acknowledge_failed_work(self):
        from threading import RLock
        from types import SimpleNamespace
        from development.tests.integration.warm_report_observations import WarmReportObservations
        jobs = SimpleNamespace(_lock=RLock(), submit=lambda request:None)
        cases = [('request-read', 'read_text'), ('snapshot', 'snapshot'), ('boundary', 'boundary'),
            ('acknowledgement-write', 'open'), ('acknowledgement-publish', 'link')]
        for stage, operation in cases:
            with self.subTest(stage=stage), TemporaryDirectory() as directory:
                root = Path(directory)
                observer = WarmReportObservations(jobs, None, root, None)
                (root / 'warm-request-1.json').write_text('{"sequence":1}', encoding='utf-8')
                observer.poll(lambda:{})
                (root / 'warm-request-2.json').write_text('{"sequence":2}', encoding='utf-8')
                denied = PermissionError(13, 'private filename must not be retained', 'PRIVATE')
                boundary = lambda:{}
                if operation == 'boundary':
                    boundary = unittest.mock.Mock(side_effect=denied)
                    target, name = observer, 'snapshot'
                    replacement = observer.snapshot
                else:
                    if operation == 'link':
                        import development.tests.integration.warm_report_observations as module
                        target, name = module.os, 'link'
                    else:
                        target, name = (observer, operation) if operation == 'snapshot' else (Path, operation)
                    replacement = unittest.mock.Mock(side_effect=denied)
                    if operation == 'open':
                        original_open = Path.open
                        def fail_ack_write(path, *args, **kwargs):
                            if path.suffix == '.tmp':
                                raise denied
                            return original_open(path, *args, **kwargs)
                        replacement = fail_ack_write
                try:
                    with patch.object(target, name, replacement), self.assertRaises(PermissionError) as failure:
                        observer.poll(boundary)
                    actual = observer.error_details(failure.exception)
                finally:
                    observer.close()

                self.assertEqual(stage, actual['stage'])
                self.assertEqual(None if operation == 'read_text' else 2, actual['current_sequence'])
                self.assertEqual(1, actual['last_acknowledged_sequence'])
                self.assertEqual(1, observer.previous_request)
                self.assertEqual(0, observer.sharing_retries)
                self.assertEqual(13, actual['errno'])
                self.assertNotIn('PRIVATE', json.dumps(actual))

    def test_warm_checkpoint_rejects_mismatched_sequence_and_published_ack_collision(self):
        from threading import RLock
        from types import SimpleNamespace
        from development.tests.integration.warm_report_observations import WarmReportObservations
        jobs = SimpleNamespace(_lock=RLock(), submit=lambda request:None)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            observer = WarmReportObservations(jobs, None, root, None)
            try:
                request = root / 'warm-request-1.json'
                request.write_text('{"sequence":2}', encoding='utf-8')
                with self.assertRaisesRegex(RuntimeError, '^fixture_warm_checkpoint_invalid$'):
                    observer.poll(lambda:{})
                request.write_text('{"sequence":1}', encoding='utf-8')
                published = root / 'warm-ack-1.json'
                published.write_text('never overwrite', encoding='utf-8')

                with self.assertRaises(FileExistsError):
                    observer.poll(lambda:{})

                self.assertEqual(0, observer.previous_request)
                self.assertEqual('never overwrite', published.read_text(encoding='utf-8'))
            finally:
                observer.close()

    def test_fixture_classifies_idle_timeout_separately_from_failed_active_transfer(self):
        from contextlib import redirect_stderr
        from io import StringIO
        source = WireHistory(8, 2, 1794052800000, 0)
        server = FixtureServer(source)
        handler_type = source.handler()
        handler = handler_type.__new__(handler_type)
        handler.server = server
        errors = StringIO()
        try:
            with redirect_stderr(errors):
                handler.response_active = False
                handler.log_error('Request timed out: %r', TimeoutError())
                handler.response_active = True
                handler.log_error('Request timed out: %r', TimeoutError())
            actual = server.lifetime()
        finally:
            server.server_close()

        self.assertEqual(1, actual['idle_keepalive_timeouts'])
        self.assertEqual(1, actual['active_transfer_timeouts'])
        self.assertEqual(1, actual['unexpected_handler_errors'])
        self.assertEqual('fixture_active_transfer_timeout\n', errors.getvalue())

    def test_persistent_source_stderr_is_drained_to_disk_and_returned_on_owned_stop(self):
        from types import SimpleNamespace
        from development.tests.integration import benchmark_web_runtime as runtime
        process = SimpleNamespace(poll=lambda: 0, communicate=lambda timeout: ('closed', None))
        args = SimpleNamespace(roots=8, asof=1794052800000, latency_ms=0, activity_pattern='recent-metadata')
        with patch.object(runtime.subprocess, 'Popen', return_value=process) as create:
            actual = runtime.start_source(args)
        sink = create.call_args.kwargs['stderr']
        self.assertIsNot(sink, subprocess.PIPE)
        message = 'retained diagnostic\n' * 8192
        sink.write(message)
        sink.flush()

        stdout, stderr = runtime.stop_owned(actual, 5)

        self.assertEqual('closed', stdout)
        self.assertEqual(message, stderr)
        self.assertTrue(sink.closed)

    def test_source_subprocess_joins_keepalive_and_sse_handlers_after_a_client_reset(self):
        source_script = Path(__file__).with_name('fixtures') / 'historical_web_source.py'
        with TemporaryDirectory() as directory:
            with (Path(directory) / 'stderr.txt').open('w+', encoding='utf-8') as errors:
                process = subprocess.Popen([sys.executable, str(source_script), '--roots', '8',
                    '--asof', '1794052800000'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=errors, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                connections = []
                try:
                    wire = json.loads(process.stdout.readline())
                    port = int(wire['url'].rsplit(':', 1)[1])
                    for route in ('/api/info', '/api/event', '/api/event'):
                        connection = socket.create_connection(('127.0.0.1', port), timeout=2)
                        connections.append(connection)
                        connection.sendall(f'GET {route} HTTP/1.1\r\nHost: localhost\r\n\r\n'.encode())
                        received = b''
                        marker = b'heartbeat' if route == '/api/event' else b'2.1.0'
                        while marker not in received:
                            received += connection.recv(4096)
                    reset = connections.pop()
                    reset.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack('hh' if os.name == 'nt' else 'ii', 1, 0))
                    reset.close()
                    deadline = time.monotonic() + 3
                    while True:
                        process.stdin.write('{"command":"snapshot"}\n')
                        process.stdin.flush()
                        snapshot = json.loads(process.stdout.readline())
                        if snapshot.get('disconnects') or time.monotonic() >= deadline:
                            break
                        time.sleep(.05)

                    process.stdin.write('{"command":"stop"}\n')
                    process.stdin.flush()
                    stdout, _ = process.communicate(timeout=10)

                    errors.seek(0)
                    stderr = errors.read()
                    actual = json.loads(stdout.strip().splitlines()[-1])
                    self.assertEqual(0, process.returncode, f'{stderr}\n{actual}')
                    self.assertFalse(actual['server_thread_alive'])
                    self.assertEqual(0, actual['handler_threads_alive'])
                    self.assertEqual(0, actual['open_connections'])
                    self.assertEqual(0, actual['unexpected_handler_errors'])
                    self.assertEqual(0, actual['active_transfer_timeouts'])
                    self.assertGreaterEqual(sum(actual['disconnects'].values()), 1)
                    self.assertNotIn('Fatal Python error', stderr)
                finally:
                    for connection in connections:
                        connection.close()
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=5)

    def test_browser_handoff_requests_a_new_one_use_link_without_exchanging_it(self):
        from io import StringIO
        from types import SimpleNamespace
        from development.tests.integration import benchmark_web_runtime as runtime
        host = SimpleNamespace(stdin=StringIO(),stdout=StringIO('{"launch":"unused-owned-link"}\n'))

        with patch.object(runtime,'Client',side_effect=AssertionError('browser must exchange the link itself')):
            actual = runtime.fresh_launch(host)

        self.assertEqual({'launch':'unused-owned-link'},actual)
        self.assertEqual('{"command":"link"}\n',host.stdin.getvalue())

    def test_finite_preparation_uses_valid_requests_then_only_passively_observes_target_progress(self):
        from io import StringIO
        from types import SimpleNamespace
        from development.tests.integration import benchmark_web_runtime as runtime
        calls = []
        progress = [dict(id='owned-job',status='running',priority=2,progress=dict(completed=3,sequence=sequence))
                    for sequence in (1,2)]
        host = SimpleNamespace(stdin=StringIO(),stdout=StringIO(''.join(json.dumps(value)+'\n' for value in progress)))

        class Client:
            def request(self, path, value):
                calls.append((path,value))
                return 200, dict(result={'view':'qualified'}) if path=='/api/data' else {}

        with patch.object(runtime,'Client',return_value=Client()), patch.object(runtime.time,'sleep'):
            actual = runtime.prepare_finite_switch(host,'owned-launch','ai-stats',time.monotonic()+5)

        self.assertEqual(progress[-1],actual)
        self.assertEqual([('/api/interest',dict(tab='b'*32,section='models',visible=True,request=dict(kind='normal'))),
            ('/api/data',dict(request=dict(kind='normal'),retry=False)),
            ('/api/interest',dict(tab='b'*32,section='watch',visible=True,request=None))],calls)
        self.assertEqual(['finite-progress','finite-progress'],
            [json.loads(line)['command'] for line in host.stdin.getvalue().splitlines()])

    def test_finite_preparation_rejects_invalid_http_instead_of_waiting_until_deadline(self):
        from types import SimpleNamespace
        from development.tests.integration import benchmark_web_runtime as runtime

        class Client:
            def request(self, path, value):
                return (400,dict(error='invalid_request')) if path=='/api/data' else (200,{})

        with patch.object(runtime,'Client',return_value=Client()), patch.object(runtime.time,'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError,'^fixture_promotion_models_request_rejected$'):
                runtime.prepare_finite_switch(SimpleNamespace(),'owned-launch','ai-stats',time.monotonic()+5)
        sleep.assert_not_called()

    def test_original_token_mix_observer_preserves_return_and_continuation_with_numeric_metrics(self):
        from types import SimpleNamespace
        from development.tests.fixtures.historical_web_inputs import observe_build
        from src.reports.history_work import HistoryContinuation
        rows, calls = [], []
        service = SimpleNamespace(metrics=SimpleNamespace(snapshot=lambda: {'counts':{'hydrated_roots':3}}))
        result = object()

        def build(owner, progress):
            calls.append((owner, progress))
            return result

        observer = observe_build(build, rows, kind='token-mix')
        self.assertIs(result, observer(service, 'progress'))

        def continued(owner, progress):
            raise HistoryContinuation()

        with self.assertRaises(HistoryContinuation):
            observe_build(continued, rows, kind='token-mix')(service, 'progress')
        self.assertEqual([(service, 'progress')], calls)
        self.assertEqual(['returned','HistoryContinuation'], [row['outcome'] for row in rows])
        self.assertEqual(['token-mix'] * 2, [row['kind'] for row in rows])
        self.assertEqual([3,3], [row['acquisition']['counts']['hydrated_roots'] for row in rows])
        self.assertTrue(all(row['wall_seconds'] >= 0 and row['cpu_seconds'] >= 0 for row in rows))
        self.assertIsNone(rows[0]['failure'])
        self.assertEqual('HistoryContinuation', rows[1]['failure']['error_class'])

    def test_failure_observation_keeps_sqlite_codes_without_error_text_or_paths(self):
        from development.tests.fixtures.historical_web_inputs import failure_facts
        error = sqlite3.OperationalError('PRIVATE SQL AND PAYLOAD')
        error.sqlite_errorcode, error.sqlite_errorname = sqlite3.SQLITE_BUSY, 'SQLITE_BUSY'
        error.cache_phase = 'write'

        actual = failure_facts(error)

        self.assertEqual(sqlite3.SQLITE_BUSY, actual['sqlite_code'])
        self.assertEqual('SQLITE_BUSY', actual['sqlite_name'])
        self.assertEqual('write', actual['cache_phase'])
        self.assertNotIn('PRIVATE', json.dumps(actual))

    def test_passive_cache_failure_observer_identifies_stats_batch_and_preserves_the_exception(self):
        from types import SimpleNamespace
        from development.tests.fixtures import historical_web_inputs as inputs
        root = Path(__file__).resolve().parents[2]
        error = sqlite3.OperationalError('PRIVATE SQL')
        error.sqlite_errorcode, error.sqlite_errorname = sqlite3.SQLITE_BUSY, 'SQLITE_BUSY'
        error.cache_phase = 'write'
        calls, failures = [], []

        def write(owner, entries, **kwargs):
            calls.append((owner, entries, kwargs))
            raise error

        observer = inputs.observe_cache_writes(write, failures, root=root)
        owner, entries = object(), object()
        for source, function in (('src/reports/ai_stats.py', '_batch'),
                ('src/reports/ai_stats.py', 'acquire'), ('src/analysis/evidence.py', '_batch')):
            with patch.object(inputs.traceback, 'extract_stack', return_value=[SimpleNamespace(
                    filename=str(root/source), name=function)]), self.assertRaises(sqlite3.OperationalError) as caught:
                observer(owner, entries, busy_timeout_ms=50)
            self.assertIs(error, caught.exception)

        self.assertEqual([(owner, entries, {'busy_timeout_ms':50})]*3, calls)
        self.assertEqual([True, False, False], [row['stats_batch'] for row in failures])
        self.assertTrue(all(row['sqlite_code']==sqlite3.SQLITE_BUSY and row['busy_timeout_ms']==50
            and not row['controlled_write_lock'] and isinstance(row['failed_wall_ms'], int) for row in failures))
        self.assertNotIn('PRIVATE', json.dumps(failures))

    def test_pacing_control_withholds_only_the_history_pending_fact_from_the_native_tick(self):
        from development.tests.fixtures.historical_web_inputs import withhold_history_pacing
        calls = []

        class Dispatcher:
            def tick(self, *, identity=None, ready=True, history_pending=False):
                calls.append((identity, ready, history_pending))
                return 'ticked'

        withhold_history_pacing(Dispatcher)
        result = Dispatcher().tick(identity='source', ready=False, history_pending=True)

        self.assertEqual('ticked', result)
        self.assertEqual([('source', False, False)], calls)

    def test_pacing_control_rejects_a_dispatcher_without_the_history_pending_seam(self):
        from development.tests.fixtures.historical_web_inputs import withhold_history_pacing
        from src.web.dispatch import DataDispatcher

        class Current(DataDispatcher):
            pass

        with self.assertRaisesRegex(RuntimeError, 'fixture_pacing_control_unsupported'):
            withhold_history_pacing(Current)
        self.assertIs(DataDispatcher.tick, Current.tick, 'rejection leaves the native tick untouched')

    def test_finite_timeline_preserves_original_calls_restores_methods_and_omits_payloads(self):
        from types import SimpleNamespace
        from threading import RLock
        from development.tests.integration.dispatch_probe_resources import FiniteTimeline
        from src.reports import ReportKind, ReportRequest
        calls = []
        request = ReportRequest(kind=ReportKind.TOKEN_MIX)

        def submit(value):
            calls.append(value)
            return 'private-job'

        jobs = SimpleNamespace(_lock=RLock(), _active=None, _parked={}, _jobs={
            'private-job':dict(request=request, status='queued', result='PRIVATE PAYLOAD', priority=0)},
            submit=submit, _park=lambda: None, _start_next=lambda: None, _receive=lambda: None, prioritize=lambda: None)
        dispatcher = SimpleNamespace(lock=RLock(), tabs={}, entries={}, interest=lambda: None, _collect=lambda: None)
        original = jobs.submit
        timeline = FiniteTimeline(jobs, dispatcher)

        actual = jobs.submit(request)
        jobs._jobs['private-job']['status'] = 'running'
        jobs._receive()
        timeline.close()

        self.assertEqual('private-job', actual)
        self.assertEqual([request], calls)
        self.assertIs(original, jobs.submit)
        self.assertEqual(['queued','running'], [row['status'] for row in timeline.events])
        self.assertNotIn('PRIVATE', json.dumps(timeline.summary()))
        self.assertNotIn('private-job', json.dumps(timeline.summary()))

    def test_direct_harness_parent_can_validate_inputs_outside_python_import_root(self):
        harness = Path(__file__).with_name('integration') / 'benchmark_web_runtime.py'
        script = ("import runpy,sys; values=runpy.run_path(sys.argv[1]); "
            "values['validate_input_time'](1794052800000,'Europe/Stockholm',now_ms=1794052800000)")
        with TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-c', script, str(harness)], cwd=directory,
                capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

        self.assertEqual(0, result.returncode, result.stderr)

    def test_raw_quota_window_stays_fixed_while_observation_time_advances(self):
        from development.tests.fixtures import historical_web_inputs as inputs
        asof = 1794052800000  # 2026-11-07 12:00 UTC.
        quota = inputs.quota_input(asof)
        provider = inputs.FixtureAccounts(quota)
        wire = WireHistory(64, 2, asof, 0)
        finishes = [message['time']['completed'] for messages in wire.messages.values()
            for message in messages if message['type'] == 'assistant']

        with patch.object(inputs.time, 'time', side_effect=[asof / 1000, (asof + 7_200_000) / 1000]):
            first, later = provider.get_account_snapshots()[0], provider.get_account_snapshots()[0]

        self.assertEqual(asof, first.fetched_at_ms)
        self.assertEqual(asof + 7_200_000, later.fetched_at_ms)
        self.assertEqual(asof + 9_000_000, first.quotas[0].reset_at_ms)
        self.assertEqual(first.quotas, later.quotas)
        self.assertEqual(18_000, later.quotas[0].duration_seconds)
        self.assertEqual('0.75', str(later.quotas[0].remaining_fraction))
        start = first.quotas[0].reset_at_ms - first.quotas[0].duration_seconds * 1000
        self.assertGreater(sum(start <= finish < first.quotas[0].reset_at_ms for finish in finishes), 0)

    def test_fixture_clock_expiry_and_local_day_change_invalidate_inputs_not_product_work(self):
        from development.tests.fixtures.historical_web_inputs import validate_input_time
        asof = 1794052800000

        validate_input_time(asof, 'UTC', now_ms=asof + 8_999_999)
        with self.assertRaisesRegex(RuntimeError, '^fixture_input_window_expired$'):
            validate_input_time(asof, 'UTC', now_ms=asof + 9_000_000)
        # Stockholm midnight is 23:00 UTC in November, before the quota expires.
        before_midnight = asof + 10 * 3_600_000 + 59 * 60_000
        with self.assertRaisesRegex(RuntimeError, '^fixture_input_calendar_changed$'):
            validate_input_time(before_midnight, 'Europe/Stockholm', now_ms=before_midnight + 120_000)

    def test_spawn_bootstrap_preserves_explicit_raw_quota_and_real_observation_timestamp(self):
        from development.tests.integration.benchmark_web_runtime import SPEC_ENV
        import os
        root = Path(__file__).resolve().parents[2]
        quota = dict(reset_at_ms=1794061800000, duration_seconds=18_000, remaining_fraction='0.75')
        script = ('import development.tests.integration.benchmark_web_runtime; '
            'from src.bootstrap import _account_providers; import json; '
            'value=_account_providers(None)[0].get_account_snapshots()[0]; '
            'print(json.dumps(dict(fetched_at_ms=value.fetched_at_ms, '
            'reset_at_ms=value.quotas[0].reset_at_ms, duration_seconds=value.quotas[0].duration_seconds, '
            'remaining_fraction=str(value.quotas[0].remaining_fraction))))')
        with TemporaryDirectory() as directory:
            spec = Path(directory) / 'spec.json'
            spec.write_text(json.dumps(dict(product_root=str(root), data_root=directory,
                source_url='http://127.0.0.1:12345', quota=quota)), encoding='utf-8')
            before = int(time.time() * 1000)

            result = subprocess.run([sys.executable, '-c', script], cwd=root,
                env={**os.environ, SPEC_ENV:str(spec)}, capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

            after = int(time.time() * 1000)
        self.assertEqual(0, result.returncode, result.stderr)
        actual = json.loads(result.stdout)
        self.assertLessEqual(before, actual.pop('fetched_at_ms'))
        self.assertEqual(quota, actual)
        self.assertLessEqual(json.loads(result.stdout)['fetched_at_ms'], after)

    def test_source_counter_snapshots_are_detached_and_deltas_exclude_preparation(self):
        from development.tests.fixtures.historical_web_retention import counter_delta
        source = WireHistory(8, 2, 1794053593853, 0)
        source.counts['catalog'] = 3
        source.bytes = 100
        before = source.snapshot()

        source.counts['catalog'] += 2
        source.counts['messages'] = 1
        source.bytes += 55
        delta = counter_delta(before, source.snapshot())

        self.assertEqual({'catalog':3}, before['requests'])
        self.assertEqual({'catalog':2, 'messages':1}, delta['requests'])
        self.assertEqual(55, delta['bytes'])
        self.assertGreaterEqual(delta['cpu_seconds'], 0)

    def test_warm_idle_summary_uses_only_samples_and_report_starts_inside_the_browser_window(self):
        from development.tests.integration.warm_idle_economy import summarize
        def host(wall, cpu, publications, busy):
            return dict(wall_ms=wall, cpu_seconds=cpu, publications=publications, busy_jobs=busy,
                working_set_bytes=wall * 2**20, read_bytes=wall, write_bytes=0)
        hosts = [host(900, 0, 0, 1), host(1000, 1, 10, 0), host(3000, 1.5, 16, 1), host(4000, 9, 99, 1)]
        sources = [dict(wall_ms=wall, requests=dict(catalog=count), bytes=count * 10)
            for wall, count in ((950, 1), (1000, 4), (3000, 6), (4100, 50))]
        imports = [dict(reports=[dict(kind='normal', started_wall_ms=2000, cpu_seconds=.25),
            dict(kind='token-mix', started_wall_ms=3500, cpu_seconds=4)])]

        summary = summarize(dict(start_wall_ms=1000, end_wall_ms=3000), hosts, sources, imports)

        self.assertEqual((.5, 25.0, 6, 1), (summary['host_cpu_seconds'], summary['host_cpu_percent'],
            summary['live_publications'], summary['busy_job_samples']))
        self.assertEqual(({'catalog':2}, 3600.0, 20), (summary['source_requests'],
            summary['source_requests_per_hour'], summary['source_bytes']))
        self.assertEqual((['normal'], .25), (summary['reports_started'], summary['report_cpu_seconds']))
        self.assertFalse(summarize(dict(start_wall_ms=3500, end_wall_ms=3900), hosts, sources, imports)['complete'])

    def test_retained_seed_includes_committed_wal_and_resets_same_cache_without_registration_rewrite(self):
        from development.tests.fixtures.historical_web_retention import CacheSeed
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'product/cache'
            cache.mkdir(parents=True)
            registration = root / 'product/service.json'
            registration.write_text('unchanged identity', encoding='utf-8')
            marker = registration.stat()
            database = cache / 'fixture.sqlite3'
            connection = sqlite3.connect(database)
            try:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('CREATE TABLE facts(value INTEGER)')
                connection.execute('INSERT INTO facts VALUES(7)')
                connection.commit()
                self.assertGreater(Path(str(database) + '-wal').stat().st_size, 0)
                (cache / 'state').mkdir()
                (cache / 'state/metadata.json').write_text('seed', encoding='utf-8')
                seed = CacheSeed(root / 'product', root / 'seed')
                seed.capture()
            finally:
                connection.close()

            fingerprints = []
            for _arm in (1, 2):
                fingerprints.append(seed.restore())
                with closing(sqlite3.connect(database)) as restored:
                    self.assertEqual([(7,)], restored.execute('SELECT value FROM facts').fetchall())
                    restored.execute('INSERT INTO facts VALUES(9)')
                    restored.commit()
                self.assertEqual('seed', (cache / 'state/metadata.json').read_text(encoding='utf-8'))
                (cache / 'state/metadata.json').write_text('arm mutation', encoding='utf-8')

            self.assertEqual(fingerprints[0], fingerprints[1])
            self.assertEqual(marker, registration.stat())

    def test_existing_product_registration_is_not_rewritten_and_different_identity_is_rejected(self):
        from development.tests.integration.benchmark_web_runtime import prepare_product_data
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source/config').mkdir(parents=True)
            (root / 'source/config/default-config.jsonc').write_text('{}', encoding='utf-8')
            wire = {'url':'http://127.0.0.1:12345', 'pid':42}
            prepare_product_data(root / 'source', root / 'product', wire)
            registration = root / 'product/state/opencode/service.json'
            marker = registration.stat()

            prepare_product_data(root / 'source', root / 'product', wire)

            self.assertEqual(marker, registration.stat())
            with self.assertRaisesRegex(RuntimeError, '^fixture_registration_identity_changed$'):
                prepare_product_data(root / 'source', root / 'product', {**wire, 'pid':43})

    def test_wire_oracle_is_prompt_finish_order_not_catalog_activity(self):
        source = WireHistory(8, 2, 1794053593853, 0)

        self.assertEqual(['ses_fixture_00000', 'ses_fixture_00005', 'ses_fixture_00002',
            'ses_fixture_00007', 'ses_fixture_00004'], source.winners)
        self.assertEqual([f'ses_fixture_{index:05d}' for index in range(8)],
            [session['id'] for session in source.sessions])
        self.assertNotEqual(source.winners, [session['id'] for session in source.sessions[:5]])

    def test_sparse_stales_change_exactly_three_revisions_and_usage_not_order_or_finish(self):
        source = WireHistory(550, 2, 1794053593853, 0)
        before = json.loads(json.dumps(dict(sessions=source.sessions, messages=source.messages)))
        winners = list(source.winners)

        result = source.make_sparse_stale()

        changed = [row['id'] for old, row in zip(before['sessions'], source.sessions) if old != row]
        self.assertEqual(['ses_fixture_00137', 'ses_fixture_00275', 'ses_fixture_00412'], changed)
        self.assertEqual({'changed_roots':3, 'usage_output_delta':3, 'ordering_preserved':True}, result)
        self.assertEqual(winners, source.winners)
        self.assertEqual([row['id'] for row in before['sessions']], [row['id'] for row in source.sessions])
        for sid in changed:
            old, current = before['messages'][sid][-1], source.messages[sid][-1]
            self.assertEqual(old['time'], current['time'])
            self.assertEqual(old['tokens']['output'] + 1, current['tokens']['output'])
        with self.assertRaisesRegex(RuntimeError, '^fixture_stales_already_applied$'):
            source.make_sparse_stale()

    def test_same_input_group_contains_two_models_and_priceable_nonzero_usage(self):
        source = WireHistory(64, 2, 1794053593853, 0)

        first = source.messages['ses_fixture_00000']
        peer = source.messages['ses_fixture_00011']

        self.assertEqual(first[0]['text'], peer[0]['text'])
        self.assertEqual('gpt-test-2', first[1]['model']['id'])
        self.assertEqual('gpt-test-1', peer[1]['model']['id'])
        self.assertEqual(120000, first[1]['tokens']['input'])
        self.assertEqual(20000, first[1]['tokens']['cache']['read'])

    def test_cutoff_effective_profile_keeps_exact_fixed_ten_percent_touched_old_roots(self):
        stress = WireHistory(550, 2, 1794053593853, 0)
        cutoff = WireHistory(550, 2, 1794053593853, 0, 'cutoff-effective')

        self.assertEqual(stress.winners, cutoff.winners)
        self.assertEqual(stress.messages, cutoff.messages)
        self.assertEqual(55, sum(value['time']['updated'] > 1794053593853 - 3_600_000
            for value in cutoff.sessions))
        self.assertEqual([value['time']['updated'] for value in cutoff.sessions],
            sorted((value['time']['updated'] for value in cutoff.sessions), reverse=True))

    def test_real_wire_pagination_does_not_truncate_at_first_500_sessions(self):
        source = WireHistory(550, 2, 1794053593853, 0)
        server = FixtureServer(source)
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval':.01}, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
        try:
            pages = []
            for query in ('limit=500&order=desc', 'cursor=500', 'cursor=550'):
                connection.request('GET', '/api/session?' + query)
                response = connection.getresponse()
                self.assertEqual(200, response.status)
                pages.append(json.loads(response.read()))

            self.assertEqual([500, 50, 0], [len(page['data']) for page in pages])
            self.assertEqual({'next':'500'}, pages[0]['cursor'])
            self.assertEqual({'next':'550'}, pages[1]['cursor'])
            self.assertEqual({}, pages[2]['cursor'])
            self.assertEqual('ses_fixture_00549', pages[1]['data'][-1]['id'])
            self.assertEqual(3, source.counts['catalog'])
        finally:
            connection.close()
            source.stopping.set()
            server.shutdown()
            server.close_connections()
            server.server_close()
            thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_wire_fixture_honors_each_page_limit_including_default_50_after_cursor(self):
        source = WireHistory(1200, 2, 1794053593853, 0)
        server = FixtureServer(source)
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval':.01}, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
        try:
            sizes = []
            for query in ('limit=1&order=desc', 'limit=500&order=desc', 'cursor=500', 'cursor=500&limit=500'):
                connection.request('GET', '/api/session?' + query)
                response = connection.getresponse()
                self.assertEqual(200, response.status)
                sizes.append(len(json.loads(response.read())['data']))
            self.assertEqual([1, 500, 50, 500], sizes)
        finally:
            connection.close()
            source.stopping.set()
            server.shutdown()
            server.close_connections()
            server.server_close()
            thread.join(2)

    def test_neutral_journey_accepts_original_http202_without_changing_reports(self):
        class HistoricalClient:
            def __init__(self):
                self.kind = None
                self.admissions = []

            def request(self, path, value=None):
                if path == '/api/reports':
                    self.kind = value['kind']
                    self.admissions.append(value)
                    return 202, {'id':'fixture_job'}
                view = {'model_comparison_sample_size':100,
                    'comparisons':{'groups':[{'runs':[{'model':'model-one'}, {'model':'model-two'}]}]}}
                return 200, {'status':'complete', 'result':{
                    'view':view, 'source':{'status':'acquired', 'revisions':[]}}}
        client = HistoricalClient()

        outcomes = backend_journey(client, False, time.monotonic() + 2)

        self.assertEqual(['normal', 'token-mix', 'ai-stats', 'comparisons'],
            [value['kind'] for value in client.admissions])
        self.assertEqual(['complete'] * 4, [row['status'] for row in outcomes])

    def test_wire_fixture_scoped_parent_cursor_and_leaf_closure_do_not_return_unrelated_roots(self):
        source = WireHistory(64, 2, 1794053593853, 0)
        source.sessions.extend(dict(id=f'ses_child_{index}', parentID='ses_fixture_00000') for index in range(3))
        server = FixtureServer(source)
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval':.01}, daemon=True)
        thread.start()
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
        try:
            values = []
            for path in ('/api/session/ses_fixture_00000', '/api/session?parentID=ses_fixture_00000&limit=1&order=desc',
                    '/api/session?cursor=1%7Cparent%3Dses_fixture_00000&limit=2',
                    '/api/session?parentID=ses_child_0&limit=500&order=desc', '/openapi.json'):
                connection.request('GET', path)
                response = connection.getresponse()
                self.assertEqual(200, response.status)
                values.append(json.loads(response.read()))
            self.assertEqual('ses_fixture_00000', values[0]['data']['id'])
            self.assertEqual(['ses_child_0'], [row['id'] for row in values[1]['data']])
            self.assertEqual(['ses_child_1', 'ses_child_2'], [row['id'] for row in values[2]['data']])
            self.assertEqual([], values[3]['data'])
            self.assertIn('/api/session/{sessionID}', values[4]['paths'])
            self.assertEqual(0, source.counts['catalog'])
            self.assertEqual(3, source.counts['scoped_children'])
        finally:
            connection.close()
            source.stopping.set()
            server.shutdown()
            server.close_connections()
            server.server_close()
            thread.join(2)

    def test_completed_models_must_really_have_100_prompts(self):
        class IncompleteSample:
            def request(self, _path, _value=None):
                return 200, {'result':{'view':{'model_comparison_sample_size':99},
                    'source':{'status':'acquired'}}}

        with self.assertRaisesRegex(RuntimeError, '^fixture_models_sample_not_100$'):
            backend_journey(IncompleteSample(), False, time.monotonic() + 2)

    def test_semantics_require_independent_paged_membership_and_positive_period_cost(self):
        class SharedClient:
            def request(self, path, value=None):
                if path == '/api/live':
                    return 200, {'values':{'live':{'view':{'history_state':'observed',
                        'history_cards':[{'session_id':'winner'}], 'history_checked':64, 'history_total':64,
                        'accounts':{'accounts':[{'primary':{'cost':{'complete':True,'ccost':'1.25'}}}]}}}}}
                offset = (value or {}).get('offset', 0)
                return 200, {'available':64, 'token':'token', 'epoch':'epoch',
                    'view':{'session_usage':[{'session_id':f'ses_fixture_{index:05d}'}
                        for index in range(offset, min(offset + 50, 64))]}}

        result = live_semantics(SharedClient(), {'roots':64, 'winners':['winner'],
            'catalog_order':[f'ses_fixture_{index:05d}' for index in range(64)]}, time.monotonic() + 2)

        self.assertEqual(64, result['sessions'])
        self.assertEqual(2, result['session_pages'])
        self.assertTrue(result['positive_complete_quota_period'])


if __name__ == '__main__':
    unittest.main()
