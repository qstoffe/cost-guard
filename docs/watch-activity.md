# Watch lifecycle and activity — v80.55

Watch derives prompt activity from already-hydrated normalized snapshots and existing causal prompt scope, including attributed task children. It does not run tools, scan skill files, mutate OpenCode data, or change usage, billing, token accounting or quota refresh.

## Global session groups

One shared six-column table shows historical sessions first and active/recent sessions last, with exactly one normal horizontal table rule between them only when both groups are nonempty. There are no extra headings or settings. Session blocks remain contiguous, with one header and unchanged internal prompt/compaction order, subtotals, context warnings and activity rows.

A session is active/recent while any prompt is running or has the existing finite completion/abort highlight controlled by `watchRecentEventSeconds`. This lower group's ordering and configured-local `HH:mm` header use the latest prompt/compaction start, with session-ID ties. A new event updates its position; completion, abort, tools and polling do not. The whole block stays there through its last finite highlight, not just until its last running prompt ends.

After that highlight expires, the existing idle update redraws the dashboard and moves the block to history. Historical ordering and headers use the latest supported prompt/compaction end from the source-neutral analysis projection, never the observation, polling, group-transition or highlight-expiry time. When an end is unavailable, the event's start is the deterministic fallback, not an invented completion or an observation-derived duration. Historical blocks stay stable unless new authoritative event information arrives or the session is reactivated. A new prompt/compaction moves the block back to the lower group immediately under the same existing lifecycle.

Persistent error `!` markers retain their red styling and existing lifetime even in history; the marker string alone never makes a session active/recent. No new timer, retention rule, completion inference or accounting is introduced. The global row soft cap and running/recent protection apply before grouping. Ordering uses all available session event information, including events omitted by the cap. Startup `[Earlier]` representatives keep their selection, marker, date-aware timestamp format, retention and exclusion from run usage; their header uses the supported end or the same stable event-start fallback. Session-specific Watch and ordinary reports are unchanged.

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
