"""Live preview ordering under a large, cache-cold source roster."""
from types import SimpleNamespace
import unittest

from src.application.session_preview_order import preview_keys


class SessionPreviewOrderTests(unittest.TestCase):
    def test_observed_activity_beats_metadata_and_future_dates_are_unknown(self):
        activity = {"z": 100, "a": 100, "b": 110, "c": 100_000, "d": 120, "e": 10}
        rows = {"b": SimpleNamespace(last_activity_ms=90), "e": SimpleNamespace(last_activity_ms=105)}
        catalog = SimpleNamespace(rows=rows, _running=lambda key: key == "d", _activity_current=rows.__contains__,
            activity=activity, activity_index=tuple(sorted((at, key) for key, at in activity.items())),
            preview_roots=tuple(sorted((*activity, "missing"))))

        selected = preview_keys(catalog, {"a"}, 120, 5)

        self.assertEqual(("e", "z", "b", "c", "missing"), selected)

    def test_cache_cold_fifty_thousand_roots_only_visit_enough_indexed_candidates(self):
        total = 50_000
        inspected = []
        index = tuple((i + 1, str(i)) for i in range(total))

        def running(key):
            inspected.append(key)
            return key == "49998"

        catalog = SimpleNamespace(rows={}, _running=running, activity_index=index,
                                  _activity_current=lambda _: False)

        selected = preview_keys(catalog, {"49999"}, total, 5)

        self.assertEqual(("49997", "49996", "49995", "49994", "49993"), selected)
        self.assertEqual(["49998", *selected], inspected)
