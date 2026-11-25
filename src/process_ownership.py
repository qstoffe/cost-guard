"""Bind spawned work to its exact parent without relying on recyclable PIDs."""
import multiprocessing
from multiprocessing.connection import wait
import os
from threading import Event, Thread


def run_owned(target, endpoint, request):
    parent = multiprocessing.parent_process()
    if parent is None:
        raise RuntimeError('worker_parent_unavailable')
    finished = Event()

    def watch_parent():
        try:
            while not finished.is_set():
                if wait([parent.sentinel], timeout=0.25):
                    os._exit(1)
        except BaseException:
            os._exit(1)  # Lost ownership proof cannot mean keep running.

    monitor = Thread(target=watch_parent, name='cost-guard-worker-parent', daemon=True)
    monitor.start()
    try:
        target(endpoint, request)
    finally:
        finished.set()
        monitor.join(timeout=1)
