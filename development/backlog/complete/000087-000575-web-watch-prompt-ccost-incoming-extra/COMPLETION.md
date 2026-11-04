# FR 000575 completion — 2026-11-04

Implemented in v80.155. Both full-Watch prompt tables show **CCost (I + E)**,
total first followed by the existing canonical Incoming Context CCost + Extra CCost.
All amounts use immutable shared Credits/USD tokens. Accessible header help explains
the three amounts, order, addition, provenance and distinction from Token Mix Input.
Existing intrinsic sizing, one-line cells, Prompt-only ellipsis and horizontal scrolling
need no CSS changes. Mini Watch remains total-only; accounting and acquisition are unchanged.

## Availability decision and remaining scope

The foreground **Decision Delegate** (`ses_e57fd1c42ffecYineOX8mGu29t`) authorized
independent report-owned component-evidence flags and the resulting full-Watch-versus-CLI
display difference for incomplete token evidence. Missing first-request input/cache-read/
cache-write counters withhold I; missing I/C/W/O categories on any attributed request
withhold E independently. Existing pricing/provisional nulls remain unavailable. Numeric
canonical diagnostics and total valuation are unchanged; JavaScript never computes costs.

Reason: existing completed CLI diagnostics normalize missing counters, sometimes producing
a zero Extra value without supporting telemetry. Full Watch must not present that as
measured zero. This is an FR-scoped availability decision, **not a test or truthfulness
waiver**. Correcting the underlying CLI/valuation missing-counter semantics remains outside
this delivery. No future authority or owner approval is inferred from the decision.

## Verification

- Final code: `py -3 development/tools/run_tests.py --suite full` — **140 file targets,
  zero failures**, four isolated workers, 84.3 seconds. Includes canonical raw-cost parity,
  cache-heavy/multi-call/model-switch/linked-child use, completed/active partial evidence,
  independently known I/unknown E, coverage corrections, supported zero, pricing unknown,
  both tables/units, sparse compaction and unchanged CLI/Mini regressions.
- `py -3 development/tools/validate_package.py --working-tree` — **11 passes, zero
  failures, six advisory size warnings**; product version/date consistency passes.
- Hidden Edge **156.0.4314.58** — **12 passing cases**, Classic/light/dark ×
  2560×1080, 1920×1080, 1366×768 and 360×800. Includes 100/150/200% text size,
  complete metric cells, Prompt numbering, horizontal panning, both units and native
  focus/click help. Classic desktop and light narrow screenshots were inspected.
- Final fresh read-only V2 probe `probe_web_live.py --watch-cards --prompt-cost` —
  three raw costs match a four-call CLI session prompt and reconcile; one Live owner,
  two advancing verified SSE streams, one active/two historical one-row cards, at most
  four capture jobs, no tracked owned threads/multiprocessing children or cleanup failures
  after close. No inference, visible desktop action or shared OpenCode stop.
- Actual LiveConnection/DOM regressions check accepted cost changes in the same keyed
  row and stale-event rejection; the existing reconnect/gap path retains accepted values.
- [Sanitized evidence and limitations](../../../tests/evidence/watch-prompt-cost/verification.json).

Natural real-source correction timing, physical touch, screen-reader use, every native
page-zoom/platform combination and macOS were not independently demonstrated. Controlled
updates/coverage corrections are deterministic evidence, not a claim of natural timing.
Daily cancellation at probe shutdown is not a Daily verification campaign; tracked worker
cleanup is not an inventory of all OS helpers. No release ZIP or GitHub Release was built.

## Documentation and accounting

Updated current Web guide, README/version history, Web architecture/code map and the
[existing prompt-table journal](../../../journal/web/watch-prompt-tables.md).
The entire original FR bundle is preserved here. Delivery proposes ordinary count 26
and `lastOrdinaryId: fr/000575` at the existing maintenance state path; only merged
default counts it. No maintenance completion is claimed.
