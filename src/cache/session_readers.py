"""Reusable readers for one-statement Sessions snapshots."""
from collections import deque
from contextlib import contextmanager


class SessionReaders:
    def __init__(self, open_reader, *, retained=4):
        self.open_reader = open_reader
        self.retained = retained
        self.idle = deque()

    @contextmanager
    def borrow(self):
        # Never wait for a reader in use, let alone for the archive writer.
        try:
            connection = self.idle.pop()
        except IndexError:
            connection = self.open_reader()
        try:
            yield connection
        except BaseException:
            connection.close()
            raise
        else:
            if connection.in_transaction:
                connection.close()
                return
            self.idle.append(connection)
            # Reclaim excess without closing a connection another caller took.
            if len(self.idle) > self.retained:
                try:
                    excess = self.idle.popleft()
                except IndexError:
                    return
                excess.close()

    def close(self):
        # The host drains HTTP before closing idle readers, then the writer.
        while self.idle:
            self.idle.pop().close()
