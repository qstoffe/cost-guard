"""The archive cannot be rebound from a client hint or a reused local path."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from src.sources.opencode_v1 import OpenCodeV1Source
from src.web.display_binding import selected_display_binding


class DisplayBindingTests(unittest.TestCase):
    def test_local_mutation_keeps_scope_but_replacing_same_path_does_not(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / "fixture"
            path.write_bytes(b"original")
            selected = SimpleNamespace(selected="v1", source=OpenCodeV1Source(path))
            initial = selected_display_binding(selected)

            path.write_bytes(b"more bytes in the same file")
            still_same = selected_display_binding(selected)
            replacement = directory / "replacement"
            replacement.write_bytes(b"separate fixture")
            replacement.replace(path)
            changed = selected_display_binding(selected)

        self.assertIsNotNone(initial)
        self.assertEqual(initial, still_same)
        self.assertIsNotNone(changed)
        self.assertNotEqual(initial.scope, changed.scope)

    def test_missing_local_binding_is_not_replaced_with_the_last_archive(self):
        with TemporaryDirectory() as tmp:
            source = OpenCodeV1Source(Path(tmp) / "missing")

            binding = selected_display_binding(SimpleNamespace(selected="v1", source=source))

        self.assertIsNone(binding)
