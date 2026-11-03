# Mini Watch

On **Watch**, click **Mini Watch: Off** to request a compact Document
Picture-in-Picture window. The control changes to **On** only after it opens.
Click On again, the small **×**, or the browser's native close control to close it.
It never opens automatically on minimization or reload and has no saved On preference.

Mini stays open across in-app navigation. Its summary is a keyboard-accessible action
that selects Watch and requests focus of the **existing** owning Cost Guard tab; it
does not open a new tab or deliberately close Mini. Focus/restoring a minimized
window depends on the browser/OS. If that request cannot restore it, use the native
return-to-tab control, which may close PiP. Closing/reloading the owning document ends
Mini; a fresh page starts Off. Browser PiP replacement may also close it.

## What the figures mean

- **Running prompts:** distinct canonical initiating prompts genuinely in progress,
  including concurrent prompts in one session. Placeholders, context/history rows,
  compaction events and terminal highlight/grace cards do not add running prompts.
- **Running CCost:** accumulated canonical prompt CCost of just that running set,
  counted once each. It is not session cost, Today or a cumulative Watch-run total.
  A finished prompt's cost leaves immediately in the next canonical publication.
- **Longest running:** maximum canonical duration, not the sum. Two prompts running
  for 10 and 20 minutes show 2 and 20m. The maximum may decrease on completion.

An acquired empty set shows **0**, zero cost in the selected unit, and **—** duration.
Initial/partial/unavailable acquisition is not an empty success. Missing/partial
pricing follows the existing N/A or `?` conventions; `~` identifies an estimate.
Retained numbers are explicitly **not live** during connection/source/auth/host
failures or missing publication updates. No browser timer invents cost, completion
or indefinitely growing elapsed time.

Each subscription appears once as **name · N% used (same-period CCost)**. The
provider-declared stable primary wins; a missing primary never promotes a more
depleted secondary. Names retain account distinctions. Unlimited and exhausted
values retain native semantics. There are no reset/secondary-window paragraphs.
Hover a row for its period/attribution basis; unavailable cost does not hide a
known percentage. `~` means estimated attribution; `?` means partial pricing.

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

The compact card follows the effective **Classic / Web light/dark** theme and live
**Credits / USD** setting. Resize using the browser's window controls; long account
names wrap and the account list scrolls without hiding the main summary. The browser
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
