"""One persistent synthetic V2 identity, equal retained cache, fresh normal hosts.

The preparation and both measured arms use the existing full-host browser journey.
No report, reader, HTTP pool or browser state survives host closure. This is a
candidate window comparison, not B0/B1/B2 or whole-FR acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
from threading import Timer

import benchmark_web_runtime as runtime
from historical_web_retention import CacheSeed


def registration_identity(product_data):
    path = product_data / 'state/opencode/service.json'
    marker = path.stat()
    return (path.resolve(), marker.st_ino, marker.st_size, marker.st_mtime_ns,
        marker.st_ctime_ns, path.read_bytes())


def run_pair(args):
    evidence = args.run_root.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    product_data = evidence / 'product'
    source = runtime.start_source(args)
    timer = Timer(3 * (args.seconds + 40), source.kill)
    timer.start()
    result = dict(kind='retained_cache_fresh_host_window_comparison', arms=[],
        limitation='Controlled candidate pair only; no native OS proof, real-source oracle or FR acceptance.',
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        seed_support_sha256=hashlib.sha256((runtime.FIXTURES / 'historical_web_retention.py').read_bytes()).hexdigest())
    try:
        wire = json.loads(source.stdout.readline())
        common = dict(vars(args), diagnostic_stacks=False, card_timeline=False, completion_refill='on',
            sampling_catalog_observer=args.sparse_stale)
        preparation = argparse.Namespace(**{**common, 'run_root':evidence / 'preparation',
            'sample_window':1, 'cache_condition':'untimed-normal-preparation'})
        runtime.run(preparation, fixture=(source, wire), product_data=product_data, emit=False)
        identity = registration_identity(product_data)
        seed = CacheSeed(product_data, evidence / 'seed')
        result['seed'] = seed.capture()
        if args.sparse_stale:
            source.stdin.write('{"command":"sparse-stale"}\n')
            source.stdin.flush()
            result['pre_arm_fixed_change'] = json.loads(source.stdout.readline())
        for ordinal, window in enumerate(args.order, 1):
            restored = seed.restore()
            if registration_identity(product_data) != identity or source.poll() is not None:
                raise RuntimeError('fixture_retained_identity_changed')
            arm_path = evidence / f'arm-{ordinal}-window-{window}'
            arm = argparse.Namespace(**{**common, 'run_root':arm_path, 'sample_window':window,
                'cache_condition':'retained-cache-fresh-host'})
            outcome = runtime.run(arm, fixture=(source, wire), product_data=product_data, emit=False)
            if registration_identity(product_data) != identity or source.poll() is not None:
                raise RuntimeError('fixture_retained_identity_changed')
            result['arms'].append(dict(ordinal=ordinal, window=window, evidence=arm_path.name,
                initial_cache=restored, models_seconds=outcome['routes'][0]['seconds'],
                host=outcome['host'], source=outcome['source'], semantic_checks=outcome['semantic_checks'],
                reports=[report for process in outcome['imports'] for report in process.get('reports', ())]))
        result.update(outcome='PASS', same_source_process=True, same_registration_path_and_marker=True,
            same_absolute_cache_location=True, equal_restored_seed=True,
            fresh_host_and_browser_per_arm=True, preparation_traffic_excluded=True)
    except BaseException as error:
        result.update(outcome='FAIL', error=type(error).__name__)
        raise
    finally:
        try:
            stdout, stderr = runtime.stop_owned(source, 10)
            (evidence / 'source-stderr.txt').write_text(stderr, encoding='utf-8')
            if stdout.strip():
                result['source_lifetime'] = json.loads(stdout.strip().splitlines()[-1])
            result['source_exit'] = source.returncode
        finally:
            timer.cancel()
            timer.join()
            (evidence / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(dict(outcome=result['outcome'],
            arms=[dict(window=arm['window'], models_seconds=arm['models_seconds']) for arm in result['arms']],
            source_exit=result.get('source_exit'))), flush=True)
    if result['source_exit'] != 0 or result.get('source_lifetime', {}).get('server_thread_alive', True):
        raise RuntimeError('fixture_retained_source_teardown_failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product-root', type=Path, required=True)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--roots', type=int, default=550)
    parser.add_argument('--seconds', type=int, default=120)
    parser.add_argument('--latency-ms', type=float, default=0)
    parser.add_argument('--asof', type=int)
    parser.add_argument('--activity-pattern', choices=('recent-metadata', 'cutoff-effective'), default='recent-metadata')
    parser.add_argument('--order', type=int, nargs=2, choices=(1, 2), default=(1, 2))
    parser.add_argument('--sparse-stale', action='store_true', help='Exactly three fixed pre-arm changes; not concurrent churn')
    args = parser.parse_args()
    if set(args.order) != {1, 2} or not 50 <= args.roots <= 3000 or not 10 <= args.seconds <= 1200:
        parser.error('one arm per window, 50..3000 roots and 10..1200 seconds required')
    run_pair(args)


if __name__ == '__main__':
    main()
