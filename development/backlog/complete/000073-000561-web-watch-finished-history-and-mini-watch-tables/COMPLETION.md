# FR 000561 completion

Implemented 2026-11-03 in v80.141, based on main `5a2fe691ba8c8bd5701b4beada8863d50930754c`.

- Earlier uses canonical finish-based representatives, five-session membership and ascending finished order; Started/Duration on Running are unchanged. Unknown endings stay unknown and fill spare history slots before known finishes. Finished exports local date/time and UTC offset, including the repeated DST hour on Windows without IANA data.
- Mini replaces aggregate boxes with keyed per-prompt Session/#/CCost/Duration/CTX rows and thin primary-subscription bars. Shared lifecycle, final terminal grace, native quota/cost provenance, one SSE owner, theme/currency, independent five/three-row scroll regions and freshness warnings remain intact. On is filled, healthy Live text and custom close/frame are removed; native close and the main toggle remain.
- PASS: local Full, 133 files, 75.2s; package validator, 11 checks, zero failures, six advisory warnings. No caps changed and no ZIP produced.
- PASS: actual headless Chrome 156.0.8078.80 and Edge 156.0.4314.58 Document PiP/CSP/SSE, native API close/resize/replacement, 560×450 initial 5/3 layout, independent overflow, keyboard, themes/units, larger fonts and hidden-opener updates. Deterministic tests additionally cover rejected/cancelled requests, quota abort/error, unknowns, exact identities, finish/start inversion, ties and DST.
- PASS: read-only installed V2 probe, three coherent publications, one genuine running prompt, two finish-ordered history cards with known finishes, three accounts/one available primary-period cost; 7.83s acquisition, 0.089s owned close. No inference or shared OpenCode manipulation.
- Limits: no physical desktop/native chrome interaction, minimized-window restoration, OS z-order/geometry, screen-reader or macOS proof. Browser tests used owned hidden profiles and a synthetic 1920×1080 screen, with no security relaxation; smaller-screen clamping is allowed and internal scrolling degrades gracefully. No new requirement/test exception was requested or applied; older FR exceptions are not reused.

Current architecture, code map, user help and `development/journal/web/mini-watch.md` are updated. The original FR bundle is preserved intact; merged progress proposes ordinary count 12.
