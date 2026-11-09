# Web Beta

After authentication, **Web Beta v…** shows the running server's CLI product version,
not a release lookup or newly edited source. Offline views retain their original version.

On initial Models entry, source selection may finish before the first healthy Live
observation. Models keeps its centered loading progress and **Waiting for source…**
stage, then continues automatically; no manual Retry is needed for a healthy startup.
Waiting uses bounded backoff. Genuine source/authentication/permission errors and
other genuine terminal failures still show actionable feedback and **Retry Models**.
Healthy finite work has no elapsed-computation cutoff; pending work retains bounded
resources and automatic recovery rather than requiring Retry just because it is old.

## Contextual help

Heading labels and useful metric labels/values explain metrics in Web and Mini
Watch, without standalone **?** buttons or dotted underlines. Hover the actual text, not
the surrounding padding, to see the help cursor immediately and explanation after **600 ms**. Only the
text highlights; empty header space does not open help or highlight the column.
Mini's Session and Total CCost labels are separate targets with no help in the gap.
Sorting controls still sort when clicked outside their help label.
Hover or focus with Tab to read; keyboard focus and deliberate taps open promptly. Press Escape to dismiss without moving
focus. You can move the pointer into the help to keep reading. Tap passive help text
to keep it open; tap again or outside to close it. Only one explanation opens in
each window. Values remain selectable; action buttons and links stay clickable.
Hover help also closes after leaving the document/window, even if a mouse-clicked
button retains focus. Keyboard-focus help and deliberately pinned passive help are
distinct; action activation dismisses its help immediately. Live updates never reopen
dismissed help without a new interaction.

Full Watch’s **CCost (I + E)** help separates first-request incoming-context cost
from output/later/linked-subagent work. **Token Mix %** explains I/C/W/O token
shares, not prices. **Model** names the main model even when other linked models
contribute to totals. **N/A** means unavailable, not zero; **?** marks partial
pricing/data. CCost is an estimated reference cost, not your bill or native quota.

When an actual reference **CCost N/A** is shown, hover/focus/tap that text for the
supported reason. An acquired, verified catalog can establish that a recognized
model (including Claude Sonnet 4) has no listed reference price in the available
GitHub Copilot list. An uncertain identity, missing required rate/tier, missing
usage or unavailable/unverified price catalog gets a different explanation; without
enough evidence the help stays neutral. Contributing child models are included,
not blamed on the visible main model. This explains unavailable valuation; it does
not fix model selection, invent rates or reprice historical work.
Full Watch, Mini, Sessions list/detail and other reference-cost cells reuse the
same help. Mini's prompt and parenthesized session amounts are separate targets,
retaining useful prompt details. Reasons update with the displayed snapshot and
unit changes. Positive partial subtotals, true zero and genuinely pending Loading
remain unchanged. An N/A daily amount can explain itself; ordinary positive partial
daily amounts gain no new help or warning.

Hover/focus the **CCost value** in either Watch table for Input, Cached input,
Cache write, Output and Subtotal, grouped into **Main prompt** and **Subagents**
by provider/model, actual effort and price tier (tier names/boundaries are not shown).
Repeated agents share a group with their contributing-session count and a first
**Number of prompts** bullet counting distinct canonical child prompts in that group,
not agents or physical requests. Missing boundaries show N/A or a qualified observed
lower bound. Categories are unrounded reference-cost contributions,
not token percentages. Unknown categories remain N/A and omitted groups retain their
known cost/call coverage. **Calls** uses the same groups for physical model requests,
not tools. Hover, focus or tap **Model** for recorded linked-agent models and effort,
even when main and all agents share one model. Unrecorded usage remains qualified;
multi-model main-only work also retains help without a participation star.
**Token Mix %** has header help only, not another per-cell popup.

Use the clock text itself for exact Started/Finished or quota-reset dates. Prompt previews
have no full-text popup in either Watch table. Mini uses column-heading help, not
row/header question marks; its full session text remains selectable and accessible.
Subscription text groups primary/additional quota details. Mini's Session and (Total CCost) headings have different scoped explanations. Connection warnings, settings explanations and longer report/account
details remain visible or expandable rather than hidden exclusively on hover.

## Open in another browser (Windows)

Right-click the Windows notification-area **Cost Guard** icon and choose
**Copy Cost Guard link** (between **Open Cost Guard** and **Exit Cost Guard**).
Paste it into Edge, Firefox, another browser profile or a private window within
**two minutes**. It authorizes that browser once, normally opening Models on the
**same running server**; navigate to Watch as usual. Copy never opens a browser,
changes the default browser or restarts the server. Existing tabs stay connected.
The notification confirms copying/expiry or asks you to retry if copying failed.

The clipboard holds a temporary **bearer secret** until overwritten: do not share
the link, and overwrite it after pasting if desired. Cost Guard marks it ineligible
for Windows clipboard history/cloud sync; other clipboard-monitoring software is
outside this protection. Expired, used or previous-instance links cannot authorize
a fresh browser. Repeating Open/Copy creates independent links; up to 16 can be
pending at once, with a retryable failure rather than revoking an unexpired link.

A normal page URL/bookmark works only in an already-authorized browser while that
host/port/session remains valid. Pasting the plain URL into a fresh browser still
requires authorization. There is no webpage Copy button, new browser API or macOS
copy-menu action. Physical Windows menu/clipboard acceptance is separately qualified
in the [verification notes](../development/journal/web/browser-links.md).

v80.139 recognizes persisted failed/interrupted runs that ended before producing an
assistant response, including resumed work followed by a system notice. The server
retires the correct prompt, freezes duration and preserves known usage through
refresh/retention and Earlier Sessions. The running aggregate excludes terminal grace;
Mini retains those final rows briefly without labeling them running. A later real attempt can still run; age, inactivity, missing
usage and quota percentages alone never establish an end. Generic failures stay
errors unless the source supports a specific abort/quota cause.

## Export a session as JSON

Open **Sessions → a session → Export JSON** to save that selected session's full
native OpenCode export, not just the displayed prompt rows. Exports use OpenCode's
native **sanitized** mode; review the file before sharing because sanitization is
not a guarantee that all private information is removed. A running session exports
its current point-in-time state and can change afterwards.

Supported Edge/Chrome browsers request **Save As** immediately from your click.
Choose a destination and `.json` filename, or Cancel without starting an export.
Other browsers use a normal download: browser settings may save automatically to
Downloads rather than showing a picker. Cost Guard does not remember a save path.

Export needs an observed session in the currently selected OpenCode V2 instance
and a compatible native export API (verified with OpenCode **2.2.6**). It also works
for sessions created by isolated LIVE servers using the shared database; opening
the session in Desktop or keeping the original private server running is not needed.
Unsupported sources/versions show **Export unavailable**, with the CLI alternative
`opencode session export <session-id> --sanitize`. Errors never substitute a summary
or silently truncated JSON. Reopen an expired/source-changed selection before retrying.

Transfers are read-only, one at a time, limited to **16 MiB** and a **four-second**
source deadline. Larger exports require the native CLI. Transcripts are not staged
in Cost Guard's cache or repository. Successful real native Save As destination
selection and disk writing remain **UNVERIFIED** under the owner's limited
acceptance-evidence exception; browser fallback files and deterministic native
write/close behavior are separately tested.

## Web settings

**Settings**, at `/#/settings`, contains five compact dropdown rows, with setting
names on the left and aligned values on the right. There is no extra page/panel
heading, frame or persistent explanatory paragraph. Narrow/zoomed layouts stack
only when needed; touch controls have larger targets. Save/loading/error feedback
remains visible below the grid.

| Setting | Inherited choice (first) | Explicit choices |
| --- | --- | --- |
| Theme | Default (Classic) | Classic / Web |
| CCost display | Default (USD) | Credits / USD |
| Mini Watch position | Default (Remember last) | Remember last / Standard position |
| Mini Watch size | Default (Fit on open) | Fit on open / Remember last size |
| Quota display | Default (Used) | Used / Remaining |

Hover/focus a setting label for its scope, or the current value for that choice's
effect. Labels use the shared 600ms pointer-hover help (immediate keyboard help),
not a separate question-mark button. In supported modern Chrome/Edge, a native
customizable picker keeps its standard selection/keyboard behavior and displays
the hovered or keyboard-focused option's explanation **beside the option list**.
Keyboard navigation changes only the preview until Enter/Space commits; Escape
cancels. Touch/narrow pickers show descriptions within the open list, before a
committing tap. Long descriptions scroll within the bounded native popup.
In the side-by-side picker, wheel over the option label to scroll its visible
explanation without moving onto the explanation or selecting the option. This
also works for Default and the selected choice; scrolling directly over the
explanation and its scrollbar remains available. Narrow/touch in-flow descriptions
retain normal popup scrolling.

Browsers without customizable-select/selected-content support retain ordinary
native selects plus an expandable **Choice help** reference for all options,
including Default. OS-rendered option popups cannot reliably show per-option
hover help; the disclosure and current-value help are the accessible alternative,
not a claim of native option-hover support. No closed row has a help paragraph.

Default labels reflect the current shipped defaults, not fixed lifetime names.
Classic is dark independently of system preference; Web follows system light/dark.
An open Mini Watch inherits this owning page's resolved Web appearance, including its
content background and overlays, even if the separate PiP document reports another
preference. Settings and owner appearance changes apply live; Classic/default remains
unchanged. Browser-native PiP chrome is not recolored by Cost Guard.
USD is reference token valuation, not billed spending. No CCost selector remains
on Models or other report pages.

Each selection saves immediately to `config/user-config.jsonc` through the private
authenticated/CSRF-protected API. Only confirmed success changes the loaded theme
or Python-prepared CCost tokens, including retained report and live session views. There is no
reload, report/history/pricing/account acquisition, host restart, Apply button or
browser-local preference. All dropdowns disable briefly during a write. Failure
restores the last confirmed choices and shows an accessible error; select again to retry.
Mini position/size preferences affect the **next opening**, never the size/existence of an open window.
Until the initial settings read succeeds, controls cannot claim a saved choice and
Mini stays unavailable; opening Settings retries the read.

```json
{"webSettings": {"theme": "default", "ccostDisplayUnit": "credits", "miniWatchPlacement": "remember-last", "miniWatchSize": "fit-on-open", "quotaDisplayMode": "default"}}
```

The enums are lowercase `default|classic|web`, `default|credits|usd`,
`default|remember-last|standard`, `default|fit-on-open|remember-last` and `default|used|remaining`. Missing overrides show Default without creating a
user file. **Default inherits that preference's current application default**, including
after a future version changes it. Explicit Classic/Credits/Remember last stay pinned
even when their effective behavior currently equals Default. Reads/saves preserve the
selected intent, not just the resolved value; opening Settings does not migrate a file.
Theme precedence is nested user choice (including symbolic `default`), then legacy
user `webTheme`, then the shipped theme. Old valid overrides still show as explicit.
Selecting Default bypasses a retained legacy override without deleting/reformatting it.
Web CCost independently defaults to **USD**, including Mini Watch and related Web views.
Missing or symbolic `default` overrides inherit USD; Settings shows **Default (USD)**.
Previously saved explicit Credits or USD choices remain untouched. The CLI still defaults
to Credits. Its `ccostDisplayUnit` key and
`--ccost-unit` override keep their behavior and cannot override a Web choice.

Reload/new tabs/relaunch read confirmed file values. Theme is in the early HTML;
CCost is read before report/Live presentation. Reopening Settings recognizes valid
external edits, without polling or automatic cross-tab broadcast. Existing tabs
retain confirmed values until their next settings read or successful change.

Mini defaults to **Fit on open**: the narrowest measured opening width fitting
Cost Guard · Watch, Earlier Sessions and complete CCost Today on one row, with
width-aware content height and capacity for two running rows, all accounts and warnings.
Earlier Sessions pointer/keyboard activation grows/shrinks to measured content;
passive Live updates never resize. Outer height is capped at 1,000 DIPs or known
available work area, and native clamps retain accessible document scrolling.
Remember last size permits browser-native manual bounds in the **same live opener
and host**, without forcing the minimal Fit width. Native placement couples position and dimensions: Fit prioritizes sizing
and may reset position; Standard position may reset remembered size. Reload/host
restart starts fresh. No exact coordinates are promised or pixel geometry persisted.
See [Mini Watch](web-mini-watch.md) for browser limits and measured evidence.

Quota display applies immediately to native finite quotas in Accounts, full Watch and
an already-open Mini, including retained observations. Remaining uses the same account,
window and denominator: 5,608/25,000 Used becomes 19,392/25,000 Remaining, about 78%.
The bar fills with available capacity; zero Remaining is still exhausted/red, while a
full Remaining bar is healthy. Unrounded native evidence determines exhaustion.
Unlimited plans keep Used with no finite bar; unknown limits/usage never acquire a
synthetic remaining amount. Stale/partial evidence remains qualified in accessible help;
brief live revalidation does not add a flashing status sentence.
The bare CCost parentheses switch too: Used is observed period reference cost;
Remaining is a same-window reference-capacity proxy. Full Watch and Accounts show **Capacity**
above each quota bar. A verified Copilot included AI-credit limit supplies nominal
Capacity and native Remaining; other valid windows extrapolate `observed CCost / raw
fraction used`. These are not guaranteed budgets or billed balances. Unknown evidence
shows **?**, Unlimited Capacity **N/A**. Focus/tap the visible label/value for native amounts,
attribution and limitations. Credits/USD converts all three reference figures together.
A provider-confirmed idle 0%-Used window shows a healthy **100% remaining** bar while
its CCost Capacity/Remaining can remain unknown; **Window not started** is preserved.
Native money, Remaining/day/workday pace and CLI orientation remain independent.

Only these five nested fields are writable. A setting stays shared while Web only
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

Models, Token Mix, AI Stats and Comparisons automatically start their existing finite
report on the first visible eligible entry. They share one centered determinate
**0–100%** bar, integer percentage and short work description below it. Percentages
use bounded stage weights, not a measured global denominator; actual local counts
appear when supplied. They never advance from elapsed time or move backwards within
an attempt. Opaque I/O can hold the bar while its work remains identified. Only an
applied usable result finishes at 100%; usable partial results still show their
separate partial/unavailable coverage warnings. Failure/cancellation/timeout never
claim successful completion. Stable nodes, reserved stage height, tabular numerals
and stage-only polite announcements avoid poll-by-poll jumping or announcement spam.

Authenticated source/slot waits use bounded backoff; terminal failures remain
actionable. **Retry** is recovery-only. Every actual report child retains its
8 MiB result limit, owned cancellation and parent-loss cleanup, not an elapsed-work
abort. Managed historical work
can resume only through bounded, verified checkpoints. No user-facing Cancel,
Stop loading or Abort is added. One host dispatcher owns route priority, retained
results and staggered inactive warming; browser hiding demotes interest without
discarding useful work. Watch/Mini/Accounts keep their protected Live owner.
Reloads and other authenticated tabs reuse valid host results, but no fresh result
is promised across host restart. Background refresh is silent once useful content
exists, retaining sort, selection, scroll and focus. Navigation/heartbeats never renew observation age.

Above the table, **Refresh price list** precedes **Prices last fetched: YYYY-MM-DD HH:mm**
in the configured timezone (or **Unavailable**). This is the last successful upstream
GitHub pricing observation, not page load or release-metadata enrichment. Explicit
refresh bypasses even a fresh cache, then rebuilds one coherent Models report on the
existing finite-job lane. Duplicate in-flight requests coalesce; account acquisition
and Watch's pinned valuation stay unchanged. **Refreshing…** disables duplicate clicks.
Offline/invalid retrieval retains the old table/date with **Price list refresh failed;
previous prices retained**, allowing retry. Unchanged successful prices can advance
the observation date without claiming a rate change. Filters, Shift multi-sort,
Credits/USD, focus and horizontal panning are preserved where possible.

There is no **More information** disclosure or concept-card block. Header text alone
reveals Publisher/Model/Release-date definitions and a grouped Relative CCost/Token
Mix explanation: actual up-to-100 qualifying completed prompt count, one identical
token mix across models/tiers, unitless full-catalog ratios, and source tier thresholds.
Without a qualifying sample, the hidden 2/96/1/1 ranking fallback is explained and
observed ratios remain blank. Credits and reference USD (`100 credits = $1.00`) are
display units on a Copilot AI-credit-equivalent reference basis, not native quota or billing.
Sorting arrows, click/keyboard/Shift actions and accessible names remain separate.
Active promotions retain their highlight and one unnumbered postfix star after the
complete Relative CCost tier chain. Hover, keyboard focus or touch opens multiline
**Price Promotion** help for that model's actual offer, discount and end/resume dates.
There are no numbered promotion footnotes below the table. **New Models** notices sit
above it, with the two filters grouped at the right (wrapping on mobile).
Routine source/catalog-verification caveats are not displayed. **Accounts** retains full supported quota,
billing, subscription and attribution details and its canonical acquisition behavior.

Healthy connections have no visible status label or banner. An unhealthy loaded page
shows a compact, actionable warning with hover/focus/touch-accessible connection
details. A server that never served the page cannot display an offline page. The
global footer is removed; guarantees remain in relevant optional report help.

## AI Stats

**AI Stats** at `/#/ai-stats` turns your robot adventures into ten numbers and a
little friendly banter. Old `/#/cost-per-hour` bookmarks arrive here too.

The emoji cards keep two sections:

- **Overview:** AI Hourly Rate, Total AI Cost, AI Working Time, Average Cost per Session.
- **Fun Facts:** Most Expensive Session, Longest Session, Busiest Day, Night Owl,
  Coding Streak, Peak Parallel Sessions.

Every card gets a number and a playful trait, even when the silicon crew has taken
the whole period off. Real session records link to their session pages. Hover,
focus or tap a card title for a short explanation of its meaning. Long names and
enlarged text wrap naturally, with equal-height cards within each responsive row.
An extra **Biggest AI Speed Gap** or **Original Thinker** fact can join the party,
with the existing Comparisons link.

Choose **Today | 7 days | 30 days | This month | All time**, starting at **30 days**.
The rolling choices cover 7/30 × 24 hours; Today and This month follow your configured
local calendar. All five buttons have friendly hover, keyboard-focus and touch help.
Switch Credits/USD to change the money display while keeping your period and cards.

Working Time counts overlapping robot activity once. Night Owl follows the
22:00–06:00 shift; Coding Streak celebrates consecutive active calendar dates.
Session records, busiest dates and parallel parties keep their familiar places.

A cold visit may briefly say the robots are warming up. Numbers arrive as the
history is collected and improve along the way. Already loaded cards stay visible
during refresh, period changes and interrupted updates; an empty period gets ten
cheerful zeros. There is no permanent Load/Refresh toolbar or Cancel button.
Automatic refresh targets about **15 minutes** in the foreground and **30 minutes**
inactive, reusing collected history across periods, reloads and host restarts.
Leaving the page does not discard requested work. Watch, Sessions, CLI, Token Mix
and Comparisons retain their own behavior. No new settings or model calls are added.

## Comparisons

`/#/comparisons` automatically checks all available recorded root history, including
archived sessions, for **exactly the same first actual user input**. Each group has
at least two independent root sessions. Case, whitespace, full text and semantic
part order matter; titles, model/effort and later prompts do not determine a match.
Recorded inline attachment content can verify identity; a filename, path or remote
URL alone cannot. Unsupported/missing input and unavailable content are excluded,
never fetched from referenced paths/URLs. Deleted/pruned history cannot be restored.

Each of up to **ten unframed groups per page** has the newest-active member's title,
then **`Prompt 1:`** and the existing short safe first-input preview, one Watch-style
table and a quiet fact strip below it. Long previews keep their truncation ellipsis;
attachment-only, private/withheld or unavailable input keeps an honest placeholder.
No prompt column or repeated per-row preview is added. Empty shared notices reserve
no box or blank height; meaningful progress, coverage and error status stays visible.
Previous/Next pages groups, not runs; all repeated runs remain separately linked,
including three executions of the same provider/model/effort. Groups and rows sort
by newest supported session-tree activity, with deterministic ties. If a page's
revision changes, a bounded retry returns to page 1 rather than silently skipping
or duplicating groups. Narrow tables pan horizontally; the document scrolls vertically.

Columns are **Session | Started | Model | Effort | CCost | Duration | Context |
Token Mix | Calls**. All metrics belong only to the first prompt's canonical causal
execution, including attributed child/tool/background work—not the whole session
or later prompts. Started uses configured-local 24-hour time. Context estimates the
next incoming tokens immediately after that prompt, not remaining model capacity
or a future prompt's context. I/C/W/O describes token usage composition. Shared
hover/focus/touch help explains actual bounds, contributors, cost splits and counts.
Mixed models/variants have `*`; running/failed/aborted/unknown runs are labeled.
`?` marks partial cost/counts; unsupported values stay N/A, not fabricated free work.

Time gaps require reliably finished runs; cost gaps additionally require full token
and price evidence. Same-model variation retains separate repetitions. Arithmetic
uses unrounded backend values; a zero baseline has no ratio. These are observed runs
with equal first input, **not controlled benchmarks or answer-quality rankings**:
repository state, instructions, files, tools, environment and remote services can differ.

Finite, read-only acquisition shares the existing 8 MiB result/resource bounds,
progress, cancellation, private session/CSRF boundary and low-priority queue. A compact
source-/tree-/pricing-/identity-keyed index stores fingerprints and derived metrics,
not raw prompts, previews or attachment bodies. Changed roots are batched; unchanged
archives are not fully rehydrated at every refresh. Only displayed cached group
representatives need fresh ephemeral previews (at most ten). Existing derived
analysis can be read, but matching does not create a new raw-prompt analysis cache.

The host targets quiet cache-first checks approximately every **five minutes**
foreground and **twenty minutes** inactive, staggered behind Live/foreground demand.
Retained DOM/focus, real observation
times remain internal; populated reports have no passive as-of/refresh strip. Complete no-matches, excluded
inputs, changing/partial coverage, loading and unavailable results remain distinct.
[Verification and limitations](../development/journal/web/comparisons.md).

**Settings → CCost display** switches Python-prepared reference
amounts in place, without report jobs or provider refresh. Native money, quotas,
Unaccounted usage and Relative CCost stay unchanged. The saved independent
`webSettings.ccostDisplayUnit` applies across routes, publications and live Sessions,
including reload/new tabs. No URL, browser storage or preference cookie is written.

v80.107 keeps healthy authenticated streams open without periodic rotation. Connected
status is now visually quiet; only actionable states show a notice, with expandable
host/source timestamps. See [real-source soak and fault evidence](../development/architecture/governance/verification/web-live-stability.md).

v80.106 fixes real-installation Normal results that exceeded the unchanged 8 MiB
limit because they carried unused month-wide causal request identities. Normal now
retains per-root revision evidence without that detail-only payload; no model rows,
account periods or totals are capped. Models renders every matching reference-model
row with document scrolling. Token Mix phase costs remain in the separate Token Mix report;
current account provenance is available through the shared live cards' help.

Classic defaults to dark; Web follows system light/dark. Both use local fonts, visible
keyboard focus, sticky headings and narrow-table scrolling; reduced motion disables
transitions. “Reading this report” contains definitions, not rows/totals. Accounts uses
only the live Watch subscription cards described below. Models follows the hierarchy above.
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

## Navigation and host-cached reports

### Disposable historical cache

SQLite is acceleration, not the source of session history. Opted-in session entries
stay hot when actual root/child activity **or** meaningful use is within the last
30 rolling days. Selected visible reports, Sessions/detail and Full/Mini Watch
count as use; hidden polling and passive warming do not. Unknown/legacy clocks
remain protected, without scanning all history at startup.

The existing host loop may attempt a small idle cleanup only after **60 minutes
of continuous host uptime**, at most daily. Active work, visible demand, source
changes and contention defer/cancel it. Pruned old history rebuilds on demand;
All time/history completeness, source sessions and operational JSON are unchanged.
Freed SQLite pages can be reused without making the physical file smaller. There
is no automatic VACUUM, database reset or user cleanup step.

The Beta shell provides Models, global Watch, live Accounts, a Sessions catalog, Token Mix, AI Stats, Comparisons, Settings and live session detail. Global `/#/watch` is canonical; legacy `/#/live` links replace the same history entry. Accounts shares Watch's publication, not a finite report. Models and the three historical reports share host-owned caching, priority and freshness; their distinct report populations/totals remain independent.

Sessions is the historical navigation entry point. The former `/#/reports` page is retired: old links, including date queries, replace that history entry with `/#/sessions` without starting a date report or applying a filter. Sessions has no date-range filter; sort on Last activity or its other catalog columns. CLI date/date-range reporting and the shared backend report APIs remain supported.

### Live Accounts

`/#/accounts` shows only the **same subscription-card grid as the bottom of Full Watch**:
account title, CCost Today, native primary percentage and period CCost, Capacity, bar,
reset/remaining pace, secondary quotas and truthful provider/freshness warnings. It has
no report title, Refresh/Cancel, snapshot/search, billing panel or observation disclosure.
Shared navigation and actionable authentication/source/host notices remain available.
Native amounts and attribution live in the existing focus/tap/600ms-hover help, not a
second report. CLI and Diagnostics keep their detailed account layouts.

The existing single authenticated Live stream updates Accounts even if Watch has never
opened. Switching routes uses the latest retained common observation immediately;
it starts no finite report, account refresh owner, provider call, history scan or second
stream. Initial pending data shows **Loading accounts…**, not a confirmed empty list.
Observed empty, unavailable/partial and retained stale observations stay distinct.
Stable account identities and bound metric/help nodes retain focus, selection and
scroll through ordinary updates. Real account removal/reordering is still applied.
Credits/USD, Used/Remaining and themes apply to visible and retained cards without
acquisition or client-side valuation. [Verification and limits](../development/journal/web/accounts-live.md).

| CLI use case | Discoverable fragment route | Protected scope |
| --- | --- | --- |
| Global Watch | `/#/watch` (legacy `/#/live` alias) | One host-owned engine; one-prompt cards, five historical sessions and independent daily/account observations |
| Models | `/#/models` (legacy `/#/overview`, `/#/models/all` normalize here) | Independent selectable/full and latest-version filters, exact tier-aware multi-sort, four columns and full document scrolling. Blank relative cells without completed priced prompts; unknown ratios retained. No account cards or native-rate fifth column. |
| Accounts | `/#/accounts` | Shared live Watch subscription cards, native windows/pace, Today/period CCost, Capacity and account-specific warnings; no finite report |
| Sessions | `/#/sessions` | Live six-column catalog, 50 sessions/page, globally sorted canonical keys and stable older-page membership; available archived roots included |
| Session detail | `/#/sessions/<id>` (legacy `/live` alias) | Complete chronological live history, no user-facing pages or modes; links from session names and Watch |
| AI Stats | `/#/ai-stats` (legacy `/#/cost-per-hour` alias) | Ten playful numeric cards plus an optional matched-input fact, five periods, early figures and retained refresh; host warms default 30 days and checks at ~15/30 minutes visible/inactive |
| Comparisons | `/#/comparisons` | All available root index, exact first-input matching, ten groups/page with every individual repetition, first-prompt metrics and qualified local gaps; host warms the first page and checks at ~5/20 minutes visible/inactive |
| Historical Token Mix | `/#/token-mix` | Host-owned first warm-up and ~5/20-minute visible/inactive checks. One total/token-volume summary and two 13-column model/publisher tables split Input / Cached input / Cache write / Output percentages and category CCost, with Prompts/Calls/Tokens/Total CCost. Every column sorts locally by exact source values; all rows and full names remain readable through horizontal panning. Partial/unavailable coverage stays explicit. |
| Web Settings | `/#/settings` | Theme, CCost display, Mini position/size and Quota display; inherited/explicit intent, authenticated narrow config read/write, no report acquisition |

Generic finite report tables retain search/filter/page controls and ascending/descending/original-order sorting. Token Mix instead has independent ascending/descending table sorts, default Total CCost descending, without filters, a pager or nested vertical scrolling. Header text owns shared hover/focus/touch help; no question-mark prefixes or icons are used. Models uses its independent filter/multi-sort contract; Watch keeps fixed chronological cards. Accounts and Sessions have no report toolbar, search, filters or snapshot controls. Sessions' catalog headings request full-catalog server sorting, not presentation-only page sorting. Detail has no sort or pager. Decimal keys stay exact and unknowns sort last.

Token Mix targets **five-minute** foreground and **twenty-minute** inactive checks. The host, not hidden browser timers, owns due times. Compact revision/config/price-keyed facts can be shared with AI Stats and Comparisons without sharing their final totals. Changed roots are revalidated; removed roots disappear. Catalog metadata is not usage. Fork deduplication, publisher grouping and pricing tiers retain canonical Python semantics. No new account polling, inference or browser history ledger is introduced.

During ordinary Token Mix refresh the accepted summary and both tables remain usable. Complete results reconcile together in place, preserving independent sorts, Credits/USD, rows, focus and scroll/pan anchors. Failed background refresh retains the actual old observation silently; it never becomes live merely because HTTP works. Fully unavailable values remain N/A; intrinsic partial costs/volumes retain their semantics. Live and its account scheduler continue independently. URL fragments contain only scope/locators, never prompt content.

### Host-owned freshness and background warming

**Models, Token Mix and Comparisons** share these presentation bands, measured from
successful source observation—not visits, timers, cache writes or failed attempts:

| Retained scope age on visible re-entry | Behavior |
| --- | --- |
| Up to its normal cadence | Display immediately; no unnecessary scan |
| Older than cadence, including hours/days-long completed work | Keep qualified content visible; host-owned cadence/backoff controls silent refresh |
| Failed background acquisition or cancellation | Retain qualified data silently and keep provenance internally; never fabricate zero/freshness |
| Proven source/dependency invalidation or malformed observation | Withhold invalid values until qualified evidence is available |

The initial selected route wins before speculative heavy warming. Thereafter the
host opportunistically warms Normal Models, Token Mix, default 30-day AI Stats and
the first ten-group Comparisons page. It does not eagerly scan every AI Stats period
or every session detail/page. Models' actual qualified sample controls cadence:
under 100 completed priceable prompts targets 15 minutes foreground / 45 inactive;
100 or more has an hourly floor. AI Stats targets 15/30 minutes; Token Mix and
Comparisons 5/20. Due times are staggered and can be postponed by foreground/Live
pressure, not promised at an exact second. Successful completion schedules the next
cadence; neither old observation age nor midnight causes immediate recomputation loops.
There is no historical as-of strip, reserved gap, passive refresh tooltip or live-region
announcement on populated reports. A successful publication lookup is not a new source
observation. AI Stats shares host-owned cadence and warming, but keeps its playful
cards and quiet refresh behavior described above instead of historical status labels.
Failed attempts, completion and navigation never renew observation age.
Sessions/details use their own source-backed age and bounded leases; Watch/Accounts
remain Live rather than becoming real-time merely from a historical snapshot.

Session-ID links open `/#/sessions/<id>`. Fragment routes support direct links, reload and browser Back/Forward without expanding the HTTP path allowlist. The one-use bootstrap fragment is removed before requests; ordinary session routes are preserved on reload. Names/prompts are text, never links or tooltips containing source paths. Navigation and paging never put prompt/history payloads in browser storage or history state.

Every finite result retains observation time, source status and per-root revision evidence. A running prompt is **running at that observation**, with provisional values. Models' explicit **Refresh price list** remains separate from routine cache-first background work: successful retrieval invalidates related warm projections; failed retrieval preserves old valid data/prices. Missing, empty, partial, source failure and unavailable accounts remain distinct from acquired zero.

A continuously changing root can remain unverifiable after bounded source retries.
Precision-oriented historical reports may omit that root and display **Partial history**, with
the omitted-root count; totals/groups then cover only verified evidence. Mixed
snapshots are never used. Healthy unresolved proof remains pending with bounded
retry; genuine source faults are reported rather than showing invented zeros.
Cached price changes are checked without fetching upstream prices.
Changing pinned runtime configuration (for example timezone/source settings) stops
the old host and requires relaunch; ordinary hot Web preferences remain applicable.

Session detail shows **Prompt | Model | Effort | CCost | Calls | Duration | Ictx | Ictx CCost | Extra CCost | Token Mix %**. Python's category order remains **I = Input; C = Cached input; W = Cache write; O = Output**. Input is uncached, Cached input is cache read, Cache write is cache creation, and Output includes reasoning. Full-session totals and main/linked-child breakdown come from the canonical result, never from loaded chunks. Unknown, incomplete and estimated amounts remain honest; a published Cache write price does not imply observed tokens. CCost is not billing. The browser performs no valuation or token attribution.

Most finite report tables show 50 rows/page from one immutable API result. Sessions instead reads the host-owned catalog without submitting finite report jobs. Its exact six columns are **Last activity | Session name | Model | CCost | Prompts | Duration**. Last activity is **YYYY-MM-DD HH:mm**, using the viewer's browser timezone/DST, never AM/PM; sorting retains raw timestamps. Names link to detail. Confirmed current running work prefixes **[RUNNING]** and colors every row value yellow; stale/failed evidence cannot assert running. Only names expand/ellipsize. Previous/Next are disabled-aware buttons around a centered range/page label; narrow layouts place the label above them. URL history and older-page membership remain stable.

Sessions, Models and both 13-column Token Mix tables share Watch's compact surface-tone headers, full cell dividers and one thin rounded frame. Numeric values retain their readable minima; deliberate horizontal panning never creates an inner vertical scroller. Model filters/promotions/multisort and Token Mix's complete one-line names, independent column sorts and five-minute acquisition stay unchanged.

Sessions can show **[RUNNING]** before scalar hydration when the shared Watch capture
affirmatively observes execution. Candidates/timestamps alone never establish running;
original proof expires after 15 seconds and source outages suppress the marker. A newer
canonical terminal observation clears it independently of summary/pricing delays.
Model, CCost, Prompts and Duration hydrate through the existing bounded index and active
five-second browser cadence. Known values remain visible with retained/partial qualifications;
only actual pending acquisition shows **Loading…**, not a definitive failure or unsupported
duration/model. The last measured execution duration is not extrapolated during idle gaps.
Keyed cells, links and help targets remain connected during metric changes; selection/focus
can defer reordering, but do not freeze live values.

Hover, keyboard-focus or tap the **Multiple models** text to see the actual distinct
provider/model contributors, including canonically attributed child requests. Shared
ContextHelp handles Escape/leave and refreshes an open list in place. Running, incomplete,
retained or bounded/truncated lists say **observed so far**; missing identities are explicit.
There is no extra column, question-mark button, native title popup or per-row browser fetch.

Last activity descending is the default. All six server comparators use canonical values, not formatted strings; exact CCost, numeric count/millisecond duration and deterministic ID ties span the entire available catalog. Activity/name work immediately. While a cold or invalidated scalar index finishes, the previous usable order/header/pager stays unchanged without a polling caption; the requested global sort applies only when all metric keys are valid. A first-ever response may initially use the actual activity order. The table never labels a page-only order as global. Canonically unknown/partial keys sort last; not every historical root is already indexed.

Initially pending summary cells show **Loading…**, not unknown/zero. An acquired zero stays zero and canonical unknown stays N/A. Failed acquisition shows **Unavailable** or silently keeps last valid values; bounded retries do not restart known values or add retained-evidence help. The most recently viewed page gets seven admissions per background fairness turn, still at most four roots per slice with a two-second admission budget. Unchanged validated summaries are reused. Slow individual source reads retain their transport limits, so this is priority, not an instant-readiness guarantee.

Detail's **Ictx** is only the prompt's first-request incoming context, never a delta/next-context arrow; Watch and CLI retain their richer context displays. Prompt previews yield before metric columns, grow on roomy screens and retain complete text in help. One horizontal region handles genuine minimum-width overflow; the document owns vertical scrolling. Initial capture and pinned-chunk acquisition show an indeterminate **Loading session…** progress bar, never a fabricated percentage. Complete retained history stays usable during background checks; explicit source errors replace loading rather than looping forever.

Visible Sessions reads about every five seconds. Page 1 follows arrivals; older pages retain epoch membership/order. Navigation restores the last requested offset/sort/epoch. Expired leases/positions recover silently with one bounded reopen per poll: without proof of the old membership, return safely to latest while preserving sort/direction and synchronizing URL, pager, rows and epoch. No position-change banner or bottom finite-report/0% widget is present; an hour-old observation never hides usable rows. While a requested global sort is pending, keep the previous actual order/header/pager until all keys are valid. Activity/name acquisition covers requested fifty-row pages only; hidden interest demotes scalar indexing. Initial missing content may show loading; retained content and stable empty sets refresh silently. No cross-root atomic snapshot is claimed.

## Complete live session history

Both normal and legacy `/live` links open the same live page; the legacy URL replaces its history entry. **Show all sessions**, the real title, full selectable **Session ID**, and Watch's shared canonical **Context:** line precede one unframed table. The line uses the same session continuation estimator, triangle/octagon severity, price impact and contextual help as Watch; unknown is N/A, never a guessed warning. No redundant total-cost/rate summary or mode buttons remain.

Every observed prompt appears oldest to newest, with no 50-row cap or user-facing pagination. Prompt alone flexes/ellipsizes; other columns keep intrinsic widths. The document scrolls vertically. Clock, actual **[RUNNING]**, number and preview share one line; running ink is yellow across all cells, reverting to theme foreground after canonical completion. Model/Effort use structured main-prompt evidence. Shared heading help covers all ten columns; prompt clock and CCost expose useful conditional detail. **Complete session** remains the aligned canonical whole-session footer, not a sum of fetched rows.

**[UNVERIFIED]** distinguishes an unfinished assistant whose complete source observation has no native running drain or supported tool/child/background activity. It is not success, failure or proof that another OpenCode process stopped. Known calls/usage remain, but Duration and affected session-duration totals are **N/A**, without an invented finish time. Later authoritative activity or terminal evidence updates the same prompt.

Stable keyed rows preserve document anchors, focus and text selection. Large new suffixes are built detached and batch-appended. Source omissions retain canonical evidence and frozen lifecycle/time until observed again; deleted-before-observation history cannot be recovered. Missing, archived, partial and unavailable remain distinguishable from observed empty. Silence/connection loss never proves completion.

Authenticated, CSRF-protected `/api/detail` uses `open`, `begin`, revision-pinned `chunk`, and `close`. Internal rich chunks contain at most 25 rows with full-session totals; a captured revision stays coherent even while acquisition advances. Compatibility `page`/`freeze` actions remain internal APIs, not a UI experience. Five-second polling is independent of SSE. The existing isolated round-robin detail lane owns acquisition; the catalog index has a separate single-worker lane, so a slow root cannot occupy the detail worker. Neither HTTP nor browser code acquires source history.

Catalog indexing admits at most four roots per slice and no further root after two seconds of measured work; a single read retains the source's timeout/cancellation bound. Fair visible/live and historical admission prevents starvation. Compact disposable summaries are checked against source identity/revision, algorithm, configuration and prices; live/running roots force fresh acquisition. Dependencies revalidate every 60 seconds while browsing, subject to in-flight source work. This is acceleration state, not a user ledger or source mutation.

Admission remains 16 observed detail trees/32 handles; catalog has 32 five-minute handles and at most eight epochs each. Busy/expired handles fail explicitly. Leaving detail closes its handle; host restart discards retained history. No model calls, source writes, new dependency, frontend build or account login is introduced.

Focused catalog/detail/real-HTTP VM tests, a hidden Chromium synthetic theme/viewport/zoom probe, and `probe_web_live.py --sessions` cover complementary boundaries. Actual results, cold-index coverage and unmeasured physical/macOS/assistive behavior are recorded in the [Sessions findings](../development/journal/web/sessions-live.md), not inferred from VM assertions. Other finite reports retain frozen DOM, controls and failure semantics.

## Global Watch and reconnect

The common shell distinguishes starting, connected, **SOURCE UNAVAILABLE** (HTTP works, acquisition does not), **RECONNECTING**, **OFFLINE — last observation**, **AUTHENTICATION EXPIRED**, changed host identity and **STOPPED — NOT LIVE**. Healthy status is visually quiet. Actionable non-sticky warnings expose host/source timestamps on hover, keyboard focus or touch disclosure. Account freshness and frozen report timestamps never become fresh merely because HTTP works. Stop/identity/authorization loss disables acquisition controls, ends retry and retains readable values. Use the OS launcher to restart or obtain fresh authorization; no host is started by the browser.

One authenticated `/api/live` watchdog runs at ten-second intervals after the preceding check completes; every ordinary request has a five-second deadline. Thus a reachable tab normally detects abrupt loss within fifteen seconds (browser/OS suspension can delay timers). `pageshow` and visible-tab resume revalidate; only stale checks (at least fifteen seconds) or interrupted streams first mark retained data as reconnecting. Healthy HTTP cannot restore a broken stream to connected. Same-instance EventSource retry preserves cookies, replay/resync and retained values. Authenticated API response identity is pinned per page; a replacement host is never silently accepted even if another tab renewed its cookie. No identity, token or report is persisted in browser storage, and no port/network scan or sensitive unauthenticated endpoint is added.

[Built-in browser, deterministic and real-source verification](../development/architecture/governance/verification/web-connection.md) records the tested states and explicit physical-tray/suspension/restart/macOS limits.

Watch gives each prompt/session card a subtle rounded frame. **Earlier Sessions** starts collapsed: five eligible
distinct sessions selected by newest supported prompt finish, then displayed oldest finished first,
newest finished last, one exact latest-finished prompt each with deterministic ID ties. Unknown-ended
history fills spare slots before known finishes, ordered by stable identity; it never displaces a known finish. It updates
while collapsed, without an age/startup cutoff, excluding active/recent sessions before
limiting. Expanded history is unframed in normal page flow, with one theme-aware divider
before running cards and no nested vertical scrolling or height cap. Collapsed/empty
history has no divider. The active list has no cap/filter/pager; concurrent prompts
get separate cards, oldest focal first, with one row even during terminal grace.

Earlier membership is published only after revision-matched complete evidence covers
every potentially displacing root. Until then both Watch and Mini show **Loading
earlier sessions…** only before the first usable set, not plausible catalog candidates.
One source-scoped proof epoch carries the five/three population atomically; ordinary
refresh retains qualified previously verified cards silently, with no appended footer,
checked-root counter or accessible refresh announcement. Verified empty history stays
**No earlier sessions** during revalidation. Computational duration never
turns healthy pending proof into **Unable to verify latest sessions**: bounded work
continues automatically, including after transient revision churn. Genuine sustained
I/O failures or immediate authentication/schema errors remain typed and actionable;
recoverable failures retry without a manual Retry. Removal/resumption invalidate
affected entries. Metadata is only an admission hint, not a finish-time proof; a
continuously changing source may remain meaningfully unverified until coherent
coverage is possible. Active prompts, Today and subscriptions do not wait for history.

Once membership is certified, supported names, finish times, model/effort and context
appear without waiting for the independent whole-session **Total CCost** or shared
numeric price-comparison sample. Missing cost says **Loading…**, not zero; the known
context and threshold warning remain usable while price comparison is pending or
retrying. Enrichment updates the same Full/Mini winners and preserves their original
proof epoch/time. Existing qualified values remain visible during ordinary refresh.
No cheap metadata-only global-winner certificate is assumed or speculative name list
presented as final history. [Controlled and real-source evidence, tradeoffs and
limits](../development/journal/web/foreground-recovery.md) distinguish correctness
from cold, retained-cache, warm and promotion timings.

Session title alone links to that canonical Sessions route. The footer keeps whole-session
CCost separate from prompt-local costs; duration remains prompt-local. Canonical child/compaction/context evidence still feeds
prompt metrics. Credits/USD follows Web Settings. Valid metrics remain visible during
ordinary refresh. Retained source values remain quiet through retries and long delays;
only genuine initial acquisition can show loading. The global **CCost Today** label,
amount and prompt count in Full/Mini have no tooltip, partial disclaimer or help target.
Host-wide actionable outages use one connection recovery surface. Replayed snapshots,
another lane's progress and cost-only updates cannot prove source recovery. Pricing gaps,
N/A and actionable provider/auth/host failures remain explicit. Finite historical
results retain their original observation internally; positive age alone does not withhold
qualified completed data, and their refresh cadence is not a live retry caption.
The ten columns are **Started, Duration, Prompt, Model, Effort, CCost (I + E), Calls,
Token Mix %, Ictx, Δ Ctx**. Ictx is the first request's effective incoming context;
the footer's Context remains the estimated next incoming context.
Running keeps **Started** and start-ascending order. Earlier replaces only column 1 with
**Finished**; Duration stays column 2. Both clocks show configured-timezone `HH:mm`,
with full local date/time on hover/accessible focus; Finished includes the UTC offset
for repeated DST hours. Unknown supported endings show **—**, never start plus duration
or observation time. Prompt starts with
its canonical session-local `#N`, never a visible-row index. Only preview text ellipsizes;
the number stays visible, with no per-row preview question mark or full-text popup,
and lifecycle state remains accessible on the row. Every header explains its metric
on hover, keyboard focus or touch/click; Escape or leaving focus dismisses the explanation.
Both prompt tables show **total CCost (Incoming Context CCost + Extra CCost)** in
the single **CCost (I + E)** column. I values the initial incoming context on the
first attributed request; E covers the remaining canonical usage, including output,
later requests and linked-child contributions. These are the CLI session report's
existing diagnostics, not billing, quota usage or Token Mix's Input category. Raw
I + E reconciles to the total when known; separately rounded Credits/USD values
need not visually sum. All three use the selected Web unit and shared formatting.
Partial totals retain `?`. Whenever the **displayed total is zero** in the selected
unit, both displayed components are zero: `0 (0 + 0)` or `$0.00 ($0.00 + $0.00)`,
even with observed calls or missing component evidence. This presentation override
also covers tiny positive costs rounded to USD zero; it never changes precise values.
Positive displayed totals keep independently unavailable components as `N/A`.
Report-owned evidence flags require first-request input/cache-read/
cache-write counters for I, and every attributed request's four token categories for E.
Full Watch can therefore withhold an unsupported component even when the existing CLI
diagnostic uses normalized placeholders; raw costs and CLI behavior are unchanged.
Wholly unavailable totals stay `N/A`; sparse non-billed compaction
cells stay empty. Accepted captures/SSE update the same prompt's split without
browser valuation, polling or extra history scans. Mini Watch remains total-only.
The Full Watch CCost value has separate detail: main prompt and distinct causally linked
subagents, split by actual model/recorded effort, with Input, Cached input, Cache write
and Output reference costs, subtotals and full prompt total. These are charged token
categories, not the header's first-request I + E decomposition. Credits/USD use canonical
unrounded request prices; rounded lines need not visibly sum. Unknown categories are
omitted, partial pricing qualified and long detail bounded with an honest omitted subtotal.
Token Mix % is raw observed **Input / Cached input / Cache write / Output** token volume,
not cost shares; reasoning is folded into Output. It uses canonical prompt-attributed
physical requests, including child/model contributions, and CLI prompt rounding.
Accepted captures update the cumulative mix at the existing cadence/SSE publication,
not client ticks or intra-call streaming. Zero/partial/missing telemetry is `N/A` or
`running`, never invented zero percentages. CLI reports and Web Watch use the same
coverage rule: every attributed call must report all four categories and their pooled
total must be positive. Missing fields make the denominator unknown, not a known-token
subset percentage. Completed rows show `N/A`; active rows without a supported share
show `running`. The FR 000558 completed-partial parity exception is closed by FR 000564.
A trailing **\*** on Model means positively linked subagents participated, even with
the same model; a model switch alone gets no star. Conditional model help names actual
models/efforts, and Calls help gives a supported main/subagent split. Ordinary cells
have no generic popup. All cells/headers
stay one line: Prompt alone flexes without a width cap and ellipsizes long text/URLs;
complete metric columns and a 14rem Prompt minimum pan horizontally when necessary.
Tables use theme-aware body/header surfaces and edges inside each session's frame.

Running focal rows and linked titles are yellow. Confirmed successful focal rows
and their titles share the same semantic success green during existing terminal grace;
Earlier titles return to neutral heading ink. Unknown outcomes never imply success,
and resumed/concurrent prompts keep each card's own focal state.
An **Unverified** focal remains visible for refresh, without yellow running ink,
a success checkmark or an advancing Duration. The running summary stays uncertain
instead of asserting that nothing is executing. Missing/partial native status alone
cannot establish this state; a later unavailable refresh does not prove a restart.
Normal activity is gold/brown, failures independently red,
and context guidance severity-specific (gold/orange triangle, ordinary foreground
approaching text; gold/orange triangle and text once exceeded). Observed success is lime, abort/error red, for
`watchRecentEventSeconds` (30 seconds by default), then the session becomes
history-eligible when no other running/grace card remains. Old history does not
replay completion flashes. Active cards show count-first tool/custom-skill
summaries with five named groups and truthful other totals; native disclosures
expand every group and retain their state/focus across updates. The longest
running tool appears at the shared ten-second threshold, in the same semantic yellow
as the running prompt (theme-aware in Web light/dark). Separate background/subagent
**Running:** lines now share that same foreground; counts/Skills remain gold/brown.
Running rows are initially collapsed native disclosures of available invocation
input. Safe command text retains quoting/newlines and available options; other
tools show named parameters, never an invented shell command. A single background
job needs a verified original-call link; aggregates or missing links show details
unavailable. Sensitive, unsupported and oversized fields are explicitly withheld,
not presented as complete arguments. Freeform screening cannot guarantee detection
of every private value. Details are bounded, memory-only and authenticated/local;
expanding executes nothing and does not fetch source data. Duration updates retain
expansion/selection; changed calls, corrections and lost live evidence clear stale
input. See [activity and privacy details](watch-activity.md#full-web-running-invocation-details).
The compact **N failed / cancelled** count includes only evidenced, distinct tool
outcomes. Expanded Tool Calls shows red tool-name/outcome subsets, for example
**2 × grep failed** and **1 × execute cancelled**, below the ordinary all-call groups.
Those red calls are already included in the ordinary totals, not extra calls.
Explicit cancellation wins over error for one physical call; missing evidence is not
success or an invented outcome. Unidentified retained aggregate differences are
labelled honestly. Expanded help explains counts and direct failure-only skill
attribution; a recently loaded skill never inherits unrelated tool outcomes.
Historical cards have no activity section. Narrow tables pan horizontally.

**CCost Today**, four pixels above subscriptions, shows current-local-day reference cost,
initiating prompts. Daily Token Mix categories are not shown here; per-prompt cells
and the dedicated Token Mix page retain them unchanged.
It includes pre-Watch history, running requests and unassigned-account usage, not just
visible cards or subscription sums. Requests use completion/attribution dates; continuing
prompts count once per relevant day, children under their initiator, compaction as usage
only. The acquired integer displays **N prompts**. Full and Mini Watch show the plain
known-priced daily subtotal without partial-cost markers or passive pricing/token/prompt
completeness notices; missing prices/tokens can mean it understates the full amount.
Underlying completeness and unassigned cost/tokens remain intact. Acquired empty usage
is zero; wholly unpriced usage is **N/A**; neither is loading or source failure.
Source changes/minute fallback update retained history and publish cost/count/mix
coherently. Routine refresh silently retains figures; only a scope without valid data
loads. Real failures remain visible. Midnight resets, rejecting yesterday's late results;
CCost Today keeps its label before 03:00. Web Credits/USD and CLI scopes are unchanged.
CCost Today label/value and prompt count each have scoped text help;
there is no far-right question-mark cue or oversized summary hitbox.

Retryable source-read failures retain observations quietly in Full Watch's tables,
footers and daily area; meaningful freshness remains in the unchanged global
connection/source-health notice. Each source/card/daily lane confirms after five monotonic seconds
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

Subscription cards align centered title bands, **CCost Today**, native primary usage
and bars; body values stay left aligned. Full Watch divides a 448-pixel budget by
effective display/page/pinch scale, leaving a rounding margin below the requested
450-screen-pixel ceiling. Cards wrap without smaller text and narrow with the viewport.
Headless Chrome raster checks cover the correction; native owner-desktop physical
measurements and actual page zoom remain unverified. Title padding is slimmer
without smaller text. Native declarations/order, never depletion or
provider identity, select the primary. Missing primary stays unavailable; weekly-only
accounts have no invented five-hour slot or duplicate secondary.

Each quota shows **period · N% used/remaining (CCost)**, then factual **Monthly Capacity**,
**5-hour Capacity**, **Weekly Capacity**, etc. Unknown periods retain **Capacity**.
Every nonmonthly primary/secondary quota adds a visible **Monthly Capacity** line
directly underneath and before its own bar: full-window reference Capacity ×
2,592,000 / verified full-window seconds, calculated with unrounded Decimal.
This standardized 30-day equivalent is always **(guesstimate)**, never an entitlement,
bill or forecast. Compare independent restrictions separately; never add them together.
Unknown duration/recurrence, inactive/expired/stale data, incompatible reference units,
contradictory native data or incomplete pricing show **Monthly Capacity: N/A**, with
the reason in the existing Capacity help. Native monthly windows have just one line.
An empty, aria-hidden noninteractive primary row aligns monthly peers beside an extra
monthly-equivalent line; it disappears for single/all-monthly or separately wrapped
cards. Watch and Accounts use the same full-size card contract by default, including
ordered text, controls, help, warnings, percentages, reset and accessibility; future
deliberate divergence requires explicit owner approval. Mini stays separately compact.
The bar is followed by a tightly adjacent reset and applicable canonical
**Remaining: …/day** and **Remaining: …/workday** (or **no workdays left**). Only real
secondaries follow a divider. No routine rolling/fixed boilerplate appears. Exact
account/window/model costs include pre-Watch native-month history, never Today/30-day
substitutions. Unavailable reference costs show **(?)**; confirmed empty windows
show Used **(0)** independently of Today. Unlimited, sub-100% precision and genuine warnings
remain distinct. Today keeps daily scope/attribution without an estimate suffix (basis
on hover). Accessible help retains native Used/Total and Remaining/Total, native money,
reset and partial/estimated attribution without raw source/observation logs.
Each quota’s Capacity label and number share one compact help target explaining usage
and reference capacity. Account CCost Today label and number explain daily scope and real attribution notes.
For Copilot the observed Used cost and native Remaining need not sum to Capacity.
For other quotas Capacity/Remaining are explicitly explained extrapolations, not
provider-promised allocation. Numeric ratio-derived Capacity shows exactly **(guesstimate)**
after the number; verified directly comparable native allowances do not. Unknown **?**,
missing and **N/A** never get the suffix. Provenance follows each quota across units
and orientations, including Accounts and Mini's Capacity help. Missing native usage never borrows CCost. Credits/USD
changes CCost, not native units. Accounts shares Full Watch's identity-matched
period costs and reference figures; Mini keeps one compact primary line with
exactly **Capacity: value** then **Next reset: value** in its subscription-text help.
Both facts belong only to the visible primary window, with canonical local reset/countdown,
**Window not started** or honest unknowns. No secondary-quota or CCost explanation prose
is repeated there; warnings remain visible on the Mini line. Full Watch/Accounts retain
their richer help. All three follow the same choice immediately, without more polling.

Watch's slim .83rem quota bars have subtle 2px corners and stay teal throughout the non-exhausted range,
including **<100%**. Canonical numeric exhaustion alone makes that quota's entire
usage summary and fill red; any exhausted window adds a muted red tint to only the
subscription header. Other windows, CCost and the card body remain unchanged.
Provider restrictions without numeric exhaustion and stale/unavailable observations
keep their separate truthful warnings. Accepted recovery clears the emphasis.

For resets under seven days, full Watch uses the same Duration notation as prompt
rows: **Reset in 1h28m, 20:09**, or **Reset in 1d3h, 14:30**. The local clock comes
from the actual deadline; its full date/time is available on hover/focus. Seven days
or more keeps the calendar date. Expired, unknown and not-started windows remain
explicit. Existing Live publications update countdowns without browser clocks or
additional provider polls; Accounts and Mini's Next reset share this wording, while CLI is unchanged.

Both prompt tables end **Token Mix %, Ictx, Δ Ctx** (ten columns in total).
**Ictx** is the effective incoming context at that prompt's first request, not its
next context or a sum of calls. It has no approximation prefix; header help explains
estimated/approximate evidence and N/A for missing first-request evidence. Help opens
on hover, focus or touch/click; only the prompt preview ellipsizes, with horizontal pan
for narrow tables.

Two lines directly below each table, before active activity, read
**Context: 123k** then **Total CCost: 4582**, each with a space after its colon. Context is the canonical
estimated next incoming context for the latest valid continuation, including hidden
compaction; its accessible help explains this distinction. Concurrent cards for one
session share this same session state, not a focal prompt's old context.
Approaching/exceeded context-price guidance appears once, in one pair of parentheses
after Context on the first line; there is no repeated threshold label.
Approaching uses an amber triangle and amber context figure. Exceeded uses a distinct
red octagonal stop/exclamation icon, red context figure and red relative-price multiplier.
The labels, session cost, threshold boundary and remaining warning text
stay in ordinary theme foreground. An alternate next-input CCost range stays neutral.
Accessible severity names and visible approaching/exceeded wording do not depend on color.
Canonical threshold, relative-price multiplier or supported cached/fresh cost details
remain visible, not ellipsized. This is guidance for the next context, not an accumulated
cost limit or bill prediction. Compaction, model/context changes and unknown evidence
update/remove guidance atomically; focus/selection cannot freeze it. Both values and
the explanation wrap naturally at narrow widths. Approaching uses
`thresholds.nextIctxPriceThresholdWarningPercent` (75%; zero disables approaching only),
with exact tier boundaries on unrounded counts.

Session CCost covers all canonical root-tree requests, including pre-Watch history,
compaction, child work and provisional usage, independently of displayed prompts.
Credits/USD and canonical partial-pricing markers apply; unknown is not zero. A single
bounded background lane reconciles minimal hashed request identities/fingerprints and
unrounded values in the disposable `session-ccost-v1` SQLite namespace. Unchanged
requests are not revalued; corrections/deletions and catalog/algorithm/source changes
reconcile or invalidate. Complete source checkpoints survive Earlier-slot eviction,
browser reload and host restart. No prompt content is stored in this namespace.
An unknown initial session total shows **Loading…** in Full and Mini Watch, never
a fabricated zero or elapsed-time delay warning. A complete source/valuation-matched
total stays stable through unchanged captures, disclosure, reconnect and Earlier
eviction/re-entry. No per-root periodic snapshot or reconciliation is scheduled for
unchanged evidence. One shared background pricing-identity check uses the existing
Wake/pricing-cache cadence; changed prices invalidate only the relevant derived work.
New/changed root-tree revisions reconcile against the persisted request baseline,
not the visible prompt-cost delta. Completed same-source results remain useful
baselines while newer evidence catches up; lifecycle generations cannot starve them.
Known prompt/session/daily/account figures stay visible quietly during routine refresh,
with no fleeting Loading/Refreshing/Retrying prose or temporary card-height change in
Running Prompts or Earlier Sessions. Observed **No running prompts**/**No earlier sessions** remain.
Column/summary help explains metric scope rather than internal freshness logs. Missing initial
Watch data remains quiet; elapsed time or independent Earlier/account/daily loading never
creates a global Watch failure warning. **No running prompts** requires observed membership
and a healthy running source/connection, not partial or retained evidence.
Initial missing-data guidance keeps 30 seconds. Useful retained prompt/daily/quota values
stay quiet through sustained background failures too, including accessible descriptions
and help. Actionable host/auth/connection failures, provider restrictions, unknown critical
values and intrinsic pricing gaps remain explicit. Observation clocks remain internal,
not a delayed-message timer or a change to source/lifecycle truth. Optional cache
failure safely computes from source; disposable-cache details are not default metric help.
No Session Total Duration returns. CLI, Sessions UI and daily/account totals retain
their existing meanings. Mini consumes this same session-cost/context projection below.

Watch still omits the normal heading, report/search/scope/refresh controls, run summaries,
valuation disclosure and model announcements. Exceptional host/source/offline notices
remain. No Observation details, Copilot Unaccounted usage or global warning list returns.

**[Mini Watch](web-mini-watch.md)** is an explicit, highlighted-while-On floating view with
compact per-prompt tables and thin primary-subscription bars on supported desktop browsers.
The name-only Session column stays separate from paired prompt CCost (whole-session
CCost). A collapsed-by-default **Earlier Sessions** header button shows up to three
verified canonical finished sessions as **Finished | Session | CCost (Total) | Ctx**
above running prompts. Finished uses configured-local HH:mm finish tokens with full
date/offset help, or a truthful unknown; running stays **Session | CCost (Total) | Duration | Ctx**.
Default opening fit targets approximately 650 outer DIPs with a two-prompt height reserve.
Explicit expansion/collapse permits one native height adjustment, retaining current width
where native clamps permit; Fit collapse remeasures, while Remember last size restores
eligible pre-expansion bounds. Live updates never auto-fit. Refusal/clamping retains
accessible document scrolling and narrow table panning. It reuses this tab's live publication and persisted session aggregate,
not another Watch engine, acquisition loop or browser-side valuation.

Four isolated session workers publish coherent canonical rows independently, without
waiting for the separate session-cost lane; generations reject superseded work. Account-history and detail
lanes cannot borrow mutable Live service. Accurate rows still require capture/analysis,
not source-level streaming. Successful admission order keeps captures fair across
catalog revision changes and rejected stale results; busy roots cannot continually
overtake a retained running card awaiting fresh termination evidence.
Active/top-five captures and a small catalog index are
retained; no per-card leases/browser acquisition loops. Adaptive 6× EMA/clamped 5–30s
cadence measures capture work; explicit intervals, buffered V2 hints and presentation wakes remain.

Live uses one process-lifetime engine starting with the host, not a tab. Closing all tabs does not stop it. CLI Watch retains its separate run, startup history and row-retention policy; Web history is continuously replenished. Both reuse canonical valuation, context, tool/skill attribution and coordinator timing/recovery policies. Source hints, idle and connection loss never prove completion. Account figures retain Watch scopes, not normal-report calendar-month substitutions.

Each authorized tab owns one same-origin SSE connection for live, finite-job progress and terminal runtime updates. The HttpOnly session authenticates it; no control secret/query credential is used. Instance-bound ordered IDs and full coherent publications reject duplicates/older/foreign-instance updates. Replay is bounded to 32 events and 8 MiB (2 MiB per publication); overflow or an uncovered gap requires a fresh authenticated `/api/live` snapshot, never inferred continuation. Oversized publications fail visibly rather than displaying truncated totals. Four streams are admitted; excess tabs can retry after capacity is available.

Stream writes retain a two-second timeout and ten-second heartbeats, without a forced healthy-stream lifetime. Authentication is checked on every stream turn; expiry, terminal shutdown and abandoned/failed writes release admission. A genuine disconnect uses ordinary EventSource retry at three seconds. Offline is visible with last known values retained. A received source-change/shutdown notification closes automatic retry and asks for a manual launcher run; an unknown disconnect never starts a server or assumes an update. A different instance requires a fresh authorized launcher link; expired sessions stop retry. Snapshot/job commands remain normal authenticated HTTP. Finite reports use isolated, cooperatively scheduled processes with explicit cancellation and no elapsed-computation cutoff; live acquisition, account publication, HTTP/control and source-change checks retain separate scheduling.

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

The Windows notification icon and browser favicon use the same original cyan/navy
CG artwork. The offline ICO includes 16/20/24/32/48px variants; the fixed, versioned
`/favicon-cg1.ico` declaration avoids the former generic tab icon, with intentional
`/favicon.ico` compatibility. CSP permits images only at those two same-origin
paths. Existing page-specific tab titles and the in-page CG badge are unchanged.
The native tray UI thread enters Per-Monitor v2 before creating its hidden owner
window/menu and restores its previous context on close. Icon pixels follow native
small-icon metrics; the hidden owner follows the popup's physical cursor monitor.
This changes neither the Python process default nor machine display settings.
Actual notification-area appearance, full 150% menu visual acceptance, other
physical scales/themes and mixed-monitor interaction remain unverified; see
[checks and limitations](../development/journal/web/branding.md).

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

Open the console's `/#bootstrap=…` link within **120 seconds**. JavaScript immediately removes the fragment with `history.replaceState`, then POSTs it once to `/api/bootstrap`. The trusted launcher/tray link remains **one-use**, not a week-long bookmark or shareable login. Obtain another link through the native Open/Copy action when needed; restarting a healthy server is unnecessary.

From v80.153, an authorized browser has a **rolling seven-day inactivity window on the same running host**. Successful protected API replies extend its in-memory deadline; the existing lightweight ten-second `/api/live` sync maintains an open Watch tab without clicks, report recalculation or extra polling. Navigation, reload, new tabs in that profile, and return after sleep/background suspension work while the cookie and seven-day authorization remain valid. Different authorized browsers have independent stable bearers: activity or a new handoff in one neither revokes nor extends another browser's session. CSRF remains instance-stable and page-memory-only; reloads recover it through authenticated `/api/session`. A new handoff in an already-authorized profile reuses its valid bearer.

The server renews the same protected cookie on the first successful API reply after each hour, not every poll. Its **seven-day-plus-one-hour storage lifetime** prevents hourly coalescing from deleting the browser cookie before a full seven days since the last valid activity. This storage margin grants **no extra authorization**: at seven inactive days the server rejects even a retained cookie, and the page shows the existing **AUTHENTICATION EXPIRED** recovery guidance. Failed/anonymous requests, public assets and passive SSE validation never extend inactivity. An SSE response cannot refresh cookie headers after opening; ordinary Live sync handles that. If a concurrent initial handoff supersedes an old stream's bearer, Live revalidates the current browser cookie before reopening or reporting genuine expiry. Session elapsed time includes host sleep; system-clock corrections can affect wall-clock inactivity, as they can browser cookie age.

Host restart, deliberate Exit/source shutdown, seven inactive days or browser/private-mode cookie clearing require a fresh trusted link. Old-host, expired and replayed bootstrap credentials stay invalid. Bearers remain only in host memory and the browser-managed HttpOnly cookie, never Web Storage, application files, URLs after bootstrap erasure, logs or diagnostics. The [verification notes](../development/journal/web/browser-sessions.md) distinguish simulated time/browser-cookie checks from real elapsed multi-day use.

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
| `/`, `/app.js`, `/render.js`, `/watch.js`, `/reports.js`, `/live.js`, `/session.js`, `/sessions.js`, `/settings.js`, `/app.css` | GET | Fixed public Beta shell/assets, no history |
| `/health` | GET | Public HTTP-shell readiness only |
| `/api/bootstrap` | POST | One-use `{"credential":"…"}` exchange with exact Origin |
| `/api/session` | GET | Authenticated CSRF recovery, no control credential |
| `/api/settings` | GET | Authenticated read of the four allowlisted Web preferences, selected choices and shipped defaults |
| `/api/settings/theme` | POST | CSRF-protected fixed `{"theme":"classic"}` or `{"theme":"web"}` write only |
| `/api/settings/ccost` | POST | CSRF-protected fixed `{"ccostDisplayUnit":"credits"}` or `{"ccostDisplayUnit":"usd"}` write only |
| `/api/settings/quota-display` | POST | CSRF-protected single `quotaDisplayMode`: `default`, `used` or `remaining` |
| `/api/status` | GET | Separate HTTP, analysis, source and account acquisition states |
| `/api/live` | GET | Authenticated coherent live/progress snapshot and instance/sequence; retained terminal state while stopping |
| `/api/events` | GET | Authenticated multiplexed SSE, bounded replay with Last-Event-ID; no query strings |
| `/api/reports` | POST | Enqueue/coalesce a finite report; return job ID (202) |
| `/api/interest` | POST | Authenticated bounded tab/route/visibility/scope lease; no worker-count authority |
| `/api/data` | POST | Strict `{request,retry}` boolean lookup/admission; shared valid result, progress ID or typed error |
| `/api/models/refresh` | POST | CSRF-protected `{}`; strict upstream pricing fetch then isolated coherent Models rebuild, coalesced in flight; no account refresh |
| `/api/sessions` | POST | Read shared catalog; validated token, offset/epoch, sort and direction; at most 50 rows, no source acquisition |
| `/api/detail` | POST | Shared complete session capture, pinned begin/chunk history and handle release; compatibility page/freeze |
| `/api/jobs/<id>` | GET | Authenticated status/progress/result |
| `/api/jobs/<id>/cancel` | POST | Cancel owned queued/running work with `{}` |

Reports select `kind`: `normal` (Models, including report account DTOs), `all-models` (catalog), `sessions`, `session`, `date` or `token-mix`. The live Accounts route never submits one. `session` requires an alphanumeric/underscore/hyphen `session_id` (max 200); `date` requires `YYYY-MM-DD` or `YYYY-MM-DD:YYYY-MM-DD` (max 32), with impossible/reversed/overflow dates rejected. `sessions` accepts `session_limit`: 1–10000 or null for all, legacy default 20. Paged requests add `session_page_size` (1–100; Web uses 50; omitted limit means all available), `session_offset` (0–1000000), and `session_catalog_revision` (64 lowercase hex digits, required for nonzero offsets). Response `session_page` exports offset/size/total/catalog_revision; a revision covers catalog identity/order, not atomic prompt values. Paged lists omit unused prompt request identities, retaining every session row and its canonical values. Page fields on other report kinds, invalid bounds and unknown fields are rejected. There are no HTTP query-string or arbitrary path parameters; client scope fragments become validated POST bodies. Reports export the shared application's explicit DTOs, retaining exact decimal **strings**, null unknowns, provisional flags and CLI-projected labels; the page does not calculate costs. Empty acquired lists, acquisition errors, partial source evidence and genuine priced zero remain distinct. Account `reported` means inspect the report's independent observation statuses, not that all accounts are healthy or atomic with history.

## Resource and failure boundaries

- Twelve HTTP workers/admitted sockets, with at most four authenticated streams so eight ordinary/control slots remain; bounded listen backlog. Two-second socket timeouts and an absolute five-second ordinary request/header deadline, including dripping clients. Only fully authenticated SSE cancels that deadline and retains its slot until disconnect, expiry or terminal shutdown. Connections close after one request.
- Request line <=2048 bytes, aggregate headers <=16 KiB, individual header lines <4096 bytes, JSON body <=4096 bytes. Duplicate headers/JSON keys, transfer encoding, non-JSON controls and unsupported methods are denied. No autoreload or directory listing.
- At most four queued/running logical reports, one executing finite child and bounded parked stacks. Identical in-flight demand coalesces. Sixteen jobs and twelve host result entries are bounded; a missing ID is not empty success.
- Every child owns fresh integrations, per-I/O source-read deadlines and exact-parent cleanup, not a computation-age watchdog. Managed Token Mix/Comparisons may continue only after independently received durable progress; each slice bounds its work while repeated churn uses capped backoff. AI Stats keeps its scope/slice bounds. Cooperative reprioritization waits for a safe checkpoint; an in-flight source operation retains its own I/O deadline. Healthy expensive computation remains pending and can complete automatically without Retry.
- Each finite report child monitors multiprocessing's exact parent kernel sentinel. A crashed/force-stopped Web parent or lost ownership proof exits that child nonzero, including a blocked scan; PID reuse is not a liveness signal. This child-only safety monitor stops/joins on ordinary completion.
- Results are limited to 8 MiB per job. Oversize: `result_too_large`; scope the request. Long Token Mix remains cancellable and never blocks shutdown. Progress exports only approved phase/stage/counts and a stale-safe job sequence, not source text. Child IPC coalesces at 100ms; host drains at most 64 messages/turn.

The shell remains reachable with offline/loading sources. At host launch only,
an eligible unavailable V2 service gets one hidden installed-CLI wake (five-second
command bound), followed by bounded fresh registration/API readiness probes.
**Starting OpenCode server…** is visible and accessible; queued reports and Watch
continue automatically after readiness. Failure clears that status and keeps
manual-start/wait/Refresh guidance. Healthy sources, selected V1, invalid/unreadable
registration, permission/authentication or incompatible contracts never launch.
Missing/unsupported CLI falls back transparently. Tabs, Refresh, routes and later
reconnects never repeat the attempt; Web shutdown never stops shared OpenCode.
There is no OS-login autostart or browser process-launch endpoint.
[Exact recovery bounds and source policy](connectivity.md#web-beta-host-startup).
Tests use synthetic read-only sources; local read-only source probes are separate
from paid/live-model tests.

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
