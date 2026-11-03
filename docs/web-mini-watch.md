# Mini Watch

On **Watch**, click **Mini Watch: Off** to request a compact Document
Picture-in-Picture window. The whole control is highlighted **On** only while it is open.
Click On again or the browser's native close control to close it; Mini has no custom ×.
It never opens automatically on minimization or reload and has no saved On preference.

Mini stays open across in-app navigation. Its summary is a keyboard-accessible action
that selects Watch and requests focus of the **existing** owning Cost Guard tab; it
does not open a new tab or deliberately close Mini. Focus/restoring a minimized
window depends on the browser/OS. If that request cannot restore it, use the native
return-to-tab control, which may close PiP. Closing/reloading the owning document ends
Mini; a fresh page starts Off. Browser PiP replacement may also close it.

## What the figures mean

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
Retained numbers are explicitly **not live** during connection/source/auth/host
failures or missing publication updates. No browser timer invents cost, completion
or indefinitely growing elapsed time.

Each subscription appears once as **name · N% used (same-period CCost)**. The
provider-declared stable primary wins; a missing primary never promotes a more
depleted secondary. Names retain account distinctions. Unlimited and exhausted
values retain native semantics. Each text row has a thin full-width primary Used
bar below it: cyan/teal below exhaustion, red only for authoritative finite 100%.
Unlimited/unknown quota has no fabricated bar. Stale, partial and restricted states
remain disclosed; there are no reset/secondary-window paragraphs.
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
**Credits / USD**. Healthy Live text is omitted; meaningful health warnings remain.
Mini requests 560×450 CSS px; browsers may clamp it. Up to five prompt rows and three
one-line subscriptions fit the normal default; rows 6/4 scroll in independent regions
with a sticky prompt header. Short lists shrink. Resize with the browser's controls;
long labels/larger fonts and unusually small windows may require internal scrolling.
The browser
owns outer chrome, origin/security indication, positioning, native return controls
and final geometry; this is not a frameless, arbitrarily positioned tooltip.

Mini has independent DOM but shares the owning tab's one authenticated live connection
and the process's bounded account-history lane. Opening/closing it never starts new
history scans, EventSources or provider polling. Updates apply directly from publications,
not a hidden-main-document animation frame; a visible PiP timer only checks freshness.
No credentials enter Mini URLs/storage/markup and no CSP relaxation is used.

Tested browsers and explicit OS/native-proof limits are recorded in
[Mini Watch verification](../development/journal/web/mini-watch.md). Availability
still depends on the actual desktop browser/version, platform and policy, not its name.
