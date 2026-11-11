# Linked headings and independent daily accounting — FR000675

2026-11-11, v81.25; implementation base `f03326dc029c72d70bb8f2fcc902e5ebcdb0983d`.

## Reproduced cause and bounded repair

The shared Web subscription card's failed/stale native-quota retention path spread
the **entire previous account DTO**. That unintentionally retained CCost Today,
its explanation and attribution fields along with native quota slots. A regression
using separate immutable publications reproduced old Today `13` surviving a new
daily `0`; positive and unknown transitions were affected too. This can produce a
stuck daily value independently of correct source/history/reference accounting.

`account-cards.js` now retains only native primary/secondary slots, with no stale
forward pace, while accepting the incoming independent accounting fields. Native
quota failures cannot freeze fresh Today values or their explanation. This is a
reproduced defect, **not proof of the owner's particular private midnight incident**.

The source/analysis/report/Watch daily pipeline needed no competing provider-alias
or midnight arithmetic patch. FR000673's exact Claude Agent reference identity and
qualified Claude subscription compatibility are reused unchanged. No price, billing,
account discovery, quota polling, authentication or source history is rewritten.

## Midnight and attribution trace

Synthetic source-shaped completed requests flow through causal normalization,
source-tree revision/cache acquisition, `WatchHistoryAcquisition`,
`PeriodCCostIndex`, `_period_scopes`, immutable `AccountPeriodHistory`, Web's
background account lane and application display tokens. CLI `WatchTodayCCost`
independently acquires/retains its daily history using the same canonical valuation.

Explicit Stockholm midnight instants cover winter, summer and the spring DST date;
UTC supplies the second-zone control. At 23:59:59, prior usage is positive. At
00:00:00, no eligible new-day usage yields **zero**, without carrying yesterday's
cost. Requests started before midnight but completed after it contribute to the
new local day. Subsequently published priced requests produce independently checked
Copilot Pro+ / OpenAI Pro Light / Claude Pro reference values of **1 / 2 / 12 credits**
($0.01 / $0.02 / $0.12) and global **15 credits**, from explicit synthetic $1/$4 per
million input rates. These are test rates/requests, not executed model costs.

Changed source revisions admit late telemetry (global 15→16); unchanged completed
roots avoid rehydration while active old roots are still rechecked. Missing history remains unknown. Mixed unpriced requests preserve
known subtotals/completeness; zero-token requests are valued zero, not unavailable.
Unknown-provider work can increase global Today without increasing a known account.
Unassigned usage with two same-provider accounts stays ambiguous; exact references
allocate only to the matching account. Fork/child physical duplicates do not add cost.
Existing tests also retain 23/25-hour DST days, account windows, deduplication,
partial telemetry, unavailable prices and rejection of old-day background results.

This establishes legitimate empty-day rollover and one independent stale-card defect.
It does not establish that every reported zero/N/A had the same cause. Supported
Opus pricing is verified without converting truly unpriceable work into a fake
positive value. Existing overnight explicit-date label policy remains unchanged.
The owner's original clock observation and unseen request/account route cannot be
retrospectively reconstructed from this work.

## Heading ownership and accessibility

`render.js::accountHeading` adds a small outline SVG before a separate bound text
span **inside the existing trusted anchor**. Static destinations, exact account
text, safe external attributes and purpose/new-tab accessible naming are unchanged.
The icon is aria-hidden and nonfocusable; unknown providers have neither icon nor
link. Inherited stroke, modest em sizing/gap and inline flex retain centered,
wrapping headings without extending navigation to header padding or the card.

Track redraws previously reconstructed/detached the heading. The shared card now
keeps that node attached and replaces only the other slots, preserving actual link
focus and one icon. Native quotas, accounting and icon rendering remain independent;
Mini Watch has no new icon/UI change. No new dependency or layer boundary was added.

## Verification

- Focused regression first reproduced the stale immutable-publication failure;
  after the repair, 38 daily/account/remaining/quota-lifecycle tests passed.
- The new source-history midnight matrix passed, including late revision/catch-up,
  explicit values for each provider and global/CLI Today, both display units and
  unknown/partial/multi-account controls.
- Hidden Chrome157 actual host/HTTP/SSE Accounts/Full Watch passed nine canonical
  accounting publication phases in USD/Credits, including stale-quota zero→positive
  and unpriced/partial states. No inference was started.
- Normal-zoom heading checks passed all 48 route/theme/width/zoom/exhaustion layouts,
  visible centered SVG, wrapping, unchanged destinations, native keyboard focus,
  AX purpose, inert padding and separate icon/text/touch new-tab activation.
  The initial broader driver then failed an obsolete test-only assumption that
  the anchor's first child was a text node; its selection target now names the text
  span. This was not a product failure or a reason to weaken selection coverage.

- Full ran all **183 registered groups** in 149.0s: 182 passed. The sole failure
  was a version consistency assertion: its parent imported v81.24 before the
  metadata edit and its child read v81.25 after it. With metadata stable, that
  complete 11-test foundation group passed in 63.3s. No passed Full group was
  repeated; this is an aggregate repaired result, not an initially green Full run.
  The new two-test midnight file also passed and is now registered in Quick/Full.
  Extending that fixture to explicitly active previous-day sessions exposed an
  overstrict test-only reuse expectation: active/noncacheable roots correctly
  rehydrate. The assertion now distinguishes those three checks from unchanged
   completed-root reuse; accounting expectations were unchanged. The corrected
   two-test file passed on continuation in 1.15s across all four timezone cases.
- Working-tree validator: **11 passes, zero failures**, seven existing advisory
  prose/design warnings. No cap/baseline was raised. No release ZIP or GitHub Release.
- Additional 48-case heading matrix passed at **real Chromium 125% default zoom**
  (disposable profile setting read back), combined with 100/125% CSS zoom.
- The remaining full Accounts driver passed after correcting its selection target;
  already-passed heading checks were skipped. Capacity/grid/slot geometry, live
  selection/focus/help retention, real hidden PiP quota compatibility, both units,
  quiet stale/failed/empty/recovery states and one SSE/no finite route jobs passed.
  Narrow dark screenshot inspection confirms a restrained chain and readable title.
- Actual read-only V2/HTTP/Live probe: three accounts, one Live/account-refresh
  owner, **512 requests / 13 initiating prompts**, complete daily pricing and
  reconciled category values. Account projections were Copilot **zero**, OpenAI
  **positive**, Claude **positive**; per-account USD/Credits tokens were checked.
  This is an observation, not proof of unseen Copilot traffic or a paid inference
  test. Synthetic qualified new-day requests prove its positive path independently.
  Initial complete publication took 54.8s while Full/browser work overlapped;
  this is not a latency guarantee. A first complementary probe published 443
  requests in 6.7s. Cancellation during owned-host shutdown can record an in-flight
  history operation error; both probes closed their owned workers successfully,
  with no pending owners or shared OpenCode stop.

Artifacts: `scratch:/full-tests.json`, `scratch:/foundation-rerun.json`,
`scratch:/midnight-browser.json`, `scratch:/account-links-browser.json` (initial
broader driver failure after passed headings), `scratch:/account-links-zoom.json`,
`scratch:/account-compatibility.json` and its synthetic screenshots. No raw usage
history, credentials, account IDs, private prompts or titles are published.

On continuation, a shell artifact-summary command was refused with
`SCRATCH_SESSION_BOUNDARY`. No environment/root override or retry was made.
Decision Delegate directed bounded supported reads of exact helper-resolved owned
artifacts; those reads succeeded. This was an evidence-access routing decision,
not an acceptance waiver or a new test result. The fetched default advanced only
by backlog authoring (`aee90d3`), incorporated without product-code changes.

No acceptance exception was needed. Original private-incident reconstruction,
new live inference, physical desktop/assistive-technology and macOS behavior are
not claimed. Shared accounting is unchanged except for accepting its fresh Web
presentation independently of quota retention. Delivery is recorded in `COMPLETION.md`.
