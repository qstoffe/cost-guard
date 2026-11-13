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

The always-visible table has exactly five columns:

**Activity | Session | CCost | Total | Ctx**

There is no Earlier Sessions button, separate history section or Duration column.

- **Activity:** uses the representative prompt's real **start** while running or
  execution-unverified, and its supported **finish** when ended. Keep configured-local
  **HH:mm** when the event is on today's configured-local date **or under 12 elapsed
  hours old**. Otherwise show floored **12h ago** through **23h ago**, then **1d ago**
  through day 29, **1m ago** from day 30, and **1y ago** from day 365. Months are fixed
  30-day buckets; years are fixed 365-day buckets. Units are lowercase; **m means
  months**, not minutes. Absolute elapsed time stays independent of DST/offset changes.
  Future timestamps retain their supported clock, never a negative age. Labels update
  on Mini's existing five-second render, without another fetch, timer or source scan.
  Hover, keyboard focus or touch either format for the full local date/time and UTC
  offset, distinguishing repeated daylight-saving hours. Unknown finish is **—** with
   **Unknown finish time** help, never source-refresh time or an inferred ending.
   A small decorative **▶** precedes the Activity value only for a verified running
   prompt. It is not a control; completion, abort, failure, execution-unverified
   work and historical-only rows have no play symbol. Existing time help stays on
   the complete value, with no additional focus stop or status announcement.
- **Session:** the flexible, left-aligned name, or canonical session ID if unnamed.
  Only the title ellipsizes. It remains selectable; its help includes the full name
   on its first line and **Prompt #N: excerpt** on the next, or **Prompt #N** without
   an available excerpt. Missing numbers say **Prompt number unavailable**, with a
   separate **Prompt: excerpt** only when supported. The hint uses that same prompt's
   existing bounded preview: up to 25 visible
   characters, without splitting combining marks or emoji, and one ellipsis only when
   shortened. Missing/non-prompt previews add nothing; no full prompt text is fetched.
- **CCost:** the representative prompt's own reference cost, retaining partial **?**
  and its prompt-specific help with model, effort, **Duration**, calls and relevant
  linked/mixed/pricing/outcome details. Only a genuinely running represented prompt’s
  complete **Duration: time** line is yellow, and it continues updating while open.
  Completion, failure, abort, unverified work or a historical representative removes
  the cue; completed duration is frozen. This help does not expose prompt text.
- **Total:** the **entire canonical root/session cost**, including supported linked
  subagents and pre-Watch history, in its own column without parentheses. The value is
  plain selectable text with **no tooltip**. Its heading help says only: “The entire
  session’s reference cost, including attributed linked subagents.” Known priced
  subtotals omit the partial **?** here only; missing pricing is not filled in.
  Credits/USD, real zero, **N/A** for wholly unpriced work and pending **Loading…**
  remain distinct. Neither amount substitutes for the other; both are reference
  costs, not verified billing. Full Watch and canonical completeness are unchanged.
- **Ctx:** the last valid **session-level next-request context**, not
   stale historical prompt context or a sum. Value help includes **Next Ctx**, matching
   the visible cell, and **Δ Ctx**, the selected representative prompt's own change.
   Historical Δ is explicitly labeled: the session estimate may be later. Source-prepared
   signs, zero and **N/A** are preserved, never calculated from rounded values. Existing
   approaching/**exceeded** threshold wording, price impact and refresh guidance follow
   these numbers. Neither number means remaining model capacity. The compact cell still
    shows only Next Ctx; full Watch's first-request Ictx and layout are unchanged.

Next and Δ use separate short tooltip paragraphs. A first prompt with evidenced
incoming **100,000** and its own compatible next estimate **112,000** has **Δ +12k**,
not +112k; exact zero reads **0**. A richer comparable prior session/compaction
anchor still takes precedence. Running tool loops update from their latest supported
root request without waiting for the prompt to finish. Before the first request,
only a proven prior baseline permits a disclosed provisional text estimate.

Prompt CCost help preserves a selected default as **`default (medium)`** (or the
best supported level/`unknown`), independently for main and linked contributors.
Explicit efforts are unchanged. Mini has no dedicated Effort column, so this help
has no default asterisk or confidence footnote. Visible labels and amounts do not
gain the parenthesized effort, and opening help never acquires source data.

When another prompt starts in the same session, Mini keeps its last valid
Ctx until the new prompt has a supported estimate. Help labels this as a
**previous same-session estimate; current prompt pending refresh**. Δ Ctx still
belongs only to the new prompt, never the previous one. Fresh evidence replaces
the retained value immediately, even when the formatted number stays the same.
Missing handoff fields, partial/retrying captures, an unbound new model, Stop/error
status, execution uncertainty and history-publication restarts are **pending**, not
context resets. A fresh Mini can use an already verified same-session summary,
including after close/reopen; it need not have rendered the preceding prompt.
Explicit compaction/reset/rewind/move, incompatible known provider/model, removed
active anchors and changed source/host clear or replace the old value immediately.
No other session's or incompatible historical prompt's tokens can seed it. First-ever
or genuinely invalid context keeps honest **N/A**. Full Watch's Context footer and
the Sessions catalog Ctx use the same source-owned continuation rule. Prompt Ictx,
Δ, cost and other prompt metrics remain independent. No timer-based grace period,
browser storage, extra history read or provider request is introduced.

Leaving current active history does not erase a retained, complete same-epoch
prompt-local pair. A historical row can therefore show session **300k** with prompt
**Δ +12k**, never +200k calculated from different times. **N/A** means the comparison
lacks evidence: missing input/usage/history, an incompatible model or context rewrite,
or an unexplained shrink. A short reason appears when available. Removed evidence
cannot be reconstructed from displayed numbers, and a move/compaction cannot revive
stale live context or price guidance.

Every canonical session appears **once**, even with several concurrent prompts or
identical display names. If several prompts run in one session, the latest genuinely
running prompt represents it (stable event-ID tie break). Its cost is not a sum of all
simultaneous focal prompts; the separate whole-session total is independent.
Execution-unverified unfinished work remains conservative, not a healthy completion.

All distinct running sessions are included without a data limit. Recent terminal-grace
and verified historical sessions compete by supported finish time for **max(0, 5 − R)**
remaining slots, where R is the number of distinct running sessions. Thus 0/1/3/4 running
sessions allow up to 5/4/2/1 finished fillers; 5 or more allow none. Fewer eligible
sessions produce fewer real rows, never duplicates or fabricated entries.
There is **no age exclusion**: eligible 100+ day and multi-year sessions still fill
these historical slots. Relative formatting changes neither membership nor ranking.

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

- The table's compact Activity, CCost, Total and Ctx column need **N**, with a generous Session
  target of about **1.6 × N** (about **2.6 × N** for the table), plus a measured scrollbar-width
  opening allowance, padding and small focus/rounding allowance.
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
When no internal scrollbar is needed, the table uses equal left/right body padding,
without a reserved empty gutter. A real scrollbar consumes only its browser-owned
width (overlay scrollbars consume none); the opening allowance remains available to Session.

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
inferred Capacity has a leading **~**. Only those estimates use the existing
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
