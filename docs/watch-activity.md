# Watch activity — v80.39

Watch uses its already-hydrated normalized session snapshot and existing causal prompt scope, including attributed task children. It does not run tools, query skill files, change OpenCode history or alter usage, billing, token accounting or quota refreshes.

## Latest-prompt rows

```text
↳ 34 tool calls · 30× shell · 3× read · 1× skill · 3 failed
↳ Skills (1): auto-agent-browser [1 tool call failure]
```

The total and breakdown count physical calls, not model requests. Native call IDs (otherwise canonical part IDs) deduplicate copies within each session; the newest canonical call state wins. Hidden breakdowns aggregate calls into `other`, never failures. Nonzero failures are red and outrank breakdown detail.

Only successful persisted `skill` invocations establish loaded skills: `input.id` (current) or `input.name` (legacy), in canonical state or top-level input. Mentions, generic tool inputs, failed loads and pending loads do not qualify. Repeated loads count once per distinct exact ID; newest load appears first. Skill information is yellow (`watchSkillActivity`), with only nonzero verified failure indicators red. Older custom palettes inherit this new role from their existing yellow Watch warning style; explicit style/null overrides remain supported. No empty Skills row is shown.

Rows remain on the latest prompt after completion/abortion; that session's next user prompt/subtask removes the old activity, even before the new prompt has tools. Other sessions are independent. Compaction does not transfer prompt activity to the checkpoint. Authoritative refresh/reconnect reconstructs observations; already-observed missing post-compaction rows retain their counts. Completed prompts show no stale running, background or TODO work. Stable idle snapshots reuse final observations.

## Reliable failures and attribution

Native `state.status = error` counts unless the existing structured cancellation/interruption rules apply. Completed shell/bash calls also count when a directly executed known Toolkit Python script returns one bounded JSON object with its exact recognized schema, `status = error` and nonempty `error.class`. Recognized cancellation classes remain neutral, including when the outer call is erroneous. Native and structured evidence for one physical call count only once.

Recognized contracts cover Toolkit browser, GitHub, Jira, Confluence, log-reading, document/transcription and checkpoint scripts, explicitly mapped in `src/watch/tool_contracts.py`. A standard trailing process-exit annotation is allowed. Wrong/missing schemas, unrecognized scripts, arbitrary prose, nested errors in successful results, compound/interpolated shell programs, malformed output and results over 64 KiB are not structured failure evidence. A nonzero exit alone is insufficient, so expected nonzero outcomes remain neutral unless a verified error contract says otherwise. This is deliberately not a universal shell-error detector.

Per-skill attribution requires explicit `skill_id`/`skillID`/`skillId` metadata or one direct Python invocation of `skills/<exact-id>/scripts/<script>.py`; a failed skill-tool invocation identifies its own skill. Conflicting identities remain unattributed. Script paths in reads, echoes or interpreted/compound programs are not execution proof. Unknown skill scripts can identify a native error's owner but cannot establish a structured Toolkit error. Only skills also confirmed loaded during the prompt appear in the Skills row. All unattributed failures still count in the tool summary; load recency never assigns a failure.

Only known script outputs are decoded, with a fixed bound; output/error messages and execution paths are never rendered or logged by this observation. Credentials/account files are not consulted.

## Narrow terminals

Activity rows fit the available terminal width independently of the fixed Watch metric table. The tool total and nonzero failed count precede breakdown detail; extremely narrow rows use compact count forms (for example `54 · 3!`). If even both counts cannot fit, only the total remains.

Skills preserve the distinct count, then newest whole IDs and verified failure indicators before older names. Omitted names use an exact `+N more`; IDs and bracketed indicators are never partially truncated or abbreviated. When no whole name fits, only the skill count/omission summary remains. Arrows keep their normal alignment whenever space permits.
