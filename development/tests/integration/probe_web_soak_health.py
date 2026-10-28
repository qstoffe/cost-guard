"""Bounded read-only shell-health timing beside an explicitly owned browser soak.

This does not authenticate, acquire source data or prove browser connectivity.
"""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--seconds', type=int, choices=range(10, 1801), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    url = urlsplit(args.origin)
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or
            url.path or url.query or url.fragment or url.username or url.password):
        parser.error('exact owned numeric-loopback origin required')
    started = time.monotonic()
    samples = []
    while True:
        before = time.monotonic()
        try:
            with urlopen(args.origin + '/health', timeout=5) as response:
                healthy = response.status == 200 and json.load(response) == {'http': 'ready'}
            samples.append(dict(at_ms=round((before - started) * 1000), healthy=healthy,
                                elapsed_ms=round((time.monotonic() - before) * 1000)))
        except Exception as error:
            samples.append(dict(at_ms=round((before - started) * 1000), healthy=False,
                                error_type=type(error).__name__))
        remaining = started + args.seconds - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(10, remaining))
    result = dict(seconds=round(time.monotonic() - started, 2), samples=samples,
                  healthy=all(sample['healthy'] for sample in samples))
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(seconds=result['seconds'], samples=len(samples), healthy=result['healthy'])))
    return 0 if result['healthy'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
