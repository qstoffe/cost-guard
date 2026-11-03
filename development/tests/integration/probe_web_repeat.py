"""Explicit finite synthetic repetition; no real providers, UI or model calls."""
import argparse
import json
import multiprocessing
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from development.tests.fixtures.web_lifecycle import competing_work, run_cycle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycles', type=int, default=10)
    parser.add_argument('--competing', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.cycles <= 20:
        parser.error('cycles must be between 1 and 20')
    context = multiprocessing.get_context('spawn')
    stop = context.Event()
    load = context.Process(target=competing_work, args=(stop,)) if args.competing else None
    started = time.monotonic()
    try:
        if load:
            load.start()
        for index in range(args.cycles):
            print(json.dumps(dict(cycle=index + 1, **run_cycle(competing=args.competing))), flush=True)
    finally:
        if load:
            stop.set()
            load.join(2)
            if load.is_alive():
                load.terminate()
                load.join(2)
            assert not load.is_alive()
            load.close()
    print(json.dumps(dict(status='PASS', cycles=args.cycles, competing=args.competing,
        seconds=round(time.monotonic() - started, 3))), flush=True)


if __name__ == '__main__':
    main()
