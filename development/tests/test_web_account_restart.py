"""Current account authorization is produced off both held acquisition lanes."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from development.tests.fixtures.account_workers import wait_for
from development.tests.fixtures.watch_runtime import make_service
from development.tests.integration.ci_cached_cold_views import _populate
from development.tests.test_display_account_history import observation
from src.accounts.claude_code import ClaudeCodeAccountProvider
from src.accounts.claude_transport import ClaudeUsageResult
from src.accounts.openai_subscription import OpenAIAccountProvider
from src.analysis.cache import dependency_signature
from src.application.live import LiveRuntime
from src.cache.display_history import SessionChange, SessionFact
from src.cache.display_requests import RequestRoster
from src.domain import AccountRef, AccountSnapshot
from src.sources.opencode_v1 import OpenCodeV1Source
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.display_archive import DisplayArchive


def claude_identity(email, config):
    principal = hashlib.sha256((email + "\0fixture-org").encode()).hexdigest()
    locator = hashlib.sha256(str(config).encode()).hexdigest()
    return AccountRef("claude-cli:" + locator, "claude-code", account_id=principal, source_account="current-login")


class WebAccountRestartTests(unittest.TestCase):
    def test_qualified_history_restores_while_history_and_native_quota_are_held(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "source.db"
            now = int(time.time() * 1000)
            _populate(path, now)
            profile = root / "selected-claude"
            source = OpenCodeV1Source(path)
            config, selection, service, _ = make_service(root, source, now_ms=now, async_accounts=True)
            account = AccountSnapshot(claude_identity("first@example.invalid", profile), now, "Claude Code", plan="Pro")
            mount = SimpleNamespace(error=None, terminal=False, coordinator=SimpleNamespace(report_service=service))
            first = DisplayArchive(root, lambda *_: None, accounts_enabled=True)
            try:
                self.assertTrue(first.initialize())
                first.observe(mount, before_tick=True)
                saved_digest = bytes.fromhex(dependency_signature(account.key))
                request = observation(1, now - 60_000, digest=saved_digest, provider="claude-agent",
                                      costs=("25", "0", "0", "0"), root="saved")
                first.history.commit_sessions(first.views.source, (
                    SessionChange(SessionFact("saved", "r1", "saved"), None, previous_progress=0,
                                  request_roster=RequestRoster("fixture", (request,), ())),
                ))
                first.accounts.offer((SimpleNamespace(account=account, label="Claude Code Pro"),), verified=True)
                for _ in range(64):
                    first.accounts.advance(now, active=lambda: True)
                    saved = first.accounts.snapshot("7-days", now)
                    if saved["revision"]:
                        break
                self.assertEqual(saved["revision"], now)
            finally:
                first.close()

            history_started, quota_started, restore, release_history, release_quota = (Event() for _ in range(5))
            switch, replaced, withheld = Event(), Event(), Event()
            replacement = claude_identity("second@example.invalid", profile)
            replacement_digest = dependency_signature(replacement.key)
            auth_file = root / "fixture-auth.json"
            auth_file.write_text("{}", encoding="utf-8")

            def auth_status():
                return {"loggedIn": True, "apiProvider": "firstParty", "authMethod": "claude.ai",
                        "subscriptionType": "pro",
                        "email": "second@example.invalid" if switch.is_set() else "first@example.invalid",
                        "orgId": "fixture-org", "orgName": "Fixture Org", "configDirectory": str(profile)}

            def quota():
                first = not switch.is_set()
                if first:
                    quota_started.set()
                    release_quota.wait(16)
                return ClaudeUsageResult(
                    account={"email": "first@example.invalid" if first else "second@example.invalid",
                             "organization": "Fixture Org", "apiProvider": "firstParty"},
                    usage={"rate_limits_available": True, "rate_limits": {
                        "five_hour": {"utilization": 25, "resets_at": "2026-11-23T17:00:00Z"},
                        "seven_day": {"utilization": 50, "resets_at": "2026-11-27T17:00:00Z"},
                    }},
                )

            service.account_providers = (
                ClaudeCodeAccountProvider(auth_reader=auth_status, usage_reader=quota),
                OpenAIAccountProvider(auth_json_path=str(auth_file), usage_get=self.unexpected_quota_call),
            )

            def publish(kind, value):
                if kind != "accounts-cache" or archive.views is None:
                    return
                if value["scope"] == archive.views.binding:
                    if replaced.is_set():
                        withheld.set()
                    return
                snapshot = archive.accounts.snapshot("7-days", now)
                if snapshot and snapshot["series"][0]["id"] == replacement_digest:
                    replaced.set()
                elif snapshot and snapshot["revision"] == now:
                    restore.set()

            def held_history():
                history_started.set()
                if not release_history.wait(18):
                    raise AssertionError("fixture failed to release the source")
                return None

            archive = DisplayArchive(root, publish, accounts_enabled=True)
            coordinator = WebWatchCoordinator(selection=selection, report_service=service, config=config,
                                              service_factory=self.unexpected_history_job)
            driver = LiveAcquisition(coordinator)
            live = LiveRuntime(lambda: driver, lambda *_: None, on_failure=lambda _: None, display_archive=archive)
            with patch.object(driver, "tick", side_effect=held_history):
                try:
                    self.assertTrue(archive.initialize())
                    live.start()
                    self.assertTrue(history_started.wait(2), "source hold was not entered")
                    self.assertTrue(restore.wait(2), "Accounts did not receive current identity while source was held")
                    self.assertTrue(quota_started.wait(2), "provider quota hold was not entered")
                    resumed = archive.accounts.snapshot("7-days", now)
                    self.assertEqual(resumed["revision"], now)
                    self.assertEqual(resumed["view"], saved["view"])
                    self.assertEqual(resumed["series"], saved["series"])
                    self.assertFalse(release_quota.is_set())

                    switch.set()
                    self.assertTrue(replaced.wait(7), "same-profile replacement did not revoke old chart")
                    current = archive.accounts.snapshot("7-days", now)
                    self.assertNotEqual(resumed["scope"], current["scope"])
                    self.assertEqual([replacement_digest], [item["id"] for item in current["series"]])
                    self.assertIsNone(current["view"])

                    release_quota.set()
                    updates = []

                    def quota_completed():
                        value = service.poll_account_refresh()
                        if value is not None:
                            updates.append(value)
                        return bool(updates)

                    wait_for(quota_completed)
                    update, = updates
                    self.assertEqual([replacement.key], [item.key for item in update.snapshots])
                    self.assertEqual("available", update.snapshots[0].availability)
                    self.assertIn(replacement.key, dict(update.observed_at_ms))
                    self.assertEqual(current, archive.accounts.snapshot("7-days", now))

                    # This is present, but intentionally unusable and omitted by
                    # credential normalization. It cannot count as an absent peer.
                    auth_file.write_text(json.dumps({"openai": {"type": "unrecognized"}}), encoding="utf-8")
                    self.assertTrue(withheld.wait(7), "unqualified peer did not revoke the whole roster")
                    unqualified = archive.accounts.snapshot("7-days", now)
                    self.assertFalse(unqualified["ready"])
                    self.assertEqual((), unqualified["series"])
                    self.assertIsNone(unqualified["view"])
                finally:
                    live.stopping.set()
                    release_history.set()
                    release_quota.set()
                    live.close()
            self.assertIsNone(live.failure)

    def unexpected_history_job(self, *_args):
        self.fail("held source admitted a secondary history job")

    def unexpected_quota_call(self, *_args):
        self.fail("absent or unusable OpenAI peer issued a quota request")
