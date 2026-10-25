# FR 000130 completion — Watch history terminal recency

Implemented in Cost Guard v80.73, 2026-10-25, from default revision `6c636ce9bfd3f2813e8902b4f00026be3210fd9d`.

## Behavior and evidence

- Global history cap membership now uses the source-neutral projection's supported terminal end, falling back deterministically to the original event start. Selection and session history ordering agree; retained display order is restored before contiguous session grouping.
- Running/recent rows retain the existing finite marker and soft-cap protection. Success, abort and failure enter historical competition on the exact expiry refresh. Newer completions can evict them normally.
- No Watch-local terminal timestamp, new timer, persistent cache, native end synthesis or source mutation was introduced. Unknown-end transitions keep the conservative start fallback, rather than receiving synthetic recency. Earlier representatives and session-scoped selection remain start-based.
- Audited V1 message completion/error normalization, V2 assistant and attempt-bound persisted idle outcomes, source-neutral causal terminal times and prompt projection. Existing propagation already carries supported ends; no provider/plugin fields or new completion inference were added to Watch. A synthetic plugin-tool-plus-native-interruption path confirms abort/end propagation; plugin tool activity alone does not prove success or a terminal timestamp. This does not establish which actor caused the original reported stop.
- Missing zero-call post-compaction rows retain established identity/placement. Their observation-derived legacy duration is not used as an end or recency signal. Report Duration, costs, quotas, geometry and source lifecycle remain unchanged.

## Verification

- Focused Watch/source/recovery regressions: 106 tests passed before the additional cold/gap case; final Full includes that case.
- `py -3 development/tools/run_tests.py --suite full`: all 92 files passed, zero failures (54.7 seconds).
- `py -3 development/tools/validate_package.py --working-tree`: zero failures; existing design-budget warnings remain, no hard caps increased.
- Read-only installed V2 headless Watch: healthy source; initialized, enriched Today, polled and generated idle-status projection. Four rows/two running at observation; free-flowing overflow zero at 80/120/160 columns. Native OpenCode service was not stopped; no accounts or model prompts requested. This live smoke does not reproduce a real terminal transition; deterministic tests provide that evidence.
- Repaired README summary overflow by shortening it. A later overlapping live-probe cache caused an intermediate Full failure; after the temporary cache closed and was removed, a sequential clean Full passed. No assertions or package limits were weakened.
- Bundle privacy assessment: specification retained unchanged; this report contains only code contracts and aggregate verification facts, no personal exports or attachments.

## Knowledge and dependencies

Architecture assessment: no boundary change; tracker/retention ownership stays intact. Updated the existing Watch module contract and visible behavior documentation. Journal assessment: **no-update**; no new durable environment/root-cause or performance conclusion beyond this bounded smoke. No cross-FR prerequisite was created; pending FR 000140 is untouched. Native maintenance and identity state are preserved with the selected transaction; retention requested no pruning.
