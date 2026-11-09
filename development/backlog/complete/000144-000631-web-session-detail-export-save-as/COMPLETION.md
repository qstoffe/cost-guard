# FR 000631 — completion with owner-approved evidence exception

Implemented 2026-11-09 as **v80.213**, for squash delivery to `main` through the
FR000631 feature PR. The original FR, hold history and owner release remain intact
beside this report. This document records implementation/verification, not a claim
that an open PR has already merged; GitHub is authoritative for delivery.

## Delivered scope

- Session-detail **Export JSON** transfers the selected complete native sanitized
  OpenCode session, not projected Cost Guard rows. Running sessions remain
  point-in-time exports; native message/lifecycle fields are preserved unchanged.
- A supported browser invokes native Save As directly from the user click before
  any asynchronous export. Cancel does no source work. Unsupported browsers use
  normal download and retain browser-controlled save-location behavior.
- Registered V2 transport checks the running OpenAPI capability, sends native
  `sanitize=true`, validates identity/JSON/envelope/completeness and strips only
  the HTTP `{data: ...}` wrapper to match the CLI's `{info, messages}` shape.
- Canonical source/instance/observation-epoch detail lease, strict session ID,
  authenticated same-origin CSRF/instance-protected POST and ordinary HTTP guards
  fail closed on stale selection, source change, denial or unsupported response.
  No download GET/lease/query token or arbitrary path parameter exists.
- One export slot, 16 MiB body, four-second source deadline and retirement checks
  bound work. Response is no-store/nosniff JSON attachment with a safe ASCII name.
  Buffers stay ephemeral; no transcript staging/cache/diagnostics, new dependency,
  OpenCode process/service restart, source mutation or model invocation is added.
- Web guide, release history/current version and affected Web architecture/code-map
  routing are updated. The export engineering journal separates fresh proof from
  historical evidence and limitations. Progress advances to ordinary count 83 only
  when this delivery's state is merged.

## Verification actually performed

- Full registered suite: **175 file units PASS**, zero failures, **146.4 s** on
  the integrated runtime (including export, existing detail/catalog, source/HTTP
  security and deterministic native picker/write/close lifecycle tests).
- Final package validation after release/docs updates: **11 passes, zero
  failures, seven advisory budget warnings**. No budgets or baselines were raised.
  No routine release ZIP was created.
- Hidden fresh-profile **Edge 157.0.4341.42**, shipped host/assets/auth and synthetic
  LIVE-style source: actual full sanitized fallback file, Unicode/native message
  and lifecycle integrity, no file for malformed output, focus/navigation/resource
  cleanup, 1280/360 px layouts without overflow. Trusted-click headless picker
  invocation had active user activation and AbortError with zero export requests.
- Real registered **OpenCode 2.2.6** export for this worker's own ongoing session:
  **51,092 bytes / 30 messages / 0.0798 s / 3,779,010 peak traced Python bytes**;
  complete native output was semantically equal to installed sanitized CLI export.
  Transcript bytes stayed in memory, not retained evidence. This is a small
  single-read measurement, not a worst-case latency/memory guarantee.
- Synthetic/deterministic cases cover zero-assistant/empty and large message
  lists, later user work after succeeded-idle metadata, invalid/foreign IDs,
  malformed/duplicate/non-finite/truncated/oversized responses, source restart,
  HTTP denial/unsupported/redirect behavior, cancellation/deadline, expired
  selection, busy/shutdown and auth/CSRF/Origin/Host/instance failures.

## Explicit exception and remaining uncertainty

**Decision-maker: owner, 2026-11-09**, as preserved in `UNBLOCK.md`. The only
waived acceptance proof is **successful real Windows/Edge/Chrome native Save As
destination selection and completed disk write: UNVERIFIED, not PASS**. The prior
isolated desktop could establish a genuine picker and Cancel, but could not safely
identify/write the native filename field. This is a capability limitation, not a
demonstrated product defect or permission denial. No new desktop-control consent
or broader correctness/test waiver was granted or used.

Historical genuine picker-opening/Cancel evidence is retained in the journal;
this worker's headless AbortError is not presented as a fresh real-dialog test.
Deterministic handle writes and actual fallback files are distinct proof, never
substitutes relabeled as real native Save As success. Native Save As remains
implemented normally. Any actual discovered saving defect would still require repair.

The integrated browser was disconnected; isolated hidden Chromium was used without
shared desktop input. No actual ordinary Desktop session-list visibility assertion,
native successful-dialog proof, future experimental-API compatibility guarantee,
or exhaustive private-source/large-history benchmark is claimed. The synthetic
LIVE-style case and real own-session transfer support their stated scopes only.

Evidence references: `development/journal/web/session-export.md`, normal test/CI
output, and scalar-only `scratch:/native-export-evidence.json` /
`scratch:/session-export-browser.json`. Durable conclusions are recorded here
because scratch cleanup may remove disposable evidence. GitHub checks/merge are
reported in the PR rather than manufacturing a pre-merge PASS in this file.
