# Watch lifecycle and activity — v80.207

Watch derives prompt activity from already-hydrated normalized snapshots and existing causal prompt scope, including attributed task children. It does not run tools, scan skill files, mutate OpenCode data, or change usage, billing, token accounting or quota refresh.

## Global session groups

One shared six-column table shows historical sessions first and active/recent sessions last, with exactly one normal horizontal table rule between them only when both groups are nonempty. There are no extra headings or settings. Session blocks remain contiguous, with one header and unchanged internal prompt/compaction order, subtotals, context warnings and activity rows.

A session is active/recent while any prompt is running or has a finite completion/abort/error highlight controlled by `watchRecentEventSeconds`. This lower group's ordering and configured-local `HH:mm` header use the latest prompt/compaction start, with session-ID ties. A new event updates its position; completion, abort, error, tools and polling do not. The whole block stays there through its last finite highlight, not just until its last running prompt ends.

After that highlight expires, the existing idle update redraws the dashboard and moves the block to history. Historical ordering and headers use the latest supported prompt/compaction end from the source-neutral analysis projection, never the observation, polling, group-transition or highlight-expiry time. When an end is unavailable, the event's start is the deterministic fallback, not an invented completion or an observation-derived duration. Historical blocks stay stable unless new authoritative event information arrives or the session is reactivated. A new prompt/compaction moves the block back to the lower group immediately under the same existing lifecycle.

Terminal failures show a red `!` and critical row styling only during the existing observation-based recent-event window, just like aborts. Afterwards the row retains a neutral `[ERROR]` outcome label, not a successful completion. `[ABORTED]` labels likewise outlast red emphasis. Polling, redraws, quota refreshes and source resynchronization do not renew an expired highlight. Historical failures loaded at startup (including scoped Watch and `[Earlier]` rows) receive no fresh emphasis. A zero-second window disables transient markers, styling and terminal activity, not historical outcome labels or running status.

The global soft prompt-row cap applies before grouping. All running/recent rows remain protected, even beyond the cap. Other current-run historical rows compete by their supported terminal end (success, abort or error), not their original start: a long-running prompt that finishes last stays eligible as the newest completion on the exact refresh its highlight expires. Genuinely newer completions can evict it normally. Membership ranking does not reorder prompts/compactions within a session. Historical session ordering uses all available session event information, including events omitted by the cap.

Unknown ends retain the deterministic event-start fallback for both history membership and headers. Watch does not introduce a local terminal-observation timestamp: confirmed transitions without a source end therefore do not receive synthetic recency. Polling, account redraws, reconnects, elapsed duration and highlight expiry never supply a native end; a later authoritative end updates history ranking without renewing the highlight. A retained zero-call post-compaction row keeps its identity and established display placement, but its observation-derived duration is not terminal-time evidence.

V1 assistant completion/error times and V2 causally matched assistant/idle terminal evidence flow through the same source-neutral projection. A plugin-driven stop with a native interruption has the same abort semantics as other interruptions; a plugin/tool call or session status alone proves neither success nor a prompt-specific end. No stop initiator is guessed. Startup `[Earlier]` representatives keep their start-based selection/one-shot eviction, marker, date-aware timestamp format and exclusion from run usage; their header uses the supported end or the same stable event-start fallback. Session-specific Watch keeps its ordering and start-time header; ordinary reports, Duration and accounting are unchanged.

## Prompt activity rows

Web cards reconcile execution against the first accepted complete authoritative capture, separately from retained usage/history. Persisted quota/interruption causes survive omitted idle rows for the same assistant attempt; later real work remains possible. A proven full-tree reclassification can end a retained row without inventing success or an end timestamp. Partial omissions and outages instead retain explicitly partial/unavailable observations, not proof of completion. Old generations and delayed captures cannot overwrite a newer publication.

The 30-second default terminal highlight starts once when running work is observed to end. It does not mean the card is still running: duration growth and live tool/background/TODO indicators stop immediately, and the prompt contributes nothing to running-only projections. Refreshes do not renew grace; cold-start terminal history does not flash as new activity. The distinct 60-second tool-call continuation rule remains unchanged; neither grace is a timeout for quiet work.

Tool-call summaries and verified custom Skills rows follow the owning prompt's existing status marker. They appear while the prompt runs and retain final counts, per-tool breakdowns, verified failures and distinct custom Skills while a terminal marker remains visible. They disappear on the same update that removes the green completion or red abort/error marker, and immediately when a newer prompt supersedes them in that session. Activity from other sessions is independent; persistent abort/error evidence alone cannot recreate an expired marker. Individual failed tool calls do not establish prompt failure.

Terminal updates clear running-tool durations, background-job indicators and active TODO progress while preserving final statistics. An unchanged `SessionSnapshot.source_revision` reuses the final observation; new authoritative revisions may update it without restarting the highlight. No separate activity timer or persistence is used. Rehydration through the active Watch tracker keeps the same marker lifecycle; a fresh tracker does not restore stale terminal activity.

## Skill categories and custom Skills row

```text
↳ 8 tool calls · 4× shell · 1× builtin skill · 2× custom skill · 1 failed
↳ Skills (2): auto-github-api · auto-agent-browser
```

Totals count physical calls, not skill IDs. OpenCode call IDs (otherwise canonical part IDs) deduplicate native copies; repeated calls remain separate counts. Verified built-in and custom skill calls are grouped in the same breakdown and all displayed categories sum to the total. Unknown origin stays `skill`.

For V2, Watch consults the read-only, location-scoped `/api/skill` registry only for active sessions containing a skill call and caches its result per location/service connection. An absolute `/builtin` source path verifies built-in origin; another absolute source path verifies a user/project-configured source. Missing, malformed or ambiguous provenance is unknown. This uses the selected skill's resolved source (so a user override of a built-in ID is treated as custom) and never classifies by skill name alone. If registry evidence is unavailable, the generic category is used and no unverified custom Skills entry is shown.

`Skills (N)` lists only distinct successfully loaded skills whose custom origin was verified, newest load first. Built-ins, unknown origins, mentions, failed/pending loads and generic tool inputs are excluded. Existing directly verified per-skill failure attribution is preserved; unattributed failures remain in the total. Built-in IDs never appear in the Skills row.

Native `state.status = error` counts unless structured cancellation/interruption evidence applies. Completed shell/bash calls also count when a directly executed known Toolkit Python script returns one bounded JSON object with its exact recognized schema, `status = error` and a nonempty `error.class`. Native and structured evidence for one physical call count once. Output decoding remains restricted to known scripts; arbitrary output, reads, mentions, compound commands and nonzero exit codes alone are not failure evidence.

## Full Web Watch outcomes

The collapsed Tool Calls summary shows one combined **N failed / cancelled** count from evidenced physical calls. Expanding it lists every ordinary tool group, then red outcome subsets such as **2 × grep failed** and **1 × execute cancelled**. Failed groups precede cancelled groups, then sort by count descending and name. The summary’s five-group cap never hides expanded outcome details.

Ordinary tool groups include **all** calls, including failures and cancellations; red lines are subsets, not extra calls or evidence that the other calls succeeded. Explicit cancellation wins over error evidence for the same call. Unknown names use `unknown`; a retained/older aggregate without a complete breakdown shows only the unidentified difference. Missing outcome evidence never supplies a label or count. The shared accessible help explains these distinctions without showing commands, output or traces.

Skills retain confirmed custom load identities and directly attributed **failure-only** counts. Tool cancellations are not allocated to a recently loaded skill; skill counts need not sum to overall outcomes. Canonical failure-only data and CLI presentation remain unchanged.

## Full Web running invocation details

The longest active native tool keeps the existing ten-second threshold. Its
**Running: tool duration** row is an initially collapsed native disclosure,
usable with keyboard, mouse or touch. Expansion shows available source input in
selectable, wrapped monospaced key/value text; command quoting and newlines are
preserved. This is observation only: opening it executes nothing and fetches no
additional source data. Tool output and metadata are never displayed here.

Only supported scalar parameters are eligible (including command, workdir,
description, background, timeout and common search/read options). Ordinary Python
commands, Windows/Unicode paths, `tokenizer.py`, `--mode=fast` and harmless
`NAME=development` assignments retain their original argument order and text, with
no extra warning. Recognized credential values are specifically replaced with
`[redacted]` when their boundaries are safe; ambiguous credential syntax, headers
and private keys are withheld. Environment blocks, content/script bodies,
unsupported/structured fields and oversized values have separate omission reasons.
Missing source input/command is identified as absent, not called sensitive or
reconstructed from a description. Limited/redacted text is never labeled complete.
Screening cannot guarantee recognition of every private value. Treat even eligible
paths/commands as private local information.
Details remain in process memory and the authenticated loopback Live publication,
not Cost Guard caches, diagnostics, logs or telemetry. Each detail is bounded to
roughly 4 KiB of formatted input across each foreground/background list; concurrent
entries share that budget. Huge arguments are omitted explicitly, not silently cut off.

For recognized OpenCode shell/bash inputs, a supplied positive finite numeric
timeout is labeled in **milliseconds**, for example `timeout: 120000 ms (2 min)`
or `1500 ms (1.5 s)`. This is the requested tool limit, not elapsed/remaining time
or proof of eventual termination. Running duration remains separate. No supplied
timeout means no invented default; zero, negative, string and other-tool timeout
values retain their raw meaning without invented units or an “unlimited” claim.

Background jobs remain separate from foreground calls. Expansion lists up to five
individually identified invocations in stable start/identity order, with an honest
`+N more` for additional jobs. Two observed tool calls do not imply two running jobs.
The compact Running summary and original counts/duration are unchanged.
Each job needs an unambiguous session/assistant/physical-call or native-shell join
inside the canonical prompt/linked-child scope. Missing original input may use the
same V2 location-scoped shell observation's command/cwd/shell; optional experimental
shell-job recovery is restricted to the verified 2.2.7 API and exact owning session.
It does not create a mandatory experimental dependency or an expansion-time read.
Session-only records without a prompt-qualified join are not assigned to a prompt.
Commands from other sessions or contradictory identities are never displayed.

When original input and registry command text differ, the independently linked
original input alone is shown, with a qualification: registry details are withheld
and the executed form is not verified. Runtime setup can legitimately differ from
the requested command; Cost Guard does not parse wrappers or guess equivalence.
Privacy-withheld input is never rescued via that conflicting registry command.
Absent input, missing original links, unobservable registry and awaiting verified
live source each get specific explanations alongside the known Running facts.

Duration-only updates preserve expansion, detail nodes, selection and focus.
Different physical calls, source generations and corrected call revisions reset
only the affected entry; unrelated jobs stay expanded. Terminal/unverified prompts and unavailable/retained observations
clear the live input; existing status/count lifecycle and CLI/Mini are unchanged.

## Width and colors

Tool totals and failures retain priority over category detail. Hidden tool calls aggregate into `other`, so the visible breakdown still sums to the total. The Skills row keeps distinct count, newest whole IDs and verified failure indicators before older names; omitted IDs use exact `+N more` and are never partially truncated.

CLI tool-call, Skills and running-status prefixes/text use the same `watchToolActivity` styling. Verified failure totals and per-skill failure indicators remain red. The legacy `watchSkillActivity` color setting is retained for configuration compatibility but no longer styles a separate row; customize `watchToolActivity` for normal CLI activity text.

In full Web Watch, both foreground and background/subagent **Running:** status lines share the prompt/session `--watch-running` foreground (yellow in Classic; theme-aware Web light/dark), even when inputs are unavailable. This supersedes only the older background-line gold/brown choice: thresholds, cadence and job meaning are unchanged. Ordinary Tool Calls/Skills groups remain gold/brown; outcome subsets stay red. No background highlight is added.
