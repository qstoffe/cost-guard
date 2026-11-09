# FR 000654 completion

Implemented in **v81.3, 2026-11-09**.

- Shared Accounts/Full Watch primary and secondary quotas omit unknown period and
  unavailable monthly capacity rows/targets, preserving native usage/reset/warnings.
- Numerical estimates use leading `~`; native amounts stay unmarked. Capacity help
  is concise, and displayed labels normalize only their first letter, including ARIA.
- Mini has five real Activity / Session / CCost / Total / Ctx columns, independent
  cost help/labels and no total parentheses. Matched opening width **550→541 CSS px**.
- Both cost tooltips safely highlight only the full genuinely running Duration
  fragment, preserving ticking, selection and open-help state/outcome updates.

Verification: local Full **180 groups passed**, package validator **11 passes / no
failures / seven existing advisories**; real hidden PiP fit **91 layouts at 125% browser
zoom**, focused live Duration help, full Accounts browser **231 layouts**, focused
real V2 Accounts continuity/cleanup and one populated running Mini source row passed.
No model calls, shared OpenCode stop, ZIP, tag or GitHub Release.

**Scoped Decision Delegate exception:** the combined live Watch/history probe failed
(earlier connection reset; later history still loading, 757/3044 at its 90-second
observation deadline). Whole-population historical completion/ranking and natural
historical transitions remain unverified; no FR functionality/assertion was waived.
Physical desktop/macOS/screen-reader proof is not claimed. See the full evidence,
reasoning and limits in [the journal](../../../journal/web/subscription-mini-polish.md).
