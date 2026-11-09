# FR 000650 — completion

Implemented 2026-11-09 as v81.0. The original specification and entire bundle are
preserved intact. This is the preparation-time verification snapshot; the final-head
four-job workflow and protected merge/readback remain required before delivery.

## Outcome

- Existing secured Web is the Windows/macOS default: top-level platform Web
  launchers and no-argument `cost-guard.py` reuse the same managed native launchers.
- Independent report/Watch remain under platform `Legacy/` and `cost-guard-cli.py`.
  Explicit root CLI arguments forward unchanged; help/version remain local, and
  unsupported no-argument platforms fail with actionable headless/CLI guidance.
- Actual serving version supplies `Cost Guard v81.0`; route titles and native
  branding drop Beta. The optional owned macOS app cache produces `Cost Guard.app`
  with canonical version metadata, updated sources and safe reuse/invalidation.
- Relative paths, executable/LF rules, SourceGuard, validator/source inventory,
  current docs, architecture map and hosted launcher cases follow the new layout.
  Existing Beta shortcuts require a one-time path update; no duplicate aliases.
- No account/history/pricing/settings migration, new dependency, Legacy retirement,
  inference, shared OpenCode stop, tag, release or generated source/release ZIP.
  Suggestion000400 is unchanged and remains a separate future owner decision.

## Verification

- Clean local Full: all 179 registered files passed in 123.4s, 2,187 tests,
  2,185 passed and two macOS-shell skips owned by actual macOS CI.
  Evidence: `scratch:/full-final.json`. The initial Full's four stale
  path/whitespace test failures were repaired; its evidence remains FAIL.
- Working-tree validator: zero failures, 11 passes, seven existing advisory/design
  warnings; no raised budget. Tracked source inventory includes only the intended
  Web/Legacy launchers, three Python entries and macOS command mode 100755.
- Local native-Web profile: 14/14 selected files/case groups passed, actual moved
  Windows CMD and PS discovery/exit plumbing without external desktop UI.
- Hidden Chrome156: authenticated shipped header/status version and six route
  titles passed, no page errors. `scratch:/branding.json`, `scratch:/branding.png`.
- Real read-only V2 Models/All Models HTTP/SSE probe: one Live owner, two verified
  authenticated streams, sequence advanced, report completion, preserved run
  origin and owned cleanup. Normal: 29 catalog/25 selectable rows, 81.333s;
  All Models: 29/29, 2.377s. `scratch:/live-models.json`. The aggregate records one
  Watch history-scheduling error; this is not full-history/account correctness
  or an inference/performance comparison claim.

## Hosted evidence and scoped limitation

The initial run42670054886 passed common and Windows; ARM64 native integration
also passed. Both macOS suites exposed a fake-interpreter fixture missing `-u`,
now corrected without weakening entry/argument/exit/PTY assertions. Intel also
reported a production-wrapper failure after adapter/fault/cache checks; its exact
cause was not captured. Corrected-source run42672593688 attempt1 passed Intel's
21 focused tests and complete native case, but GitHub reported run FAILURE while
only that job was available through reconciled REST/GraphQL inventories. The
Delegate authorized one unchanged full rerun to recover the missing evidence.
Attempt2 also reported FAILURE, with common, ARM64 and Intel successful but Windows
unavailable. Common passed all 179 files, validation and rendered Chromium smoke;
each macOS architecture passed all 21 focused tests and the complete production-
wrapper/native case with one accepted owned-loopback OS handoff. Windows on the
earlier head passed its 52 focused tests and complete native case; that result is
not substituted for missing current-source Windows CI. Neither attempt is PASS.

The [promotion journal](../../../journal/web/product-promotion.md) records actual
results and unknowns. On 2026-11-09 **Decision Delegate** authorized a minor FR000650-
only verification exception for physical appearance/input/accessibility, Finder/
Gatekeeper/quarantine, consumer double-click/Terminal-window lifetime and rendering
in the OS-selected default browser. These remain NOT VERIFIED; the workstation
native-UI probe is NOT RUN. The underlying real lifecycle/shell/regression/rendered
evidence is adequate without disruptive workstation reassurance; hosted repetition
cannot prove physical acceptance. Consumer-environment-specific risk remains.

The exception waives no native correctness/security, settings preservation, Legacy
fallback, process ownership/shutdown/exit semantics, failed/missing CI or history-
probe evidence. No Suggestion/hold is needed for this isolated physical caveat.
The Delegate authorized this necessary completion publication, but final-head
common/Windows/ARM64/Intel jobs and expected phases must all actually pass before
merge. Final CI/merge truth is recorded in PR251/run evidence, avoiding another
reporting-only commit; only confirmed merge/default readback counts as Delivered.
