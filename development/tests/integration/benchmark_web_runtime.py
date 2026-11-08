"""Version-pinned complete Web-backend smoke with isolated raw V2/input boundaries.

This does not measure browser paint or replace large-source B0/B1/B2 acceptance.
Every selected version retains its own default WebHost composition and workers.
"""
import argparse
import hashlib
import http.client
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryFile
from threading import Event, Thread, Timer
import time
from urllib.parse import urlsplit

HARNESS_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = HARNESS_ROOT / 'development/tests/fixtures'
sys.path.append(str(FIXTURES))
sys.path.append(str(HARNESS_ROOT))  # Parent-only input validation; selected child root takes precedence below.
from historical_web_inputs import quota_input, validate_input_time
SPEC_ENV = 'COST_GUARD_HISTORICAL_WEB_SPEC'
SPEC = None
PORTS = None
if os.environ.get(SPEC_ENV):
    # Executed in the host AND Windows spawn bootstrap before product unpickling.
    SPEC = json.loads(Path(os.environ[SPEC_ENV]).read_text(encoding='utf-8'))
    sys.path.insert(0, str(Path(SPEC['product_root']).resolve()))
    from historical_web_inputs import install
    PORTS = install(SPEC)


def serve_host():
    from dispatch_probe_resources import Resources
    from historical_web_inputs import verify_origins
    from src.web.host import WebHost
    from src.version import DISPLAY_VERSION
    started, cpu = time.monotonic(), time.process_time()
    host = WebHost(Path(SPEC['product_root']))
    if SPEC.get('finite_switch') and SPEC.get('finite_promotion') == 'hold':
        original_prioritize = host.jobs.prioritize

        def hold_background(priorities):
            with host.jobs._lock:
                retained = dict(priorities)
                for key, job in host.jobs._jobs.items():
                    if job['request'].kind.value == SPEC['finite_switch']:
                        retained[key] = max(2, retained.get(key, 1))
                return original_prioritize(retained)

        host.jobs.prioritize = hold_background
    finite_timeline = None
    if SPEC.get('report_timeline'):
        from dispatch_probe_resources import FiniteTimeline
        finite_timeline = FiniteTimeline(host.jobs, host.dispatcher)
    timeline = None
    updates = None
    owner_profile = None
    if SPEC.get('owner_profile'):
        from owner_cost_timeline import OwnerCostTimeline
        owner_profile = OwnerCostTimeline(Path(SPEC['product_root']), functions=SPEC.get('owner_functions', 'on') == 'on')
    if SPEC.get('live_updates') or SPEC.get('history_switch'):
        from live_update_timeline import LiveUpdateTimeline
        updates = LiveUpdateTimeline()
    if SPEC.get('card_timeline') or updates is not None or owner_profile is not None:
        from card_service_timeline import CardServiceTimeline
        timeline = CardServiceTimeline() if SPEC.get('card_timeline') else None
        original_factory = host.live.factory

        def observed_factory():
            driver = original_factory()
            if timeline is not None:
                timeline.attach(driver.coordinator.cards)
            if updates is not None:
                updates.attach_cards(driver.coordinator.cards)
                updates.attach_runtime(host.live, driver)
            if owner_profile is not None:
                owner_profile.attach(host.live, driver)
            return driver

        host.live.factory = observed_factory
    resources = Resources()
    stopping = Event()
    publications, milestones = [], {}
    latest = {}
    if SPEC.get('history_switch'):
        from src.reports import ReportRequest
        from src.web.dispatch import usable
        original_tick = host.dispatcher.tick
        finite_usable = {}
        # Pacing-only observation exists only where the replayed product has the seam.
        pending = {} if 'history_pending' in inspect.signature(original_tick).parameters else None

        def observed_tick(**kwargs):
            result = original_tick(**kwargs)
            now, wall = int(time.time() * 1000), time.monotonic() - started
            entry = host.dispatcher.entries.get(ReportRequest())
            if entry and usable(entry['result'], now):
                milestones.setdefault('models_qualified', wall)
            with host.dispatcher.lock:
                entries = list(host.dispatcher.entries.items())
            for request, value in entries:
                if usable(value['result'], now):
                    finite_usable.setdefault(request.kind.value, now)
            if pending is not None and kwargs.get('history_pending'):
                # Native owner fact; the pacing control may withhold it from the dispatcher.
                pending.setdefault('first_wall_ms', now)
                pending['last_wall_ms'] = now
                key = entry and entry['job']
                with host.jobs._lock:
                    job = host.jobs._jobs.get(key) if key else None
                    if job is not None and job['status'] in {'queued', 'running'}:
                        priorities = pending.setdefault('models_priorities', {})
                        priorities[str(job.get('priority'))] = priorities.get(str(job.get('priority')), 0) + 1
            milestones['finite_usable_wall_ms'], milestones['history_pending'] = finite_usable, pending
            return result

        host.dispatcher.tick = observed_tick
    original_publish = host.live.publish

    def observe(kind, value):
        if kind == 'live':
            now = time.monotonic()
            publications.append(now)
            # Read only the few immutable fields needed for this milestone. The
            # normal publisher remains the sole full serialization owner.
            def field(record, name, default=None):
                if isinstance(record, dict):
                    return record.get(name, default)
                return next((value for key, value in getattr(record, 'fields', ()) if key == name), default)

            view = field(value, 'view')
            latest.clear()
            cards = field(view, 'history_cards', ())
            latest.update(state=field(view, 'history_state'), checked=field(view, 'history_checked'),
                total=field(view, 'history_total'), cards=len(cards))
            if cards:
                milestones.setdefault('first_history_visible', now - started)
            if {field(card, 'session_id') for card in cards} == set(SPEC['winners']):
                milestones.setdefault('independent_winners_observed', now - started)
                if latest['state'] == 'observed' and latest['checked'] == SPEC['roots']:
                    milestones.setdefault('certified_history', now - started)
        result = original_publish(kind, value)
        if kind == 'live' and updates is not None:
            updates.publication(value)
        return result

    host.live.publish = observe
    idle = None
    if SPEC.get('warm_idle'):
        from warm_idle_economy import HostIdleTimeline
        idle = HostIdleTimeline(host.jobs, publications, cpu, getattr(host.live, 'catalog', None))
    warm, warm_errors = None, []
    if SPEC.get('observe_warm'):
        from warm_report_observations import WarmReportObservations
        native_usable = None
        if getattr(host, 'dispatcher', None) is not None:
            from src.web.dispatch import usable as native_usable
        warm = WarmReportObservations(host.jobs, getattr(host, 'dispatcher', None),
            SPEC['evidence_root'], native_usable)

    def sample():
        while not stopping.wait(.2):
            resources.sample(host.jobs)
            if idle is not None:
                idle.sample(resources._read)
            if warm is not None:
                try:
                    warm.poll(lambda: dict(host_cpu_seconds=time.process_time()-cpu,
                        elapsed_seconds=time.monotonic()-started, resources=resources.summary(),
                        live_publications=len(publications)))
                except Exception as error:
                    warm_errors.append(warm.error_details(error))
                    break

    sampler = Thread(target=sample, daemon=True)
    host.start()
    PORTS.add(host.server.server_port)
    host.publish_ready()  # Test-owned headless host; excludes native launcher/icon readiness.
    sampler.start()
    try:
        print(json.dumps(dict(launch=host.browser_url(), version=DISPLAY_VERSION, interpreter=Path(sys.executable).name,
            dispatcher=getattr(host, 'dispatcher', None) is not None)), flush=True)
        for line in sys.stdin:
            command = json.loads(line)['command']
            if command == 'stop':
                break
            if command == 'link':
                print(json.dumps(dict(launch=host.browser_url())), flush=True)
            if command == 'update-progress':
                print(json.dumps(updates.progress() if updates is not None else {}), flush=True)
            if command == 'finite-progress':
                with host.jobs._lock:
                    values = [dict(id=key, status=job['status'], priority=job.get('priority'),
                        progress=job.get('progress'), slices=job.get('slices', 0), covered=job.get('covered', 0))
                        for key, job in host.jobs._jobs.items()
                        if job['request'].kind.value == SPEC.get('finite_switch')]
                print(json.dumps(values[-1] if values else {}), flush=True)
    finally:
        stopping.set()
        sampler.join(5)
        resources.sample(host.jobs)
        host.close()
        if finite_timeline is not None:
            finite_timeline.close()
        if owner_profile is not None:
            owner_profile.close()
        if warm is not None:
            warm.close()
        gaps = [b - a for a, b in zip(publications, publications[1:])]
        with host.jobs._lock:
            stats = [dict(status=job['status'], error=job.get('error'),
                result_error=(job.get('result') or {}).get('error'), progress=job.get('progress'),
                slices=job.get('slices'), covered=job.get('covered'))
                for job in host.jobs._jobs.values() if job['request'].kind.value == 'ai-stats']
        print(json.dumps(dict(host_failure=type(host.failure).__name__ if host.failure else None,
            host_cpu_seconds=time.process_time() - cpu, elapsed_seconds=time.monotonic() - started,
            live_publications=len(publications), live_max_gap_seconds=max(gaps, default=None),
            history=latest, milestones=milestones, resources=resources.summary(),
            imported_src_modules=len(verify_origins(Path(SPEC['product_root']).resolve())),
            serving_thread_alive=host.thread.is_alive(), live_thread_alive=host.live.thread.is_alive(),
            card_timeline=timeline.summary() if timeline is not None else None,
            owner_profile=owner_profile.summary() if owner_profile is not None else None,
             live_update_timeline=updates.summary() if updates is not None else None,
             finite_timeline=finite_timeline.summary() if finite_timeline is not None else None,
              warm_idle_timeline=idle.rows if idle is not None else None,
              warm_observations=warm.summary() if warm is not None else None,
               warm_observer_errors=warm_errors, stats_jobs=stats)), flush=True)


class Client:
    def __init__(self, launch):
        url = urlsplit(launch)
        self.host, self.port = url.hostname, url.port
        self.origin = f'http://{url.hostname}:{url.port}'
        self.cookie, self.csrf = None, None
        status, value = self.request('/api/bootstrap', dict(credential=url.fragment.split('=', 1)[1]))
        if status != 200:
            raise RuntimeError('fixture_host_bootstrap_failed')
        self.csrf = value['csrf']

    def request(self, path, value=None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        headers = dict(Origin=self.origin)
        if self.cookie:
            headers['Cookie'] = self.cookie
        if self.csrf:
            headers['X-CG-CSRF'] = self.csrf
        if value is not None:
            headers['Content-Type'] = 'application/json'
        try:
            connection.request('POST' if value is not None else 'GET', path,
                None if value is None else json.dumps(value), headers)
            response = connection.getresponse()
            cookie = response.getheader('Set-Cookie')
            if cookie:
                self.cookie = cookie.split(';', 1)[0]
            return response.status, json.loads(response.read())
        finally:
            connection.close()


def backend_journey(client, dispatcher, deadline):
    outcomes = []
    for section, kind in (('models', 'normal'), ('token-mix', 'token-mix'),
            ('ai-stats', 'ai-stats'), ('comparisons', 'comparisons')):
        request = dict(kind=kind)
        started = time.monotonic()
        if dispatcher:
            client.request('/api/interest', dict(tab='a' * 32, section=section, visible=True, request=request))
        value, job_id = None, None
        observations, last_observed = [], float('-inf')
        while time.monotonic() < deadline:
            if job_id is None:
                status, admitted = client.request('/api/data' if dispatcher else '/api/reports',
                    dict(request=request, retry=False) if dispatcher else request)
                if status in (429, 503) and admitted.get('error') in {'busy', 'source_starting', 'source_unavailable'}:
                    time.sleep(.1)
                    continue
                if status not in (200, 202):
                    raise RuntimeError('fixture_report_admission_failed')
                if admitted.get('result'):
                    value = admitted['result']
                    break
                job_id = admitted.get('id')
                if job_id is None:
                    raise RuntimeError('fixture_report_terminal_admission')
            status, job = client.request('/api/jobs/' + job_id)
            if status != 200:
                raise RuntimeError('fixture_report_poll_failed')
            if time.monotonic() - last_observed >= 5:
                progress = job.get('progress') or {}
                observations.append(dict(seconds=time.monotonic() - started, status=job['status'],
                    progress={key: progress.get(key) for key in ('phase', 'completed', 'total')},
                    work=job.get('work')))
                last_observed = time.monotonic()
            if job['status'] == 'complete':
                value = job['result']
                break
            if job['status'] in {'failed', 'cancelled'}:
                outcomes.append(dict(section=section, status=job['status'], error=job.get('error') or
                    (job.get('result') or {}).get('error')))
                break
            time.sleep(.1)
        if value is None:
            outcomes.append(dict(section=section, status='incomplete', observations=observations))
            break
        view = value.get('view') or {}
        if value.get('error') or not view or value.get('source', {}).get('status') != 'acquired':
            raise RuntimeError('fixture_report_not_qualified')
        sample = view.get('model_comparison_sample_size')
        if section == 'models' and sample != 100:
            raise RuntimeError('fixture_models_sample_not_100')
        if section == 'comparisons' and not any(len({run['model'] for run in group['runs']}) > 1
                for group in (view.get('comparisons') or {}).get('groups', ())):
            raise RuntimeError('fixture_comparisons_missing_cross_model_group')
        outcomes.append(dict(section=section, status='complete', seconds=time.monotonic() - started,
            model_sample=sample, stats_periods=len(view.get('ai_stats', ())),
            source_revisions=len(value['source'].get('revisions', ()))))
    return outcomes


def live_semantics(client, wire, deadline):
    """Independent synthetic membership and nonempty subscription period checks."""
    page = None
    while time.monotonic() < deadline:
        status, live = client.request('/api/live')
        if status != 200:
            raise RuntimeError('fixture_live_read_failed')
        view = (live.get('values', {}).get('live') or {}).get('view') or {}
        cards = view.get('history_cards', ())
        accounts = (view.get('accounts') or {}).get('accounts', ())
        period_ready = bool(accounts and accounts[0].get('primary', {}).get('cost') and
            accounts[0]['primary']['cost']['complete'] and float(accounts[0]['primary']['cost']['ccost']) > 0)
        if view.get('history_state') == 'observed' and {row['session_id'] for row in cards} == set(wire['winners']) and period_ready:
            break
        time.sleep(.1)
    else:
        raise RuntimeError('fixture_live_semantics_incomplete')
    status, page = client.request('/api/sessions', {})
    if status != 200 or page['available'] != wire['roots']:
        raise RuntimeError('fixture_sessions_catalog_incomplete')
    ids = [row['session_id'] for row in page['view']['session_usage']]
    token, epoch = page['token'], page['epoch']
    for offset in range(50, wire['roots'], 50):
        status, page = client.request('/api/sessions', dict(token=token, epoch=epoch, offset=offset))
        if status != 200:
            raise RuntimeError('fixture_sessions_page_failed')
        ids.extend(row['session_id'] for row in page['view']['session_usage'])
    if ids != wire['catalog_order']:
        raise RuntimeError('fixture_sessions_membership_mismatch')
    return dict(exact_history_winners=True, sessions=len(ids), session_pages=(len(ids) + 49) // 50,
        account_cards=len(accounts), positive_complete_quota_period=True,
        product_history_checked=view.get('history_checked'), product_history_total=view.get('history_total'))


def source_digest(root):
    digest = hashlib.sha256()
    files = sorted((root / 'src').rglob('*'))
    for path in files:
        if path.is_file() and '__pycache__' not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def stop_owned(process, timeout):
    """Close only this producer handle, including failed startup/cleanup paths."""
    if process.poll() is None:
        try:
            process.stdin.write('{"command":"stop"}\n')
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
    errors = getattr(process, '_fixture_stderr', None)
    try:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
        if errors is not None:
            errors.seek(0)
            stderr = errors.read()
        return stdout, stderr
    finally:
        if errors is not None:
            errors.close()


def prepare_product_data(root, data, wire, *, timezone='UTC'):
    (data / 'config').mkdir(parents=True, exist_ok=True)
    defaults = data / 'config/default-config.jsonc'
    if not defaults.exists():
        shutil.copyfile(root / 'config/default-config.jsonc', defaults)
        (data / 'config/user-config.jsonc').write_text(json.dumps(dict(timezone=timezone, openCode=dict(source='v2'))), encoding='utf-8')
    state = data / 'state/opencode'
    state.mkdir(parents=True, exist_ok=True)
    registration = state / 'service.json'
    value = dict(url=wire['url'], pid=wire['pid'], version='2.1.0')
    if registration.exists():
        if json.loads(registration.read_text(encoding='utf-8')) != value:
            raise RuntimeError('fixture_registration_identity_changed')
    else:
        registration.write_text(json.dumps(value), encoding='utf-8')


def start_source(args):
    flags = dict(creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    # A persistent fixture may outlive hundreds of hosts. A disk sink drains
    # diagnostics continuously instead of letting an unread stderr pipe block IO.
    errors = TemporaryFile(mode='w+t', encoding='utf-8')
    try:
        process = subprocess.Popen([sys.executable, str(FIXTURES / 'historical_web_source.py'), '--roots', str(args.roots),
            '--asof', str(args.asof or int(time.time() * 1000)), '--latency-ms', str(args.latency_ms),
            '--activity-pattern', args.activity_pattern, *(['--active-probe'] if getattr(args, 'live_updates', 0) else [])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True, **flags)
    except BaseException:
        errors.close()
        raise
    process._fixture_stderr = errors
    return process


def source_snapshot(source):
    source.stdin.write('{"command":"snapshot"}\n')
    source.stdin.flush()
    return json.loads(source.stdout.readline())


def known_updates(source, host, count, deadline, stopping, changes, errors):
    """Serial controlled changes; next change follows actual prior active publication.

    Own process pipes only, no product/source HTTP mutation. Main must join this
    controller before reusing either process's stdout protocol.
    """
    try:
        for ordinal in range(1, count + 1):
            if stopping.wait(1):
                return
            source.stdin.write('{"command":"active-update"}\n')
            source.stdin.flush()
            change = json.loads(source.stdout.readline())
            if change['ordinal'] != ordinal:
                raise RuntimeError('fixture_update_sequence_mismatch')
            changes.append(change)
            while time.monotonic() < deadline and not stopping.is_set():
                host.stdin.write('{"command":"update-progress"}\n')
                host.stdin.flush()
                published = json.loads(host.stdout.readline())
                if str(ordinal) in published:
                    break
                stopping.wait(.05)
            else:
                raise RuntimeError('fixture_active_content_update_not_published')
    except Exception as error:
        errors.append(type(error).__name__ + ':' + str(error))


def finish_updates(thread, deadline, errors):
    if thread is not None:
        thread.join(max(0, deadline - time.monotonic()) + 2)
        if thread.is_alive() or errors:
            raise RuntimeError('fixture_known_update_diagnostic_incomplete')


def fresh_launch(host):
    """Obtain a new one-use handoff without exchanging it in this process."""
    host.stdin.write('{"command":"link"}\n')
    host.stdin.flush()
    return json.loads(host.stdout.readline())


def prepare_finite_switch(host, launch, section, deadline):
    """Finish Models, then passively identify advancing native speculative work."""
    client = Client(launch)
    tab = 'b' * 32
    status, _ = client.request('/api/interest', dict(tab=tab, section='models', visible=True, request=dict(kind='normal')))
    if status != 200:
        raise RuntimeError('fixture_promotion_interest_failed')
    while time.monotonic() < deadline:
        status, value = client.request('/api/data', dict(request=dict(kind='normal'), retry=False))
        if status not in (200, 429, 503):
            raise RuntimeError('fixture_promotion_models_request_rejected')
        if status == 200 and value.get('result'):
            break
        time.sleep(.05)
    else:
        raise RuntimeError('fixture_promotion_models_preparation_incomplete')
    status, _ = client.request('/api/interest', dict(tab=tab, section='watch', visible=True, request=None))
    if status != 200:
        raise RuntimeError('fixture_promotion_interest_failed')
    previous = None
    while time.monotonic() < deadline:
        host.stdin.write('{"command":"finite-progress"}\n')
        host.stdin.flush()
        value = json.loads(host.stdout.readline())
        progress = value.get('progress') or {}
        if value.get('status') == 'complete':
            raise RuntimeError('fixture_promotion_already_complete')
        if (value.get('priority') == 2 and value.get('status') in {'queued', 'running'}
                and (progress.get('completed') or 0) > 0):
            if (previous and previous['id'] == value['id'] and
                    (previous.get('progress') or {}).get('sequence') != progress.get('sequence')):
                return value
            previous = value
        time.sleep(.05)
    raise RuntimeError('fixture_no_advancing_background_' + section)


def warm_options(args):
    append = getattr(args, 'warm_reentry', False)
    return dict(observe_warm=append or getattr(args, 'untouched_warm', False), append_warm_reentry=append)


def run(args, *, fixture=None, product_data=None, emit=True):
    root, data = args.product_root.resolve(), args.run_root.resolve()
    data.mkdir(parents=True, exist_ok=False)
    product_data = data if product_data is None else product_data.resolve()
    flags = dict(creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    source = start_source(args) if fixture is None else fixture[0]
    host = None
    source_timer = None
    if fixture is None:
        source_timer = Timer(args.seconds + 30, source.kill)
        source_timer.start()
    host_timer = None
    update_thread, updates_stop, changes, update_errors = None, Event(), [], []
    counters = None
    outcome = dict(kind='full_historical_web_backend_smoke', product_source_and_assets_sha256=source_digest(root),
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), roots=args.roots,
        limitation='No browser/native paint, performance acceptance, real-source oracle or controlled update-freshness proof.')
    outcome['fixtures_sha256'] = {name: hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
        for name in ('historical_web_source.py', 'historical_web_inputs.py', 'card_service_timeline.py',
            'live_update_timeline.py', 'owner_cost_timeline.py')}
    warm = warm_options(args)
    if warm['observe_warm']:
        outcome['resource_phase_limitation'] = (
            'Host/source totals combine the primary journey, passive observer and appended warm work; '
            'browser primary-boundary snapshot is separate.' if warm['append_warm_reentry'] else
            'Host/source totals include passive untouched-warming observation and the primary journey; no appended reentry.')
    outcome['support_sha256'] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('probe_historical_web.cjs', 'dispatch_probe_resources.py', 'warm_report_observations.py')}
    outcome['controls'] = dict(roots=args.roots, prompts_per_root=2, io_latency_ms=args.latency_ms,
        diagnostic_stacks=args.diagnostic_stacks, card_timeline=args.card_timeline, resource_sample_seconds=.2,
        fixture_pattern=args.activity_pattern, timezone=getattr(args, 'timezone', 'UTC'), sample_window=args.sample_window,
        completion_refill=args.completion_refill, cache_condition=getattr(args, 'cache_condition', 'cold'),
        card_readers=getattr(args, 'card_readers', None),
        card_brackets=getattr(args, 'card_brackets', None),
        live_updates=getattr(args, 'live_updates', 0),
        owner_profile=getattr(args, 'owner_profile', False),
             owner_functions=getattr(args, 'owner_functions', 'on'),
              history_switch=getattr(args, 'history_switch', False),
        history_pacing=getattr(args, 'history_pacing', None),
         report_timeline=getattr(args, 'report_timeline', False),
         finite_switch=getattr(args, 'finite_switch', None), finite_promotion=getattr(args, 'finite_promotion', 'normal'),
        warm_idle=getattr(args, 'warm_idle', 0), warm_settle=getattr(args, 'warm_settle', 0),
         sampling_catalog_observer=getattr(args, 'sampling_catalog_observer', False),
          accounts_switches=getattr(args, 'accounts_switches', 0),
          observe_cache_failures=getattr(args, 'observe_cache_failures', False),
          stats_cache_lock_once=getattr(args, 'stats_cache_lock_once', False),
          stats_lock_probe=getattr(args, 'stats_lock_probe', False),
          warm_reentry=getattr(args, 'warm_reentry', False), untouched_warm=getattr(args, 'untouched_warm', False), **warm)
    outcome['git_head'] = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    try:
        wire = json.loads(source.stdout.readline()) if fixture is None else fixture[1]
        before = source_snapshot(source)
        outcome['fixture_asof_ms'] = wire['asof']
        timezone = getattr(args, 'timezone', 'UTC')
        quota = quota_input(wire['asof'])
        outcome['input_timing'] = dict(asof_ms=wire['asof'], timezone=timezone,
            quota=quota, started_ms=int(time.time() * 1000))
        validate_input_time(wire['asof'], timezone, now_ms=outcome['input_timing']['started_ms'])
        prepare_product_data(root, product_data, wire, timezone=getattr(args, 'timezone', 'UTC'))
        spec = dict(product_root=str(root), data_root=str(product_data), evidence_root=str(data), source_url=wire['url'],
            quota=quota,
            winners=wire['winners'], roots=args.roots, diagnostic_stacks=args.diagnostic_stacks,
            sample_window=args.sample_window, card_timeline=args.card_timeline, completion_refill=args.completion_refill,
            card_readers=getattr(args, 'card_readers', None),
            card_brackets=getattr(args, 'card_brackets', None),
            live_updates=getattr(args, 'live_updates', 0),
            owner_profile=getattr(args, 'owner_profile', False),
             owner_functions=getattr(args, 'owner_functions', 'on'),
             history_switch=getattr(args, 'history_switch', False),
            history_pacing=getattr(args, 'history_pacing', None),
             report_timeline=getattr(args, 'report_timeline', False),
             finite_switch=getattr(args, 'finite_switch', None), finite_promotion=getattr(args, 'finite_promotion', 'normal'),
             warm_idle=getattr(args, 'warm_idle', 0),
              observe_warm=warm['observe_warm'],
             observe_cache_failures=getattr(args, 'observe_cache_failures', False),
             stats_cache_lock_once=getattr(args, 'stats_cache_lock_once', False),
            sampling_catalog_observer=getattr(args, 'sampling_catalog_observer', False))
        spec_path = data / 'run.json'
        spec_path.write_text(json.dumps(spec), encoding='utf-8')
        environment = dict(os.environ, **{SPEC_ENV: str(spec_path), 'XDG_STATE_HOME': str(product_data / 'state'),
            'XDG_DATA_HOME': str(product_data / 'data'), 'XDG_CONFIG_HOME': str(product_data / 'configuration'),
            'OPENCODE_DB': str(product_data / 'absent-legacy.db'), 'PYTHONDONTWRITEBYTECODE': '1'})
        host_executable = Path(sys.executable)
        if os.name == 'nt':
            # Match the shipped launcher: all finite descendants must also be
            # console-free, not merely the immediate hidden host process.
            host_executable = host_executable.with_name('pythonw.exe')
            if not host_executable.is_file():
                raise RuntimeError('fixture_gui_interpreter_unavailable')
        host = subprocess.Popen([str(host_executable), str(Path(__file__).resolve()), '--host'], env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **flags)
        host_timer = Timer(args.seconds + 10, host.kill)
        host_timer.start()
        line = host.stdout.readline()
        if not line:
            raise RuntimeError('fixture_host_exited_before_startup')
        launch = json.loads(line)
        outcome.update(version=launch['version'], dispatcher=launch['dispatcher'], interpreter=launch['interpreter'])
        deadline = time.monotonic() + args.seconds
        if getattr(args, 'live_updates', 0):
            update_thread = Thread(target=known_updates,
                args=(source, host, args.live_updates, deadline, updates_stop, changes, update_errors), daemon=True)
            update_thread.start()
        if getattr(args, 'warm_idle', 0):
            from warm_idle_economy import SourceCounters
            counters = SourceCounters(lambda: source_snapshot(source))
            counters.start()
        if args.browser:
            promotion = (prepare_finite_switch(host, launch['launch'], args.finite_switch, deadline)
                if getattr(args, 'finite_switch', None) else None)
            if promotion:
                outcome['finite_before_browser'] = {key: value for key, value in promotion.items() if key != 'id'}
                # Preparation exchanged the original one-use handoff in Client;
                # Chrome has its own cookie jar and must receive an unused link.
                launch = fresh_launch(host)
            browser = subprocess.run(['node', str(Path(__file__).with_name('probe_historical_web.cjs')),
                str(args.browser.resolve()), str(data / 'browser')], input=json.dumps(dict(
                    launch=launch['launch'], seconds=args.seconds, winners=wire['winners'], roots=args.roots,
                      catalog_order=wire['catalog_order'], history_switch=getattr(args, 'history_switch', False),
                      finite_switch=getattr(args, 'finite_switch', None), promotion_job=promotion['id'] if promotion else None,
                      warm_idle=getattr(args, 'warm_idle', 0), warm_settle=getattr(args, 'warm_settle', 0),
                      accounts_switches=getattr(args, 'accounts_switches', 0),
                       accounts_boundary_resets=getattr(args, 'accounts_boundary_resets', None),
                       warm_directory=str(data) if warm['observe_warm'] else None,
                       append_warm_reentry=warm['append_warm_reentry'],
                       stats_lock_probe=getattr(args, 'stats_lock_probe', False),
                       untouched_warm=getattr(args, 'untouched_warm', False))),
                capture_output=True, text=True, timeout=args.seconds + 5, **flags)
            if counters is not None:
                counters.stop()
            (data / 'browser-stderr.txt').write_text(browser.stderr, encoding='utf-8')
            outcome['browser'] = json.loads(browser.stdout)
            if browser.returncode != 0:
                raise RuntimeError('fixture_browser_journey_failed')
            outcome['kind'] = 'full_historical_web_browser_smoke'
            outcome['limitation'] = 'Controlled smoke only; no native OS geometry, large-real-source oracle or matched performance acceptance.'
            outcome['routes'] = outcome['browser']['routes']
            finish_updates(update_thread, deadline, update_errors)
            launch = fresh_launch(host)
        else:
            outcome['routes'] = backend_journey(Client(launch['launch']), launch['dispatcher'], deadline)
            finish_updates(update_thread, deadline, update_errors)
            launch = fresh_launch(host)
        outcome['semantic_checks'] = live_semantics(Client(launch['launch']), wire, deadline)
        finished_ms = int(time.time() * 1000)
        validate_input_time(wire['asof'], timezone, now_ms=finished_ms)
        outcome['input_timing']['validated_through_ms'] = finished_ms
    except RuntimeError as error:
        if str(error).startswith('fixture_input_'):
            outcome['input_invalid'] = str(error)
        raise
    finally:
        updates_stop.set()
        if counters is not None:
            counters.stop()  # Idempotent; must release the source pipe before its stop command.
        if update_thread is not None:
            update_thread.join(2)
        outcome['known_source_changes'] = changes
        outcome['update_errors'] = update_errors
        try:
            if host is not None:
                stdout, stderr = stop_owned(host, 15)
                (data / 'host-stderr.txt').write_text(stderr, encoding='utf-8')
                if stdout.strip():
                    outcome['host'] = json.loads(stdout.strip().splitlines()[-1])
                outcome['host_exit'] = host.returncode
        finally:
            if host_timer:
                host_timer.cancel()
                host_timer.join()
            if fixture is None:
                stdout, stderr = stop_owned(source, 10)
                source_timer.cancel()
                source_timer.join()
                (data / 'source-stderr.txt').write_text(stderr, encoding='utf-8')
                if stdout.strip():
                    outcome['source'] = json.loads(stdout.strip().splitlines()[-1])
            else:
                from historical_web_retention import counter_delta
                outcome['source'] = counter_delta(before, source_snapshot(source))
                outcome['source']['persistent_fixture'] = True
            if update_thread is not None:
                update_thread.join(5)
                outcome['update_controller_alive'] = update_thread.is_alive()
        outcome['imports'] = [json.loads(path.read_text(encoding='utf-8')) for path in sorted(data.glob('imports-*.json'))]
        windows = (outcome.get('browser') or {}).get('warm_idle_windows')
        if counters is not None and windows:
            from warm_idle_economy import summarize
            host_rows = (outcome.get('host') or {}).get('warm_idle_timeline') or []
            outcome['warm_idle'] = {row['label']: dict(summarize(row, host_rows, counters.rows, outcome['imports']),
                earlier_open=row['earlier_open'], history_demand=row['history_demand']) for row in windows}
            outcome['warm_idle_source_rows'] = counters.rows
        (data / 'result.json').write_text(json.dumps(outcome, indent=2), encoding='utf-8')
    if emit:
        print(json.dumps(outcome), flush=True)
    owned = outcome.get('host', {})
    if warm['observe_warm']:
        if owned.get('warm_observer_errors') or (owned.get('warm_observations') or {}).get('dropped') != 0:
            raise RuntimeError('fixture_warm_observer_incomplete')
    expected_updates = {str(number) for number in range(1, getattr(args, 'live_updates', 0) + 1)}
    update_timeline = owned.get('live_update_timeline') or {}
    if (expected_updates and (not expected_updates <= update_timeline.get('accepted', {}).keys()
            or not expected_updates <= update_timeline.get('published', {}).keys()
            or outcome.get('update_controller_alive') or outcome.get('update_errors'))):
        raise RuntimeError('fixture_known_updates_not_accepted_and_published')
    if (outcome.get('host_exit') != 0 or owned.get('host_failure') or owned.get('serving_thread_alive', True)
            or owned.get('live_thread_alive', True) or owned.get('live_publications', 0) < 2
            or len(outcome['imports']) < 2 or any(row['foreign_src_modules'] for row in outcome['imports'])
            or len(outcome.get('routes', ())) < 4 or any(row['status'] != 'complete' for row in outcome.get('routes', ()))
            or not outcome.get('semantic_checks')):
        raise RuntimeError('fixture_backend_smoke_incomplete')
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--product-root', type=Path)
    parser.add_argument('--run-root', type=Path)
    parser.add_argument('--roots', type=int, default=64)
    parser.add_argument('--seconds', type=int, default=120)
    parser.add_argument('--latency-ms', type=float, default=0)
    parser.add_argument('--asof', type=int)
    parser.add_argument('--activity-pattern', choices=('recent-metadata', 'cutoff-effective'), default='recent-metadata')
    parser.add_argument('--timezone', choices=('UTC', 'Europe/Stockholm'), default='UTC', help='Matched input timezone; includes shipped Windows fallback')
    parser.add_argument('--sample-window', type=int, choices=(1, 2, 4, 8), help='Candidate-only bounded sampling input control')
    parser.add_argument('--completion-refill', choices=('on', 'off'), help='Candidate-only readiness notification control')
    parser.add_argument('--card-readers', choices=('off',), help='Candidate-only fresh-reader comparator; omitted uses native default')
    parser.add_argument('--card-brackets', choices=('global',), help='Candidate-only global bracket comparator; omitted uses native scoped cards')
    parser.add_argument('--live-updates', type=int, choices=(1, 3), default=0,
        help='Controlled active-source update diagnostic during the normal whole-Web journey, not static performance acceptance')
    parser.add_argument('--history-switch', nargs='?', const='full', choices=('full', 'mini'), default=False,
        help='Scripted partial-warming Earlier switch (Full, or visible Mini over a hidden opener); requires browser')
    parser.add_argument('--history-pacing', choices=('off',), help='Candidate-only control withholding history-pending finite pacing')
    parser.add_argument('--report-timeline', action='store_true', help='Candidate-only finite transitions and original Token Mix entrypoint; diagnostic overhead')
    parser.add_argument('--finite-switch', choices=('ai-stats',), help='Candidate-only navigation into advancing speculative work; requires browser')
    parser.add_argument('--finite-promotion', choices=('normal', 'hold'), default='normal',
        help='Diagnostic control retaining the selected finite job at its ordinary background priority')
    parser.add_argument('--diagnostic-stacks', action='store_true', help='Owned synthetic processes only; not a performance run')
    parser.add_argument('--card-timeline', action='store_true', help='Candidate-only numeric scheduling diagnostic; adds observation overhead')
    parser.add_argument('--owner-profile', action='store_true', help='Candidate-only stage/threadCPU and short function profile; adds overhead')
    parser.add_argument('--owner-functions', choices=('on', 'off'), default='on', help='Coarse-only owner comparison when off')
    parser.add_argument('--browser', type=Path, help='Explicit headless Chromium executable; exercises selected shipped assets')
    parser.add_argument('--warm-idle', type=int, default=0, metavar='SECONDS',
        help='Warm-complete idle economy window after the journey, then warm re-entry; requires browser')
    parser.add_argument('--warm-settle', type=int, default=30, metavar='SECONDS',
        help='Fixed browser settle before the warm idle window, not a product timeout')
    parser.add_argument('--warm-reentry', action='store_true',
        help='Passive per-entry host checkpoints, then same-tab/fresh-page sequences without idle windows')
    parser.add_argument('--untouched-warm', action='store_true',
        help='After Models, passively await untouched native warming; no appended reentry unless explicitly selected')
    args = parser.parse_args()
    if args.host:
        if SPEC is None:
            parser.error('missing fixture specification')
        serve_host()
    else:
        if args.product_root is None or args.run_root is None or not 50 <= args.roots <= 3000 or not 10 <= args.seconds <= 1200:
            parser.error('explicit product/run roots, 50..3000 roots and 10..1200 seconds required')
        if args.history_switch and args.browser is None:
            parser.error('history-switch requires an explicit browser')
        if args.finite_switch and (args.browser is None or args.history_switch or args.live_updates or not args.report_timeline):
            parser.error('finite-switch requires browser/report-timeline and no history-switch/live-updates')
        if args.finite_promotion == 'hold' and not args.finite_switch:
            parser.error('finite-promotion hold requires finite-switch')
        if args.warm_idle and (args.browser is None or args.live_updates or args.warm_idle < 10 or args.warm_settle < 0):
            parser.error('warm-idle needs >=10 seconds, an explicit browser and no live-updates (shared source pipe)')
        if warm_options(args)['observe_warm'] and (args.browser is None or args.warm_idle or args.live_updates or args.finite_switch or args.history_switch):
            parser.error('warm observation requires browser and no idle/update/promotion scenario')
        run(args)


if __name__ == '__main__':
    main()
