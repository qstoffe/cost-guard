# Mini Watch

On **Watch**, click **Mini Watch: Off** to request a compact Document
Picture-in-Picture window. The whole control is highlighted **On** only while open.
Click On again or the browser's native close control to close it. Mini never opens
automatically, has no custom × and does not save an On preference.

Mini stays open across in-app navigation. **Cost Guard · Watch** selects Watch and
requests focus of the **existing** owning tab without deliberately closing Mini.
Restoring a minimized window depends on the browser/OS; the native return-to-tab
control is the fallback. Closing/reloading the owner ends Mini. A fresh page starts Off.

## One session activity table

The always-visible table has exactly four columns:

**Activity | Session | CCost (Total) | Ctx**

There is no Earlier Sessions button, separate history section or Duration column.

- **Activity:** configured-local **HH:mm**, using the representative prompt's real
  **start** while running or execution-unverified, and its supported **finish** when
  ended. Hover, keyboard focus or touch the time for the full local date/time and UTC
  offset, distinguishing repeated daylight-saving hours. Unknown finish is **—** with
  **Unknown finish time** help, never source-refresh time or an inferred ending.
- **Session:** the flexible, left-aligned name, or canonical session ID if unnamed.
  Only the title ellipsizes. It remains selectable; its help includes the full name
  and represented **Prompt #**, or **Prompt number unavailable**.
- **CCost (Total):** the representative prompt's own reference cost, followed by the
  **entire canonical root/session cost** in parentheses, including supported linked
  subagents and pre-Watch history. Neither amount substitutes for the other. Credits/
  USD, zero, **N/A**, unknown **Loading…** and partial **?** retain their meanings.
  Each amount has independent help with model, effort, **Duration**, calls and relevant
  linked/mixed/pricing/outcome details. Completed duration is frozen. These are reference
  costs, not verified billing. Raw prompt text is not exposed.
- **Ctx:** the running/recent representative's supported next-incoming estimate; a
  historical-only row uses the last valid **session-level next-request context**, not
  stale historical prompt context or a sum. Warning/help, token formatting and N/A
  remain. This differs from full Watch's first-request Ictx and per-prompt Δ Ctx.

Every canonical session appears **once**, even with several concurrent prompts or
identical display names. If several prompts run in one session, the latest genuinely
running prompt represents it (stable event-ID tie break). Its cost is not a sum of all
simultaneous focal prompts; the parenthesized whole-session total is independent.
Execution-unverified unfinished work remains conservative, not a healthy completion.

All distinct running sessions are included without a data limit. Recent terminal-grace
and verified historical sessions compete by supported finish time for **max(0, 5 − R)**
remaining slots, where R is the number of distinct running sessions. Thus 0/1/3/4 running
sessions allow up to 5/4/2/1 finished fillers; 5 or more allow none. Fewer eligible
sessions produce fewer real rows, never duplicates or fabricated entries.

The selected rows are ordered by **Activity ascending**, oldest at the top, newest at
the bottom, with deterministic identity ties and a conservative unknown-time fallback.
Resumed sessions promote the same keyed row and move with their actual new start.
Running is yellow. Successful endings are green and abort/errors red **only during
the existing server-owned recent-terminal grace**. Historical rows use the theme's
normal foreground, including on first opening; their accessible outcome text remains
accurate after the highlight expires. Refresh/reopen does not restart that grace.
Full Watch keeps its separate per-prompt cards and Earlier list.

The shared server still certifies five eligible historical winners **after excluding
active/grace sessions**. Provisional candidates are not presented as the newest set.
Initial loading/unavailability is explicit; active rows, Today and subscriptions work
independently. Certified rows and empty history remain quiet during normal refresh.
Removal, resumption and source corrections retain the existing lifecycle guarantees.
Whole-session costs/guidance can finish enriching after certified membership without
inventing zero values or changing the proof epoch.

An open, visible Mini requests its own bounded history-interest lease when fewer than
five distinct running sessions need fillers, including while the opener is hidden.
Five-plus running sessions, closing Mini or a host change withdraw unnecessary interest.
It shares the existing acquisition/proof and **one EventSource**, never another scanner.

## Position, opening size and Fit Height

**Settings** separates **Mini Watch position** (Default / Remember last / Standard
position) and **Mini Watch size** (Default / Fit on open / Remember last size). Defaults
resolve to **Remember last** and **Fit on open**. Symbolic Default follows shipped
defaults; explicit choices stay pinned. Missing preferences create no user file.

Fit on open measures styled content before one PiP request. Width is the larger of:

- The table's compact Activity, CCost and Ctx column need **N**, with a generous Session
  target of about **1.6 × N** (about **2.6 × N** for the table), plus stable table scrollbar
  gutter, padding and small focus/rounding allowance.
- The complete intrinsic header: **Cost Guard · Watch**, **↕**, and the actual/reference
  **CCost Today 90 000 · 999 prompts**, or wider real text.

This is a responsive visual target, not an exact pixel invariant. Extra available width
goes to Session, not the compact metric columns. Long titles do not determine opening
width. Real fonts/styles, native zoom and available screen bounds remain relevant.

Height fits the current header, genuine messages, **table header plus five styled body
rows**, and **all currently displayed subscriptions**. Missing rows reserve empty space,
not fake data. With six or more running sessions, all remain in the same table with an
internal vertical scrollbar and sticky column heading. Header/Today/subscriptions stay
outside that scroll area. A sixth row never passively resizes the native window.
At narrow widths the table can also pan horizontally without clipping metrics.

The small **↕ Fit Mini Watch height** action deliberately fits this **bounded five-row
viewport plus header/messages/subscriptions**, not offscreen sixth-plus rows. Mouse,
touch, Enter and Space activation immediately dismiss visible/pending help, including
no-op/refused fits. It requests height only at the current width, without fetching,
changing settings or periodically autosizing. Another deliberate click can fit changes.

Remember last size respects browser-owned manual dimensions rather than forcing the
default opening fit. Fit on open wins over remembered position; Standard position may
reset remembered size. These are best-effort native intentions, not independent absolute
coordinates. Preference changes affect the next opening. No geometry is persisted in
config, SQLite, browser storage, cookies or URLs.

The initial native-frame estimate is conservative; no pre-open frame query exists.
Native minimum/maximum, work-area and zoom clamps can prevent a snug fit. Normal document
scrolling preserves access to accounts/messages in a too-short window, while table-only
overflow handles extra running rows. Header controls reflow instead of clipping at narrow
widths. No passive Live/SSE publication, timer or quota change resizes the window.

## Today and subscriptions

**CCost Today** is the same global configured-local-day reference cost and distinct
initiating-prompt count as full Watch, including pre-Watch activity. It is not a sum of
Mini rows or account periods. This readout is non-clickable and has no tooltip. Known
priced subtotals remain plain; wholly unpriced usage is N/A, acquired empty usage zero.
At configured-local midnight the old day clears even disconnected, using server DST-aware
day boundaries rather than browser time. Corrections replace values, never accumulate.

Each subscription appears once as **name · N% used (reference quota amount)** and a
thin primary-window bar. A missing primary never promotes a more depleted secondary.
Unknown/unlimited quota has no invented bar; finite authoritative exhaustion is red.
Text help starts with **Capacity** and **Next reset**, with relevant unrounded-estimate
details. Richer secondary-window/native details remain on Accounts/full Watch.
Authentication/provider restrictions stay meaningful; ordinary refreshes stay quiet.

**Quota display → Remaining** updates open Mini together with Accounts/Watch, without
another stream. Verified convertible native allowances supply matching Used, Remaining
and Capacity reference equivalents (100 Credits = $1), not cash or billing. Other
eligible percentage-only plans retain disclosed OpenCode-observed period-cost estimates;
inferred Capacity includes **(guesstimate)**. Only those estimates use the existing
one/two-significant-digit display rounding, with original Decimal values in subscription
help. Observed costs, Today and prompt/session costs are unchanged. Missing/invalid/
stale/unlimited facts remain unknown, not fabricated Remaining. Idle provider-confirmed
windows can show 100% remaining with unknown reference Remaining/Capacity; Used can
retain independently proven zero. Native windows retain their actual boundaries and
history from before Mini opened; there is no Today or arbitrary-calendar substitution.

## Appearance, support and privacy

Classic/Web light/dark and Credits/USD update the existing keyed rows. The PiP document
inherits the owner's resolved Web semantic roles, not a second palette. Hover help is
delayed 600 ms; deliberate focus/touch is immediate. No duplicate `?`, row-wide tooltip
or native-title help is added. Source disconnection retains usable figures without
pretending retention is fresh evidence. Host stop, expired authorization and changed
identity expose concise recovery guidance.

Secure top-level Document PiP support is detected; loopback HTTP qualifies. Unsupported,
disabled or refused requests remain Off with a reason. There is no popup fallback,
extension, login flow, CSP relaxation or credential exposure in URLs/storage/markup.
The shared CG favicon remains; browser/OS owns frame/security/return/close/taskbar UI.

Owned headless Edge tests exercise actual Document PiP, themes/fonts, native zoom/DPR,
screenshots, help, Fit and scrolling. They do **not** prove physical Windows frames,
manual OS dragging, monitor transitions, macOS or screen-reader behavior. Current evidence
and explicit limits: [Mini Watch journal](../development/journal/web/mini-watch.md).
