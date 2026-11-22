"""Offline synthetic input for probe_web_help.cjs --raw-models; no saved sessions."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.claude_alias import catalog, desktop_service, DesktopSource, snapshot
from development.tests.fixtures.session_snapshots import make_snapshot, one_request
from src.analysis import analyze_snapshot
from src.application.display import with_display
from src.application.projection import project, prompt
from src.domain import ModelRef
from src.reports import ReportKind, ReportRequest
from src.reports.prompt_rows import PromptRowProjector


def rows(saved):
    bundle = analyze_snapshot(saved, tracked_provider=None)
    projector = PromptRowProjector(snapshot=saved, bundle=bundle, catalog=catalog(), config={})
    return bundle, projector


def main():
    owner = unittest.TestCase()
    try:
        service = desktop_service(owner, snapshots=(snapshot(), snapshot(1, "claude-sonnet-5-5", "github-copilot")))
        views = {kind.value: project(service.build(ReportRequest(kind,
            **({"session_id": "root-0000"} if kind is ReportKind.SESSION else {}))), prompt_details=True).to_json()
            for kind in (ReportKind.SESSIONS, ReportKind.SESSION, ReportKind.AI_STATS)}
        saved = DesktopSource((snapshot(),)).load_session_snapshot("root-0000")
        bundle, projector = rows(saved)
        alias = replace(projector.prompt(bundle.prompts[0]), event_id="sonnet")
        failed = one_request(running=False)
        failed = replace(failed, invocations=(), events=tuple(replace(event, metadata={}) for event in failed.events),
            messages=tuple(replace(message, model=ModelRef("claude-agent", "claude-haiku-4-5-20251001"),
                tokens=None, error_name="provider.unknown") if message.role.value == "assistant" else message
                for message in failed.messages))
        bundle, projector = rows(failed)
        failed_row = projector.prompt(bundle.prompts[0])
        mixed = make_snapshot()
        mixed = replace(mixed, invocations=tuple(replace(inv,
            model=ModelRef("openrouter", "vendor/future-release") if inv.summary else
                ModelRef("github-copilot" if inv.session_id == "child" else "claude-agent", "claude-sonnet-5-5"))
            for inv in mixed.invocations))
        bundle, projector = rows(mixed)
        cases = (projector.prompt(bundle.prompts[0]), projector.compaction(bundle.compactions[0], 3))
        wire = lambda row: with_display(prompt(row, details=True)).to_json()
        output = dict(browser_rows=[wire(alias), wire(failed_row)], synthetic_views=views,
            synthetic_prompt_cases=[wire(row) for row in cases], evidence="synthetic only; no inference or private sessions")
        Path(sys.argv[1]).write_text(json.dumps(output), encoding="utf-8")
    finally:
        owner.doCleanups()


if __name__ == "__main__":
    main()
