# Completion — FR 000551

2026-11-02 · v80.129

## Delivered scope and reproduced cause

Fixed a concrete post-FR000546 Web acquisition defect at baseline v80.128,
`d57760e7cd9c9070c3b9ee20f13fd2155f0ba620`. Catalog revision changes reset
capture scheduling timestamps to -1. With more eligible roots than the four
capture slots, changing early session IDs repeatedly won the sort. Later cached
running cards could never read fresh terminal evidence, even after their own
revision stabilized. The equivalent fresh CLI root had already retired.

The scheduler now records successful admission order, independently of source
revision and result acceptance. Changing roots and rejected generations cannot
reset their place ahead of waiting roots. Four bounded capture workers, the
active/history rotation, adaptive cadence and canonical lifecycle remain intact.
No browser-only filter, new provider polling, age/cost/quota cutoff or inference
from inactive metadata was added. CLI, accounting, layout and history selection
are unchanged. Future Mini Watch still consumes server-owned lifecycle truth.

## New failing regression and resulting behavior

The first deterministic scheduler test failed because roots 4/5 never received
capture turns. Real current-V2 HTTP fixtures then failed CLI=False/Web=True for
the same sixth canonical root in all three cases:

- Quota failure with absent final usage.
- Interrupted attempt with zero usage.
- Abandoned `tool-calls` continuation, with earlier usage but no idle/final/abort
  row, after the existing canonical 60-second continuation grace elapsed.

These regressions use actual isolated source capture, normalization, analysis,
retention, card acceptance and immutable export; only admission completion is
controlled through futures, without sleeps. After the fix all three retire on
their accepted capture, preserve known usage/outcome, freeze duration and leave
the active area after one terminal grace. Repeated refresh does not restart it.
Cold source reconstruction, Session detail and exported-stage Web rendering agree.
The abandoned case remains `Ended`, not successful. Existing partial/outage,
missing-child/idle, delayed publication, new attempt and live-work tests remain.

## Actual verification

- `py -3 -B development/tools/run_tests.py --suite full`: PASS, 126 files,
  zero failures, four bounded workers, 65.7 seconds.
- `py -3 -B development/tools/validate_package.py --working-tree`: PASS,
  11 checks, zero failures. Four existing design warnings remain: README,
  analysis/context, reports/service and Watch coordinator. Hard caps unchanged.
- Source regression plus JavaScript VM: PASS for all three stop shapes, including
  terminal/history duration, styling/activity and fresh-view reconstruction.
- Integrated-browser DOM check using those actual source-derived stages: PASS.
  Quota/interruption became `Aborted` (quota cause preserved); abandoned work
  became `Ended`. Terminal durations stayed 3s/3s/1s through history/reload,
  stopped cards were not running, and the console reported no errors. This is
  synthetic browser evidence, not the owner's incident or native desktop proof.
- Read-only actual installation: OpenCode V2 service **2.2.5**, own Web/CLI code
  **v80.129**. `probe_web_live.py --watch-cards --detail`: PASS in a serial run,
  one owner/two SSE streams/three accounts, preserved run origin and advancing
  sequence, two active/two history cards, four populated cards, one row/card,
  four pending captures, first rows 5.84s; detail/freeze consistent. Owned HTTP/
  Live workers closed; shared OpenCode was untouched.
- Baseline v80.128 real-V2 probe also passed: first rows 3.33s and detail/freeze/
  clean shutdown. This proves compared runtime liveness, not the reported mismatch.
- `git diff --check`: PASS before publication.

An initial Full run copied the then-oversized version history and failed two
validator assertions. The history was compressed without raising its cap; the
subsequent complete Full run above passed. An initial post-fix real-source probe
reached cards/detail successfully but failed `web_shutdown_timeout` while Full
was also running. Its cause is unknown; that run is not PASS. The serial rerun
passed including shutdown, not proof of a diagnosed timeout repair. A baseline
probe cancelled by the OpenCode server restart has no result.

## Evidence limits and decisions

The owner's exact affected prompt/session/attempt and installed Web/CLI versions
were not supplied and remain unverified. The ordinary checkout's bounded Web
diagnostics returned `not_observed`, not evidence of an outdated/stopped host.
The fixture-proven starvation mechanism is not asserted to be that incident's
exact cause or proof that every possible old-running case has been identified.

The foreground Decision Delegate directed bounded starvation characterization,
then normal fix/delivery after the concrete failures. No scope/test exception,
desktop authorization or claimed human approval was granted or needed.

Current Web architecture, user-facing acquisition docs, version facts and the
existing lifecycle journal were updated. No model call, prompt intervention,
quota mutation, installation, ordinary-checkout edit, ZIP, tag or Release.
