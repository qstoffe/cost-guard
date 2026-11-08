"""Exclusive source lifetimes for the existing bounded card-pool threads."""
from contextlib import contextmanager
from threading import Lock, get_ident

from src.sources.errors import transport_failure
from .source_reads import cancel_source


class CardReaders:
    def __init__(self, factory, *, limit=4):
        self.factory = factory
        self.limit = limit
        self.lock = Lock()
        self.sources = {}
        self.discarded = set()
        self.stopping = False

    @contextmanager
    def borrow(self):
        owner = get_ident()
        with self.lock:
            if self.stopping:
                raise transport_failure(ConnectionAbortedError(), phase='shutdown')
            source = self.sources.get(owner)
            if source is None:
                if len(self.sources) >= self.limit:
                    raise RuntimeError('card_reader_capacity_exceeded')
                # This factory constructs only: no probe/read before registration.
                source = self.factory()
                self.sources[owner] = source
        try:
            yield source
        except BaseException:
            self.discard(source)
            raise
        finally:
            with self.lock:
                retire = self.stopping or source in self.discarded
                if retire:
                    self.sources.pop(owner, None)
                    self.discarded.discard(source)
            if retire:
                try:
                    cancel_source(source)
                finally:
                    source.close_reads()

    def discard(self, source):
        # Member failures do not interrupt certified siblings in the same job.
        with self.lock:
            self.discarded.add(source)

    def cancel(self):
        with self.lock:
            self.stopping = True
            sources = tuple(self.sources.values())
        for source in sources:
            cancel_source(source)

    def close(self):
        """Called after the card executor has joined all owned reads."""
        self.cancel()
        with self.lock:
            sources = tuple(self.sources.values())
            self.sources.clear()
            self.discarded.clear()
        for source in sources:
            source.close_reads()
