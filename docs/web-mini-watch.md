# Mini Watch

On **Watch**, click **Mini Watch: Off** to request a compact Document
Picture-in-Picture window. The whole control is highlighted **On** only while it is open.
Click On again or the browser's native close control to close it; Mini has no custom ×.
It never opens automatically on minimization or reload and has no saved On preference.

Mini stays open across in-app navigation. Its left **Cost Guard · Watch** title is a keyboard-accessible action
that selects Watch and requests focus of the **existing** owning Cost Guard tab; it
does not open a new tab or deliberately close Mini. Focus/restoring a minimized
window depends on the browser/OS. If that request cannot restore it, use the native
return-to-tab control, which may close PiP. Closing/reloading the owning document ends
Mini; a fresh page starts Off. Browser PiP replacement may also close it.

## Position and size preferences

**Settings** separates **Mini Watch position** (Default / Remember
last / Standard position) and **Mini Watch size** (Default / Fit on open / Remember
last size). Defaults resolve to **Remember last** and **Fit on open**. Existing
`miniWatchPlacement` intent is retained; `miniWatchSize` is the only new enum.
Symbolic Default follows shipped defaults; explicit choices stay pinned. Missing
preferences inherit without creating a user file.

Fit on open measures the themed header before requesting PiP: **Cost Guard · Watch,
Earlier Sessions and the complete CCost Today cost/prompt count fit on one row in
both disclosure states**, where browser/native limits permit. It reserves at least
the formatted reference **CCost Today 90 000 · 999 prompts**, or wider real opening
text, plus **8 CSS pixels** for focus/rounding and a measured stable scrollbar gutter.
The reference exists only in inert measurement clones: real displayed totals are
never changed. The equal-width disclosure markers and stable gutter prevent a
toggle or capped-height scrollbar from stealing header space. Each opening uses
actual fonts, gaps and padding, not a fixed pixel width or table minimum.
Height is measured at the resulting available content width,
with current content, every account and warning, and capacity for **two complete
running-prompt rows**. This is empty height
capacity, not fabricated prompt entries. More than two rows use their actual height.
The initial request uses a conservative native-frame estimate because no pre-open
frame query exists. Actual native bounds are inspected, not inferred from API success.
Content is mounted only after styles load, avoiding a premature scrollbar that
would steal header width. The browser may clamp; then responsive header wrapping
and scrolling keep all content reachable, with a limitation notice in the owning tab.
Later longer Live text stays accessible without passive resizing. The total outer
height request never exceeds **1,000 DIPs** or the known available work area.

Remember last size permits the browser's manually chosen dimensions within the same
live opener/host; it does **not force the minimal Fit opening width** and is
intentionally exempt from the initial two-row fit guarantee.
The native placement option couples position and dimensions: **Fit on open wins
over remembered position**, and **Standard position can reset remembered size**.
These are best-effort intentions, not four independent native geometry controls.
Reload, a new opener or a changed host starts fresh. Standard asks for initial
browser placement, not absolute coordinates or a guaranteed bottom-right corner.
Changing a preference affects only the next opening. Manual window controls remain
browser-owned. No geometry is saved in config, SQLite, browser storage, cookies or URLs.

Fresh headless Chrome/Edge tests exercise real PiP, pointer/keyboard activation,
native clamps, browser zoom and emulated device scales. These are not physical
Windows-frame, manual-drag, monitor-transition, macOS or screen-reader proof.
Exact measurements and verification limits are in the [Mini journal](../development/journal/web/mini-watch.md).

## What the figures mean

- **CCost Today**, on the right, is the same global configured-local-day CCost and
  distinct initiating-prompt count as full Watch, including earlier pre-Watch activity
  across sessions/providers. It is not a sum of Mini rows or subscription periods.
   Only the left title navigates; the daily summary is non-clickable. Loading and unknown
   pricing remain explicit; pricing/token gaps stay visible without transient source captions. Genuine
  observed zero is zero; the next canonical day/correction replaces the prior value.
- **Session:** the name only (canonical session ID if unnamed). Only the title
  ellipsizes; its full text remains selectable and in the row’s accessible name.
  In **both tables**, Session hover, keyboard focus or touch exposes the full name and
  the represented canonical **Prompt #** in that session (or **Prompt number unavailable**), without a separate visible ordinal column.
  Concurrent prompts remain separate rows ordered by actual start.
- **CCost (Total):** one nonwrapping, right-aligned cell, **prompt cost (whole-session
  cost)**, e.g. **49 (562)**. The first amount belongs to the row’s focal running/recent
  prompt; the parenthesized amount covers the entire available root/session tree:
  pre-Watch history, compactions, causal children and provisional running usage.
  It is not a visible-row sum, this Watch run or Today. Concurrent rows in one session
  share the same full total, not necessarily the same prompt cost. Both amounts use
  canonical Credits/USD formatting, independently retaining zero, **N/A** and partial
  **?** conventions. An unknown session total shows **Loading…**, never prompt cost
  or fabricated zero. Both cost headings explain the scopes and that these are
  reference costs, not provider billing. Complete unchanged totals remain quiet
  through Earlier re-entry and normal checks; corrections reuse the existing shared
  incremental valuation cache, also used by full Watch.
  In both tables, hover/focus/tap the cost text for that prompt's compact model,
  effort, duration, known calls and relevant linked/mixed/pricing/outcome details.
  Running uses its focal prompt; Earlier uses its latest actual historical representative.
  This is not Full Watch's detailed I/C/W/O cost breakdown.
- **Duration:** that prompt's canonical elapsed execution time, frozen when ended.
- **Ctx:** estimated next incoming context for the prompt, shown as a formatted number
  without an added `~`. The header tooltip explains the estimate; N/A means unavailable.
  This next-context estimate is distinct from full Watch's first-request **Ictx** and
  its per-prompt **Δ Ctx**.

Running rows use Watch's yellow tone, successful endings green, abort/error red;
outcome and known stop cause remain accessible without color. Ended rows retain
their final prompt-local metrics for Watch's existing ~30-second grace, then leave.
An acquired empty set shows a compact empty message, never dummy zero-cost rows.
Initial/partial/unavailable acquisition is not an empty success.
Brief delays and reconnects quietly retain the last usable figures without retry banners.
Retained/partial source evidence stays in accessible values and targeted help, not
an extra caption below the session name. Pricing gaps, N/A, unknown usage and genuine
provider/authentication restrictions remain meaningful; internal timestamps are not default help.
Retention is **not** a new live observation. Valid empty publications still remove rows after the shared
grace policy. No browser timer invents cost, completion or growing elapsed time.

### Earlier Sessions

The neutral **Earlier Sessions** header button expands a separate four-column table
**above** the running prompts: **Activity | Session | CCost (Total) | Ctx**.
Activity shows only the canonical representative prompt's supported finish in configured
local **HH:mm** (24-hour, no seconds). Focus, hover or tap the time for the server-prepared
full **YYYY-MM-DD HH:mm +offset**; DST repeated hours remain distinguishable.
Unknown finish times show **—** with **Unknown finish time** help, never a source-update
or current-time substitute. Activity is narrow and nonwrapping; Session keeps the remaining
elastic title width. The running/recent table is exactly
**Session | CCost (Total) | Duration | Ctx**. Earlier starts collapsed
every time a fresh Mini window opens; keyboard/click/touch works, and ordinary Live
updates preserve the choice. The newest **up to three distinct eligible finished
sessions** come from full Watch's canonical Earlier Sessions selection, displayed
oldest-to-newest within that subset, including its unknown-finish fallback ordering.
Running/recently ended sessions never appear in both tables. After the shared terminal
grace a session may enter history; resuming moves it back out coherently.

Earlier cost cells show the **latest actual canonical prompt’s cost (whole-session
cost)**. Hover, focus or tap that value for the same prompt’s **Prompt #, main Model**
(provider-qualified where available), **Effort, finished Duration and known Calls**.
Linked subagents, multiple contributing models, partial pricing/attribution and
failed/aborted work are noted when relevant; unknown facts remain N/A or unavailable,
never borrowed from another prompt. No raw prompt text is exposed.
The **latest valid session/current-next Ctx** remains distinct from historical prompt
context or a sum of contexts. Ctx keeps N/A and accessible heading help, without an
added `~`. No ordinal, model, effort, duration or calls column is added.
Empty, loading and unavailable history are
explicit; retained/partial totals remain qualified in values/help without a flashing extra row caption. Collapsing
does not revalue or reacquire history.

Earlier Sessions has no tooltip. Both tables use their actual headings for help;
Session explains the name, and CCost (Total) explains prompt versus whole-session cost.
Both Session values and both cost values supply their separate targeted details above,
not a second row-wide tooltip or native browser title. Hover opens after **600 ms**;
the passive help cursor is immediate, as are deliberate keyboard-focus/tap requests.
There is no table-level `?`, row cue or daily/header help icon. The return-to-Watch
action retains concise help, dismissed immediately on activation by mouse, touch,
Enter or Space. Hover help closes within a short exit grace when leaving its target
or the PiP document; keyboard-focus and intentionally pinned quota/header help have
separate ownership. Stationary focus and Live rerenders cannot reopen dismissed help.

Pointer, Enter or Space activation measures expanded content and makes at most one
native height adjustment within that activation. Collapse in Fit mode shrinks to the
current compact two-row baseline, not a fixed height. Remembered-size mode restores
eligible pre-expansion bounds only after achieved growth; manual resizing invalidates
stale restoration. Actual current width is retained where native clamps permit.
Vertical-only `resizeBy` is preferred; observed one-DIP zoom rounding is compensated
on the next eligible click, never with an extra call or background repair.

No passive Live/SSE update, timer, prompt/account change or settings read resizes the
window. Later content exceeding its opening reserve scrolls normally. Missing activation,
refusal and clamps preserve disclosure and accessible document scrolling. There is no
activation spoofing, retry loop, automatic reopen, programmatic move or vertical lock.

After **10 continuous minutes** without a usable new observation, one muted, separate
“Updates unavailable · showing last values” notice appears. Prompt, daily and native
quota observation clocks are independent: retries or progress elsewhere do not hide
a stuck lane. A genuinely fresh usable observation resets its clock. Definitive host
stop, expired authorization or changed host identity instead show concise action guidance
immediately. Before first usable data, Mini shows neutral Loading/empty states, not
invented numbers. At configured-local midnight, Yesterday's total is cleared even if
the connection is down; Mini waits for the new canonical day. Its day-end metadata
respects configured timezone/DST, not the browser's calendar or a fixed 24-hour guess.

Each subscription appears once as **name · N% used (same-period CCost)**. The
provider-declared stable primary wins; a missing primary never promotes a more
depleted secondary. Names retain account distinctions. Unlimited and exhausted
values retain native semantics. Each text row has a thin full-width primary Used
bar below it: cyan/teal below exhaustion, red only for authoritative finite 100%.
Unlimited/unknown quota has no fabricated bar. Routine retained/partial refresh copy
stays quiet under Mini's existing ten-minute health owner; authentication problems and genuine provider restrictions
remain visible; exhausted finite quota stays red. There are no reset/secondary-window paragraphs.
The visible subscription text, not a `?` or progress track, exposes its primary
**Capacity** and **Next reset** in two compact help lines. Rich native/secondary
quota explanations remain on full Watch and Accounts.
No `Last quota update` or raw source enums appear. Unavailable cost
shows **(?)** without hiding a known percentage. Partial observed subtotals are
disclosed in help; the compact cost has no visible estimate decoration.

**Settings → Quota display** offers **Default (Used) / Used / Remaining**.
Remaining switches this already-open window along with Accounts and full Watch, without
quota refresh, restart or another stream. A Copilot quota can show **91.6% remaining
(22912)** beside independently observed Used **(1814)** and native Capacity 25000.
Help explains why these do not reconcile. Other valid windows extrapolate Capacity
from observed CCost divided by the unrounded fraction Used, then subtract observed
CCost for Remaining. These are reference proxies, not guaranteed allocation or bills.
Capacity stays in help, not an extra visible Mini row. Numeric ratio-derived Capacity
includes **(guesstimate)**; verified comparable native limits and unknown figures do not.
Full remaining
bars are healthy; empty, truly exhausted bars retain a red text warning and accessible
exhaustion description. Tiny positive capacity is not marked exhausted by rounding.
Unlimited keeps Used with no bar, and missing capacity/usage stays unknown rather than
inventing Remaining. A provider-confirmed idle window still shows **100% remaining**
with a full healthy bar, but unknown reference Remaining **(?)** and Capacity **?**;
Used preserves independently proven **(0)**. Credits/USD updates all reference figures.
Default follows the shipped Used orientation; explicit Used pins it. CLI, remaining
pace, period attribution and native money are unaffected.

Cost uses verified native boundaries and acquired history **before Watch/Mini
opened**, including earlier days of a supported fixed UTC calendar month.
Five-hour native windows use their actual start/reset; unknown boundaries,
arbitrary billing dates or ambiguous accounts remain unavailable. No Today,
trailing-30-day, configured-local-month or percentage-times-budget substitution
is made. Cached history is rebound to the **current** quota period on publication,
so a reset percentage never inherits the old period's cost.

## Support, appearance and privacy

Runtime feature detection checks secure/top-level context and Document PiP support;
loopback HTTP is a browser-trusted context. Unsupported, policy-disabled or rejected
requests stay Off with a reason. There is no popup fallback advertised as always-on-top,
extension, flag, notification permission, native helper or second sign-in flow.

The unframed compact tables follow **Classic / Web light/dark** and live
**Credits / USD**. **Default (Classic)** and explicit **Classic** retain the existing
dark presentation. **Web** matches the owning Web page's effective system appearance:
light content canvas and coordinated surfaces in light mode, the Web blue-dark palette
in dark mode, never Classic as a fallback. The application inherits the owner's resolved
semantic colors because the separate PiP document can report a different light/dark
preference. Header actions, daily summary, both tables/sticky headings, status text,
quota tracks/fills, empty states, scrollbars and accessible help use those shared roles.
Changes in Settings and the owner's system appearance update an already-open Mini
without reopening, report refresh, server restart, another live stream or browser storage.
This styles application content only; browser-native frame/security/return/close controls
remain browser-owned. Healthy Live text and transient operational warnings are omitted.
Opening requests use **screen DIPs**, not physical pixels or zoomed CSS document
pixels. Measured layout is converted to those units before opening; native chrome
and browser clamps can change actual outer/inner dimensions. Earlier fixed-height
Windows measurements are historical, not the new fit target or a physical-height cap.
Metric headings are centered; Session titles are left-aligned. Numeric metric values
remain right-aligned with tabular numerals. Metric columns fit their full heading or
longest displayed value, without wrapping, clipping or ellipses. Session takes all
remaining width and ellipsizes only the title; neither cost amount shrinks or ellipsizes.
The complete Session-column heading stays readable. Widths adapt to live values/units;
an empty message does not expand metric columns. If a manually narrowed window cannot
fit every heading/metric, the prompt region scrolls horizontally instead of clipping.
There are no premature vertical max-height caps on prompts, accounts or warnings.
Content uses its natural height and the document scrolls only when the current native
window is insufficient. Horizontal table panning remains available at narrow widths;
all rows and headings remain readable, without a Mini-specific running-row limit.
Resize with browser controls; narrow widths wrap the header instead of overlapping it.
The browser
owns outer chrome, origin/security indication, positioning, native return controls
and final geometry; this is not a frameless, arbitrarily positioned tooltip.

Mini supplies the same CG favicon as the normal tab. Native window-icon adoption
was verified in Windows Chrome 156.0.8078.80 at 150% display scaling. Actual
taskbar-preview/Alt+Tab rendering and grouping remain unverified; the browser/OS
owns those surfaces and may cache or present icons differently. Native Edge and
macOS appearance are also unverified. Chrome's normal application icon and the
Windows tray are unchanged.

Mini has independent DOM but shares the owning tab's one authenticated live connection
and the process's bounded account-history/session-cost lanes. Opening/closing Mini or
toggling Earlier Sessions never starts new history scans, EventSources or provider
polling. Whole-session figures reuse the persisted incremental SQLite-derived projection;
the browser never sums or values usage. Updates apply directly from publications,
not a hidden-main-document animation frame; a visible PiP timer only checks freshness.
No credentials enter Mini URLs/storage/markup and no CSP relaxation is used.

Tested browsers and explicit OS/native-proof limits are recorded in
[Mini Watch verification](../development/journal/web/mini-watch.md). Availability
still depends on the actual desktop browser/version, platform and policy, not its name.
