"""Real disposable SQLite connections with deterministic setup/transaction faults."""
from __future__ import annotations

import sqlite3
from unittest.mock import patch


class SQLiteFaults:
    def __init__(self, database):
        self.database = database
        self.phase = ""
        self.error = sqlite3.OperationalError("private path/token must never be logged")
        self.opened = self.closed = self.rollbacks = self.failures = 0

    def install(self):
        connect = sqlite3.connect
        owner = self

        class Connection(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                phase = "pragma" if sql == "PRAGMA synchronous=NORMAL" else (
                    "write" if sql.lstrip().startswith("INSERT") else
                    "read" if sql.lstrip().startswith("SELECT") else "")
                if phase and owner.phase == phase:
                    owner.failures += 1
                    raise owner.error.with_traceback(None)
                return super().execute(sql, *args, **kwargs)

            def commit(self):
                if owner.phase == "commit":
                    owner.failures += 1
                    raise owner.error.with_traceback(None)
                return super().commit()

            def rollback(self):
                owner.rollbacks += 1
                return super().rollback()

            def close(self):
                owner.closed += 1
                return super().close()

        def open_connection(path, *args, **kwargs):
            if str(path) == str(self.database.paths.database):
                kwargs["factory"] = Connection
                self.opened += 1
            return connect(path, *args, **kwargs)

        return patch("src.cache.database.sqlite3.connect", open_connection)
