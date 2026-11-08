"""Owned, read-only real-source correctness probe; never cold-performance proof."""
import hashlib
import json
from pathlib import Path
import subprocess
from threading import Lock
import time
from uuid import uuid4

from development.tests.integration.history_reference import HistoryReference
from development.tests.integration.web_live_observations import ProbeObservations, probe_lifecycle
from src.config import load_configuration
from src.sources.selection import SourceSelector
from src.web.host import WebHost


def field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return next((item for key, item in getattr(value, 'fields', ()) if key == name), default)


def product_proof(driver, value):
    """Called on Live's owner; actual evidence only, NEVER the expected ranking."""
    view = field(value, 'view')
    if field(view, 'history_state') != 'observed':
        return None
    owner = driver.coordinator
    entries = owner.cards.sessions
    rows = []
    for card in field(view, 'history_cards', ()):
        card_rows = field(card, 'rows', ())
        if len(card_rows) != 1:
            return None
        prompt = field(card_rows[0], 'prompt')
        rows.append((field(card, 'session_id'), field(prompt, 'event_id'), field(prompt, 'completed_at_ms')))
    return dict(epoch=owner.source.observation_epoch,
        revisions={key: entry.revision for key, entry in entries.items()}, rows=tuple(rows),
        verified=driver.error is None and field(view, 'history_checked') == field(view, 'history_total') == len(entries)
            and field(view, 'history_epoch', 0) > 0 and all(entry.verified_generation == entry.generation
                and entry.source_status.failed_at is None and entry.history_status.failed_at is None
                for entry in entries.values()))


def run(root, output, browser, *, seconds=1800, serial_first=False):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + seconds
    facts = dict(outcome='INCONCLUSIVE', limitation='Correctness observation with reference acquisition/revalidation overhead; '
        'not cold performance, rewritten semantic engine, native OS geometry or final epic acceptance.')
    facts['observation_mode'] = 'serial_first_certificate' if serial_first else 'concurrent_reference'
    facts['cache_condition'] = 'Existing application caches retained; independent preparation may warm storage; not OS-cold.'
    reference = source = host = None
    latest, publications, first_certificate = [], [], []
    lock = Lock()
    stage = 'reference_preparation'
    try:
        config = load_configuration(root).values
        selection = SourceSelector(inspect_migration_gap=False).select(str(config['openCode']['source']))
        source = selection.source
        if selection.selected != 'v2':
            raise RuntimeError('probe_reference_requires_selected_v2')
        reference = HistoryReference(source)

        def progress(summary):
            with lock:
                product = dict(facts.get('last_product_history', {}))
                count = len(publications)
            (output / 'progress.json').write_text(json.dumps(dict(stage=stage,
                elapsed_seconds=time.monotonic() - started, reference=summary,
                product=product, live_publications=count)), encoding='utf-8')

        while not reference.refresh(deadline=deadline, progress=progress):
            if time.monotonic() >= deadline:
                raise RuntimeError('probe_reference_preparation_censored')
            time.sleep(2)
        facts['reference_preparation_seconds'] = time.monotonic() - started
        facts['reference'] = reference.summary()
        facts['reference_method'] = 'separate_reader_complete_global_brackets_shared_canonical_lifecycle_no_cache_or_pricing'
        if len(reference.revisions) < 1000 or len(reference.expected()) != 5:
            raise RuntimeError('probe_reference_large_population_or_five_winners_missing')
        stage = 'product_history'
        host = WebHost(root)
        publish = host.live.publish
        host_started = time.monotonic()

        def observe(kind, value):
            if kind == 'live':
                now = time.monotonic()
                view = field(value, 'view')
                proof = product_proof(host.live.driver, value) if host.live.driver is not None else None
                with lock:
                    publications.append(now)
                    latest[:] = [proof]
                    facts['last_product_history'] = dict(state=field(view, 'history_state'),
                        checked=field(view, 'history_checked'), total=field(view, 'history_total'),
                        cards=len(field(view, 'history_cards', ())))
                    if proof is not None and proof['verified']:
                        facts.setdefault('first_product_certified_seconds', now - host_started)
                        if not first_certificate:
                            # product_proof detached all identity/revision/row scalars on the owner.
                            # Freeze this exact first certificate, even if later publications change.
                            first_certificate.append((proof, now, tuple(publications),
                                dict(facts['last_product_history'])))
            return publish(kind, value)

        host.live.publish = observe
        host.start()
        host.publish_ready()  # Owned headless test host, not native icon/event-loop proof.
        tab = uuid4().hex

        def validate_first_certificate():
            nonlocal stage
            renewed = next_progress = 0
            while time.monotonic() < deadline and not host.failure:
                now = time.monotonic()
                if now - renewed >= 30:
                    host.dispatcher.interest(tab, 'watch', True, history=True)
                    renewed = now
                with lock:
                    certificate = first_certificate[0] if first_certificate else None
                if certificate is not None:
                    break
                if now >= next_progress:
                    progress(facts['reference'])  # Cached summary only: NO independent source work.
                    next_progress = now + 5
                time.sleep(.25)
            else:
                raise RuntimeError('probe_first_product_certificate_censored')
            proof, certified_at, timestamps, history = certificate
            facts['timed_product_phase'] = dict(seconds=certified_at - host_started,
                reference_refreshes=0, live_publications=len(timestamps), last_history=history,
                first_publication_seconds=timestamps[0] - host_started,
                max_live_publication_gap_seconds=max((b-a for a,b in zip(timestamps, timestamps[1:])), default=None))
            stage = 'first_certificate_validation'
            validation_started = time.monotonic()
            ready = reference.refresh(deadline=deadline, progress=progress)
            matched = bool(ready and reference.matches(proof))
            facts['first_certificate_validation'] = dict(reference_ready=bool(ready), matched=matched,
                seconds=time.monotonic() - validation_started)
            if not matched:
                # Source churn can make this inconclusive. A later matching proof cannot bless it.
                raise RuntimeError('probe_first_certificate_validation_inconclusive')
            host.dispatcher.interest(tab, 'watch', False)
            return time.monotonic() - host_started

        def await_match(censored):
            """Freshly refreshed reference and actual certified proof agree exactly."""
            renewed = next_reconcile = 0
            while time.monotonic() < deadline and not host.failure:
                now = time.monotonic()
                if now - renewed >= 30:
                    host.dispatcher.interest(tab, 'watch', True, history=True)
                    renewed = now
                if now >= next_reconcile:
                    reference.refresh(deadline=deadline, progress=progress)
                    next_reconcile = time.monotonic() + 5
                with lock:
                    proof = latest[0] if latest else None
                if reference.matches(proof):
                    host.dispatcher.interest(tab, 'watch', False)
                    return time.monotonic() - host_started
                time.sleep(.25)
            raise RuntimeError(censored)

        facts['first_independently_matched_seconds'] = (validate_first_certificate() if serial_first
            else await_match('probe_product_reference_match_censored'))
        # Live sources keep changing: each cycle verifies the browser against one exactly matched
        # state, then requires a fresh exact re-match whose winners are still the ones rendered.
        for cycle in range(1, 4):
            expected = reference.expected()
            salt = uuid4().bytes
            facts['winner_run_digest'] = hashlib.sha256(salt + json.dumps(expected).encode()).hexdigest()
            facts['comparison'] = dict(epoch=True, complete_membership=True, all_root_revisions=True,
                full_identity_prompt_finish_order=True, full_count=len(expected), mini_count=len(expected[-3:]))
            facts['browser_cycles'] = cycle
            stage = 'shipped_browser'
            browser_seconds = min(120, max(1, int(deadline - time.monotonic())))
            completed = subprocess.run(['node', str(Path(__file__).with_name('probe_historical_web.cjs')),
                str(browser), str(output / f'browser-{cycle}')], input=json.dumps(dict(launch=host.browser_url(),
                    seconds=browser_seconds, private_history=True, history_rows=expected)),
                capture_output=True, text=True, timeout=browser_seconds + 5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            # The private mode returns fixed classifications, never raw exception text.
            browser_facts = json.loads(completed.stdout)
            facts['browser'] = browser_facts
            if completed.returncode != 0 or browser_facts.get('outcome') != 'PASS':
                raise RuntimeError('probe_private_history_browser_failed')
            stage = 'post_browser_revalidation'
            facts.setdefault('post_browser_rematch_seconds', []).append(
                await_match('probe_post_browser_rematch_censored'))
            if reference.expected() == expected:
                break
        else:
            raise RuntimeError('probe_history_winners_kept_changing')
        facts['post_browser_revalidated'] = True
        facts['outcome'] = 'PASS'
    except Exception as error:
        facts['failure'] = dict(stage=stage, type=type(error).__name__,
            code=str(error) if type(error) is RuntimeError and str(error).startswith('probe_') else None,
            source_code=str(error.code) if hasattr(error, 'code') else None)
    finally:
        if reference is not None:
            facts['reference'] = reference.summary()
        if host is not None:
            observations = ProbeObservations()
            observations.stage = stage
            try:
                with probe_lifecycle(host, [], observations):
                    pass
                facts['closure'] = dict(serving_thread_alive=host.thread.is_alive(),
                    live_thread_alive=host.live.thread.is_alive(), parked_children=len(host.jobs._parked))
            except Exception as error:
                facts['outcome'] = 'INCONCLUSIVE'
                facts['cleanup_error'] = type(error).__name__
        if source is not None:
            try:
                source.close_reads()
                facts['reference_reader_closed'] = True
            except Exception as error:
                facts['outcome'] = 'INCONCLUSIVE'
                facts['reference_cleanup_error'] = type(error).__name__
        facts['elapsed_seconds'] = time.monotonic() - started
        facts['live_publications'] = len(publications)
        facts['max_live_publication_gap_seconds'] = max((b-a for a,b in zip(publications, publications[1:])), default=None)
        (output / 'result.json').write_text(json.dumps(facts, indent=2), encoding='utf-8')
        print(json.dumps(facts), flush=True)
    return facts['outcome'] == 'PASS'
