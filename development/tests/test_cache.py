from __future__ import annotations

import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from src.cache import CACHE_FILENAME, CacheDatabase, CacheRepository


class CacheFoundationTests(unittest.TestCase):
    def test_cache_is_created_on_demand_and_can_be_rebuilt_after_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = CacheDatabase(root)
            self.assertFalse((root / "cache").exists())
            path = db.initialize()
            self.assertEqual(CACHE_FILENAME, path.name)
            repo = CacheRepository(db)
            repo.put("test", "one", {"value": 1})
            self.assertEqual({"value": 1}, repo.get("test", "one").payload)

            shutil.rmtree(root / "cache")
            rebuilt = CacheDatabase(root)
            rebuilt.initialize()
            self.assertIsNone(CacheRepository(rebuilt).get("test", "one"))

    def test_cache_generations_coexist_without_migration_or_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = CacheDatabase(root, generation=0)
            current = CacheDatabase(root, generation=1)
            old_path = old.initialize()
            current_path = current.initialize()
            self.assertTrue(old_path.exists())
            self.assertTrue(current_path.exists())
            self.assertNotEqual(old_path, current_path)

    def test_wal_and_busy_timeout_are_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = CacheDatabase(Path(tmp))
            db.initialize()
            with db.connect() as connection:
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
            self.assertEqual("wal", journal_mode.lower())
            self.assertGreaterEqual(busy_timeout, 5000)

    def test_concurrent_writers_and_reader_share_cache_without_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = CacheDatabase(root)
            db.initialize()
            errors: list[BaseException] = []
            start = threading.Barrier(5)

            def writer(worker: int) -> None:
                try:
                    repo = CacheRepository(CacheDatabase(root))
                    start.wait(timeout=5)
                    for index in range(40):
                        repo.put("concurrency", f"{worker}:{index}", {"worker": worker, "index": index})
                except BaseException as exc:  # surfaced in parent test
                    errors.append(exc)

            def reader() -> None:
                try:
                    repo = CacheRepository(CacheDatabase(root))
                    start.wait(timeout=5)
                    for _ in range(100):
                        repo.get("concurrency", "0:0")
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=writer, args=(worker,)) for worker in range(4)]
            threads.append(threading.Thread(target=reader))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertFalse(any(thread.is_alive() for thread in threads), "cache concurrency test timed out")
            self.assertEqual([], errors)

            repo = CacheRepository(db)
            for worker in range(4):
                for index in range(40):
                    entry = repo.get("concurrency", f"{worker}:{index}")
                    self.assertIsNotNone(entry)
                    self.assertEqual(worker, entry.payload["worker"])


if __name__ == "__main__":
    unittest.main()
