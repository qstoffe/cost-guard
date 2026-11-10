"""Owned synthetic SQLite + genuine host/Live/HTTP/SSE; private stdio control only."""
import json
from pathlib import Path
import shutil
import sys
from threading import Timer

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.v1_watch import V1Watch
from development.tests.fixtures.report_loading import LoadingJobs
from src.web.host import WebHost


def main():
    root = Path(sys.argv[1])
    (root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "config/default-config.jsonc", root / "config/default-config.jsonc")
    scenario = V1Watch(root / "source", mode=sys.argv[2] if len(sys.argv) > 2 else "auto")
    host = WebHost(root, jobs=LoadingJobs(), live_factory=lambda: scenario.driver)
    host.benchmark.next_due = float("inf")
    gate = ["pending"]

    def publish(kind, value):
        value = value.to_json()
        # Fault-injection ONLY after the real owner prepared its publication.
        # Baseline/run uses the unmodified selected-V1 source contract.
        if gate[0] == "pending":
            value.update(state="starting", source_generation="unknown", view=None)
        elif gate[0] == "failed":
            value.update(state="failed", source_generation="unknown", view=None)
        elif gate[0].startswith("wire-"):
            value["source_generation"] = gate[0].removeprefix("wire-")
        host.events.publish(kind, value)

    host.live.publish = publish
    timer = Timer(240, host.stop)
    try:
        host.start()
        host.publish_ready()
        timer.start()
        print(json.dumps({"url": host.browser_url()}), flush=True)
        for line in sys.stdin:
            command = json.loads(line)["command"]
            if command == "stop":
                break
            if command in {"complete", "cancelled", "error"}:
                scenario.phase(command)
            else:
                gate[0] = command
            print(json.dumps({"ok": True}), flush=True)
    finally:
        timer.cancel()
        host.stop()
        host.close()
        scenario.cli.close()


if __name__ == "__main__":
    main()
