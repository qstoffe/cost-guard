# Optional Web runtime

Source revision: 76cd4cb7fbada74de2b37cd926891b802533b507
Checked revision: 76cd4cb7fbada74de2b37cd926891b802533b507
Last checked: 2026-10-26
Status: current

## Responsibility and ownership

`src/web/http.py` owns bounded loopback HTTP, fixed packaged assets and routing; `security.py` owns per-instance one-use bootstrap/HttpOnly sessions/CSRF; `jobs.py` owns finite admission, process isolation, progress, cancellation and result retention. `composition.py` creates fresh canonical integration owners for ReportApplication. The foreground host never owns the shared OpenCode service or a live Watch scheduler.

## Public contract

`cost-guard-web.py` is separate from CLI. Only 127.0.0.1 with an assigned port is supported; exact Host/Origin and authenticated sensitive reads are mandatory. Standard-library only; no browser auto-launch, setup, autoreload, arbitrary file/proxy/shell routes or background instance discovery. All browser presentation uses text nodes and application DTOs, never a second calculator. Source/account/analysis acquisition remains distinct from HTTP readiness. Per-account observation status remains in reports; account `reported` is not a healthy-all claim.

Eight HTTP slots, aggregate/header/body/request deadlines, four outstanding jobs, one spawned process, sixteen retained results, 8 MiB/result and a 120-second report deadline bound resources. Absolute HTTP deadlines supplement per-read timeouts, which alone do not stop dripping clients. The analysis deadline applies even while progress arrives. Cancellation/shutdown terminate and join only owned work, including blocked history scans. Each child owns one fresh service and one-shot account cleanup; no live scheduler is transferred. Result and error contracts preserve decimal strings/null/provisional fields and omit raw exceptions. The bootstrap fragment is intentionally printed once to the foreground owner, not access logs; it is erased before exchange. This is not a same-OS-user malware boundary.

API routes, request fields, session expiry and limitations: `docs/web-beta.md`. No persistent control credential is implemented or given to browser storage. No permanent release gate is introduced.

## Allowed dependencies

HTTP/security/assets depend on standard library and jobs. Jobs consume shared report requests/application DTOs. Web composition uses canonical source/config/cache/pricing/providers and reuses existing bootstrap account/model wiring, never CLI dispatch/source wake or Watch. CLI and Diagnostics do not import web. Application/reports never import the Web layer.

## Entrypoints

`cost-guard-web.py`, `src/web/main.py`, `src/web/http.py`, `src/web/jobs.py`, `src/web/security.py`, `src/web/composition.py`, `src/web/assets/index.html`, `src/web/assets/app.js`, `src/web/assets/app.css`.

## Tests

`development/tests/test_web_runtime.py` uses real synthetic loopback requests and spawn-safe `development/tests/fixtures/web_reports.py`. It covers auth/replay/expiry, Host/Origin/rebinding/CSRF, request/routing bounds, DTO exactness, text injection, empty/offline distinction, progress, cancellation, admission/retention, hard deadlines and oversize/error sanitation. Existing `development/tests/test_application_reports.py` owns broader calculator parity. The Full suite includes both. Read-only real-installation probes and Diagnostics remain separate from default-denied live-model tests; synthetic tests are not proof of native browser/macOS behavior.
