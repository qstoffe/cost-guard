# Full Web Watch cards, reset display and context markers

Source revision: 678659f35bae71dddc0db987fcb1c5b41a58b8f3
Checked revision: 678659f35bae71dddc0db987fcb1c5b41a58b8f3
Last checked: 2026-11-05
Status: current

## Summary

Current evidence below describes this base plus FR 000586's presentation diff;
older sections retain their original dates and limits, not refreshed PASS claims.

## v80.167 — FR 000586 (2026-11-05)

The Full Watch cell alone overrides I/E when the selected unit's formatted total
is zero, preserving `?` and all raw/component evidence. Positive totals and unknown
totals keep their original availability semantics. Python-prepared Credits/USD
regressions cover observed/no calls, missing components, tiny positive amounts,
partial totals, unknown totals, repeat updates and unit round trips; CLI is unchanged.

The status audit covered card messages, active/Earlier placeholders, session cost,
daily acquisition/retries, accounts and the separate global Live health owner.
Brief operations retain coherent values quietly; initial neutral placeholders do
not claim observed empty data. Existing publication wakeups expose continuous
30-second delays without another timer/poll/SSE. Confirmed unavailable/partial,
pricing, provider/auth and global connection warnings remain immediate. Invalidated
context guidance is never revived by retained cost. Actual running-tool text stays.
Focal row/title success now requires `completed_successfully`; idle/unknown/abort/error
never implies green. Historical titles stay neutral and each concurrent card owns
its focal ink; backend grace and history membership remain unchanged.

## Evidence

Full passed 142 files / zero failures in 89.2s; working-tree validator passed all
11 checks / zero failures / six existing advisory warnings. Hidden Chrome
156.0.8078.80 passed Classic/Web light/Web dark × 1366/360px: exact retained card
heights, virtual sustained delay/unavailable/recovery, cost units, success/unknown/
abort/error/resumption, link focus/navigation, copy selection, no page overflow and
success contrast >=4.5. [Structured browser evidence](../../tests/evidence/watch-presentation/browser.json)
is synthetic publication/paint, not real-account end-to-end, physical desktop,
screen-reader, Firefox/Safari or macOS proof. Reproduce via
`probe_watch_presentation.cjs <absolute-Chromium> <owned-output-directory>`.

The independent read-only V2 `probe_web_live.py --watch-cards --prompt-cost --daily`
passed prompt CLI/raw cost parity (four calls) and daily reconciliation (651 requests,
18 prompts; complete prices, incomplete prompt attribution retained). One owner,
two advancing instance-bound streams, four one-row cards, four bounded pending
captures, preserved run origin. All owned workers closed; shared OpenCode untouched.
Shutdown instrumentation recorded an interrupted independent history read, not a
complete-source/attribution claim. No inference or provider mutation was started.

## Next investigations

**Failed ancillary proof / scoped exception:** the additional command with
`--session-cost` failed at `session_cost_observations.py:32`:
`assert reused.valued_requests == 0 and not reused.cache_written`, after revision
matching and total/report parity assertions succeeded. Actual valuation/write values
were not captured; cause and live-cache reuse reliability remain unknown. Concurrent
writes are only a hypothesis. Decision Delegate explicitly approved delivery of
FR 000586 with this unresolved ancillary failure once the focused live probe passed
(it did); no FR acceptance requirement or other applicable check was waived. The
HTTP-only probe does not execute the changed assets. Backend/cache and its assertion
were not modified or weakened. This is not a cache-reuse PASS or a blanket exception.

## Rejected hypotheses

Idleness alone is not successful completion. The failed cache assertion does not
establish a presentation regression, but concurrency has not been established as
its cause either. No unrelated cache repair was included.

## v80.165 — FR 000584 (2026-11-05)

`watch/tools.py` classifies each existing deduplicated physical call once, preserving
native/verified-script rules and cancellation precedence. Ordered `ToolOutcome`
tuples carry tool name, failed/cancelled category and count. Failure-only CLI/skill
counts remain separate; cancellation and combined counts derive from canonical
observation data. `live_projection.py` explicitly exports both totals and groups
for shared rows/cards, without raw outputs, command strings or another source read.

Full Watch appends every red outcome subset below its inclusive all-call groups.
Only an unidentified difference is shown for an older/partial aggregate; the
undifferentiated repeated total is removed. Header and list retain the same accepted
counts while either contains focus/selected text, then apply the next publication
together. Native disclosure nodes, focus and scroll remain intact. Expanded shared
help explains subset arithmetic, unknown evidence and direct failure-only skill
attribution. Only `.watch-running-tool` uses `--watch-running`; ordinary activity,
background work and independently red errors keep their established colors.

Regression coverage includes mixed success/failure/cancellation, cancellation-only,
unknown/nonstandard names, untrusted output/exit codes, call-ID copies, terminal
corrections/retention/expiry, child scope, skill separation, seven tool groups beyond
the compact cap, literal hostile names, unidentified differences, focus/selection
coherence and dynamic disappearance. CLI behavior is unchanged.

Hidden fresh-profile Chrome 156.0.8078.80 passed six synthetic cases: Classic/Web
light/Web dark at 1366×900 and 360×900. Native Enter disclosure, keyed/focus stability,
shared help/ARIA and Escape, all nine expanded rows, no injected markup, no page or
detail overflow, terminal hiding and exact semantic color equality passed. Classic
running ink was `rgb(255, 255, 85)`; background and ordinary names stayed activity
ink, with no running background fill. Representative Classic desktop and Web light
narrow screenshots were inspected. Reproduce with `serve_watch_summary.py
--tool-outcomes` and `probe_watch_tool_outcomes.cjs --browser <absolute-browser>
--output <owned-directory>` in `development/tests/integration/`.

The read-only real V2 probe `probe_web_live.py --watch-cards --tool-outcomes` passed:
one activity card, four evidenced failures, zero observed cancellations; all per-name
subsets and totals reconciled. One owner/two advancing streams, one active/two history
cards, max one row/card, four bounded pending captures; first rows at 4.441s. All owned
workers closed and shared OpenCode stayed untouched. Shutdown interrupted independent
account-history work; Daily completeness is not claimed. Real mixed cancellations
were not observed; deterministic canonical and synthetic-browser checks cover them.
No inference, personal profile, native desktop input, provider mutation or end-to-end
real-account paint is claimed. Integrated browser access was disconnected; hidden
Chromium supplied the adequate browser evidence without a requirement/test waiver.

Final product verification: Full passed all 141 files in 89.4s, zero failed files;
working-tree validation passed all 11 checks with six existing/advisory warnings
(README/Web guide/history prose and three pre-existing module design budgets).
No requirement/test exception or release ZIP was requested or performed.

The historical 450 CSS-pixel cap below is superseded by FR000566's
[scale-aware physical-width correction](watch-account-pixels.md). Historical DPR1
and root-font evidence is not proof of a 450-physical-pixel cap at Windows150%.

## v80.142 — FR 000562 (2026-11-03)

`watch.js` now places each finite quota's own observed-period CCost in numeric
parentheses immediately after Used, preserving native Used/Total and units.
Unavailable/unpriced cost is omitted; a known empty window shows (0). Focusable
provenance retains the specific window, numerical independence and partial/estimated
attribution. Reset is the first detail directly below its matching bar, then pace.
Today/global daily scopes, acquisition, accounting and Mini are unchanged.

`live_projection.py` adds a full-Watch-only `context_cell`, explicitly matching
canonical guidance's owner ID. Its current continuation tokens include hidden
compaction/epoch invalidation; unrelated rows retain their own numbers without a
borrowed warning. The old `live_context` is unchanged for Mini. Full Context numbers
have no approximation prefix; approaching/exceeded use the same gold/orange triangle
and retain the complete footer. Focusable named icons describe severity and reference
that footer. In-place updates prevent focus/selection from freezing a stale warning.
No browser threshold calculation or new analysis/acquisition owner is introduced.

### Measured browser geometry

Windows headless Edge 156.0.4314.58, current assets, synthetic loopback fixture,
Classic/Web light/Web dark: all 12 viewport/theme cases passed. Every account in
each case had these widths (CSS px):

| Viewport | Default 15px root | 150% text (22.5px) | 200% text (30px) | Singleton/default |
| --- | ---: | ---: | ---: | ---: |
| 360 | 315 | 300 | 285 | 315 |
| 1366 | 450 | 450 | 450 | 450 |
| 1920 | 450 | 450 | 450 | 450 |
| 2560 | 450 | 450 | 450 | 450 |

Restoring the former effective 30rem rule/max-width behavior in actual DOM layout
at 150% text reproduced **675px** desktop cards in all themes. This explains a
plausible 670–680px overgrowth mechanism, not proof of the owner's exact browser
configuration. New grid tracks and card caps both use 450px; narrow cards shrink.
Font enlargement is text-size emulation, not physical browser zoom; viewport scale
and device-pixel ratio were 1. Browser zoom may enlarge physical pixels while CSS
pixels remain the layout unit. No page overflow or clipped account text occurred.

At the default root, bars measured **12.4375px** (.83rem), versus the previous
18.75px: 66.3% of their former height. Track radius is **2px**, with matching
Chromium/WebKit/Gecko fill selectors. Primary Reset gaps were **3.75px** and
secondary gaps **0px**. The probe checks per-window native/cost currency independence,
aligned subgrid tracks, singleton cap, exhausted/partial/unlimited/reset recovery,
theme contrast, keyboard focus, warning transitions and ownership, unknown compaction,
multiple rows, preserved selection, history transitions and 100-card layout.
Representative Classic desktop, Web light subscriptions and Web dark mobile
screenshots were inspected. Firefox/Safari engines, physical zoom, screen readers,
native desktop input and real-account browser paint were not executed or claimed.

### Real installation and verification

Fresh `probe_web_live.py --watch-cards` passed against read-only V2: one owner,
two advancing streams, three accounts, preserved run origin, one active/two history
cards, three cards with rows, one row/card and four bounded pending captures.
First rows appeared at 6.459s. All owned workers closed without cleanup failures;
shared OpenCode was untouched. Shutdown interrupted account-history work, so Daily
publication/completeness is not claimed. No inference, quota manipulation or extra
provider polling was added. Synthetic browser and real-source HTTP proofs remain
complementary, not an end-to-end real-account UI claim.

Focused tests cover exact thresholds/disabled approaching, per-window identity in
reversed source order, known zero/unavailable/unpriced/partial/estimated cost,
compaction/epoch changes, owning versus unrelated/concurrent rows, and rejection
of older captures/generations. Full passed all 133 files; the working-tree validator
passed all 11 checks with six advisory/pre-existing warnings. No requirement/test
exception, release ZIP, model call or provider mutation was requested or performed.

## Retired presentation measurements

FR 000560's superseded geometry remains in Git history, not current proof.
