# Token Mix period controls and compact grids — FR000705

2026-11-14; v81.49. This is scoped implementation evidence, not a fresh audit of
unmodified reports or an independent reconstruction of private historical usage.

## Semantics and ownership

- Web `ReportRequest.token_mix_scope` defaults to `all`, independently of Stats'
  `30-days` and Sessions' `today`. Explicit initial `?period=<id>` is supported.
  The request value participates in existing finite-job/dispatcher identity;
  existing source, timezone/config and catalog dependency qualification remains.
- `reports/token_mix_history.py` deduplicates canonical physical calls before
  selecting request completion/event times, using the same local-day/month and
  rolling windows as AI Stats. Valid child calls are not gated by parent-prompt
  start. Every summary, model/publisher row, prompt/call count, share and category
  cost uses that same selected population. Future calls are excluded from Web
  scopes. Undated calls stay in All time only, with a separate source-time warning.
- Revision-checked `token_mix_cache.py` facts and per-request category valuations
  remain reusable across periods; period selection neither rehydrates unchanged
  history nor recalculates prices. Cache/config/source/catalog validation and the
  existing bounded managed-history mechanism retain authority. CLI calls omit
  the Web scope and preserve their historical output/semantics.
- Browser scope changes abort only the superseded browser attempt, retire its
  result and hide its content immediately. Late admission/poll/finally callbacks
  cannot mutate the replacement. Same-period quiet refresh still retains useful
  values, row identities, independent sort states, focus and scroll.

## Presentation

The period row precedes Total Token Mix. Token Mix/AI Stats use Sessions' compact
main top padding; controls retain the shared wrapping/gaps/pressed semantics.
Both model and publisher tables have exactly nine columns, with Total CCost as
the only visible cost column. Shares still sort by exact integer ratios, never
tooltip cost; other numeric sorts retain integer/Decimal comparison and unknowns
last. One decorative arrow accompanies `aria-sort`; the Token Mix CSS override
now beats the shared pseudo-element's specificity.

Percentage-value help consumes server-prepared exact category reference amounts
in Credits/USD. Missing prices/usage remain explicitly partial or N/A, never a
fabricated complete zero. These supplemental tokens are opt-in for Token Mix
DTOs only: adding them indiscriminately to shared Watch mixes initially crossed
the existing 2 MiB 100-card replay cap by 430 bytes. Restricting the projection
restored that required test without raising caps or shrinking source evidence.

Model header help is removed; Publisher's manufacturer definition and meaningful
metric definitions remain, without sorting instructions. Heading help contains
only exact recorded/known tokens and actual configured-local period bounds,
including seconds/milliseconds and DST offsets. All time derives bounds from
available shown requests; undated/empty scope never gets an invented date.
Partial pricing/telemetry explanation remains on appropriate value targets and
source coverage stays separate from the concise heading.

## Verification

- Deterministic `test_token_mix_periods.py`: five independent expected request
  populations, midnight/month/rolling cutoffs, future exclusion, physical recapture
  deduplication, valid child usage, model/publisher reconciliation, prompt counts,
  unknown dates/prices/telemetry, >2^53 tokens, both DST changes and exact unit help.
  A warmed 40-root fixture forbids both hydration and repricing across all scopes.
- Existing cached/CLI parity, remaining-view and browser-attempt lifetime coverage
  is retained and updated for the intentional nine-column/title-help contract.
- Hidden Chromium `probe_token_mix.cjs` passes three themes at 360/800/1280/1920
  widths, 65 full readable rows in each grid, every column's two directions against
  independent exact expectations, one arrow after each sort, focus/Escape and
  hover/touch help, unknown/partial values and unit switching. Its period probe
  covers five scopes/deep link, superseded slow attempts, preserved sort/unit
  state, other pages' defaults and matching three-page control geometry.
- The browser uses synthetic data. Its Sessions controller is mounted without a
  Sessions source for geometry/defaults only; an unavailable HTTP state is not
  counted as source validation. Date help is tested under browser locale/zone
  changes with configured Stockholm/UTC and spring/fall/year boundaries.
- The existing ~five-minute refresh path is exercised by moving the lookup
  deadline overdue, not by claiming a fresh five-minute wall-clock wait.
  Physical OS input and screen-reader output were not measured.

Final local Full: **197 groups, 2,428 tests, zero failures**, 160.6 seconds; four
native macOS zsh/PTY checks are skipped on Windows, not locally certified. Final
validator: zero failures, seven existing advisory prose/design warnings. GitHub
common plus native Windows, macOS ARM and macOS Intel jobs passed on the initial
implementation commit. Final-HEAD checks are read again before merge.

An initial Full invocation hit the shell's 120-second outer timeout; a subsequent
run exposed the corrected Watch payload regression above and a version-test race
from editing metadata while that file was running. Neither initial run is counted
as a full PASS; the final complete run follows both repairs.

The initial strict/unmanaged installation probe encountered a retryable
`connection_timeout` at 178.15 seconds after hydrating 2,600 roots. It returned no
report, so no values or period correctness are inferred from that attempt. The
follow-up used the production managed Web partial-history/quantum path, retained
existing durable evidence and reported actual omitted-root/source status. No
OpenCode source mutation, paid inference or shared-service restart was involved.

### Real installation: managed Web reports

The completed read-only probe ran all five scopes through `ManagedReport` with
a 600-second per-report budget. Every job returned `complete`, no job/result
error, and nonzero known tokens:

| Scope | Seconds | Model rows | Publisher rows | Source status | Omitted roots |
| --- | ---: | ---: | ---: | --- | ---: |
| All time | 36.262 | 17 | 3 | partial | 1 |
| Today | 18.065 | 2 | 1 | acquired | 0 |
| 7 days | 17.958 | 10 | 3 | acquired | 0 |
| 30 days | 20.327 | 13 | 3 | acquired | 0 |
| This month | 19.732 | 12 | 3 | acquired | 0 |

All time's single omitted root remains **partial source coverage**, not proof
of complete private history. Its bounds came from shown dated requests. Today
and This month started at configured-local midnight; rolling bounds differed
by exactly 7/30 days in milliseconds, with Stockholm's DST offset reflected.
These production-path observations complement the deterministic independent
population oracles; they are not a manual reconciliation of every private
native request. Only sanitized aggregates are published here.
