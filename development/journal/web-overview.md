# Overview parity investigation

Source revision: ad28c1e842447e6e66bb695cd6fc5cb2be552b99
Checked revision: ad28c1e842447e6e66bb695cd6fc5cb2be552b99
Last checked: 2026-10-28
Status: current

## Summary

At the source revision, the owner's V2 Normal report produced 25 models in CLI,
but Web returned result_too_large. The failure was transport payload, not a
missing catalog row. Normal exported unused month-wide request identities; the
candidate removes that aggregate-only payload while preserving all root revisions,
account scopes, model selection and the unchanged 8 MiB security/resource limit.
Session/detail identity exports remain unchanged. Overview also needs its complete
table, rather than the shared 50-row page, and stable DOM across host heartbeats.

## Evidence

CLI Normal was captured privately from the scratch clone with default config and
the already running V2 service. First cold capture exceeded a 180-second harness
deadline; a bounded 600-second retry completed without source/model mutations.
Web was started through cost-guard-web.py --foreground and opened in the built-in
Desktop browser using its normal one-use authorization flow.

Original compact result: 9,445,447 bytes, including 9,129,161 bytes of unused
request identities. Candidate repeat: 316,288 bytes; source revision evidence
alone remained 283,150 bytes. Counts are installation/time-specific, not budgets.
Application composition captured one canonical report; the CLI renderer and
application export consumed that exact report. The private export was loaded
into the real browser's shipped renderer without sending history to Git.
All 25 ordered model rows/four columns, phase costs, account scopes, native-money
and reset tokens matched. See the [sanitized matrix](../architecture/governance/verification/overview-real-installation.md)
for browser coverage and limits. Deterministic DOM cases include 0/1/49/50/51/123
rows, duplicate names across publishers, fallback ranking and unknown values.

## Next investigations

Keep aggregate views independent of per-request payload growth. If root revision
evidence itself reaches the bound, investigate an explicit provenance transport
contract; do not silently truncate it or raise the limit. Physical outer-window
resize and unrelated page-specific scrolling remain separate acceptance areas.

## Rejected hypotheses

The 50-row slice cannot explain this capture's failure: CLI had only 25 models,
and the browser rejected the result before model rendering. It is still a real
boundary defect, covered independently. Shared DTO ownership alone is not parity
proof; actual DOM, payload size, status-driven redraw and source scope must be checked.
