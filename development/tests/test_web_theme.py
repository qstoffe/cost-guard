"""File-preserving Web preferences, CLI isolation and real HTTP security."""
import http.client
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.config import ConfigError, load_configuration
from src.web.change_guard import SourceGuard
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.web.settings import MAX_CONFIG_BYTES, SettingsError, WebSettings, replace_preference

ROOT = Path(__file__).resolve().parents[2]


class ThemeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # macOS exposes its temporary directory through the /var symlink.
        # Canonicalize the trusted fixture, not paths accepted by the write owner.
        self.root = Path(temporary.name).resolve()
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default-config.jsonc", self.root / "config/default-config.jsonc")
        self.settings = WebSettings(self.root)
        self.path = self.settings.path

    def test_defaults_missing_file_and_cli_configuration_stay_independent(self):
        before = load_configuration(self.root).values
        self.assertEqual({"theme": "classic", "ccostDisplayUnit": "credits"}, before["webSettings"])
        self.assertEqual(before["webSettings"], self.settings.read())
        self.assertFalse(self.path.exists())
        self.assertEqual({"theme": "web", "ccostDisplayUnit": "credits"}, self.settings.write("theme", "web"))
        after = load_configuration(self.root).values
        self.assertEqual(dict(before, webSettings={"theme": "web", "ccostDisplayUnit": "credits"}), after)
        self.assertEqual({"webSettings": {"theme": "web"}}, json.loads(self.path.read_bytes()))
        self.assertEqual(after["webSettings"], WebSettings(self.root).read())

    def test_legacy_precedence_and_independent_ccost_defaults_external_edits_and_relaunch(self):
        for overrides, expected in (
            ({"webTheme": "web", "ccostDisplayUnit": "usd"}, {"theme": "web", "ccostDisplayUnit": "credits"}),
            ({"webTheme": "web", "webSettings": {"ccostDisplayUnit": "usd"}}, {"theme": "web", "ccostDisplayUnit": "usd"}),
            ({"webTheme": "web", "webSettings": {"theme": "classic"}}, {"theme": "classic", "ccostDisplayUnit": "credits"}),
            ({"webTheme": "classic", "webSettings": {"theme": "web", "ccostDisplayUnit": "usd"}}, {"theme": "web", "ccostDisplayUnit": "usd"}),
        ):
            with self.subTest(overrides=overrides):
                self.path.write_text(json.dumps(overrides))
                self.assertEqual(expected, load_configuration(self.root).values["webSettings"])
                self.assertEqual(expected, self.settings.read())
                self.assertEqual(expected, WebSettings(self.root).read())
                self.assertEqual(overrides, json.loads(self.path.read_bytes()), "reads never migrate the file")
        self.settings.write("ccostDisplayUnit", "credits")
        saved = json.loads(self.path.read_bytes())
        saved["ccostDisplayUnit"] = "usd"
        self.path.write_text(json.dumps(saved))
        self.assertEqual("credits", self.settings.read()["ccostDisplayUnit"])
        self.assertEqual("usd", load_configuration(self.root).values["ccostDisplayUnit"])

    def test_round_trip_preserves_comments_nested_objects_order_and_cli_overrides(self):
        original = b'''// leading comment\r\n{\r\n  "timezone": "UTC", /* untouched */\r\n  "openCode": {"source": "v2"},\r\n  "colorScheme": "modus-operandi-tinted",\r\n  "colors": {"activeRunning": {"ansi256": 118}},\r\n  "copilotQuota": {"authJsonPath": "PRIVATE//file"},\r\n  "ccostDisplayUnit": "usd",\r\n  "webTheme": "web",\r\n  "webSettings": { /* group */ "theme" /* label */: "classic", "ccostDisplayUnit": "credits" } // final comment\r\n}\r\n'''
        self.path.write_bytes(original)
        before = load_configuration(self.root).values
        self.settings.write("theme", "web")
        self.assertEqual(original.replace(b': "classic"', b': "web"'), self.path.read_bytes())
        self.assertEqual(dict(before, webSettings={"theme": "web", "ccostDisplayUnit": "credits"}), load_configuration(self.root).values)
        self.settings.write("ccostDisplayUnit", "usd")
        self.assertEqual(original.replace(b': "classic"', b': "web"').replace(b': "credits"', b': "usd"'), self.path.read_bytes())
        self.settings.write("theme", "classic")
        self.settings.write("ccostDisplayUnit", "credits")
        self.assertEqual(original, self.path.read_bytes())

    def test_insertion_and_escaped_nested_keys_preserve_every_other_byte(self):
        for raw in (b'{}', b'{ /* stays */ }\n', b'{"timezone":"UTC"}',
                    b'{"openCode":{"source":"v2"},"timezone":"UTC"}\n'):
            with self.subTest(raw=raw):
                changed = replace_preference(raw, "theme", "web")
                self.assertEqual(raw, changed.replace(b'\n  "webSettings": {"theme": "web"}' + (b',' if b'"' in raw else b''), b''))
        raw = b'{"web\\u0053ettings":{"th\\u0065me":"classic","ccostDisplayUnit":"usd"}}'
        self.assertEqual(raw.replace(b'"classic"', b'"web"'), replace_preference(raw, "theme", "web"))
        for raw in (b'{"webSettings":{ /* keep */ }}', b'{"webSettings":{"theme":"web" /* keep */}}'):
            changed = replace_preference(raw, "ccostDisplayUnit", "usd")
            self.assertEqual(raw, changed.replace(b'\n    "ccostDisplayUnit": "usd"' + (b',' if b'"theme"' in raw else b''), b''))

    def test_invalid_or_ambiguous_config_is_never_rewritten_or_exposed(self):
        for raw in (b'{PRIVATE', b'[]', b'{"webTheme":"invalid"}',
                    b'{"webTheme":"web","webTheme":"classic"}',
                    b'{"unknown":"PRIVATE"}', b'{"openCode":{"source":"PRIVATE"}}',
                    b'{"webSettings":null}', b'{"webSettings":[]}',
                    b'{"webSettings":{"theme":"Web"}}', b'{"webSettings":{"ccostDisplayUnit":"USD"}}',
                    b'{"webSettings":{"theme":"web","theme":"classic"}}',
                    b'{"webSettings":{"other":"PRIVATE"}}',
                    b'{"timezone":"UTC" /* unclosed', b'{"watchDashboardMaxRows":' + b'9' * 400 + b'}'):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(SettingsError, "^settings_invalid_config$"):
                    self.settings.write("theme", "web")
                self.assertEqual(raw, self.path.read_bytes())
        for value in ("Web", "CLASSIC", "modus-operandi-tinted", None, True, [], {}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(SettingsError, "^invalid_request$"):
                    self.settings.write("theme", value)
        for value in ("USD", None, [], {}, True, "web"):
            with self.assertRaisesRegex(SettingsError, "^invalid_request$"):
                self.settings.write("ccostDisplayUnit", value)
        self.path.write_text('{"webTheme": "Web"}')
        with self.assertRaises(ConfigError):
            load_configuration(self.root)

    def test_readonly_oversize_links_and_failed_replace_leave_no_temporary_files(self):
        self.path.write_bytes(b'{}')
        self.path.chmod(stat.S_IREAD)
        try:
            with self.assertRaisesRegex(SettingsError, "settings_not_writable"):
                self.settings.write("theme", "web")
        finally:
            self.path.chmod(stat.S_IREAD | stat.S_IWRITE)
        self.path.write_bytes(b' ' * (MAX_CONFIG_BYTES + 1))
        with self.assertRaisesRegex(SettingsError, "settings_config_too_large"):
            self.settings.write("ccostDisplayUnit", "usd")
        self.path.write_bytes(b'{}')
        with patch("src.web.settings.os.replace", side_effect=PermissionError("PRIVATE path")):
            with self.assertRaisesRegex(SettingsError, "^settings_not_writable$"):
                self.settings.write("ccostDisplayUnit", "usd")
        self.assertEqual(b'{}', self.path.read_bytes())
        self.assertEqual([], list(self.path.parent.glob(".web-settings-*.tmp")))
        target = self.root / 'unrelated.jsonc'
        target.write_bytes(b'{}')
        self.path.unlink()
        os.link(target, self.path)
        with self.assertRaisesRegex(SettingsError, "settings_unsafe_path"):
            self.settings.write("ccostDisplayUnit", "usd")
        self.assertEqual(b'{}', target.read_bytes())

    def test_reparse_and_symlink_ancestors_are_rejected_before_read(self):
        import src.web.settings as module
        real = Path.lstat
        for hazard in (self.path.parent, self.root, self.root.parent):
            with self.subTest(hazard=hazard):
                def info(path, **kwargs):
                    value = real(path)
                    return Mock(st_mode=value.st_mode, st_file_attributes=0x400) if path == hazard else value
                with patch.object(Path, 'lstat', autospec=True) as lstat:
                    lstat.return_value = Mock(st_mode=stat.S_IFLNK, st_file_attributes=0)
                    with self.assertRaisesRegex(SettingsError, "settings_unsafe_path"):
                        module.safe_info(hazard)
                with patch.object(Path, "lstat", info):
                    with self.assertRaisesRegex(SettingsError, "settings_unsafe_path"):
                        self.settings.read()
                    with self.assertRaisesRegex(SettingsError, "settings_unsafe_path"):
                        self.settings.write("ccostDisplayUnit", "usd")
                self.assertFalse(self.path.exists())

    def test_concurrent_external_edit_and_stopping_are_not_overwritten(self):
        self.path.write_bytes(b'{}')
        real = self.settings._snapshot
        calls = 0
        def snapshot():
            nonlocal calls
            calls += 1
            if calls == 2:
                self.path.write_bytes(b'{"timezone":"UTC"}')
            return real()
        with patch.object(self.settings, '_snapshot', side_effect=snapshot):
            with self.assertRaisesRegex(SettingsError, "settings_conflict"):
                self.settings.write("ccostDisplayUnit", "usd")
        self.assertEqual(b'{"timezone":"UTC"}', self.path.read_bytes())
        self.assertEqual([], list(self.path.parent.glob(".web-settings-*.tmp")))
        with self.assertRaisesRegex(SettingsError, "instance_stopping"):
            self.settings.write("ccostDisplayUnit", "usd", allowed=lambda: False)
        self.assertEqual("credits", self.settings.read()["ccostDisplayUnit"])
        permission = iter((True, False))
        with self.assertRaisesRegex(SettingsError, "instance_stopping"):
            self.settings.write("ccostDisplayUnit", "usd", allowed=lambda: next(permission))
        self.assertEqual(b'{"timezone":"UTC"}', self.path.read_bytes())
        other_tab = WebSettings(self.root)
        other_tab.write("theme", "web")
        self.settings.write("ccostDisplayUnit", "usd")
        self.assertEqual({"theme": "web", "ccostDisplayUnit": "usd"}, other_tab.read())

    def test_source_guard_ignores_only_actual_user_override(self):
        guard = SourceGuard(self.root, interval=0)
        self.settings.write("theme", "web")
        self.settings.write("ccostDisplayUnit", "usd")
        self.assertEqual("unchanged", guard.check())

    @unittest.skipUnless(shutil.which("node"), "optional JavaScript runtime unavailable")
    def test_live_page_theme_state_machine(self):
        result = subprocess.run(["node", "development/tests/integration/web_theme.cjs"],
            cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_real_http_authentication_enum_preservation_errors_and_early_shell(self):
        host = WebHost(self.root, jobs=ReportJobs())
        host.guard.interval = 0
        host.guard.next_check = 0
        host.start()
        server = host.server
        cookie = csrf = None
        def request(path, value=None, **extra):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            headers = {"Origin": server.origin, "Content-Type": "application/json"}
            if cookie:
                headers.update(Cookie=cookie, **{"X-CG-CSRF": csrf})
            headers.update(extra)
            conn.request("GET" if value is None else "POST", path,
                None if value is None else json.dumps(value), headers)
            response = conn.getresponse()
            result = response.status, dict(response.getheaders()), response.read()
            conn.close()
            return result
        try:
            self.assertIn(b'data-theme="classic"', request('/')[2])
            self.assertFalse(self.path.exists())
            self.assertEqual(401, request('/api/settings')[0])
            self.assertEqual(401, request('/api/settings/theme', {"theme":"web"})[0])
            self.assertEqual(401, request('/api/settings/ccost', {"ccostDisplayUnit":"usd"})[0])
            _, headers, body = request('/api/bootstrap', {"credential":server.session.bootstrap()})
            cookie = headers['Set-Cookie'].split(';')[0]
            csrf = json.loads(body)['csrf']
            self.assertEqual({"webSettings":{"theme":"classic", "ccostDisplayUnit":"credits"}}, json.loads(request('/api/settings')[2]))
            for headers in ({"Origin":"https://foreign.invalid"}, {"X-CG-CSRF":""},
                            {"Content-Type":"text/plain"}, {"Host":"localhost"}):
                self.assertEqual(403, request('/api/settings/theme', {"theme":"web"}, **headers)[0])
                self.assertEqual(403, request('/api/settings/ccost', {"ccostDisplayUnit":"usd"}, **headers)[0])
            for value in ({}, {"theme":"web","path":"PRIVATE"}, {"theme":[]}, {"theme":"bad"}):
                self.assertEqual(400, request('/api/settings/theme', value)[0])
            self.assertFalse(self.path.exists())
            for value in ({}, {"theme":"web"}, {"ccostDisplayUnit":"usd","path":"PRIVATE"}, {"ccostDisplayUnit":[]}, {"ccostDisplayUnit":"bad"}):
                self.assertEqual(400, request('/api/settings/ccost', value)[0])
            self.assertEqual(200, request('/api/settings/theme', {"theme":"web"})[0])
            self.assertEqual(200, request('/api/settings/ccost', {"ccostDisplayUnit":"usd"})[0])
            self.assertIn(b'data-theme="web"', request('/')[2])
            self.assertEqual({"webSettings":{"theme":"web", "ccostDisplayUnit":"usd"}}, json.loads(request('/api/settings')[2]))
            self.assertFalse(host.stopping.is_set())
            self.assertEqual("unchanged", host.guard.check())
            self.path.chmod(stat.S_IREAD)
            try:
                status, _, body = request('/api/settings/ccost', {"ccostDisplayUnit":"credits"})
                self.assertEqual(503, status)
                self.assertEqual({"error":"settings_not_writable"}, json.loads(body))
            finally:
                self.path.chmod(stat.S_IREAD | stat.S_IWRITE)
            with patch.object(server.settings, '_commit', side_effect=SettingsError('settings_conflict')):
                self.assertEqual(409, request('/api/settings/theme', {"theme":"classic"})[0])
            self.path.write_bytes(b'{PRIVATE secret/path')
            status, _, body = request('/api/settings/ccost', {"ccostDisplayUnit":"credits"})
            self.assertEqual(503, status)
            self.assertEqual({"error":"settings_invalid_config"}, json.loads(body))
            self.assertFalse(host.jobs._jobs)
        finally:
            host.close()
            self.assertFalse(host.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
