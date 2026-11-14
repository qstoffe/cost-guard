# App-wide stable refresh — FR000703

Date: 2026-11-14. Scope: qualified last-good presentation, not new acquisition,
accounting, source history or refresh cadence. This extends
[quiet refresh](quiet-refresh.md); it is not a replay of the owner's private browser.

## Causes and fixes

- `application/session_catalog.py` erased known context whenever the source revision
  changed, before a replacement scalar observation existed. It now preserves the
  same-root/provenance value and exports `retained`, including zero. Incomplete
  context/model/effort observations retain their corresponding prior display/help
  fields. Qualification remains independent: a retained key cannot complete a new
  metric sort. Complete authoritative unknowns, removal, source changes and late
  revision rejection retain their existing meaning.
- `assets/watch.js::historyNotice` checked recent-finished demand before retained
  content. Real Earlier cards could therefore acquire an extra status paragraph.
  Retained content now wins, followed by observed/epoch-qualified empty history.
  Cold acquisition and real cold-source failure remain visible.
- `assets/mini.js` confused useful background history demand with eligibility for
  a physical status row. The latter additionally requires fewer than five real
  visible rows. Five real rows cannot acquire a sixth loading row. Existing
  running-first membership, finished fillers and internal history demand remain.
- Full and Mini share guarded context/session-summary retention. A missing pending
  value does not erase a known value; a source/root, context epoch, provider/model
  change or explicit invalidation still prevents inappropriate context reuse.
  Mini prunes per-session observations against certified populations.
- `assets/benchmark.js` no longer turns automatic refresh into visible Refreshing
  prose. An explicit toolbar refresh still reports its actual progress/failure.
- CLI `watch/coordinator.py::_advance` no longer publishes a transient Refreshing
  projection before each acquisition. Watching and actual source/provider failure
  feedback remain; the last rendered data survives acquisition.

No timer/CSS mask, new request, worker, persistent cache, dependency, source write,
credential change, inference, release archive or shared OpenCode stop is introduced.

## Loading-capable surface inventory

This inventory follows shipped renderers, subscribers and their publication owners,
not only the three reported strings. “Retain” always means eligible same-scope
display; it never authorizes a fresh sort, total, export or security decision.

| Surface / owners | Cold, explicit action and real invalidation | Ordinary populated refresh / regression route |
| --- | --- | --- |
| Sessions cells — `sessions.js`, `application/session_catalog.py`, `reports/session_summary.py` | Missing first scalar fields load; acquired unknown/zero stay distinct. Source/provenance/removal invalidate. Direct new sort needs qualified keys. | Retain independent context/model/effort display/help through revision/partial churn; never qualify retained keys as fresh. `test_stable_refresh.py`, catalog/period/effort suites and Sessions VM/navigation fixtures. |
| Sessions page/period/sort — `sessions.js`, `session_catalog_scope.py` | New period/page/sort may use scoped measured progress; Cancel restores the prior view, late generations are ignored. | Existing page survives passive polls and lease recovery; incompatible old membership retires before new URL/pager publication. Catalog/detail VM and `probe_quiet_refresh.cjs`. |
| Session detail/history — `session.js`, `application/session_detail.py`, `reports/session_history.py` | First acquisition/transfer has source progress; missing/archive/failure remains actionable. Revision-pinned chunks publish coherently. | `loading()` does not replace existing data; stable keyed rows/help, protected selection and attempt guards. Detail/liveness tests and quiet-refresh detail browser cases. |
| Full Running cards, context and session footer — `watch.js`, card/context/session-cost owners | New session/prompt has independent unknowns; explicit context invalidation is truthful. Source-owned tool identity/lifetime still clears obsolete details. | Shared context/summary helper retains missing pending fields, including zero. Card and disclosure identity remain keyed; cost qualification is not recomputed in JS. Watch/context/Live suites, `watch_refresh.cjs`. |
| Full Earlier — `watch.js`, `watch/history_publication.py` | No usable population permits initial loading; observed empty is stable; new source starts cold. Actual acquisition failure uses its established surface. | Retained cards win over recent-overlay/pending status. Producer retains one qualified epoch and atomically replaces certified membership; browser does not reconstruct history. Watch/history tests, `watch_refresh.cjs`, actual DOM/AX portfolio. |
| Mini/PiP sessions — `mini.js::Observations/drawSessions`, shared Watch helpers | Cold missing slots may show status; completed 0–4/empty populations do not restart loading. Source/instance resets observations. | Five real rows remain five physical rows; history-demand usefulness is independent. Same-session cost/context retain, certified absent identities prune. Mini VM, `mini_sessions.cjs`, real hidden Document PiP DOM/AX. |
| Full/Mini Today — `today_ccost.py`, `watch.js`, `mini.js` | New local day is cold; previous day expires at its configured boundary, including disconnected PiP. | Same-day atomic last-good survives independent daily/account/history work; true zero is real data. Daily/midnight/lifecycle suites and quiet-refresh portfolio. |
| Accounts and shared quota cards — `account-cards.js`, `watch/accounts.py`, native slot observations | Initial missing publication differs from verified empty. Provider/account/slot identity, expiry, auth/restriction/exhaustion remain factual. Daily cost is not borrowed from native quota. | Missing publication or failed empty read retains usable keyed cards/slots; actual warnings remain actionable. Account/period/quota suites and shared Watch VM; quiet-refresh route DOM/AX. |
| Models pricing — `app.js`, `cached-reports.js`, `render.js`, dispatcher | First/withheld result has finite progress; explicit price refresh has local toolbar status. Malformed future/source-incompatible results are not reusable. | Valid retained report/rows survive queued/running/failed refresh, preserving filters, sorts, focus and scroll. Models/loading/lifetime suites and quiet-refresh route matrix. |
| Models benchmark — `benchmark.js`, `web/benchmark.py` | First absent aggregate and genuine failure stay distinct; manual refresh still reports progress and result. | Automatic `refreshing` is silent; retained rows/date/filter/sort survive. `web_models.cjs`, benchmark tests and Models route matrix. |
| Token Mix — `app.js`, `token-mix.js`, `cached-reports.js`, report cache | Cold/invalid scope loads; known zero, intrinsic missing prices/telemetry and genuine unavailable remain distinct. | Same-scope accepted summary and both tables stay together through refresh; independent sorts/unit/pan survive. Token Mix/remaining/loading/lifetime suites and route matrix. |
| AI Stats — `ai-stats.js::remember`, `app.js`, Stats jobs/dispatcher | Unready cards contain only Loading; actual blocker is page-level. Source identity/generation/timezone and period readiness qualify reuse. | Only newer ready period observations replace eligible last-good results; partial attempts cannot erase ready cards. Stats/recovery/resume/loading/lifetime tests and route matrix; preserves FR000689. |
| Comparisons — `comparisons.js`, `app.js`, matched-input reports | Deliberate page navigation may load; rejected pin rebases explicitly; certified no-match is real empty. Request/match identity remains canonical. | Retained groups survive automatic refresh without passive status; attempt/pin guards reject abandoned results. Matched-input/loading/lifetime tests and route matrix. |
| App/Live source and transport — `live.js`, `app.js`, `data-demand.js` | Terminal host/auth/source change and real offline errors retain established feedback. HTTP health is not source readiness. | Sequence/instance/gap recovery retains eligible publications; ordinary source retry adds no passive populated-view caption. Connection/Live/runtime tests and quiet-refresh health cases. |
| Settings and Mini opening — `settings.js`, `mini.js::Controller` | Explicit save/open/cancel/fallback/error feedback is deliberate action progress, not a data refresh. | Settings has no periodic data-loading surface. Existing controls, save rollback and PiP lifetime tests remain applicable. |
| CLI Watch — `watch/coordinator.py`, `presentation/watch.py`, `presentation/token_mix.py`, accounts | Initial daily Pending, first-source waits and factual recovery/auth/error status remain. One-shot report/bootstrap progress is initial acquisition. | No passive Refreshing projection before ordinary `_advance`; same-day totals and buffered rendered frame remain. `test_stable_refresh.py` plus Watch/rendering/daily/source-recovery suites. |

Remaining text matches were classified rather than globally deleted: finite report
acquisition stages, startup/launcher progress, help-controller internal pending
tickets, first-source waits, account error recovery, and the AI Stats descriptive
trait “A quick quest. Refreshing.” are not recurring populated-data placeholders.

## Verification

### Deterministic and rendered causal evidence

`test_stable_refresh.py` exercises cold → 42k → repeated revision/partial retention
→ 47k → zero → authoritative unknown, sort qualification, independent model/effort,
failure, changed provenance/removal and late result rejection. Its CLI case executes
three actual `_advance` cycles. Five focused tests passed.

`watch_refresh.cjs` exercises the shipped Full View with recent overlays, three
history epochs and loading/refreshing/retrying/observed/unavailable, retained row/card
and disclosure identity, coherent verified promotion, cold/error/observed-empty,
independent footer retention, zero and explicit invalidation. Mini fixtures assert
physical row counts and completed 0–4 populations. Models fixtures distinguish
silent automatic refresh from explicit manual progress.

The first Full run failed three obsolete expectations: same-session known Mini cost
was expected to become Loading, and two suites treated a bare null context as
authoritative invalidation. Independent cold identities and explicit invalidation
now model the intended cases; all three focused suites passed after correction.
The new Full View fixture runs last so its VM window listeners cannot overwrite
earlier fixtures. Final Full passed **194 isolated files / 2,417 tests**, with
2,413 passed, four native-macOS shell/PTY skips, zero failures/errors, in 163.7 s
with four workers. The new five-test regression group is registered in Quick/Full.
Package validation passed all 11 checks, zero failures, seven existing advisory
prose/module-size warnings; no cap or baseline was raised.

The first `probe_web_help.cjs ... --stable-refresh` run passed the 18 controlled
Full/PiP frames (three epochs × six states), physical five-row bounds, DOM identity,
expansion, geometry and AX checks, then completed the nine-route theme/width matrix.
The overall run nevertheless FAILED at an obsolete promotion-help literal. Its
strict expectation now includes existing native tiers/promotion/Token Mix content.
Later runs also passed the rendered Sessions sequence (cold → 42k → repeated
retained → 47k → zero → authoritative unknown) with stable row/help/focus/scroll.
The promotion continuation exposed an unsafe outside-dismiss point: (2,2) actually
navigated to Settings. A neutral owned test target now exercises real touch
dismissal without activating navigation. The overall portfolio remains **FAIL**
at the later mixed-input promotion hover; unreached promotion cases are **NOT RUN**.

The focused `--promotion-help` run retained the original same-node Classic
360 → 1366 → 1920 journey. Pass-through instrumentation recorded a trusted mouse
arrival on the exact connected trigger with native hover true, then false from
the unchanged production 600 ms `matches(':hover')` guard. No intervening pointer
departure or focus loss was recorded. Logging neither changes the return value nor
forces the panel open, and restores the target method/listeners afterward.

Decision Delegate then directed a fresh-document `--promotion-isolation` control:
Classic 1920 throughout, one retained trigger, two ordinary keyboard/Escape/blur
and single-arrival hover cycles before touch, followed by the existing touch/open/
outside-dismiss sequence and a third hover cycle after disabling touch emulation.
Both pre-touch cycles **passed**; the post-touch cycle **failed**. At arrival and
the guard the trigger bounds, viewport/scroll offsets and hit-tested descendant
were unchanged; the guard's actual native false result was read before geometry
diagnostics. Identity, connectedness and document focus remained valid. This
isolates a mixed-input-dependent failure without proving its browser-internal
cause or a replay on physical hardware. Production help code/guards are unchanged.
The exact terminal-authorization feedback assertion previously located after
promotion was run independently in the focused harness and **passed**.

A second Delegate-directed control enabled touch emulation once before the first
input and left it enabled through all three fixed-1920 phases. Again both pre-touch
hover cycles **passed**, touch/open/outside-dismiss **passed**, and post-touch hover
**failed**. Delivered mouse events remained trusted `pointerType: "mouse"`, not
converted touch. The same unchanged bounds, offsets, identity, focus and descendant
hit were recorded while native hover changed from true at arrival to false at the
guard. Thus repeated capability toggling is not required for this failure. Its
browser-internal/physical-hardware cause remains unknown; no production hover
guard was weakened and no diagnostic failure is relabeled PASS.

**Decision Delegate authorized scope-limited FR000703 completion**, excluding the
demonstrated ancillary mixed-input promotion-help failure. The independently
tested retention fixes remain useful; this non-refresh reproduction does not
establish a retention regression, and weakening shared hover safety is unjustified.
The observed failure, distinguishing experiments, unknown cause and safe future
acceptance are published in existing
[Suggestion000684](../../backlog/suggestions/000684-mini-help-mixed-input-hover-opening/SUGGESTION.md),
not a duplicate or a journal-only omission. No On Hold or further mixed variants
are required. This is an exclusion of a failed interaction check, not a statement
that mixed-input help works, and does not waive later tooltip requirements.

As required by that decision, separate keyboard/mouse and touch journeys each
**passed all nine** Classic/Web-light/Web-dark × 360/1366/1920 configurations in
Chrome 157.0.8103.51. Each used one fresh document for the entire journey, retained
the exact trigger across cases, and preserved strict content, bounds and named
dismissal assertions. No identity change or browser exception was recorded.
Terminal authorization feedback also passed in each. These results prove only
their named interactions; the original mixed portfolio is still **FAIL** and its
unreached mixed cases **NOT RUN**. The earlier real-source Mini/rematch exception
below is unchanged. No final global reacquisition or Full rerun was needed for
these test-driver-only diagnostics; validator remained 11 passes/seven advisories.

### Real-installation evidence and limitations

Read-only Sessions observation passed against V2: 3,214 roots, six eligible Today
roots, 6/6 indexed, exact Ctx sort ready, 14 shared-lane attempts, zero retries,
first page 0.12 s, one-row/one-chunk complete detail 1.928 s. Context formatting,
states and provenance were checked without exporting private context values.
No model calls were started. Natural arrivals and the owner's exact incident were
not observed.

That combined probe later failed because concurrent product edits tripped its
source guard. A subsequent background Watch run left no usable output and is
unknown, not PASS. A foreground unchanged-source Watch observation timed out after
90.9 s at 625/3,214 history roots: no host/source failure, 219 Live publications,
354 captures and 193 history batches; complete global history was not established.
Two slow provider-quota threads were recorded at cleanup, not claimed exited.

Decision Delegate directed the supported serial-first real-history oracle with a
900-second observation cap, no competing heavy probes or guarded-source edits.
It independently validates the exact first product certificate's source epoch,
complete membership, revisions and ranked prompt identities. Actual outcome:
**INCONCLUSIVE**, original browser journey **FAIL**. Reference preparation took
355.95 s; the first product certificate covered **3,216/3,216 roots**, five cards,
at 404.48 s of product acquisition, with 703 Live publications and no concurrent
reference refreshes. Independent refresh matched that exact first certificate
in 1.37 s. Full's five identity/prompt/finish/order DOM checks completed.

The later private browser wait failed without a browser exception. Its precise
predicate is not retained by the redacted failure. The old harness incorrectly
required Mini to contain all five historical winners, ignoring running-first
membership, and assumed absolute finish clocks despite relative-age/start display.
The harness now uses an independent canonical-publication expectation, not rendered
rows or the product selector. Mini regression fixtures demonstrate why a running
representative displaces one historical filler. This does not retroactively make
the failed original journey pass.

The separate supported `probe_mini_fit.cjs ... 1 1 history-only` run **passed**:
actual authenticated HTTP/SSE, Full five historical cards versus Mini one running
representative plus four historical fillers, DOM/AX, cold loading, silent
refresh/failure, source switch and stable PiP bounds. Source data is synthetic;
the browser is real hidden Chrome 157.0.8103.51.

**Decision Delegate approved a minor scoped verification exception** after reading
both artifacts: no repeated complete global acquisition solely for the remaining
corrected real-source Mini journey (including activity/order and hidden-opener
checks) or post-browser independent rematch. Those checks are **NOT RUN**. Successful
first-certificate/Full evidence plus the distinct narrow mixed-population proof
and causal regressions justify this bounded omission, not equivalence of synthetic
and real-source evidence. Simultaneous live-source Mini correctness and
end-of-browser source consistency remain unestablished. The original wait's exact
predicate and final scalar-validity loss remain undetermined; the final
3,215/3,216 summary does not itself prove source churn.

The oracle retained 992 publications, maximum gap 6.24 s, no recorded reference
failures/epoch invalidations, unchanged source guard, closed reference reader,
stopped host/Live threads, zero owned processes/threads/parked children and no
cleanup failures. Its 882.30 s elapsed time includes reference and browser work;
this is neither cold-performance evidence nor an overall oracle PASS. The
Delegate exception waives no product behavior, qualification, invalidation or
error requirement, and does not cover the still-pending promotion portfolio.

Synthetic browser publications establish causal rendering, not every possible
real failure, an owner-incident replay, physical desktop/macOS geometry, spoken
screen-reader behavior, OS-cold performance or natural arrival latency. Retained
source facts remain retained, never reported newly acquired merely because a
browser/HTTP request succeeded.

Task-owned evidence: `scratch:/stable-refresh-live.txt`,
`scratch:/stable-refresh-browser.json`, `scratch:/stable-refresh-full.json`,
`scratch:/stable-refresh-history-mixed.json` and
`scratch:/stable-refresh-history-oracle/`, plus
`scratch:/stable-refresh-promotion-trace.json`,
`scratch:/stable-refresh-promotion-isolation.json` and
`scratch:/stable-refresh-promotion-capability.json`, with separate passing
`scratch:/stable-refresh-promotion-mouse.json` and
`scratch:/stable-refresh-promotion-touch.json`. These logical locators are local
sanitized evidence, not bundled private records or portable artifacts.
