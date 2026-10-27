# FR 000490 — delivered implementation

## Outcome and scope

Implemented in Cost Guard v80.98 (2026-10-27). Accounts now uses shared provider/account
cards instead of a diagnostic paragraph/table wall: known-only remaining progress,
native credits/money, reset/status/windows, Pace, billed today/month, Normal local-month /
Today CCost, Copilot Unaccounted usage and visible attribution/error notes. Native
observation/used details expand with keyboard-accessible disclosures. Unknown, zero,
unlimited, blocked, unavailable, partial, rate-limited and stale remain distinct.

Shared the unchanged terminal reset formatter through `src/display.py`; immutable DTO
tokens use the frozen observation time and configured timezone. Exact raw values remain
unchanged. Readable classified method labels replace primary raw error-code strings;
private provider warning/reason payloads and credentials remain excluded.

Selected approach: reuse the existing Overview card and display seams, not another Web
account acquisition path, provider call, formatter formula or framework. Normal cached
observation, refresh ownership, account/report scopes and Watch rolling behavior remain
unchanged. No browser editing, privacy expansion, ZIP, release/tag or live inference.

Candidate implementation: [8dc82a38](https://github.com/qstoffe/cost-guard/commit/8dc82a38dddd7f2999e7872d52e1e6a8a0949725).
The native delivery receipt owns the confirmed PR/merge identity; this report does not
invent a future merge SHA.

## Verification

- Full suite PASS: 111 test files, zero failures (46.9s), including new equivalent
  CLI/DTO/DOM account fixtures and existing quota/reset/display/HTTP/Watch regressions.
- Working-tree package validation PASS: zero failures, four existing design-budget
  warnings. No hard cap or assertion weakened. Initial raw-code assertion and generated
  screenshot-placement failures were repaired, then the entire suite reran successfully.
- Real headless Edge PASS: 1200px/360px × light/dark, no document overflow, correct known /
  unknown / unlimited bars; Enter opens, Space closes and Tab advances with visible focus.
  Desktop-light and narrow-dark captures inspected. Desktop-pane input helper failed;
  the bounded isolated headless browser is the verified equivalent.
- Real V2 observation: one live owner, two streams, three available accounts / four quotas,
  preserved run origin; direct Normal facade acquisition succeeded. Owned test hosts and
  browser processes were closed; shared OpenCode was not stopped.

Detailed reproducible facts/measurements and privacy limits:
[Accounts parity evidence](../../../architecture/governance/verification/accounts-display-parity.md).

## Limitations, repairs and follow-up

The real Normal HTTP job hit the **pre-existing** 8 MiB `result_too_large` ceiling.
On identical canonical input, verified-base result = 8,683,533 bytes; candidate =
8,683,732 bytes; provenance identity vector alone = 8,403,281 bytes; limit = 8,388,608.
No limit was raised or provenance discarded. Thus integrated real-history browser
Accounts was not validated; this is not recorded as a passing HTTP probe. Follow-up
proposal is deferred in the evidence: design bounded Normal provenance delivery as a
separate change. Physical keyboard/mouse, screen-reader and macOS acceptance NOT RUN.

Knowledge assessment: journal **no-update** (no duplicate chronology); Web module,
code-map, display baseline and current Beta docs updated. No architectural boundary
change. The installed knowledge reader rejected the pre-existing >12 KiB Web module;
bounded equivalent inspection used exact HEAD/source, SHA256 preflight and targeted
metadata/context edits, preserving all unrelated content. No installed helper was patched.
No pending FR refers to this selected bundle; future items retain their bytes/identity.
