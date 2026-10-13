# Watch activity — v80.44

Watch derives prompt activity from already-hydrated normalized snapshots and existing causal prompt scope, including attributed task children. It does not run tools, scan skill files, mutate OpenCode data, or change usage, billing, token accounting or quota refresh.

## Prompt activity rows

Tool-call summaries and verified custom Skills rows follow the owning prompt's existing status marker. They appear while the prompt runs and retain final counts, per-tool breakdowns, verified failures and distinct custom Skills while a terminal marker remains visible. They disappear on the same update that removes the green completion or red abort marker, and immediately when a newer prompt supersedes them in that session. Activity from other sessions is independent; persistent abort data alone cannot recreate an expired marker.

Terminal updates clear running-tool durations, background-job indicators and active TODO progress while preserving final statistics. An unchanged `SessionSnapshot.source_revision` reuses the final observation; new authoritative revisions may update it. No separate activity timer or persistence is used. Rehydration through the active Watch tracker keeps the same marker lifecycle; a fresh tracker does not restore stale terminal activity. Existing terminal-error marker behavior is unchanged.

## Skill categories and custom Skills row

```text
↳ 8 tool calls · 4× shell · 1× builtin skill · 2× custom skill · 1 failed
↳ Skills (2): auto-github-api · auto-agent-browser
```

Totals count physical calls, not skill IDs. OpenCode call IDs (otherwise canonical part IDs) deduplicate native copies; repeated calls remain separate counts. Verified built-in and custom skill calls are grouped in the same breakdown and all displayed categories sum to the total. Unknown origin stays `skill`.

For V2, Watch consults the read-only, location-scoped `/api/skill` registry only for active sessions containing a skill call and caches its result per location/service connection. An absolute `/builtin` source path verifies built-in origin; another absolute source path verifies a user/project-configured source. Missing, malformed or ambiguous provenance is unknown. This uses the selected skill's resolved source (so a user override of a built-in ID is treated as custom) and never classifies by skill name alone. If registry evidence is unavailable, the generic category is used and no unverified custom Skills entry is shown.

`Skills (N)` lists only distinct successfully loaded skills whose custom origin was verified, newest load first. Built-ins, unknown origins, mentions, failed/pending loads and generic tool inputs are excluded. Existing directly verified per-skill failure attribution is preserved; unattributed failures remain in the total. Built-in IDs never appear in the Skills row.

Native `state.status = error` counts unless structured cancellation/interruption evidence applies. Completed shell/bash calls also count when a directly executed known Toolkit Python script returns one bounded JSON object with its exact recognized schema, `status = error` and a nonempty `error.class`. Native and structured evidence for one physical call count once. Output decoding remains restricted to known scripts; arbitrary output, reads, mentions, compound commands and nonzero exit codes alone are not failure evidence.

## Width and colors

Tool totals and failures retain priority over category detail. Hidden tool calls aggregate into `other`, so the visible breakdown still sums to the total. The Skills row keeps distinct count, newest whole IDs and verified failure indicators before older names; omitted IDs use exact `+N more` and are never partially truncated.

Tool-call, Skills and running-status prefixes/text use the same `watchToolActivity` styling. Verified failure totals and per-skill failure indicators remain red. The legacy `watchSkillActivity` color setting is retained for configuration compatibility but no longer styles a separate row; customize `watchToolActivity` for all normal activity text.
