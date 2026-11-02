# FR 000548 completion — shared Web CI and focused native startup

Implemented 2026-11-02 in [PR 121](https://github.com/qstoffe/cost-guard/pull/121).
The original specification and bundle are preserved intact. No product source,
version, release, Full registry membership, assertion or deadline changed.

## Delivered scope

- One explicitly provisioned Linux common job runs Full, package validation and
  rendered Chromium. No repeated common suite/browser stack on native runners.
- Windows x64, Mac ARM64 and Mac Intel retain focused `native-web` startup
  regressions and real Win32/AppKit/HTTP/ownership/restart/fault cleanup smoke.
  Windows selects two focused files and ten lifecycle cases (27 tests); Macs
  select one focused file and two lifecycle cases (20 tests each). Exact cases
  are in `NATIVE_WEB_PATTERNS` and each `native-tests.json` artifact.
- One production registered-browser handoff per disposable native runner targets
  only its owned loopback host. All three returned ACCEPTED. The offline shim
  and callback dispatch checks remain separate from that production OS boundary.
- Explicit common/native phase plans fail closed for missing/malformed/unfinished,
  blocked or failed expected phases, incomplete suite evidence, previous step
  failure and cancellation. Assigned-elsewhere phases are not fake PASS.
- Public hosted/read-only token/offline fixture/path trigger/cancellation/short
  artifact boundaries remain; at most three jobs execute concurrently. Native
  jobs no longer provision browser tools or discover Node.

## Actual verification and measurements

[Run 41526896465](https://github.com/qstoffe/cost-guard/actions/runs/41526896465)
passed all four jobs for source `232fb1ae73b47c1999f13779132c58ec2209bbac`,
PR merge checkout `be4ca4ee598b24e6d5ebaa523ad462d6b7cf15b7`:

| Job | Actual tests | Regression / selection | Native smoke / browser |
| --- | --- | --- | --- |
| [Linux](https://github.com/qstoffe/cost-guard/actions/runs/41526896465/job/125556835754) | 125 Full files; 1,506 passed, 15 named OS-only skips, zero errors/failures | Full + validator PASS, 86.65s | Chromium PASS, 10.24s |
| [Windows x64](https://github.com/qstoffe/cost-guard/actions/runs/41526896465/job/125556835295) | 27 passed, zero skips/errors/failures | 23.75s | PASS, 17.14s |
| [Mac ARM64](https://github.com/qstoffe/cost-guard/actions/runs/41526896465/job/125556836025) | 20 passed, zero skips/errors/failures | 2.79s | PASS, 17.33s |
| [Mac Intel](https://github.com/qstoffe/cost-guard/actions/runs/41526896465/job/125556835831) | 20 passed, zero skips/errors/failures | 3.56s | PASS, 23.33s |

The latest base had 125 registered Full files (121 Quick + four Full-only), not
the FR's inspected earlier 124. They remain unchanged by this delivery. Native
Web cases skipped on Linux execute in their retained platform selection; legacy
terminal-only Windows shell cases remain available locally but are intentionally
no longer hosted Web acceptance. Full/native JSON retain complete names/counts,
skips/durations and sanitized failures; Checks may expose only some individual
skip notices. Image/tool facts and historical records are preserved in the
updated current CI scope document.

Baseline 41516683348 repeated Full/validation for combined 13m17s; this run did
it once in 86.65s, plus 87.90s combined focused native selection/smoke. Whole-job
combined execution was 4m47s versus 16m58s in that baseline. Different images,
revisions and OS assignments: observed work reduction, not controlled benchmark,
fixed savings, billing estimate or wall-clock guarantee.

Local Windows checks also passed: 13 deterministic CI accounting/OS-boundary
tests, and all 12 `native-web` groups in 16.1s. No hosted portability repair,
test exclusion, loosened assertion or increased timeout was needed.

## Decision authority and remaining limits

The **Decision Delegate** explicitly authorized one production browser handoff
per confirmed disposable native runner, not local workstation UI, profile/account
discovery, registration changes, physical clicks or additional browser automation.
ACCEPTED is only the OS handoff result: browser process, default-browser page
load/first paint, consumer desktop, physical tray/menu acceptance, Finder/Explorer
double-click, Gatekeeper and accessibility remain unverified. Shared headless
Chromium proves only its own rendered-page scope. Real source/model/provider
work remains intentionally excluded; Web remains Beta.

The **Decision Delegate** resolved inherited workstation/version-policy conflict
using the user's instruction, “Development-only edits need no product
tests/release/version work.” This scoped development-only delivery therefore did
not run unrelated local Full, Diagnostics, live-source checks, product version,
release or ZIP work. The FR's requested actual hosted Full/validator/browser and
all native architecture checks did run successfully; no requested hosted test
was waived or labelled PASS without execution.

### Documentation-head duplicate-check exception

After all four implementation jobs passed, documentation-only head
`26b5ca1fdcbef8ad6b938346a042e92cb5fbbc88` triggered duplicate
[run 41527754941](https://github.com/qstoffe/cost-guard/actions/runs/41527754941),
tested merge checkout `dbf7d079896b91a5bdd4351b2867fa58da353296`. Its Linux,
Windows and Intel Mac jobs passed; ARM64 job 125559763048 remained capacity-queued
with no executed steps at the decision, **not PASS / not verified at that head**.

The **Decision Delegate** explicitly authorized merge using the unchanged
implementation's successful ARM64 result from run 41526896465 at source
`232fb1ae73b47c1999f13779132c58ec2209bbac` (merge checkout
`be4ca4ee598b24e6d5ebaa523ad462d6b7cf15b7`), plus the three current-head successes.
This is evidence equivalence, not a queue-time threshold. This reporting-only
exception-note commit may also merge without waiting for newly triggered
duplicate checks; those uncompleted checks are not PASS. Executable content,
workflows, tests and acceptance scope remain unchanged. Any observed failure or
changed base must be investigated; no cancellation, retry or protection bypass
is authorized. Actual final statuses belong in the PR/final delivery result.

## Knowledge

Updated current CI owner evidence at
`development/architecture/governance/verification/web-beta-ci.md` and reusable
Web journal routing/topic at `development/journal/web/INDEX.md` / `ci-scope.md`.
Historical successful/failed evidence remains attributed to its original source.
No architecture diagram/dependency-contract update: runtime owners and existing
workflow activation intent remain unchanged; no permanent release gate added.
