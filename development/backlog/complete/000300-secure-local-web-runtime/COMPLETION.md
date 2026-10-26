# FR 000300 completion — 2026-10-26

Delivered in Cost Guard v80.81: a separate foreground `cost-guard-web.py`, standard-library loopback host, fixed local Beta shell and authenticated finite report API. Existing CLI/Diagnostics imports and OS launchers remain independent; no dependencies, setup downloads, browser launch, native icons, detached workers/restarts or background lifecycle were introduced.

## Implementation and ownership

- `src/web/http.py` owns exact assigned Host/Origin checks, fixed routes/assets, bounded framing/body/concurrency, absolute request deadlines, security headers and no request logging. `security.py` owns expiring one-use bootstrap, instance browser session and CSRF. Provider/control credentials do not enter browser storage or URLs. The short-lived bootstrap fragment is intentionally printed to the foreground owner and erased before exchange.
- `jobs.py` owns four outstanding requests, in-flight coalescing, one spawned finite analysis process, bounded retention/results, safe phase/count progress, cancellation and a hard whole-job deadline. Stopping/cancelling terminates and joins only the owned report process, including blocked historical scans. Fresh one-shot application/services do not share mutable integrations or a live account scheduler.
- `composition.py` wires canonical sources/config/cache/providers into the existing ReportApplication. Exact decimal strings, unknown/null/provisional fields, report semantics and independent source/account observations survive transport. The browser inserts text only, never calculates costs or executes source markup.
- API/security/limits are documented in [Web Beta](../../../../docs/web-beta.md). Native background/instance lifecycle remains FR 000310; navigable views/live parity remain their separately pending FRs. No claims of public-server or same-user-malware isolation.

## Verified evidence

Runtime source commit: `76cd4cb7fbada74de2b37cd926891b802533b507`; final follow-up changes are architecture/completion/state and a Windows test-closure assertion, not shipped runtime changes.

- `python -B development/tools/run_tests.py --suite full`: initial 97-file run passed. Final real-installation Diagnostics reran the Full suite: **97 files, zero failures**, 40.7 seconds; its embedded product validator also passed.
- `python -B development/tools/validate_package.py --working-tree`: passed after condensing README within its existing hard cap. Existing design-budget warnings remain in README, analysis/context, reports/service and watch/coordinator; no caps were raised.
- `python -B development/tools/collect_diagnostics.py --no-network --snapshots 1`: verified `validation.ok`, `tests.ok` and `package_validator.ok` all true; actual selected source V2. No live provider quota requests. The private diagnostic archive is intentionally not committed or required for future recovery; this sanitized result is the retained evidence.
- Read-only real-installation loopback probe: authenticated browser-session exchange, finite sessions request and polling completed successfully; source `acquired`, one session row. No browser opened, model inference, OpenCode mutation or shared-service restart.
- `cost-guard.py --help` and `cost-guard-web.py --help` succeeded with no optional environment setup. Shared application parity and CLI/Diagnostics import isolation remain covered by the Full suite.
- Thirteen new tests cover healthy/empty/offline DTOs, exact decimal/null/text transport, authentication/expiry/replay/instance scope, foreign Host/Origin/rebinding/CSRF, malformed requests/traversal/framing/size limits, secret-free failures, oversize results, progress/coalescing/backpressure/retention, cancellation, hard job deadlines, HTTP admission and absolute dripping-client shutdown.

Validation caught README hard-cap growth and a Windows-only test expectation: enforced socket closure may be EOF, reset or abort. The README was condensed without changing budgets; the test now accepts only actual connection closure variants, not timeout. Full Diagnostics was rerun to verified success. Knowledge helper rejected CRLF metadata matching before writes; LF-normalized proposed documents then applied with unchanged source hashes and HEAD guards.

No actual browser rendering or real macOS execution was performed. Synthetic HTML-injection/text-node checks and Diagnostics' simulated macOS checks are not native UI/macOS proof. Long reports remain subject to the documented 120-second/8-MiB bounds rather than fake success or unlimited historical blocking.

## Knowledge, retention and dependencies

Architecture **updated**: overview routes the new Web/process boundary and `modules/web.md` records ownership, dependencies, entries and tests; reports contract links the secured adapter. Journal **no-update**: no distinct investigation warrants a duplicate journal entry; current operational facts live in module/API contracts.

Selected FR payload moved byte-for-byte; only this truthful root completion report is added. Exact native maintenance nextState is staged; identity high watermark/retention are unchanged and no records pruned. FR 000290 shared contracts/design remain authoritative. All other pending FR specifications/dependencies are preserved; no competing source/state writes or stashes were found in the owned clone. Sanitized evidence above is sufficient outside owned scratch; private runtime cache/Diagnostics and probe artifacts need not survive cleanup.
