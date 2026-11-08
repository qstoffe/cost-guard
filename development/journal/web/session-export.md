# FR 000631 — session export implementation, not delivered

2026-11-08. Work preserved on `fr-000631`; no feature-delivery claim.

## Candidate and verified evidence

- Candidate: registered-source native `sanitize=true` transfer, pinned observation
  epoch and canonical observed detail token; CSRF/instance-protected POST-only
  attachment; one export at a time, 16 MiB maximum body and four-second source
  deadline. No transcript staging/cache, model call or OpenCode service mutation.
- Running OpenCode v2.2.6 OpenAPI confirms the experimental export endpoint and
  `{data: {info, messages}}` envelope. For this worker's own session the candidate's
  native payload was semantically identical to CLI `session export --sanitize`.
  A measured read returned 64,575 bytes / 36 messages in 46 ms. These are single
  local observations, not a universal performance or compatibility guarantee.
- Full suite: 171 test-file units, zero failures, 120.1 seconds. Focused export and
  existing detail tests: 17 tests passed. Package validation: zero failures,
  seven pre-existing advisory prose/design-budget warnings. No release ZIP.
- Hidden fresh-profile Edge 156.0.4314.58, shipped loopback HTTP/auth/assets and
  synthetic LIVE-style source: correct complete native fallback file (including
  Unicode and a later user message after a succeeded idle), malformed-response
  rejection without a second file, URL cleanup, focus/navigation retention and
  1280/360-pixel layouts without page overflow. This does not assert visibility in
  the owner's ordinary Desktop session list.
- Deterministic client checks: picker-first ordering, no source work on picker
  abort, write/close ordering, fallback and navigation/resource retirement.
- Integrated browser unavailable (`browser.disconnected`). Headless abort is not
  proof of a real chooser cancellation. A separate headed Edge attempt on an
  owned, never-switched Windows desktop did establish the genuine browser-owned
  native picker and real Cancel: operation settled, zero native export requests,
  no output file. Targeted native Button cancellation used no shared input or
  clipboard. Initial UIA discovery attempts are not acceptance proof.

## Decision and outstanding scope

The foreground Decision Delegate directed **On Hold for FR 000631 only** after
bounded nondisruptive alternatives. The native filename field had no safely
identifiable writable UIA Edit named `File name:` on the isolated desktop; no
filename write or Save invocation followed that failed identification. Successful
native destination selection and filesystem completion remain **UNVERIFIED**.
This is a verification-capability limitation, not a demonstrated product failure
or permission denial. No acceptance waiver, visible-desktop authority, unrelated
file access, shared input or unidentified consent-dialog acceptance was granted.

Prerequisite: a safe authorized route to control the native filename/destination
and verify Save As of the correct complete sanitized JSON on a real loopback
Edge/Chrome host, or a later explicit owner change to that acceptance requirement.
No automatic release, dependency holds, completed progress or product delivery.
Architecture/current user documentation and release metadata are not promoted for
this unfinished candidate. The published hold is documentation-only from default.
