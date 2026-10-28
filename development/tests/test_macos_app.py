"""Local applet cache/quoting/failure contracts with a fake compiler, never UI."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.web import macos_app
from src.web.change_guard import SourceGuard
from src.web.instance_state import InstanceStore
from src.web.process_identity import InstanceConflict

ROOT = Path(__file__).resolve().parents[2]


class MacAppTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        # Fingerprint metadata is synthetic here. Python 3.11 may implement OS
        # discovery via subprocess.run, which these compiler tests replace.
        for name, value in (("mac_ver", ("test-macos", ("", "", ""), "")),
                            ("release", "test-kernel"), ("machine", "test-arch")):
            metadata = patch.object(macos_app.platform, name, return_value=value)
            metadata.start()
            self.addCleanup(metadata.stop)
        self.root = self.base / "clone space ü ' quote"
        self.root.mkdir()
        for name in macos_app.SOURCES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        self.store = InstanceStore(self.root, data_home=self.base / "state")

    def compile(self, arguments, **options):
        app = Path(arguments[2])
        (app / "Contents/MacOS").mkdir(parents=True)
        executable = app / "Contents/MacOS/applet"
        executable.write_bytes(b"synthetic compiled fixture; never executed")
        executable.chmod(0o700)
        (app / "Contents/Info.plist").write_text("synthetic plist")
        self.assertEqual(arguments[:2], ["/usr/bin/osacompile", "-o"])
        self.assertIn("--launch-macos", Path(arguments[3]).read_text())
        self.assertEqual(options["timeout"], 30)
        self.assertNotIn("shell", options)
        return Mock(returncode=0)

    def test_compile_cached_reuse_source_os_and_python_rebuild_outside_checkout(self):
        with patch.object(macos_app.subprocess, "run", side_effect=self.compile) as compiler, \
                contextlib.redirect_stdout(io.StringIO()):
            first = macos_app.prepare_app(self.root, self.store)
            self.assertEqual(first, macos_app.prepare_app(self.root, self.store))
            self.assertEqual(compiler.call_count, 1)
            self.assertTrue(first.is_relative_to(self.store.directory))
            self.assertFalse(first.is_relative_to(self.root))
            source = self.root / "src/web/native_macos.py"
            source.write_text(source.read_text() + "\n# changed\n")
            changed = macos_app.prepare_app(self.root, self.store)
            self.assertNotEqual(first, changed)
            with patch.object(macos_app.platform, "release", return_value="different-os"):
                other_os = macos_app.prepare_app(self.root, self.store)
            self.assertNotEqual(changed, other_os)
            with patch.object(macos_app.sys, "executable", str(self.base / "other python")):
                other_python = macos_app.prepare_app(self.root, self.store)
            self.assertNotEqual(changed, other_python)
        self.assertEqual(compiler.call_count, 4)
        self.assertEqual(list(self.store.directory.glob("finder-build-*")), [])

    def test_cache_corruption_is_refused_not_recompiled_or_overwritten(self):
        with patch.object(macos_app.subprocess, "run", side_effect=self.compile) as compiler, \
                contextlib.redirect_stdout(io.StringIO()):
            app = macos_app.prepare_app(self.root, self.store)
            executable = app / "Contents/MacOS/applet"
            executable.write_bytes(b"tampered")
            with self.assertRaisesRegex(InstanceConflict, "app_preparation_failed"):
                macos_app.prepare_app(self.root, self.store)
        self.assertEqual(compiler.call_count, 1)
        self.assertEqual(executable.read_bytes(), b"tampered")

    def test_hyphenated_launcher_name_and_bytes_invalidate_finder_cache(self):
        launcher = "macos/Beta/Cost-Guard-Web.command"
        self.assertIn(launcher, macos_app.SOURCES)
        before = macos_app.fingerprint(self.root)
        source = self.root / launcher
        source.write_bytes(source.read_bytes() + b"\n# changed launcher\n")
        self.assertNotEqual(before, macos_app.fingerprint(self.root))
        # Identical content at another basename still gives a different identity.
        renamed = source.with_name("renamed.command")
        source.rename(renamed)
        changed = tuple("macos/Beta/renamed.command" if name == launcher else name
                        for name in macos_app.SOURCES)
        with patch.object(macos_app, "SOURCES", changed):
            renamed_key = macos_app.fingerprint(self.root)
        renamed.rename(source)
        self.assertNotEqual(renamed_key, macos_app.fingerprint(self.root))

    def test_runtime_guard_observes_applescript_but_not_external_generated_cache(self):
        guard = SourceGuard(self.root, interval=0)
        (self.store.directory / "unrelated-cache").write_text("local data")
        self.assertEqual(guard.check(), "unchanged")
        source = self.root / "macos/Beta/launcher.applescript"
        source.write_text(source.read_text() + "\n-- changed\n")
        self.assertEqual(guard.check(), "source_changed")

    def test_failed_compile_and_timeout_remove_partial_build(self):
        for result in (Mock(returncode=1), subprocess.TimeoutExpired("osacompile", 30)):
            with self.subTest(result=result), patch.object(macos_app.subprocess, "run") as compiler, \
                    contextlib.redirect_stdout(io.StringIO()):
                if isinstance(result, Exception):
                    compiler.side_effect = result
                else:
                    compiler.return_value = result
                with self.assertRaisesRegex(InstanceConflict, "app_preparation_failed"):
                    macos_app.prepare_app(self.root, self.store)
                self.assertEqual(list(self.store.directory.glob("finder-*")), [])

    def test_success_exit_without_actual_applet_is_not_success(self):
        with patch.object(macos_app.subprocess, "run", return_value=Mock(returncode=0)), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises((InstanceConflict, FileNotFoundError)):
                macos_app.prepare_app(self.root, self.store)
        self.assertEqual(list(self.store.directory.glob("finder-*")), [])

    def test_source_changed_during_compile_does_not_publish_mismatched_cache(self):
        def compile_and_change(arguments, **options):
            result = self.compile(arguments, **options)
            source = self.root / "src/web/native_macos.py"
            source.write_text(source.read_text() + "\n# changed while building\n")
            return result
        with patch.object(macos_app.subprocess, "run", side_effect=compile_and_change), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(InstanceConflict, "app_preparation_failed"):
                macos_app.prepare_app(self.root, self.store)
        self.assertEqual(list(self.store.directory.glob("finder-*")), [])

    def test_shell_and_applescript_quoting_preserves_arbitrary_path_as_data(self):
        python = '/synthetic/python space/ü"quote\\path'
        with patch.object(macos_app.sys, "executable", python):
            source = macos_app.app_source(self.root)
        # Decode just the AppleScript literal, then POSIX shell arguments, without execution.
        literal = source.split('do shell script "', 1)[1].split('"\n', 1)[0]
        command = json.loads('"' + literal + '"')
        self.assertEqual(macos_app.shlex.split(command),
                         [python, str(self.root / "cost-guard-web.py"), "--launch-macos"])
        self.assertNotIn("{{LAUNCH_COMMAND}}", source)
        self.assertIn("errorNumber is 4", source)

    def test_linked_cache_destination_is_refused(self):
        key = macos_app.fingerprint(self.root)
        destination = self.store.directory / ("finder-" + key)
        foreign = self.base / "foreign"
        foreign.mkdir()
        try:
            destination.symlink_to(foreign, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink privilege unavailable")
        with patch.object(macos_app.subprocess, "run") as compiler:
            with self.assertRaises(InstanceConflict):
                macos_app.prepare_app(self.root, self.store)
        compiler.assert_not_called()
        self.assertEqual(list(foreign.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
