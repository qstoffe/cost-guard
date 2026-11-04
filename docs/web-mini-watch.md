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

## What the figures mean

- **Total Today**, on the right, is the same global configured-local-day CCost and
  distinct initiating-prompt count as full Watch, including earlier pre-Watch activity
  across sessions/providers. It is not a sum of Mini rows or subscription periods.
   Only the left title navigates; the daily summary is non-clickable. Loading and unknown
   pricing remain explicit; focus/hover discloses partial data and observation time. Genuine
  observed zero is zero; the next canonical day/correction replaces the prior value.
- **Session:** actual session title, truncated to fit; focus/hover for the full title.
- **#:** canonical session-local prompt ordinal, not a Mini list index. Concurrent
  prompts within one session remain separate rows, ordered by actual start.
- **CCost:** accumulated reference-price cost of that one prompt, not session/Today
  cost or billed spending. Missing/partial pricing retains N/A or `?` conventions;
  focus a row for estimated/partial provenance without a distracting cost `~` glyph.
- **Duration:** that prompt's canonical elapsed execution time, frozen when ended.
- **CTX:** estimated next incoming context for the prompt (`~` means approximate;
  N/A means unknown), with the same meaning as Watch's Context column.

Running rows use Watch's yellow tone, successful endings green, abort/error red;
outcome and known stop cause remain accessible without color. Ended rows retain
their final prompt-local metrics for Watch's existing ~30-second grace, then leave.
An acquired empty set shows a compact empty message, never dummy zero-cost rows.
Initial/partial/unavailable acquisition is not an empty success.
Brief delays, reconnects and incomplete reads quietly retain the last usable figures;
they do not append orange “Not current” / “Partial” labels or flash retry banners.
Focus/hover discloses observation times and retained-data state: retention is **not**
a new live observation. Valid empty publications still remove rows after the shared
grace policy. No browser timer invents cost, completion or growing elapsed time.

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
Unlimited/unknown quota has no fabricated bar. Transient stale/partial acquisition is
disclosed on focus/hover, not in repeated warning suffixes. Genuine provider restrictions
remain visible; exhausted finite quota stays red. There are no reset/secondary-window paragraphs.
Focus/hover a row for its period/estimated-attribution basis; unavailable cost does
not hide a known percentage. `?` retains partial pricing; cost has no visible `~`.

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
**Credits / USD**. Healthy Live text and transient operational warnings are omitted.
Mini requests 560×250 **screen DIPs**, not physical screen pixels or zoomed document
CSS pixels. On the tested Windows 150% display, its complete visible native frame
opens/reopens at **428–429 physical pixels** high, below 470, including native chrome.
The previous 450-DIP request measured 729 physical pixels. Chrome page zoom changes
document dimensions, not that request's screen units. Other scales/platforms can
produce different outer geometry; a universal 470-physical-pixel cap is not verified.
Prompt headings are centered; titles remain left-aligned and numeric values right.
The four metric columns fit their full heading or longest displayed value, without
wrapping, clipping or ellipses. Session alone takes all remaining width and ellipsizes
long titles (focus/hover retains the full title). Widths adapt to live values/units;
an empty message does not expand metric columns. If a manually narrowed window cannot
fit every heading/metric, the prompt region scrolls horizontally instead of clipping.
Prompt and account regions scroll independently with a sticky prompt header; larger
lists may scroll immediately at the smaller opening size. Resize with the browser's
controls; narrow widths wrap the header instead of overlapping it. Reopening requests
the compact initial size again; later manual resizing is never forcibly undone.
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
and the process's bounded account-history lane. Opening/closing it never starts new
history scans, EventSources or provider polling. Updates apply directly from publications,
not a hidden-main-document animation frame; a visible PiP timer only checks freshness.
No credentials enter Mini URLs/storage/markup and no CSP relaxation is used.

Tested browsers and explicit OS/native-proof limits are recorded in
[Mini Watch verification](../development/journal/web/mini-watch.md). Availability
still depends on the actual desktop browser/version, platform and policy, not its name.
