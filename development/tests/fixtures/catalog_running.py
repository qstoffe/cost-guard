"""Real scalar acquisition over owned synthetic running/terminal catalog trees."""
from dataclasses import replace

from development.tests.fixtures.catalog_prompt_activity import at
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.session_catalog import SessionCatalog
from src.domain import NormalizedPart, TerminalEvidence, TerminalOutcome
from src.reports.session_summary import session_summary
from src.watch.observers import observe_catalog


def configure(runtime, command):
    service, source = runtime.service, runtime.service.source
    runtime.scalar_hold = True
    if command.startswith("running-source-"):
        count = int(command.removeprefix("running-source-"))
        service.now_ms = at("02:00:00")
        service.config["timezone"] = "UTC"
        source.snapshots = SyntheticMonthSource(100 + count, 1,
            month_start_ms=service.now_ms - 20_000_000, running_roots=count).snapshots
        source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
        runtime.catalog = SessionCatalog(clock_ms=lambda: service.now_ms, timezone_id=service.timezone_id)
        runtime.catalog.tick(service)
    else:
        key = "root-0025"
        snapshot = source.snapshots[key]
        root = replace(snapshot.root, updated_at_ms=service.now_ms,
                       active=command != "running-finish")
        assistant = snapshot.messages[-1]
        if command == "running-finish":
            assistant = replace(assistant, termination=TerminalEvidence(
                service.now_ms - 100, TerminalOutcome.CANCELLATION))
        else:
            part = NormalizedPart("stream", assistant.message_id, key, "text",
                assistant.created_at_ms, service.now_ms, assistant.provenance, {"text": "streaming"})
            assistant = replace(assistant, parts=(part,))
        source.snapshots[key] = replace(snapshot, root=root, sessions=(root,),
            messages=(*snapshot.messages[:-1], assistant), source_revision=command)
    catalog = runtime.catalog
    catalog.observe(observe_catalog(source, include_archived_revisions=True))
    for key, root in catalog.roots.items():
        if catalog._current(key):
            continue
        row, revision = session_summary(service, root, catalog.revisions[key], active=key in catalog.active)
        catalog.rows[key] = row
        catalog.valid[key] = revision, catalog.clock()
        catalog.activity_valid[key] = revision
        catalog._record_summary_prompt(key, row, catalog.clock_ms())
