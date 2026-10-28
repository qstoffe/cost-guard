# FR 000531 completion

## Delivered change

Normal aggregate export omits unused month-wide causal request identities while
preserving root revisions, model/account scope and the unchanged 8 MiB bound.
Overview renders its complete CLI-ranked model table without hidden pages, shows
phase costs/native account detail, and retains its frozen DOM across host-status
updates so scroll/focus/selection survive. CLI calculation/selection is unchanged.

## Verification

- Real Windows/OpenCode V2 CLI and normal foreground Web host, built-in Desktop
  browser: baseline result_too_large reproduced (9,445,447 bytes); repaired capture
  316,288 bytes. CLI had 25 models, not more than 50.
- Same frozen real-source projection: all 25 ordered rows / 100 rendered model
  cells match CLI; phase costs, account scopes, native money, resets and notices match.
- Real browser synthetic 0/1/49/50/51/123-row boundaries; reversible sort/filter,
  desktop mouse/keyboard scroll, heartbeat-stable DOM/focus/selection and 360px
  Chromium subviewport layout verified. Physical outer-window resize is not claimed.
- Full suite: 114 files passed. Detailed sanitized matrix, causal evidence and
  explicit limitations: [Overview verification](../../../architecture/governance/verification/overview-real-installation.md).

## Knowledge and safety

Updated journal route/topic and report/code-map contracts; no major architecture
boundary changed. The whole original FR bundle remains byte-identical; new evidence
lives outside it. No paid inference, source mutation, private-data publication,
package ZIP, dependency or permanent gate added. Parallel FR-only publication was
reconciled from fresh main without changing this selection/transaction; its new
FR and identity watermark are preserved instead of replaying the stale watermark.
