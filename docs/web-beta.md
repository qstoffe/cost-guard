# Web Beta

After authentication, **Web Beta v…** shows the running server's CLI product version,
not a release lookup or newly edited source. Offline views retain their original version.

## Web settings

v80.120 groups exactly two controls under **Settings → Web settings**, at
`/#/settings`: **Theme** (Classic / Web) and **CCost display** (Credits / USD).
Classic is dark independently of system preference; Web follows system light/dark.
USD is reference token valuation, not billed spending. No CCost selector remains
on Models or other report pages.

Each selection saves immediately to `config/user-config.jsonc` through the private
authenticated/CSRF-protected API. Only confirmed success changes the loaded theme
or Python-prepared CCost tokens, including retained Snapshot/Live views. There is no
reload, report/history/pricing/account acquisition, host restart, Apply button or
browser-local preference. Both dropdowns disable briefly during a write. Failure
restores the last confirmed choices and shows an accessible error; select again to retry.

```json
{"webSettings": {"theme": "classic", "ccostDisplayUnit": "credits"}}
```

The enums are exactly lowercase `classic|web` and `credits|usd`. Missing overrides
inherit the shipped Classic/Credits defaults without creating a user file.
Theme precedence is explicit user `webSettings.theme`, then legacy user `webTheme`,
then Classic. Legacy `webTheme` remains accepted and is never destructively migrated;
subsequent Theme changes write the nested key. Web CCost independently defaults to
Credits even if the original CLI `ccostDisplayUnit` is USD. The CLI key and its
`--ccost-unit` override keep their behavior and cannot override a Web choice.

Reload/new tabs/relaunch read confirmed file values. Theme is in the early HTML;
CCost is read before report/Live presentation. Reopening Settings recognizes valid
external edits, without polling or automatic cross-tab broadcast. Existing tabs
retain confirmed values until their next settings read or successful change.

Only these two nested fields are writable. A setting stays shared while Web only
consumes it; promotion to an editable Web control requires a separate approved
feature and an independent value in `webSettings`. No other settings migrate here.
CLI `colorScheme`, custom palettes and unpromoted shared settings are unchanged.
Minimal JSONC edits preserve other preferences, legacy keys, comments/order and CLI
palettes. Invalid/ambiguous JSONC, links/reparse points, hard links, permission errors,
files over 1 MiB and detected editor conflicts fail closed. Private same-directory
temporary files and atomic replacement protect ordinary edits, not hostile same-user
races. Defaults, OpenCode, credentials, accounts, prices and reports remain read-only.

## Unified Models

v80.118 replaces Overview and the old separate Models view with **Models** at
`/#/models`. Legacy `/#/overview` and `/#/models/all` bookmarks replace their current
history entry with Models. Bootstrap credentials are still erased before requests.
The four-column table spans the available content width: **Publisher | Model |
Relative CCost | Release date**. All matching rows scroll with the **document**, never
an independently scrolling/fixed-height table body. Narrow screens can pan the table
horizontally; long names wrap without truncation. There is no model search, pager,
catalog-tab strip, native-rate fifth column or subscription card on this page.

Two independent checkboxes reset on every fresh page load:
- **Show all Copilot-priced models**, off: intersect the parsed priced catalog with
  the selected installation's global OpenCode selectable list. This is not separately
  verified subscription entitlement. Unavailable/unreliable availability fails open
  with an explicit warning; a verified empty intersection is distinct.
- **Latest versions only**, on: hide only conservatively recognized older stable
  versions **within that candidate set**. Variants, preview/unstable and ambiguous
  names remain distinct. Turn it off to show older versions at normal text contrast.

The Web receives one frozen full-catalog snapshot with selectable membership and the
same global latest-100-completed-priceable-prompt sample. Its cheapest positive
comparable full-catalog base remains 1.0x in every filter state. Unknown ratios remain
unknown and visible, not zero. Toggling never reprices or reacquires history/accounts.
CLI candidate selection, ranking, denominators and Watch valuation are unchanged.

Default sorting is **Relative CCost ↓**. Every header toggles its single sort;
Shift+click or Shift+Enter/Space adds/toggles keys in priority order. Ordinary touch
sorts one column; there is no separate sort-mode control. Arrows and priority numbers
show active keys; only the primary header has ascending/descending `aria-sort`.
Relative CCost compares unrounded decimal base, then each later ratio, **before** a
secondary column; boundaries/operators/markers never rank prices. Dates compare
chronologically, text uses case-insensitive locale order, missing values are last
in either direction, and ties retain original order. Filters preserve chosen sorting.

First acquisition shows only branding/navigation and a centered progress bar with
one short stage line. Its **≈ percentage is a bounded stage-weighted estimate**, not
a measured global total; actual stage counts appear when supplied. It never moves
backwards or reaches 100 before a complete, usable source result. Failed/partial
acquisition stops activity and gives actionable feedback; missing data is not zero.
Completed units advance separate sample/account-history/preparation bands. Unknown
sampling totals stay estimated; blocked I/O can pause. No extra scan or timed advance.
Reload requests fresh Models; Back/Forward to a retained view and live host
heartbeats do not refresh its frozen report or reset its table scroll/selection.

Below the table, **More information** starts collapsed and contains CCost, Token Mix,
and the shared global latest-100-completed-priceable-prompt Relative CCost explanation,
followed by genuine **Price Promotion**
notices for shown markers. Genuine **New Models** notices sit above the table at the
left, with the two filters grouped at the right (wrapping on mobile). Partial and
unverified-source warnings remain explicit. **Accounts** retains full supported quota,
billing, subscription and attribution details and its canonical acquisition behavior.

Healthy connections have no visible status label or banner. An unhealthy loaded page
shows a compact, actionable warning with hover/focus/touch-accessible connection
details. A server that never served the page cannot display an offline page. The
global footer is removed; guarantees remain in relevant optional report help.

## Cost per Active Hour

v80.115 adds Web-only `/#/cost-per-hour`: **Today**, **Month to date** and
**Rolling 30 days**, plus a compact rate in complete session Snapshot/Live detail.
Use **Refresh snapshot** to capture period history explicitly. Opening/revisiting
the page never scans it. Progress, Cancel, the existing 120-second/8 MiB job bounds
and dependency-aware derived cache apply; Watch/accounts keep their own cadence.

Each scope shows reference CCost, active execution duration and rate with observation
time and complete/partial/provisional/unavailable status. Complete means complete
*observed* evidence, not recovered deleted/pruned history. Unknown or zero duration,
incomplete telemetry, unpriceable cost or known source gaps suppress the rate; true
priced zero with positive known duration can show zero. Running work is provisional.
Freeze preserves the whole-session rate, independent of the visible 50-row page;
source loss retains the last observation and never proves completion.

Python computes `CCost / (active milliseconds / 3,600,000)` using unrounded Decimal
inputs, then applies the shared credits/USD display policy: `CCost/h` or `$/h`
(100 credits = $1.00, two USD decimals). JavaScript only chooses prepared text.
Active time reuses qualified prompt, child, compaction, tool and background execution
boundaries, excluding idle gaps and unverified time. Clip to the window, then union
overlap within **and across** sessions: this is observed concurrent execution,
not summed agent-worker-hours. Distinct concurrent requests still each incur CCost.
Deduplicated request cost is allocated by its canonical event/completion timestamp;
cross-boundary requests are **not** proportionally token-billed.

Today/month use configured timezone boundaries including DST. Rolling 30 days is
exactly the preceding 30 × 24 hours at capture, not another calendar-month scope.
This is reference spending per active hour, not provider billing, a consultant
invoice or human hours/salary saved. No model selector, new CLI command/option,
provider/model call, browser persistence or durable history ledger is added.

**Settings → Web settings → CCost display** switches Python-prepared reference
amounts in place, without report jobs or provider refresh. Native money, quotas,
Unaccounted usage and Relative CCost stay unchanged. The saved independent
`webSettings.ccostDisplayUnit` applies across routes, publications and Snapshot/Live,
including reload/new tabs. No URL, browser storage or preference cookie is written.

v80.107 keeps healthy authenticated streams open without periodic rotation. Connected
status is now visually quiet; only actionable states show a notice, with expandable
host/source timestamps. See [real-source soak and fault evidence](../development/architecture/governance/verification/web-live-stability.md).

v80.106 fixes real-installation Normal results that exceeded the unchanged 8 MiB
limit because they carried unused month-wide causal request identities. Normal now
retains per-root revision evidence without that detail-only payload; no model rows,
account periods or totals are capped. Models renders every matching reference-model
row with document scrolling. Token Mix phase costs are available in More information;
account provenance is on Accounts.

Classic defaults to dark; Web follows system light/dark. Both use local fonts, visible
keyboard focus, sticky headings and narrow-table scrolling; reduced motion disables
transitions. “Reading this report” contains definitions, not rows/totals. Accounts keeps
native quotas, Remaining/Pace, known bills and independent warnings; observation/billing
detail is expandable. Models follows the hierarchy above.
See the [synthetic before/after gallery](../development/architecture/governance/verification/web-design/index.html)
and [visual evidence/limits](../development/architecture/governance/verification/web-design.md).

The Web shares CLI-owned numeric display primitives through server-provided display
tokens while retaining exact raw values for sorting. CCost, USD, quotas/Pace,
multiplier tiers and durations no longer expose incidental Decimal precision;
CLI all-model native reference rates intentionally retain every meaningful digit;
the retired Web native-rate column is not restored.
See the [display parity baseline](../development/architecture/governance/verification/web-display-parity.md)
for per-view mapping, role/notice semantics and explicit page-specific remaining work.

## Hosted revalidation

The optional **Web Beta revalidation** Actions workflow tests the delivered Beta on standard Windows x64 and macOS Apple Silicon/Intel runners, with manual dispatch and relevant PR/main triggers. See the [coverage matrix, cost boundaries and remaining manual checklist](../development/architecture/governance/verification/web-beta-ci.md). CI-only Python/Node/Chromium tooling adds no product dependency. Native API execution is not physical desktop/Finder/Gatekeeper or accessibility acceptance; macOS remains experimental. This is not a mandatory release gate or automatic promotion.

Run `python cost-guard-web.py --foreground` using already installed Python 3.11+. It binds **127.0.0.1 only**, on an OS-assigned port. There is no LAN/proxy mode, install step, frontend build or automatic browser launch in this explicit developer mode. Leave the console open. Ctrl+C or a detected runtime-source change stops only this host and its owned finite reports; it does not stop OpenCode. Foreground instances are intentionally separate from managed launcher discovery.

## Navigation and static reports

The Beta shell provides Models, global Watch, Accounts, recent Sessions with older-page navigation, local date/range Reports, explicit historical Token Mix, and session details with Snapshot/Live modes. Global `/#/watch` is canonical; legacy `/#/live` links replace the same history entry. Models and Accounts reuse the same normal-report observation when retained; presentation changes do not multiply account acquisition. Explicit Refresh on other views creates a new observation for that view, not a silent cross-view update.

Accounts uses the shared provider/account cards with native quota windows, known-only remaining bars, configured-timezone CLI reset wording, Pace, billed USD and Normal local-month/Today CCost. Unknown, zero, unlimited, blocked, partial, rate-limited and stale observations remain distinct. Stale quota values are visibly muted and labeled as last observations, not current availability. Native-money equivalents, Copilot Unaccounted usage and attribution notes remain visible; observation/used details expand through keyboard-accessible native disclosures. Classified method failures use readable labels; arbitrary private provider reasons/warnings and credentials remain excluded. No account editing or additional acquisition is introduced.

| CLI use case | Discoverable fragment route | Protected scope |
| --- | --- | --- |
| Global Watch | `/#/watch` (legacy `/#/live` alias) | One host-owned engine; one-prompt cards, five historical sessions and independent daily/account observations |
| Models | `/#/models` (legacy `/#/overview`, `/#/models/all` normalize here) | Independent selectable/full and latest-version filters, exact tier-aware multi-sort, four columns and full document scrolling. Blank relative cells without completed priced prompts; unknown ratios retained. No account cards or native-rate fifth column. |
| Accounts | `/#/accounts` | Native units/windows, Remaining/Pace, independent observations and method errors, report local-month/Today CCost and Copilot Unaccounted usage; never Watch rolling substitution |
| Sessions | `/#/sessions`, optional `/#/sessions?limit=20` | Immediate recent-first 50-root page, including available archived history; Previous/Next links carry offset/catalog revision. Optional N/all scope is collapsed under Advanced. |
| Session report | `/#/sessions/<id>` | Complete report Snapshot/Live detail; links from session lists and global Watch |
| Date / inclusive range | `/#/reports?date=2026-10-25`, `/#/reports?date=2026-10-24:2026-10-25` | Configured-local boundaries/DST; canonical range valuation and union duration; impossible/reversed dates fail explicitly |
| Historical Token Mix | `/#/token-mix` | Explicit Capture/Refresh only, never navigation/prefetch; CLI Input / Cached input / Cache write / Output share-and-CCost cells, model/publisher Prompts/Calls/Tokens/CCost, exact-volume sorting with compact K/M/B labels and explicit partial/unknown telemetry, full-report total above the table and optional sample/price coverage |
| Web Settings | `/#/settings` | Theme only; authenticated narrow config read/write, no report acquisition |

Outside Models and Watch, report tables retain their search/filter/page controls. Their column clicks cycle ascending, descending, then original server order. Models uses the independent filter/multi-sort contract above, with no three-click reset; Watch keeps fixed chronological cards without report controls. All controls are presentation-only: totals and source queries never change. Decimal strings compare exactly and unknowns sort last. Complete revision-paged session detail has its own controls; global search is disabled there rather than implying unloaded-row coverage.

Token Mix shows actual phase/completed/total progress and Cancel terminates only that finite scan. Reopening a retained view reuses its timestamped result; explicit recapture checks the real source/config/pricing dependencies through the existing derived-analysis cache (`src/reports/acquisition.py`, `src/analysis/cache.py`), not a browser ledger or request-name-only cache. Deleted/pruned history stays unavailable. Timeout/cancellation/empty history are distinct; Live and its account scheduler continue independently. Date prompt links open full session detail; Back restores the retained range. URL fragments contain only scope/locators, never prompt content.

Session-ID links open `/#/sessions/<id>`. Fragment routes support direct links, reload and browser Back/Forward without expanding the HTTP path allowlist. The one-use bootstrap fragment is removed before requests; ordinary session routes are preserved on reload. Names/prompts are text, never links or tooltips containing source paths. Navigation and paging never put prompt/history payloads in browser storage or history state.

Every result retains observation time, source status and per-root revision evidence; Models hides the verbose snapshot paragraph, not partial/error warnings. A running prompt is **running at that snapshot**, with frozen provisional values. **Refresh snapshot** reacquires other views; reload reacquires Models. Source events, elapsed time, navigation and paging cannot update a frozen report. Failed refresh preserves the last known result with **STALE** status. Missing/empty/partial/source-failure and independently unavailable accounts remain distinct from acquired zero.

The session table retains Prompt, CCost, Calls, Duration, ~Ictx, ~Ictx CCost, ~Extra CCost and Token Mix %. Category names and adjacent legends come from Python's shared display tokens: **I = Input; C = Cached input; W = Cache write; O = Output**. Input is uncached, Cached input is cache read, Cache write is cache creation, and Output includes reasoning. This order also applies to compact reference-price and Watch run fields. Full-session totals and main/linked-child breakdown come from the canonical result, never from the visible page. Unknown, incomplete and estimated amounts are labeled; a published Cache write price does not imply observed tokens. Catalog `Not applicable` is an unpublished rate, not measured zero. CCost is not billing. The browser performs no valuation or token attribution.

Most finite report tables show 50 rows per page from **one complete immutable API result**. Sessions instead requests at most 50 roots per Web page: catalog membership and CLI activity-descending/id-descending order are fingerprinted (including child activity/source identity), and only that slice is hydrated/analyzed. Totals count discovered available roots, not missing history; partial-source warnings remain visible. Each page's row values are observed separately, not an atomic cross-page snapshot. Search/filter/sort apply only to the loaded slice. Changed catalogs reject older-page requests with `session_catalog_changed`; Latest sessions / restart browsing discards cached list observations and captures a fresh first page. Previous/Next use ordinary fragment links, supporting Back/Forward and direct-link reload. The existing 8 MiB/120-second job limits still apply: oversized/slow pages fail explicitly. Session detail uses its independent bounded revision-aware contract below. Up to twelve views are retained only in page memory; reload/eviction requests a new capture, while Back to a retained Snapshot does not refresh it.

## Complete session Snapshot/Live

Models is the exception to finite-table paging: every matching row is present and
the document scrolls. Background connection-status updates
retain that frozen DOM, including scroll position, keyboard focus and text selection.

Normal `/#/sessions/<id>` links default to Snapshot; `/#/sessions/<id>/live` explicitly requests Live. The mode button switches without stopping the shared server. Entering Live queues an authoritative source observation, not event-only continuation of an old snapshot. Snapshot freezes the whole report, including running durations and totals; Refresh requests a new capture. Leaving Live freezes one consistent current revision. Idle, abort and prompt completion never end Live.

Session history reuses Python's detailed report projection, not Watch-only context/duration fields or browser calculations. All root-tree rows remain available, without a prompt count, Watch row cap, history TTL or durable ledger. First/Previous/Next and Jump to latest traverse 50-row pages; totals always cover the full observed report. Loading, observation time, missing/archive/outage and partial pricing remain explicit. A catalog absence is not proof of deletion: the last report remains readable. Rows omitted by source compaction/gaps retain canonical evidence, last-observed provenance and frozen lifecycle/time until observed again; source history deleted before observation cannot be reconstructed. No completion is inferred from connection loss.

Session controls say **Follow live** / **Freeze snapshot**; Refresh captures a new observation.
Summaries use the shared CLI CCost, money and duration tokens, never raw Decimal strings.
Prompt clocks use the configured timezone; Next Ictx and context warnings stay beside the
history. Whole-session child-cost breakdowns remain distinct from page totals. Technical
source/provenance and reading guidance are optional. Date/range explanations show inclusive
configured-local calendar dates, with links to full detail and browser Back to the frozen range.
The [owner-facing review matrix](../development/architecture/governance/verification/remaining-web-parity.md)
distinguishes deterministic/browser evidence and intentional CLI differences; it is scoped
Beta evidence, not a permanent gate or native macOS acceptance.

Pages carry a revision and canonical row identities. A stale cursor rebases to the existing anchor, never silently combines pages into a report. The client caches only its current 50-row page and retains keyed DOM nodes on updates. Scrolling up or focusing controls disables follow; Jump to latest re-enables it. Background updates preserve row anchors/pixel offset and defer row replacement during text selection. Copy/selection covers the current page, not unloaded pages; use paging to reach other rows. Real-browser layout, resize and assistive-technology behavior still require owner validation; VM checks are not visual acceptance.

Authenticated, CSRF-protected `/api/detail` POST actions: `open` (`session_id`, `mode: snapshot|live`) returns an opaque token; `page` takes token, nonnegative offset, optional revision/anchor and returns up to 50 rows plus full totals; `freeze` captures the live revision; `close` releases a handle. Detail polling is independent of SSE replay: every response is authoritative, so stream gaps cannot drop rows. One host-owned round-robin detail queue serves all tabs on an isolated single-worker lane, using fresh source/service integrations rather than borrowing Live's mutable service. It admits at most one due session per detail turn with five-second acquisition cadence; native account acquisition retains its single owner. Stable revisions reuse analysis; timer-only ticks do no detail acquisition/valuation. The session-local retained snapshot never enters persistent source/cache state.

Resource admission allows 16 distinct observed session trees per host and 32 transport handles. Abandoned handles expire after five minutes, but history does not; expiration is explicit (410), not an empty report or row eviction. Busy admission is explicit (429). Repeated refresh/mode changes release their old handle. Restarting the host discards observed history. Synthetic 100/1,000/10,000-row probes test complete first/middle/latest access, totals, page bounds, source omission/reconnect and unchanged work. `test_web_session_detail.py` also exercises real HTTP authorization and shipped assets in an optional Node VM, not a browser or model runner.

Layout choices: wrapping navigation, system light/dark palette, keyboard focus and skip-to-report. Other report tables keep sticky headings, search/paging and complete totals; Models alone uses document scrolling and its two filters. Shown older models have normal contrast. Refresh/status messages do not take focus. No frontend build, Node installation, CDN, analytics, account login or editing is needed.

`test_web_views.py` exercises the shipped JavaScript and real HTTP/facade with deterministic sources through an optional developer-only Node DOM harness. It tests navigation/hash events, reload, safe hostile/Unicode text, long/running/aborted/compacted/empty/missing/partial reports, complete totals and frozen/explicit-refresh/stale behavior. It is not visual browser, CSS layout or native macOS acceptance. Owner checks: open the Beta, try narrow/wide windows and light/dark mode, tab through navigation and page controls, select prompt text, follow a session link, use Back/Forward and reload, and Refresh a running session. No new permanent release gate is added.

## Global Watch and reconnect

The common shell distinguishes starting, connected, **SOURCE UNAVAILABLE** (HTTP works, acquisition does not), **RECONNECTING**, **OFFLINE — last observation**, **AUTHENTICATION EXPIRED**, changed host identity and **STOPPED — NOT LIVE**. Healthy status is visually quiet. Actionable non-sticky warnings expose host/source timestamps on hover, keyboard focus or touch disclosure. Account freshness and frozen report timestamps never become fresh merely because HTTP works. Stop/identity/authorization loss disables acquisition controls, ends retry and retains readable values. Use the OS launcher to restart or obtain fresh authorization; no host is started by the browser.

One authenticated `/api/live` watchdog runs at ten-second intervals after the preceding check completes; every ordinary request has a five-second deadline. Thus a reachable tab normally detects abrupt loss within fifteen seconds (browser/OS suspension can delay timers). `pageshow` and visible-tab resume revalidate; only stale checks (at least fifteen seconds) or interrupted streams first mark retained data as reconnecting. Healthy HTTP cannot restore a broken stream to connected. Same-instance EventSource retry preserves cookies, replay/resync and retained values. Authenticated API response identity is pinned per page; a replacement host is never silently accepted even if another tab renewed its cookie. No identity, token or report is persisted in browser storage, and no port/network scan or sensitive unauthenticated endpoint is added.

[Built-in browser, deterministic and real-source verification](../development/architecture/governance/verification/web-connection.md) records the tested states and explicit physical-tray/suspension/restart/macOS limits.

Watch uses unframed prompt cards. **Earlier Prompts** starts collapsed: five eligible
distinct sessions selected by newest actual prompt start, then displayed oldest first,
newest last, one latest prompt each with deterministic ID ties. It updates
while collapsed, without an age/startup cutoff, excluding active/recent sessions before
limiting. Its outlined container grows in normal page flow, with no nested vertical
scrolling or height cap. The active list has no cap/filter/pager; concurrent prompts
get separate cards, oldest focal first, with one row even during terminal grace.

Session title alone links to that canonical Sessions route. Watch has no session
aggregate cost/duration or dedicated aggregate acquisition; complete-session totals
remain available on Sessions. Canonical child/compaction/context evidence still feeds
prompt metrics. Credits/USD follows Web Settings. Valid metrics remain visible during
ordinary refresh; first acquisition, partial evidence and genuine failure stay explicit.
The nine columns are Started, Prompt, Model, Effort, CCost, Model Calls, Duration,
Δ Ctx and Context (estimated next incoming context using CLI Watch semantics).
Started uses the real sequence and configured-timezone start: `Prompt N HH:mm` while
active, `Prompt N YYYY-MM-DD HH:mm` in history. Prompt contains only actual preview
text, with the full preview on hover and lifecycle state accessible on the row.
Additional model contribution is identified on the Model field. All cells/headers
stay one line: Prompt alone flexes without a width cap and ellipsizes long text/URLs;
complete metric columns and a 14rem Prompt minimum pan horizontally when necessary.
Tables use theme-aware body/header surfaces and edges; compact dividers separate siblings.

Running focal rows and linked titles are yellow; historical/terminal titles use
neutral heading ink. Normal activity is gold/brown, failures independently red,
and context guidance severity-specific (gold/orange triangle, ordinary foreground
approaching text; gold/orange triangle and text once exceeded). Observed success is lime, abort/error red, for
`watchRecentEventSeconds` (30 seconds by default), then the session becomes
history-eligible when no other running/grace card remains. Old history does not
replay completion flashes. Active cards show count-first tool/custom-skill
summaries with five named groups and truthful other totals; native disclosures
expand every group and retain their state/focus across updates. The longest
running tool appears at the shared ten-second threshold. Tool and canonical
background/subagent lines explicitly start **Running:** and clear on completion.
Historical cards have no activity section. Narrow tables pan horizontally.

**Total Today**, four pixels above subscriptions, shows current-local-day reference cost,
initiating prompts and Input / Cached input / Cache write / Output shares/category costs.
It includes pre-Watch history, running requests and unassigned-account usage, not just
visible cards or subscription sums. Requests use completion/attribution dates; continuing
prompts count once per relevant day, children under their initiator, compaction as usage
only. The known integer displays **N prompts**, retaining incomplete attribution internally
and all unassigned cost/tokens. Missing telemetry/prices remain partial; empty differs from
loading. Source changes/minute fallback update retained history and publish cost/count/mix
coherently. Routine refresh silently retains figures; only a scope without valid data
loads. Real failures remain visible. Midnight resets, rejecting yesterday's late results;
Total Today keeps its label before 03:00. Web Credits/USD and CLI scopes are unchanged.

Retryable source-read failures with a retained observation first say **Retrying** in
ordinary detail text, explicitly **not current**, instead of immediately announcing
**Source unavailable**. Each source/card/daily lane confirms after five monotonic seconds
from its first failure (one existing source retry interval); further failures and
partial/retained-only card publications cannot renew that window. Confirmation is
evaluated on existing Live publications, normally every second, not on another timer
or polling loop. In-flight bounded acquisition and browser suspension can delay a
publication; five seconds is a confirmation window, not a network-latency promise.
A successful relevant source observation clears the status; HTTP, SSE heartbeats,
job progress and a successful unrelated card do not. Initial missing data and
non-retryable/authentication failures have no grace. Daily failures request a retry
on the existing single history lane after five seconds rather than waiting a minute.
Browser reconnect/offline/host-stop notices remain separate from source acquisition.

Subscription cards align centered title bands, **CCost Today**, native primary percentage
and bars; body values stay left aligned. Native declarations/order, never depletion or
provider identity, select the primary. Missing primary stays unavailable; weekly-only
accounts have no invented five-hour slot or duplicate secondary.

Each quota shows **period · N% used (CCost)**, its bar/reset and applicable canonical
**Remaining: …/day** and **Remaining: …/workday** (or **no workdays left**). Only real
secondaries follow a divider. No routine rolling/fixed boilerplate appears. Exact
account/window/model costs include pre-Watch native-month history, never Today/30-day
substitutions. Unknown/stale/unacquired boundaries show **(—)**; confirmed empty windows
show zero independently of Today. Unlimited, sub-100% precision and genuine warnings
remain distinct. Today keeps daily scope/attribution without an estimate suffix (basis
on hover). Credits/USD changes CCost, not native Remaining. Accounts is unchanged.

Context-price guidance appears directly below each session table, before active activity,
without a separate divider/frame or empty reserved space. It uses the latest valid Watch
continuation (including hidden compaction), not historical context from another prompt.
Compaction removes/downgrades it, unknown/replaced contexts never revive old guidance,
and older concurrent cards do not borrow a newer focal's warning. Approaching keeps
the existing gold/orange triangle but uses theme body foreground for its text and values;
exceeded keeps both gold/orange. Approaching uses
`thresholds.nextIctxPriceThresholdWarningPercent` (75%; zero disables approaching only);
exact tier boundaries use unrounded counts. Gold/orange exceeded guidance includes the
canonical relative price factor or supported cached/fresh cost fallback, not a bill
prediction. Prompt cells contain no context-warning stars, footnotes or threshold color.

Watch still omits the normal heading, report/search/scope/refresh controls, run summaries,
valuation disclosure and model announcements. Exceptional host/source/offline notices
remain. No Observation details, Copilot Unaccounted usage or global warning list returns.

**[Mini Watch](web-mini-watch.md)** is an explicit On/Off floating status card on supported
desktop browsers. It reuses this tab's live publication, not another Watch engine.

Four isolated session workers publish coherent canonical rows independently, without a
complete-total phase; generations reject superseded work. Account-history and detail
lanes cannot borrow mutable Live service. Accurate rows still require capture/analysis,
not source-level streaming. Successful admission order keeps captures fair across
catalog revision changes and rejected stale results; busy roots cannot continually
overtake a retained running card awaiting fresh termination evidence.
Active/top-five captures and a small catalog index are
retained; no per-card leases/browser acquisition loops. Adaptive 6× EMA/clamped 5–30s
cadence measures capture work; explicit intervals, buffered V2 hints and presentation wakes remain.

Live uses one process-lifetime engine starting with the host, not a tab. Closing all tabs does not stop it. CLI Watch retains its separate run, startup history and row-retention policy; Web history is continuously replenished. Both reuse canonical valuation, context, tool/skill attribution and coordinator timing/recovery policies. Source hints, idle and connection loss never prove completion. Account figures retain Watch scopes, not normal-report calendar-month substitutions.

Each authorized tab owns one same-origin SSE connection for live, finite-job progress and terminal runtime updates. The HttpOnly session authenticates it; no control secret/query credential is used. Instance-bound ordered IDs and full coherent publications reject duplicates/older/foreign-instance updates. Replay is bounded to 32 events and 8 MiB (2 MiB per publication); overflow or an uncovered gap requires a fresh authenticated `/api/live` snapshot, never inferred continuation. Oversized publications fail visibly rather than displaying truncated totals. Four streams are admitted; excess tabs can retry after capacity is available.

Stream writes retain a two-second timeout and ten-second heartbeats, without a forced healthy-stream lifetime. Authentication is checked on every stream turn; expiry, terminal shutdown and abandoned/failed writes release admission. A genuine disconnect uses ordinary EventSource retry at three seconds. Offline is visible with last known values retained. A received source-change/shutdown notification closes automatic retry and asks for a manual launcher run; an unknown disconnect never starts a server or assumes an update. A different instance requires a fresh authorized launcher link; expired sessions stop retry. Snapshot/job commands remain normal authenticated HTTP. Finite reports run in one isolated, deadline-bounded process while live acquisition, account publication, HTTP/control and source-change checks retain separate scheduling.

`test_web_live.py` covers canonical live/CLI parity, lifecycle/source recovery, hints/overflow, account-only publication, midnight/DST/partial pricing, detached exports, replay/gap/instance handling, actual HTTP stream admission/terminal delivery, fatal fault ownership and stop beside an occupied finite-report process. Its optional JavaScript VM checks safe presentation and ordering without automating a browser. `development/tests/integration/probe_web_live.py` is an opt-in, read-only real-source check (no UI/model calls): two streams, one acquisition owner, retained run origin and owned shutdown. Native visual/browser/macOS acceptance is not claimed by these probes.

For Daily/shutdown investigations, run `probe_web_live.py --watch-cards --daily --detail`
from `development/tests/integration/` using the repository's Python runtime. Add
`--reports` for finite-report competition. The probe records bounded monotonic
acquisition/projection/publication, HTTP and cleanup phases, pending work and owned
resource counts without source identities or credentials. Primary and cleanup
failures are retained together, never replaced by a green rerun. Daily still has
its 120-second wait, HTTP requests three seconds and host join ten seconds. Stop
cancels the host's own V2 capture/history/detail reads before joining; it neither
stops OpenCode nor converts delayed/missing Daily data into empty success.
`probe_web_repeat.py --cycles 10 [--competing]` is an explicit synthetic lifecycle
campaign, not a new recurring CI or live-provider loop.

## Windows detached launcher and tray

Double-click `windows/Beta/Cost-Guard-Web.cmd`, or invoke it from an existing console. The short-lived console shows one **Starting CostGuard web...** label and updates only its spinner cell while PowerShell locates Python 3.11+, checks configuration/native support, waits for validated host readiness and requests the registered default browser. No PowerShell progress panel or successful stage transcript is drawn. Redirected/noninteractive output is one plain startup line; failure feedback remains actionable after animation stops. Source ZIPs retain relative-path support, including spaces/Unicode. No packages, compiler, download, administrator access or global execution-policy change is needed; the override applies only to that PowerShell process.

The console exits naturally after **validated host readiness and a successful OS browser-open request**, not browser paint or report completion. An existing terminal regains control at that point. The managed host remains detached from console, standard handles and launcher lifetime. Later deliberate launch restarts only this checkout's verified instance; overlapping clicks reuse a ready winner. Preflight failure preserves the existing instance. Failures after it stopped cannot restore the old code and never claim success.

This is a **no-build status-console handoff**, not a new host worker/supervisor or frozen application. Python discovery retains its five-second per-candidate bound. Lock/restart/readiness deadlines, authentication and host ownership are unchanged. No invented percentage, autostart, early unauthenticated page or second acquisition engine is added. Native Windows cold/warm launcher checks and integrated-browser evidence are distinct from physical Explorer or first-paint proof.

**Cache/build/repair:** Windows generates no executable artifact or helper cache. Current source and source-change shutdown still apply. Do not delete runtime state, user configuration or analysis caches to repair startup. Direct PowerShell invocation uses the same status path. Failures retain actionable text/native feedback and private allowlisted logs; a visible interactive fallback may wait for Enter if native feedback is unavailable. Historical hidden-handoff measurements in [windows-handoff.md](../development/architecture/governance/verification/windows-handoff.md) describe the superseded design, not v80.118 behavior.

The browser's static branded startup view survives slow authorization; initial report acquisition has indeterminate activity and real job phase/count notices. HTTP-shell readiness never implies source/account readiness. Failed authorization asks for tray Open Cost Guard/relaunch; unavailable reports offer Refresh and preserve stale evidence. With JavaScript blocked the static page still explains reload/fresh-link recovery. Timings and automated/native/visual limitations are recorded in the completed startup FR; actual Explorer mouse interaction and macOS desktop behavior are not inferred from tests.

The original source-rendered shield/bar icon has only **Open Cost Guard** and **Exit Cost Guard**. Double-clicking the icon also opens Web. Open reuses the current server and asynchronously hands off a fresh bootstrap route. Exit stops only this Web instance and removes its icon; browser tabs, CLI Watch and OpenCode stay running. Source changes and HTTP failure remove it too. Explorer taskbar recreation reinstalls the matching icon; failure to restore it shuts down Web rather than leave an invisible unmanaged server. There is no service, login task, autostart or firewall registration.

Missing Python, native tray failure, startup timeout, unverifiable existing state and browser-open failure are distinct. A failed initial browser handoff shows an actionable dialog but leaves the healthy tray Open action available; failed tray Open shows a native notification. Startup errors also print the existing Diagnostics path. Private allowlisted lifecycle records live under the instance directory below; the PowerShell boundary records only a timestamp and `python_unavailable`/`launcher_failed` in `%LOCALAPPDATA%/CostGuard/Web/launcher/startup.log` if its private directory is safe. No URL, credential or session data is logged. Run `development/user-tools/diagnostics/windows/Cost-Guard-Diagnostics.cmd` for normal Diagnostics.

Opt-in `development/tests/integration/probe_windows_web.py --allow-native-ui` requires current UI approval: it displays icons, opens local Beta tabs, tests native menu labels/command delivery, browser failure, Exit, HTTP-fault cleanup, transient consoles, detached survival, overlap/restart, source-change exit and ShellExecute from a no-Git source copy with spaces/Unicode. Synthetic Quick/Full tests never open a native icon or browser. The probe does not claim physical mouse double-click or visual light/dark inspection, nor macOS proof. No new permanent release gate is introduced.

## Experimental macOS launcher and CG menu — hosted native checks passed

**Real hosted ARM64 and Intel native checks passed on 2026-10-26; consumer-desktop acceptance remains pending.** See the hosted matrix above for actual AppKit/lifecycle/compiler/browser results. Neither these offline probes nor an app-shaped directory proves Finder/Gatekeeper or physical desktop behavior. Existing root macOS CLI/Watch and development Diagnostics launchers remain the fallback.

Use `macos/Beta/Cost-Guard-Web.command` with already-installed Python 3.11+. Terminal shows **Launching web…**, display-only indeterminate activity and sanitized stages throughout discovery, native preflight and browser handoff. The activity child is stopped/joined at exit; it never owns the detached server. Python missing or launch failure retains actionable text and, in an interactive Terminal, waits for Return. No percentage or browser-paint guarantee is shown. It checks PATH, standard Homebrew and Python.org locations without installing anything. Paths are relative to the checkout. Bounded native preflight preserves a healthy old instance on failure; the host retains the same private lifecycle/security owner. Closing the browser does not stop Web. Physical macOS spinner/handoff behavior remains unverified.

The source-only Python `ctypes` adapter binds in-box AppKit/Objective-C with explicit pointer, NSInteger, BOOL and double signatures (native-tested on hosted 64-bit Intel/Apple Silicon). It creates an accessory `NSApplication` and a **CG** status item with **Open Cost Guard** and **Exit Cost Guard**. AppKit stays on the main thread; HTTP/analysis stays off it. Callbacks only queue actions; `/usr/bin/open` runs in one bounded asynchronous browser worker, not via `$BROWSER` or shell interpolation. A failed browser retry changes the tooltip and retains Open. A main/tracking-mode timer dismisses an open menu when its HTTP owner stops so the icon can be removed. Hosted callbacks/pumping/cleanup passed; physical menu interaction remains unverified.

### Locally generated optional Finder app

The `.command` first tries to compile the committed `macos/Beta/launcher.applescript` using **`/usr/bin/osacompile` only**, with a 30-second timeout and concise progress/errors. No SDK/Xcode/Command Line Tools, package manager, Python bridge, virtualenv or download is invoked. There is no committed/precompiled `.app` executable. A preparation failure is logged as `app_preparation_failed` and the direct `.command` launch continues; it does not pretend a Finder app exists.

Success prints the generated `Cost Guard Web.app` path under `~/Library/Application Support/CostGuard/Web/<checkout-id>/finder-<fingerprint>/`. Open that local app in Finder for the intended terminal-free route; it calls the same Python launcher through safely quoted AppleScript `do shell script`, not Terminal scripting. The applet exits after bounded launcher completion. Its GUI alerts distinguish startup failure from a healthy host whose browser could not open. It adds no login item, daemon, service, Automation/Accessibility request or global Terminal preference change.

Source/version/OS/architecture/Python/check-out fingerprints select the cache. Unchanged apps are reused only after bounded file/mode/hash verification; changed fingerprints build a new app atomically. Failed partial builds are removed; old fingerprinted apps are retained rather than deleting unverified user artifacts. Tampered/linked/unsafe cache entries are refused, not overwritten. Moving a checkout or interpreter requires rerunning its `.command`; an old app shortcut can still point at the old path. Generated binaries/state/logs stay outside Git. This is protection against accidental/stale state, not against same-user malware.

### Executable bits, quarantine and remaining native checks

Git records the `.command` as executable. Finder/ZIP extraction and downloaded-file quarantine behavior are **unverified**. If extraction loses executable metadata, an explicit owner action `chmod u+x macos/Beta/Cost-Guard-Web.command` restores the script bit; alternatively run `zsh macos/Beta/Cost-Guard-Web.command` from the checkout. Neither bypasses Gatekeeper. No quarantine removal, signing workaround, forced launch or security-policy change is performed. Respect any macOS security prompt; use the existing CLI/Watch path if Web is blocked.

The `.command` may leave Terminal depending on user preferences; it never scripts closing Terminal windows or requests Automation permission. The optional Finder app remains no-Terminal/no-Automation, with its existing OS app-launch cue and supported error alert; no new console or unverified notification/permission mechanism is introduced just for a spinner. Only physical Finder launch proves that behavior. Offline startup needs installed Python/system frameworks/osacompile; source/pricing keep their existing network policies.

Synthetic `test_macos_web.py` / `test_macos_app.py` run without any GUI and cover typed 64-bit dispatch, main-thread enforcement, callback queuing, readiness, partial cleanup, preflight preserving a healthy instance, asynchronous Open/Exit, browser-fault handoff, app quoting, cached reuse/rebuild, tampering and compile failures. With separate current UI approval on macOS, `python development/tests/integration/probe_macos_web.py --allow-native-ui` exercises real AppKit labels/Objective-C callbacks, event pumping, browser-failure retention and HTTP-owner cleanup without opening a browser or calling a model/provider. It is never part of Quick/Full.

Still required on ordinary macOS desktops: source ZIP bits/quarantine/Gatekeeper, physical `.command` and generated `.app` Finder launch, no-Terminal behavior, registered default browser, visual/menu tracking and accessibility, consumer Python discovery/missing/old Python and real-source offline startup. Hosted tests passed typed ABI/callbacks, repeated restart/Open/Exit, source-change/HTTP-fault cleanup, spaces/Unicode paths, executable `.command`, in-box compiler/cache rebuild on both architectures with an offline entry shim. This is limited native PASS, not complete consumer-launcher acceptance or a permanent release gate.

## Browser session and privacy

Cookies are not port-isolated. Cookie **names are checkout-scoped** so authorizing a second local checkout does not replace the first checkout's session. Credentials/CSRF remain instance-specific: replacement hosts reject old cookies. Cookies use host-only `127.0.0.1`, `Path=/`, HttpOnly and SameSite=Strict; browsers can send both checkout cookies to loopback ports, but each host accepts only its own name/value. This is not confidentiality from another program running as the same user. Repeated restarts reuse the checkout cookie name rather than accumulating one cookie per instance.

Open the console's `/#bootstrap=…` link within 120 seconds. JavaScript immediately removes the fragment with `history.replaceState`, then POSTs it once to `/api/bootstrap`. The server issues an instance-scoped HttpOnly SameSite=Strict cookie with an eight-hour lifetime and a separate CSRF value held only in page memory. Reloads recover CSRF through the authenticated `/api/session` route. Replay, expiration and other instances are rejected. Restart this foreground host for a new bootstrap link. The console link is an intentional short-lived handoff to the foreground owner, not a reusable control token; do not save/share it or capture startup output in general-purpose logs.

Sensitive reads require the cookie. All POST requests require exact Origin and JSON content type; authenticated POSTs additionally require `X-CG-CSRF`. Every request checks the exact Host and assigned port, rejects foreign Origin/Fetch-Site, ambiguous framing and unsafe targets. No CORS access is granted. Packaged assets are fixed, local and symlink/junction-checked, not a general file server. Responses are no-store, deny frames/service workers and third-party runtime assets, and use restrictive CSP. Report text is inserted with `textContent`, never HTML. Access/error request logging is disabled; failures expose allowlisted codes, never source exception messages.

This is loopback HTTP, not a public server or protection against malware/other code executing as the same OS user. A separate persistent launcher/control credential exists only in private local instance state, never in page responses, browser storage or logs. Provider credentials never enter URLs or browser storage. No generic OpenCode proxy, source mutation, shell-command or arbitrary path API exists.

## Diagnostics and owner-test limits

Windows startup preserves specific causes: `process_identity_access_denied` or
`process_identity_unavailable`, corrupt/unsafe private state, busy/unavailable
transition or lifetime coordination, and control/readiness failures. Unresolved
ownership does **not** establish that a Web host exists. Preserve the state, retry
after a busy transition, and run Diagnostics for repeated/unavailable/unsafe cases;
do not elevate, delete state or alter permissions. The existing console and failure
dialog show the same fixed guidance without raw OS errors or private paths.
`stale_instance_recovered` records successful retirement, not an active conflict.
Diagnostics exports the latest allowlisted lifecycle event with its timestamp even
without a new host snapshot; an older `ready` snapshot remains historical evidence.

Existing Diagnostics now reads only this checkout's private Web lifecycle codes and `diagnostics.json`; it does not start Web or contact a control endpoint. Managed hosts periodically persist schema/product version, readiness/shutdown reason, last sampled source state, capped source transitions, uptime and capped API failure categories (denied/invalid/busy/unavailable). Persistence is at most once per five seconds plus shutdown, not per tab/request. Final facts survive instance-record removal; crash evidence may be up to five seconds old. Missing/stale data is not a health PASS. The current snapshot replaces only Web diagnostics, never legacy caches/config/history. No prompt/title, raw session/instance ID/path, URL, cookie/control token, provider payload or exception text is collected. Lifecycle codes retain native startup/browser failures even before HTTP readiness.

For `source_changed`, finish updating and relaunch manually. For source unavailable, keep OpenCode available and inspect existing source Diagnostics; never install optional packages to repair Beta. For browser failure, use native Open; for startup/native failure, retain the failure evidence and use the unchanged root CLI/Watch launchers. HTTP shell readiness never proves complete account/history acquisition.

The historical synthetic parity and bounded integration inventory is [Beta stabilization evidence](../development/architecture/governance/verification/web-beta-stabilization.md); the hosted matrix above adds subsequent real Mac/API/browser evidence without rewriting that history. Physical UI/suspend proof remains unavailable. Offline first-run refers to **shell/launcher startup with installed Python and in-box OS APIs**, not guaranteed fresh pricing/accounts without network. No compiler is needed on Windows; in-box macOS app compilation/reuse/regeneration passed hosted probes, but Finder acceptance remains unverified. This is a Beta milestone, not promotion, Legacy removal or a new permanent approval gate.

## Allowlisted routes

| Route | Method | Meaning |
| --- | --- | --- |
| `/`, `/app.js`, `/render.js`, `/watch.js`, `/reports.js`, `/live.js`, `/session.js`, `/settings.js`, `/app.css` | GET | Fixed public Beta shell/assets, no history |
| `/health` | GET | Public HTTP-shell readiness only |
| `/api/bootstrap` | POST | One-use `{"credential":"…"}` exchange with exact Origin |
| `/api/session` | GET | Authenticated CSRF recovery, no control credential |
| `/api/settings` | GET | Authenticated read of only `webSettings.theme` and `webSettings.ccostDisplayUnit` |
| `/api/settings/theme` | POST | CSRF-protected fixed `{"theme":"classic"}` or `{"theme":"web"}` write only |
| `/api/settings/ccost` | POST | CSRF-protected fixed `{"ccostDisplayUnit":"credits"}` or `{"ccostDisplayUnit":"usd"}` write only |
| `/api/status` | GET | Separate HTTP, analysis, source and account acquisition states |
| `/api/live` | GET | Authenticated coherent live/progress snapshot and instance/sequence; retained terminal state while stopping |
| `/api/events` | GET | Authenticated multiplexed SSE, bounded replay with Last-Event-ID; no query strings |
| `/api/reports` | POST | Enqueue/coalesce a finite report; return job ID (202) |
| `/api/detail` | POST | Shared complete session capture, revision-aware pages, freeze and handle release |
| `/api/jobs/<id>` | GET | Authenticated status/progress/result |
| `/api/jobs/<id>/cancel` | POST | Cancel owned queued/running work with `{}` |

Reports select `kind`: `normal` (overview/Models/Accounts), `all-models` (catalog), `sessions`, `session`, `date` or `token-mix`. `session` requires an alphanumeric/underscore/hyphen `session_id` (max 200); `date` requires `YYYY-MM-DD` or `YYYY-MM-DD:YYYY-MM-DD` (max 32), with impossible/reversed/overflow dates rejected. `sessions` accepts `session_limit`: 1–10000 or null for all, legacy default 20. Paged requests add `session_page_size` (1–100; Web uses 50; omitted limit means all available), `session_offset` (0–1000000), and `session_catalog_revision` (64 lowercase hex digits, required for nonzero offsets). Response `session_page` exports offset/size/total/catalog_revision; a revision covers catalog identity/order, not atomic prompt values. Paged lists omit unused prompt request identities, retaining every session row and its canonical values. Page fields on other report kinds, invalid bounds and unknown fields are rejected. There are no HTTP query-string or arbitrary path parameters; client scope fragments become validated POST bodies. Reports export the shared application's explicit DTOs, retaining exact decimal **strings**, null unknowns, provisional flags and CLI-projected labels; the page does not calculate costs. Empty acquired lists, acquisition errors, partial source evidence and genuine priced zero remain distinct. Account `reported` means inspect the report's independent observation statuses, not that all accounts are healthy or atomic with history.

## Resource and failure boundaries

- Twelve HTTP workers/admitted sockets, with at most four authenticated streams so eight ordinary/control slots remain; bounded listen backlog. Two-second socket timeouts and an absolute five-second ordinary request/header deadline, including dripping clients. Only fully authenticated SSE cancels that deadline and retains its slot until disconnect, expiry or terminal shutdown. Connections close after one request.
- Request line <=2048 bytes, aggregate headers <=16 KiB, individual header lines <4096 bytes, JSON body <=4096 bytes. Duplicate headers/JSON keys, transfer encoding, non-JSON controls and unsupported methods are denied. No autoreload or directory listing.
- At most four queued/running reports and one spawned analysis process. Identical in-flight requests coalesce. Sixteen jobs retained; old completed/cancelled entries are evicted, so a missing ID is not an empty report.
- A fresh ReportApplication/ReportService owns each job's mutable integrations and one-shot account cleanup. Existing integration request timeouts apply; a 120-second hard process deadline bounds whole-job work. Cancellation/shutdown terminate and join only that owned process. No live scheduler is shared or cleaned by these one-shot jobs.
- Each finite report child monitors multiprocessing's exact parent kernel sentinel. A crashed/force-stopped Web parent or lost ownership proof exits that child nonzero, including a blocked scan; PID reuse is not a liveness signal. This child-only safety monitor stops/joins on ordinary completion.
- Results are limited to 8 MiB per job. Oversize: `result_too_large`; scope the request. Long Token Mix may time out but never blocks shutdown. Progress exports only approved phase/stage/counts and a stale-safe job sequence, not source text. Child IPC coalesces at 100ms; host drains at most 64 messages/turn.

The shell remains reachable with offline/loading sources. There is no autostart. Tests use synthetic read-only sources; local read-only source probes are separate from paid/live-model tests.

## Shared managed lifecycle (native launcher integration contract)

`src/web/lifecycle.py:launch(root, gui_module)` is the trusted Python launcher interface. Only the fixed `src.web.native_windows` / experimental `src.web.native_macos` adapters are accepted; missing adapters fail before advertising a usable server. Entries are `--launch-windows` / `--launch-macos`; prefer the user-facing `.cmd` / `.command`. `--preflight-macos` is a bounded internal child check. Do not manually use private `--managed` child arguments as an unmanaged background mode. No third-party GUI package, service, autostart or downloaded helper is required or installed.

- Identity is SHA-256 of the resolved canonical checkout path (Windows case-normalized). Private state lives under `%LOCALAPPDATA%/CostGuard/Web/<identity>` on Windows, `~/Library/Application Support/CostGuard/Web/<identity>` on macOS, and `$XDG_STATE_HOME/CostGuard/Web/<identity>` (default `~/.local/state`) elsewhere. Protected owner-only inherited Windows DACLs or Unix 0700 directories/0600 files protect state; linked/reparse ancestors are rejected. Nonce, PID/birth/image, loopback port, schema/build, readiness timestamp and control secret are atomically persisted. Nothing is written to Git for instance ownership.
- An OS-held transition lock serializes launcher operations. A second lifetime lock held by the child prevents duplicates even if a launcher crashes before readiness. A click begun before the winner becomes ready reuses that winner; a later deliberate invocation restarts it even without a version change. Different checkouts have different identities/locks. Available ports are assigned by the OS; previous port occupants are never terminated.
- Restart requests authenticated graceful shutdown and waits up to ten seconds. Owned finite report jobs are cancelled/joined; HTTP sockets have a five-second hard deadline. Forced termination revalidates exact process birth/image using a retained Windows kernel handle or Linux pidfd. Platforms without an atomic process handle (currently macOS) refuse force-stop and report a conflict if graceful shutdown fails, rather than race PID reuse. A changed/dead PID is stale, not authority over its replacement. A responding wrong-nonce/auth/schema/build endpoint is a conflict, not authority to kill a port occupant.
- Corrupt/incompatible state is an explicit conflict: it cannot establish that no host exists. Do not blindly delete it and relaunch; first establish the old host has stopped. Stale valid records recover automatically. No scan/kill by process name, port, Python executable or OpenCode identity is used.
- On Windows, an inaccessible reused PID is not considered absent. Retirement also requires acquiring the checkout's existing lifetime byte lock while holding the launch transition lock. Every managed schema-1 host acquires lifetime before publishing and retains it through cleanup; Windows prevents deletion/replacement of that open lock file. A free lock proves the old managed host no longer owns the record, including legacy records with no boot metadata. Retirement checks the full unchanged record before nonce-guarded removal, never sends its control secret, then releases lifetime for the child while transition stays held through replacement readiness. A delayed child can win only the same exclusive lifetime lock, never create a second managed host; failed launch cleanup removes only its own nonce. Busy/unsafe/unavailable proof preserves the record and refuses replacement. No wall-clock boot inference or schema change is used; non-Windows identity/termination policy is unchanged.
- Child stdin/stdout/stderr are detached to the null device, inherited handles are closed, and cwd is private app data, not the checkout. Windows uses `DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`; Unix uses a new session. Owned lifecycle diagnostics contain only timestamp/allowlisted codes in a roughly 32 KiB rotating log; no URLs, bootstrap/control secrets, raw exceptions or account/source data. Browser failure is returned separately from server startup failure; native Open can retry without restarting.
- `WebHost.run_gui(gui)` stays on the main thread. The adapter's `run(owner)` must create the required native icon/event loop, call `owner.publish_ready()` only once usable, route Open to `owner.open_browser()`, route Exit to `owner.stop()`, and observe `owner.stopped` so a dead HTTP worker removes the icon. `gui.close()` is idempotent and runs on the main thread in all exit paths. HTTP/jobs and the live acquisition thread share this stop owner. A missing/failed/returned GUI stops the server, never silently falling back to an unmanaged background host. Live closes account/event workers and joins before the host reports stopped; unexpected live/cleanup faults retain the original exception for the fatal main boundary.
- Readiness means shell plus required GUI only, not account/history loading. A browser Open handoff receives a fresh 120-second one-use fragment via authenticated control; existing same-instance sessions stay valid. New instances have independent cookies, CSRF, nonce and control secrets, so old clients cannot control a replacement.

Private `/control/status` (GET), `/control/stop` and `/control/open` (POST) require `X-CG-Control`, exact Host, no Origin, no Cookie and empty bodies. They are not browser APIs and never use browser CSRF/session credentials. Public `/health` is not an ownership/readiness proof. Authenticated `/api/status` additionally exposes sanitized lifecycle instance/state/guard status, never the control secret.

## Best-effort source-change stop

Before normal serving, take a metadata baseline of `src/`, Web Beta runtime launcher trees `windows/Beta` and `macos/Beta`, root Python entrypoints, `config/default-config.jsonc`, `pyproject.toml` and `requirements.txt`. Owned code/asset extensions are explicitly enumerated in `SourceGuard`; membership, size and nanosecond mtime are compared every five seconds. Added/deleted/renamed runtime files stop the host. Symlinks/reparse points are inspected as links, never traversed to external code. CLI processes are never stopped.

Exclude development/docs, user configuration, Git, logs/cache/diagnostics, bytecode, virtual environments and dependency-installation trees. Transient stat errors expose `source_check_unavailable` and retry against the original baseline; they are not proof of a change. A proven change makes `source_changed` terminal, rejects new API work and initiates the same shutdown immediately without browser acknowledgement. There is **no** reload, automatic restart, Git operation, updater, file watcher dependency or deployment copy. Finish updating and invoke the launcher manually.

This can miss modifications with identical size/mtime, and a mixed-code interval can precede detection. It is not an atomic update protocol or guarantee against Windows file locks. Runtime reads do not retain open source handles. Hosted native detachment/source-stop passed on Windows and both Mac architectures; physical icon and terminal-lifetime acceptance remain pending. Mocked spawn flags alone are not native proof; opt-in desktop probes remain separate.
