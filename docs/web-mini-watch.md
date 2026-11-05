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

## Placement preference

**Settings → Web settings → Mini Watch placement** has **Default (Remember last)**,
**Remember last** and **Standard placement**, saved immediately in the user config.
Default follows the current application's shipped default; explicit Remember last
stays pinned even if a later version changes it. Theme and CCost display use the same
Default-versus-explicit convention. Missing preferences inherit without creating a file.

- **Remember last:** the first opening in an opener/server instance requests the
  standard **560×250 screen DIPs** and browser-initial placement. After moving/resizing
  and closing, subsequent openings in that same live opener reuse the browser's last
  size **and position**, as the browser permits.
- **Standard placement:** every opening requests the standard size and initial
  placement, regardless of prior move/resize. On the target Chrome setup this is
  normally near bottom-right; browser/OS work areas may clamp or choose differently.
- Switching modes only affects the **next opening**. It does not move/resize/close
  the current window, disable manual controls or auto-open Mini.
- The mode is persistent; **geometry is not**. Host restart starts standard again.
  Reload/navigation/new tabs also start standard: this is per live opener, not a
  server-wide remembered position shared between tabs. Later reopens can remember again.
  No geometry is written to JSONC, SQLite, browser storage, cookies or URLs. Only the
   browser owns cached bounds; the application keeps an in-memory first-open flag/host identity
   and temporary bounds only while an Earlier Sessions disclosure is being auto-enlarged.

Fresh headless Chrome 156 / Edge 156 tests verify the actual Document PiP API, both
bounds dimensions and position, mode switching, close/reopen, reload and a Python
server-process restart in the same disposable browser profile. They use CDP bounds
changes and `Window.close()`/pagehide, not physical manual dragging or native-X clicks.
Physical Windows-150% frames/edges, manual/native-X interaction and monitor/work-area
transitions remain **UNVERIFIED**, under an FR-only Decision Delegate exception.
Browser-imposed limitations and exact evidence are in the [Mini journal](../development/journal/web/mini-watch.md).

## What the figures mean

- **CCost Today**, on the right, is the same global configured-local-day CCost and
  distinct initiating-prompt count as full Watch, including earlier pre-Watch activity
  across sessions/providers. It is not a sum of Mini rows or subscription periods.
   Only the left title navigates; the daily summary is non-clickable. Loading and unknown
   pricing remain explicit; meaningful partial/unavailable notes stay visible, without polling timestamps. Genuine
  observed zero is zero; the next canonical day/correction replaces the prior value.
- **Session (Total CCost):** within one column, Session/title stays at the left edge
  and `(Total CCost)` / `(<whole-session cost>)` stays at the right edge. Only the title's
  end ellipsizes; the parentheses and complete cost remain visible. Short amounts use only
   their natural width, not a header-sized reserved block. The full underlying title
   (or canonical session ID) remains selectable and in the row’s accessible name, with no row popup.
   The column heading explains Session and Total CCost in two separated sections. This server-owned total covers the
  entire available root/session tree: pre-Watch history, compactions, causal children
  and provisional running usage, not just visible prompts, this Watch run or Today.
  Concurrent prompts share the same session total. Credits/USD, zero, missing/partial
  pricing and retained/corrected totals use the same canonical cache as full Watch;
  loading is never replaced with prompt cost or fabricated zero.
- **#:** canonical session-local prompt ordinal, not a Mini list index. Concurrent
  prompts within one session remain separate rows, ordered by actual start.
- **CCost:** accumulated reference-price cost of that one prompt, not session/Today
  cost or billed spending. Missing/partial pricing retains N/A or `?` conventions;
   the column heading explains these conventions without per-row help controls.
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
Confirmed unavailable/partial session or daily data and stale/partial quota remain
readable where relevant; internal observation timestamps never appear as default help.
Retention is **not** a new live observation. Valid empty publications still remove rows after the shared
grace policy. No browser timer invents cost, completion or growing elapsed time.

### Earlier Sessions

The neutral **Earlier Sessions** header button expands a separate two-column table
**above** the running prompts: **Session (Total CCost)** in one column, plus **Ctx**.
The first column uses the same left-title/right-total alignment. It starts collapsed
every time a fresh Mini window opens; keyboard/click/touch works, and ordinary Live
updates preserve the choice. The newest **up to three distinct eligible finished
sessions** come from full Watch's canonical Earlier Prompts selection, displayed
oldest-to-newest within that subset, including its unknown-finish fallback ordering.
Running/recently ended sessions never appear in both tables. After the shared terminal
grace a session may enter history; resuming moves it back out coherently.

Earlier rows show the **whole-session** total and the **latest valid session/current-next
Ctx**, not the last prompt's cost/context, nor a sum of contexts. Ctx remains an estimate
with N/A for missing evidence and accessible help, without an added `~`. No prompt
number, duration or state badge is added. Empty, loading and unavailable history are
explicit; confirmed retained/partial totals remain indicated in the row. Collapsing
does not revalue or reacquire history.

Earlier Sessions has no tooltip. Both tables use their actual headings for help.
Within the same first column, **Session** explains only the name and **(Total CCost)**
only the whole-session cost, with no help in the gap. Hover opens after **600 ms**;
the passive help cursor is immediate, as are deliberate keyboard-focus/tap requests.
There is no table-level `?`, row cue or daily/header help icon. The return-to-Watch
action retains concise help, dismissed immediately on activation by mouse, touch,
Enter or Space. Hover help closes within a short exit grace when leaving its target
or the PiP document; keyboard-focus and intentionally pinned quota/header help have
separate ownership. Stationary focus and Live rerenders cannot reopen dismissed help.

If explicit pointer/keyboard activation introduces a **new vertical session scrollbar**,
Mini attempts one height-only enlargement of the existing PiP window, directly within
that gesture. Expanded sessions can use the added space instead of the compact height cap.
Already-fitting content, a pre-existing vertical scrollbar and horizontal panning alone
never trigger growth. Live publications, new rows, day changes and settings never auto-fit.
Collapse attempts to restore the measured pre-expansion size only after actual enlargement;
a later manual resize cancels that restoration. Reopening still follows the selected
placement mode, with Earlier Sessions collapsed. No geometry or new setting is persisted.

Chrome and Edge can refuse or clamp native resizing. Disclosure still works silently,
with usable session scrolling and independent subscription scrolling; Mini never retries,
reopens or deliberately moves the window. Hidden-browser tests measure actual outer/inner
bounds, pointer/keyboard activation, missing activation, refused/unsupported methods and
simulated short-work-area clamps. Physical dragging, monitor transitions and native frame
pixels are not established by these tests; final placement/rounding remains browser-owned.

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
Unlimited/unknown quota has no fabricated bar. Stale/partial quota and authentication
problems have concise visible notes. Genuine provider restrictions
remain visible; exhausted finite quota stays red. There are no reset/secondary-window paragraphs.
The visible subscription text, not a `?` or progress track, exposes its **Primary quota** and, when present,
**Additional quotas**, separated by a blank line: actual period, native Used/Remaining
amounts, limits, resets, same-period CCost and concise reference-capacity/attribution caveats.
No `Last quota update` or raw source enums appear. Unavailable cost
shows **(?)** without hiding a known percentage. Partial observed subtotals are
disclosed in help; the compact cost has no visible estimate decoration.

**Settings → Web settings → Quota display** offers **Default (Used) / Used / Remaining**.
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
Mini requests 560×250 **screen DIPs**, not physical screen pixels or zoomed document
CSS pixels. Historical standard-placement measurements on Windows 150% showed a
complete visible native frame **428–429 physical pixels** high, below 470, including native chrome.
The previous 450-DIP request measured 729 physical pixels. Chrome page zoom changes
document dimensions, not that request's screen units. Other scales/platforms can
produce different outer geometry; a universal 470-physical-pixel cap is not verified.
Metric headings are centered; the split Session heading/title is left-anchored and
its parenthesized total suffix right-anchored. Numeric metric values remain right-aligned.
The four prompt-metric columns fit their full heading or longest displayed value, without
wrapping, clipping or ellipses. Session takes all remaining width; its inner layout
ellipsizes only the title while the full-session cost suffix never shrinks or ellipsizes.
The complete first-column heading stays readable. Widths adapt to live values/units;
an empty message does not expand metric columns. If a manually narrowed window cannot
fit every heading/metric, the prompt region scrolls horizontally instead of clipping.
Earlier and running tables share **one vertical session viewport/scrollbar**, with no
Mini-specific running-row limit. Each table's sticky headers stay within its own table.
The subscription region still scrolls independently. Explicit history expansion may
enlarge PiP once under the rule above; larger/clamped lists remain scrollable. Resize with
the browser's controls; narrow widths wrap the header instead of overlapping it. Remember last
reopens at the browser's last bounds; Standard placement requests the compact initial
geometry again. While open, later manual resizing is never forcibly undone.
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
