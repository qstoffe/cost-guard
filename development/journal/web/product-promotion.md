# Web as the default product — FR000650

2026-11-09, v81.0. Entry-point and branding migration only: no new Web host,
accounting/source/pricing engine, dependency, user-data migration or Legacy retirement.

## Ownership and compatibility

- `src/product_entry.py` routes desktop default intent to the existing Windows
  PowerShell handoff or macOS managed launcher; help/version stay local. Every
  explicit legacy argument is forwarded unchanged to bootstrap, including unknown
  option errors. Unsupported no-argument platforms fail with actionable alternatives.
- `cost-guard-cli.py` retains the independent guarded bootstrap. Platform CLI pairs
  moved intact to `Legacy/` with corrected parent traversal and this explicit entry.
  The macOS report's exit variable avoids zsh's read-only `status` parameter.
- Web launchers/template moved out of Beta. SourceGuard covers real native trees
  and all three entries, with unchanged link/reparse and metadata-only safeguards.
  The owned content-addressed Finder cache now emits `Cost Guard.app` with canonical
  display/version metadata; old generated outputs are not deleted or overwritten.
- The authenticated header uses the serving `/api/status` version; per-route titles
  and tray/menu branding drop Beta. The existing guide URL is intentionally retained.
- Redirected/noninteractive Windows startup failures print recovery/Legacy guidance
  without attempting a blocking desktop dialog; ordinary interactive errors retain it.

## Verification

- Native-Web profile: 14/14 files passed on Windows. Actual moved CMD/status plumbing
  and PS discovery/exit behavior use non-UI fixtures with spaces/Unicode paths.
- Full: the clean final Windows run passed all 179 registered files in 123.4 seconds
  (`scratch:/full-final.json`). The initial run executed all files with four causal
  stale launcher-path/version-whitespace test failures; those owners were repaired
  and passed focused reruns before the final clean run. The initial run remains FAIL.
- Working-tree package validation passed; seven existing advisory/design warnings,
  no hard-cap or structure-policy relaxation. No source/release ZIP was generated.
- Hidden Chrome 156 rendered the authenticated shipped shell: `Cost Guard v81.0`
  and correct Models/Watch/Accounts/Sessions/AI Stats/Settings tab titles; no duplicate
  branding or page errors. Private one-use launch credentials remained in memory.
  Evidence: `scratch:/branding.json`, `scratch:/branding.png`.
- Real read-only V2 installation probe completed Normal (29 catalog/25 selectable)
  and All Models (29) reports with the same Live owner, authenticated HTTP/SSE, and
  owned cleanup; shared OpenCode was untouched. It does not prove full history
  acquisition or private account correctness. Its aggregate records one Watch history-
  scheduling error without a causal payload; that unavailable scope is not PASS.
  Evidence: `scratch:/live-models.json`.

## Native verification decision and remaining scope

Decision Delegate rejected disruptive workstation reassurance and requested a bounded
improvement to the existing hosted native case: moved shell → production `main()` →
production launch wrapper, including config/native preflight and macOS app preparation;
one existing OS browser handoff only, then restart/owned cleanup with unchanged
preferences and checkout identity. The old offline shim bypassed those wrappers.
The case now isolates acquisition/private test state, not the launcher path. An
unavailable opener is exit 4 and is distinct from successful browser launch/rendering.
The initial hosted run [42670054886](https://github.com/qstoffe/cost-guard/actions/runs/42670054886)
passed Linux/common and Windows. Windows and ARM64 macOS passed the production-wrapper
path, restart/cleanup, preference and checkout-identity checks. Each recorded one
accepted registered-browser handoff to the owned loopback destination; rendering was
NOT VERIFIED. Both macOS regression jobs found a fixture that omitted Python's real
`-u` argument; it now asserts all three exact arguments and preserves exit/PTY checks.
Intel macOS also failed the wrapper case after its adapter, HTTP-fault and app-cache
checks passed. Its first diagnostic did not identify the wrapper's caught error.
The same bounded case now retains allowlisted lifecycle codes and separates child
mode traces, without private logs/paths/URLs, new jobs, extra handoffs or weaker gates.
On corrected-source run [42672593688](https://github.com/qstoffe/cost-guard/actions/runs/42672593688),
attempt 1, Intel passed all 21 focused tests and the complete native case, including
the production wrapper and one accepted handoff. The earlier Intel failure's cause
remains unresolved, not retrospectively explained by that passing observation.
GitHub nevertheless reported the run/suite as FAILURE while normal and attempt-
specific paginated job inventories, suite checks and a completely paged GraphQL
rollup exposed only that successful Intel job. Head/suite/run identities matched;
the PR merge commit had no rollup. Common/Windows/ARM64 were therefore unavailable,
not inferred PASS from old-head checks or the green one-context rollup.

Decision Delegate authorized one full rerun of that unchanged existing workflow to
recover coherent current-source evidence, with the same runners/topology/timeouts,
no debug logging, no extra handoff budget and no automatic further retry. The owning
transport confirmed the request (HTTP 201). Attempt 1 remains FAILURE with incomplete
job evidence. Attempt 2 also reported FAILURE: common, ARM64 and Intel completed
successfully, but the attempt-specific paginated inventory omitted Windows.
Common passed all 179 files (2,187 tests: 2,165 passed, 22 platform skips), package
validation and rendered Chromium smoke. Each macOS architecture passed all 21
focused tests plus adapter/fault/cache and complete production-wrapper lifecycle;
each recorded one accepted owned-loopback OS handoff, never page-rendering proof.
Evidence: [attempt 2](https://github.com/qstoffe/cost-guard/actions/runs/42672593688/attempts/2),
`scratch:/ci-c88aad7-attempt2.json`. Missing Windows is unavailable, not PASS; the
earlier Windows result belongs to the earlier source head. No further manual
rerun or dummy commit was authorized.

## Scoped physical-verification exception

On 2026-11-09, **Decision Delegate** authorized a minor FR000650-only verification
exception for physical appearance/input/accessibility, Finder/Gatekeeper/quarantine,
consumer double-click, consumer Terminal/window lifetime and rendering in the OS-
selected default browser. These remain NOT VERIFIED; the workstation native-UI
probe remains NOT RUN. No Suggestion or hold is needed for this isolated caveat.

Reason: real production-wrapper/native lifecycle execution on both macOS
architectures, earlier Windows native execution with unchanged Windows production
code, shell/PTY contracts, clean Full regression and independent rendered-browser
evidence establish underlying paths without claiming consumer-desktop acceptance.
More hosted repetition cannot supply physical proof. This waives no native
correctness, security, settings preservation, Legacy fallback, underlying process
ownership/shutdown/exit semantics, missing/failed CI or real-probe history evidence.

The Delegate authorized publication of the necessary completion/progress/journal
delta to the same PR, followed by its normal cumulative-path four-job execution.
This document is the preparation-time verification snapshot: final-head common,
Windows, ARM64 and Intel jobs and their expected phases must actually pass before
protected merge. Final results belong in the PR/run evidence, not another reporting
commit. Any missing job/failure blocks merge and returns to the same Delegate;
there is no further automatic rerun or old-head substitution.

Integrated browser was unavailable (`browser.disconnected`); hidden Chromium was used
without changing identity, security or desktop permissions. The workstation native UI
probe is NOT RUN. Physical Windows appearance/input, macOS Finder/Gatekeeper, quarantine,
consumer-desktop launch and accessibility remain unverified, never inferred from mocks,
hidden DOM or hosted APIs. Consumer-environment-specific behavior remains a disclosed
risk; neither the earlier unexplained Intel failure nor missing CI is relabeled PASS.
