# FR 000631 — native sanitized session export

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

## Resumed candidate — 2026-11-09

The owner released FR000631 to Ready with a limited evidence exception, preserved
in its `UNBLOCK.md`: **only successful real native Save As destination selection
and completed disk write are waived as a delivery proof**. Native Save As remains
implemented; correctness, cancellation, authentication, native sanitized content,
source identity, fallback and ordinary verification are not waived. No new shared
desktop-control authority was granted. The historical hold above is superseded by
that owner decision, not erased or retroactively called a successful test.

Resumed `fr-000631` from `155103c`, integrated current main `c2b2185` in `3474c9a`.
The app API conflict retains both attachment-instance headers and main's visible-use
cache-retention header. No existing feature/analytics behavior was intentionally
changed. Architecture routing, the Web guide and v80.213 metadata now describe export.

Fresh evidence for the integrated runtime:

- Full suite: **175 test-file units, zero failures, 146.4 s**, including export,
  existing detail/catalog, transport/security and deterministic picker/write tests.
- Integrated browser remained unavailable (`browser.disconnected`); hidden owned
  fresh-profile **Edge 157.0.4341.42** used shipped HTTP/auth/assets against a
  synthetic LIVE-style native source. Correct complete fallback JSON was written,
  including Unicode, succeeded-idle metadata and a later user message. Malformed
  source output created no second file. Focus/navigation and object-URL retirement
  passed, with no page overflow at 1280/360 px and a 40.25 px action height.
- Trusted-click native picker invocation had active user activation and headless
  `AbortError`, with zero export requests. This is **not** a new real Windows
  chooser test. Historical real picker-opening/Cancel evidence above is retained
  as such. Deterministic native handle tests cover write/close and retirement.
- Registered **OpenCode 2.2.6**: the actual capability/shape check and native
  `sanitize=true` transport succeeded for this worker's own ongoing session.
  Native `{info, messages}` was semantically identical to the installed CLI
  `session export <own-session> --sanitize`: **51,092 bytes, 30 messages,
  0.0798 s**, **3,779,010 peak traced Python bytes**. These are a small single-read
  observation with tracing overhead, not worst-case or universal performance.
  Transcript content remained in memory only; retained evidence contains scalars,
  not the export. No other session/private storage was inspected.

Successful real native Save As destination selection and filesystem write remain
**UNVERIFIED**, explicitly accepted by the owner for this delivery. There is no
claim of actual Desktop session-list visibility, compatibility with every future
experimental API, or exhaustive private-history/native-OS proof. The synthetic
source exercises LIVE-style selected-session export independently of Desktop; the real
source check verifies the installed transfer interface. No inference, service
restart, new dependency or release ZIP was used.

Final v80.213 package validation: **11 passes, zero failures, seven advisory
prose/design-budget warnings** (Web guide, root README, version history and four
existing Python modules); no hard-cap or baseline was raised. Only release metadata
and documentation changed after the passing runtime suite; version consistency,
syntax/imports, boundaries and file budgets were then validated on that tree.
