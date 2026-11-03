"""Own the isolated sources used by Web capture lanes, including stop races."""
from contextlib import contextmanager
from threading import Lock

from src.sources.errors import transport_failure


def cancel_source(source):
    cancel = getattr(source, 'cancel_reads', None)
    if callable(cancel):
        cancel()


class SourceReads:
    def __init__(self):
        self.lock = Lock()
        self.sources = set()
        self.stopping = False

    @contextmanager
    def using(self, source):
        with self.lock:
            stopped = self.stopping
            if not stopped:
                self.sources.add(source)
        try:
            if stopped:
                cancel_source(source)
                raise transport_failure(ConnectionAbortedError(), phase='shutdown')
            yield
        finally:
            with self.lock:
                self.sources.discard(source)
            close = getattr(source, 'close_reads', None)
            if callable(close):
                close()

    def cancel(self):
        with self.lock:
            self.stopping = True
            sources = tuple(self.sources)
        for source in sources:
            cancel_source(source)
