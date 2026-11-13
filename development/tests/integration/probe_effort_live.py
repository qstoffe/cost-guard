"""Read-only supported OpenCode catalog probe; allowlisted output, no inference/history writes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.analysis.effort_defaults import request_effort
from src.application.effort_help import effort_help
from src.domain import ModelRef
from src.sources.opencode_v2_effort import option_level
from src.sources.opencode_v2_model_identity import DesktopModelCatalog


class NativeAPI:
    def __init__(self):
        self.executable = shutil.which("opencode")
        if self.executable is None:
            raise RuntimeError("native_cli_unavailable")
        self.reads, self.models = 0, []

    def json(self, route, *, query=None, **_):
        self.reads += 1
        result = subprocess.run([self.executable, "api", "get",
            route + ("?" + urlencode(query) if query else "")],
            capture_output=True, encoding="utf-8", timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError("native_api_read_failed")
        value = json.loads(result.stdout)
        if route == "/api/model":
            self.models = value["data"]
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--location", required=True)
    args = parser.parse_args()
    api = NativeAPI()
    version = api.json("/api/info")["version"]
    resolver = DesktopModelCatalog(lambda: api)
    # One real location observation discovers the models; no saved raw API payload.
    resolver.resolve(ModelRef("probe", "unavailable"), args.location)
    counts = Counter()
    models = []
    examples = []
    for value in api.models:
        if value.get("status") == "deprecated":
            continue
        model = resolver.resolve(ModelRef(value["providerID"], value["id"]), args.location)
        models.append(model)
        evidence = request_effort(SimpleNamespace(model=model, variant="default", selected_effort="", summary=False))
        counts[evidence.source] += 1
        assert effort_help(evidence).startswith("default (")
        assert "*" not in effort_help(evidence)
        assert "*\n* " in effort_help(evidence, value_cell=True)
        if value["providerID"] == "claude-agent" and value["id"] in ("opus", "sonnet", "haiku", "fable"):
            examples.append(dict(provider=value["providerID"], selected=value["id"],
                tooltip=effort_help(evidence), source=evidence.source))
    reads = api.reads
    for _ in range(100):
        assert resolver.current(models), "catalog_turnover"
    assert api.reads == reads == 3, "unexpected_per_tooltip_read"
    config_counts = {}
    for kind in ("agent", "command"):
        values = api.json("/api/" + kind, query={"location[directory]": args.location})["data"]
        if isinstance(values, dict):
            values = list(values.values())
        config_counts[kind] = dict(entries=len(values),
            numeric_options=sum(bool(option_level(v.get("settings")) or option_level(v.get("body")))
                for v in values if isinstance(v, dict)))
    print(json.dumps(dict(outcome="PASS", version=version, models=len(models),
        evidence_sources=dict(counts), examples=examples, config_counts=config_counts,
        catalog_reads=2, warm_validation_reads=0,
        limitations=["Current catalog/config estimates, not historical executed effort.",
            "Fresh probe process; shared OpenCode service is never restarted or reconfigured.",
            "Agent/command counts inspect only numeric option paths, not private templates or credentials."])))


if __name__ == "__main__":
    main()
