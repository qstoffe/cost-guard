# FR 000528 — Add an accessible credits/USD CCost display toggle in Web Beta

## Goal and dependency

Following FR000526's globally configured CCost credits/reference-USD presentation, let Web Beta users switch the **display** of CCost without changing what any number means or triggering a new history/price/provider acquisition. The default on a freshly opened browser tab follows the configured ccostDisplayUnit; CLI remains independent.

## Required behavior

- Add one compact, discoverable **CCost: Credits | USD** toggle in the shared Web shell/toolbar, keyboard and screen-reader accessible. Label that USD represents reference token valuation, not actual billing.
- Switch *every CCost-specific amount* in Overview, Watch, Models where applicable, Accounts CCost, Sessions, Date/Range, Token Mix and Snapshot/Live detail. Reference USD shows **$ and two decimal digits everywhere**, matching FR000526. The view must not mix USD-labelled and credits-labelled CCost after navigation, refresh, SSE publication or Live/Snapshot switches.
- Reuse canonical Python-computed display tokens or equivalent shared back-end presentation for both modes from the same underlying result; JavaScript selects the already prepared display and does not reprice model data or compute its own dollars/rounding. Raw numeric sorting, totals and warnings stay identical; no new source/account/history requests solely due to toggling.
- Keep the selected mode as transient **page-memory UI state** only, following Web Beta's existing no localStorage/sessionStorage/cookie-settings policy. A fresh tab defaults from validated application configuration; document predictable behavior when reloading. Never include private report data or auth state in the URL, storage or browser history.
- Preserve stale/frozen report identity, live update anchors/selection/scroll, table filtering and paging, unknown/partial amount markers and native provider money/credits. Native quota/used/remaining, Billed, Unaccounted usage and Relative CCost multipliers are not converted by this control.

## Acceptance

A single retained sample switches instantly and reversibly, without extra report jobs or provider refresh, across all report routes. Web Watch live publications, frozen Snapshot, stale/offline, Back/Forward, narrow layout and keyboard interactions have consistent display and preserve raw ordering. Cross-compare displayed USD/credits figures against FR000526's CLI fixtures. Browser tests must verify no storage persistence or client-side monetary valuation.

**Priority:** Later normal feature, after FR000526 and compatible with FR000520; Web Beta remains optional and independent of CLI.
