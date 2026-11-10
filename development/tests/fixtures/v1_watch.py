"""Read-only V1 acquisition over safely synthesized, independently writable SQLite."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from threading import Event
from unittest.mock import Mock, patch

from development.tests.fixtures.opencode_v1_database import create_v1_database
from development.tests.fixtures.watch_runtime import make_service
from src.sources.opencode_v1 import OpenCodeV1Source
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.selection import SourceSelector
from src.watch.acquisition import LiveAcquisition
from src.watch.coordinator import WatchCoordinator
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.source_startup import SourceStartup


class V1Watch:
    def __init__(self, root, *, mode="auto", plugins=True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "synthetic.db"
        self.now = 20_000
        self.serial = 0
        create_v1_database(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            user = {"role": "user", "time": {"created": 10_000}, "agent": "build"}
            assistant = {"role": "assistant", "time": {"created": 11_000}, "parentID": "live-user",
                "providerID": "github-copilot", "modelID": "gpt-test", "agent": "build"}
            for identity, at, data in (("live-user", 10_000, user), ("live-assistant", 11_000, assistant)):
                db.execute("INSERT INTO message VALUES(?,?,?,?,?)", (identity, "ses_root", at, at, json.dumps(data)))
            parts = [("live-text", "live-user", {"type": "text", "text": "Synthetic active prompt"})]
            if plugins:
                for index, (tool, status) in enumerate((("custom_lookup", "completed"),
                        ("custom_lookup", "completed"), ("skill", "completed"),
                        ("custom_failure", "error"), ("custom_pending", "pending"),
                        ("custom_running", "running"))):
                    state = {"status": status, "input": {"name": "fixture-skill"},
                        "time": {"start": 12_000}, "metadata": {"syntheticPlugin": True}}
                    if status in {"completed", "error"}:
                        state.update(output="synthetic", error="synthetic failure" if status == "error" else "",
                            time={"start": 12_000, "end": 13_000})
                    parts.append((f"plugin-{index}", "live-assistant", {"type": "tool", "tool": tool,
                        "callID": f"call-{index}", "state": state}))
                parts.append(("plugin-opaque", "live-assistant", {"type": "plugin-unknown", "metadata": {"fixture": True}}))
                parts.append(("plugin-copy", "live-assistant", parts[1][2]))  # Same physical callID, not another call.
            for identity, message, data in parts:
                db.execute("INSERT INTO part VALUES(?,?,?,?,?,?)", (identity, message, "ses_root", 12_000, 12_000, json.dumps(data)))
            db.execute("UPDATE session SET time_updated=15000 WHERE id='ses_root'")
            db.commit()
        self.cli_selection = self.selector().select(mode)
        self.startup = SourceStartup(self.root, Mock(), Event())
        with patch("src.web.source_startup.load_configuration", return_value=Mock(values={"openCode": {"source": mode}})), \
                patch("src.web.source_startup.SourceSelector", return_value=self.selector()), \
                patch("src.web.source_startup.wake_cli_service") as wake:
            self.web_selection = self.startup.prepare()
            wake.assert_not_called()
        config, _, service, _ = make_service(self.root / "cli", self.cli_selection.source, now_ms=self.now)
        self.cli = WatchCoordinator(selection=self.cli_selection, report_service=service,
            config=config, clock_ms=lambda: self.now, record_observations=False)
        config, _, service, _ = make_service(self.root / "web", self.web_selection.source, now_ms=self.now)
        self.web = WebWatchCoordinator(selection=self.web_selection, report_service=service,
            config=config, service_factory=self.service, clock_ms=lambda: self.now, record_observations=False)
        self.driver = LiveAcquisition(self.web, monotonic=lambda: self.now / 1000)

    def selector(self):
        return SourceSelector(inspect_migration_gap=False,
            v1_factory=lambda: OpenCodeV1Source(self.path),
            v2_factory=lambda: OpenCodeV2Source(self.root / "absent-registration.json"))

    def service(self, now):
        self.serial += 1
        return make_service(self.root / f"worker-{self.serial}", OpenCodeV1Source(self.path), now_ms=now)[2]

    def phase(self, phase):
        self.now += 10_000
        with closing(sqlite3.connect(self.path)) as db:
            data = json.loads(db.execute("SELECT data FROM message WHERE id='live-assistant'").fetchone()[0])
            if phase != "running":
                data["time"]["completed"] = self.now - 1000
                data["finish"] = "stop" if phase == "complete" else "error"
                data["tokens"] = {"input": 1000, "output": 12, "cache": {"read": 100}}
                if phase in {"cancelled", "error"}:
                    data["error"] = {"name": "MessageAbortedError" if phase == "cancelled" else "ProviderError"}
            db.execute("UPDATE message SET data=?,time_updated=? WHERE id='live-assistant'", (json.dumps(data), self.now))
            for identity, raw in db.execute("SELECT id,data FROM part WHERE message_id='live-assistant'").fetchall():
                part = json.loads(raw)
                if part.get("type") == "tool" and part["state"]["status"] in {"pending", "running"}:
                    part["state"].update(status="completed", output="synthetic", time={"start": 12_000, "end": self.now - 1000})
                    db.execute("UPDATE part SET data=?,time_updated=? WHERE id=?", (json.dumps(part), self.now, identity))
            db.execute("UPDATE session SET time_updated=? WHERE id='ses_root'", (self.now,))
            db.commit()

    def settle(self):
        """Wait on actual bounded card futures; never replace Web with the CLI owner."""
        for _ in range(8):
            for future in tuple(self.web.card_workers.jobs.values()):
                future.result(timeout=5)
            self.web.service_completed()
        return self.web.status_projection()

    def close(self):
        self.cli.close()
        self.driver.close()
