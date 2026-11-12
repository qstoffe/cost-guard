# FR 000685 — AI Stats: replace Token Consumption Rate with a Top 3 provider-response tokens/sec podium

**Owner-approved Ready to Develop FR, 2026-11-12.** Permanent ID **000685**, temporary Ready priority **001030**. This changes **only the existing Token Consumption Rate card** on Web AI Stats, plus the minimum AI Stats data/projection/test/documentation support required. It deliberately corrects FR000682's three-hourly-rates interpretation.

## Desired user experience

The owner does **not** want another Calendar / Workday / Active AI hourly-average card. The existing `AI Hourly Rate` is already correct and must remain completely unchanged. The existing `Total Tokens` volume card is useful and must also remain unchanged.

**Repurpose the existing `Token Consumption Rate` Overview card** as a fun **Top 3 fastest used AI models** highscore for the *selected AI Stats period* (Today, 7 days, 30 days, This month, All time).

- Show at most **three model rows**, highest **generated output tokens per second** first, with **🥇 gold, 🥈 silver, 🥉 bronze**. One distinct model per podium position, not three individual high-scoring prompts. Display model identity/name, readable `tokens/s` (or `tok/s`) and a modest sample count such as `24 model calls`, with terse helpful hover/focus copy. The numeric values and ranking must come from that user's observed calls, never an external benchmark or an advertised model specification.
- **Remove** the card's existing `Calendar average`, `Workday average` and `Active AI average` rows and all associated hourly-token-help text and “Unavailable” treatment driven by whole-prompt active time. Do not turn the new card into a fourth rate table elsewhere. Keep the card in its current Overview position/layout, with the familiar playful tone and existing responsive styling.
- Keep the current **Loading-only** card-shell presentation on not-yet-ready selected-period historical work, and same-period last-good retention. After readiness, show the complete podium atomically. If no relevant usable call has been observed in a truly ready period, use a short friendly truthful state (e.g. `No measured model calls yet — the podium is waiting.`) rather than invented medals, zero speed, or a generic whole-period `Unavailable`.
- The ranking should be **lightweight** and should not delay the twelve-card AI Stats page, require an explicit refresh, or trigger expensive independent scans.

## Precise metric: provider-response throughput, not prompt-workflow speed

The owner means the elapsed time **from a specific model call being sent to its provider until the provider response is received/finished**. This is a client-observed **provider request round-trip / response throughput** metric: it includes upstream queueing, network transit, time-to-first-token, model generation and response delivery, insofar as they occur inside that call. It is **not** a pure GPU decoding benchmark and should not be labelled as such.

**Crucially exclude** all *unrelated local harness work*: time before dispatch while the client prepares context, local tool invocations, filesystem/terminal actions, agent orchestration between calls, prompt-wide waits, human idle time and post-response local processing. A prompt can execute multiple sequential model requests separated by tools; each eligible request must have **its own numerator and its own provider-call interval**. Background/subagent requests may qualify individually for their actual model, but the enclosing parent prompt's elapsed time never becomes their denominator.

Per eligible provider call:

`response_tps = actual generated output tokens / ((provider response received - provider request sent) / 1000)`

For one displayed model over the selected period use the volume-weighted aggregate:

`model_tps = SUM(eligible output tokens) / SUM(matched provider-call durations in seconds)`

Do **not** average the per-call rounded TPS values or select a single unusually fast outlier as the model's period speed. Use unrounded numerator/denominator for sorting, format a compact numeric value only at presentation.

**Numerator:** provider-observed **generated output** tokens for that exact model request (including separately reported reasoning generation if and only if established canonical output semantics include it without double-counting). **Never** use Input, cached input, cache write, or Total Tokens (which is traffic across all categories) as the TPS numerator. Preserve per-request source/provider/model/variant/step identity and existing step-over-message/tool-continuation/clone deduplication. Attribution of usage and timing must agree; do not attach a parent duration to a child model or merge different provider responses into one.

**Period membership:** align with the selected AI Stats period's existing request completion-time convention, current timezone/day boundaries and source generation, including the already supported All time and archived roots when available. Count only independently attributable completed calls; one long call is counted once in its finishing period (do not prorate time or tokens through calendar boundaries).

**Model identity:** rank unique actual provider/model identities. If variants/effort settings have materially different response behavior, either keep them distinct and clearly label them or aggregate with a documented consistent rule that does not silently conflate incompatible identities. Deterministic ties and zero/one/two eligible models are handled cleanly; avoid fuzzy provider aliases. The goal is a Top 3 of *used models*, not the top three requests or externally benchmarked speeds.

## Source feasibility — important existing evidence and required resolution

FR000682 originally proposed a generation-only TPS fact but **omitted it** after a small real-source inventory found no proven **first-to-last-generated-token** interval. This FR intentionally asks for a **different, broader and potentially more feasible interval**: **dispatch-to-completion of one provider request**, including prefill/TTFT, *not* first-token-to-last-token decoding speed. Do not reject this request simply because the older first/last-output-token test failed.

Current Cost Guard relevant facts:

- `src/sources/opencode_v2_normalization.py` already normalizes assistant `time.created` and `time.completed`, optional `time.streamed`, and per-step `step-finish` usage into `ModelInvocation`. `src/domain/models.py::ModelInvocation` carries per-invocation created/completed timestamps. **Presence of fields does not yet prove they exactly bracket network send and final provider response**.
- `src/reports/ai_stats_evidence.py` currently stores prompt/compaction **execution-duration intervals** for AI Working Time; these include tool/agent workflow and are categorically **not** eligible provider-call denominators. `src/analysis/ai_stats.py::_token_metrics` currently divides total token traffic by unioned whole-workflow duration: delete/replace this token-rate use, not the shared duration or the existing cost-rate calculation.
- Current OpenCode V2 source/event vocabulary includes step start/streamed/completed; check **the actually supported installed V2/V1 versions** and their persistent event semantics. Verify where `step-start`, assistant `time.created`, step-finish `time.end`/assistant `time.completed` originate relative to a real provider dispatch, request transport completion, tool-call generation and local processing. A stream-completion metadata burst or a tool-only continuation must not produce ridiculous six-digit `tokens/s` winners.
- Decide from that evidence whether an existing, already-acquired per-call timestamp pair is a sufficiently accurate **provider-response-duration proxy**. A transparent approximate call-level throughput estimate is acceptable for this playful card; **whole-prompt time is not**. If available timestamps include a material local pre/post-call phase, find a narrower existing observable seam where possible and document the distinction in short tooltip wording. Do not silently claim exact provider-only timing from an unrelated assistant lifecycle timestamp.
- If legacy V1, an older OpenCode release, or a particular provider lacks usable per-call timing, exclude **those calls only**, not the entire period. Ranking may use a qualified subset, labelled as such with sample count; **one missing historical interval must not make all three positions `Unavailable`**. If *no* calls in that scope have trustworthy enough request timing, show a friendly **“No measurable provider calls yet”** explanation, and record the actual capability gap. Do not fill the podium with guessed fixed durations or arbitrary speed figures.
- Before adopting a new observer/collector, first exhaust the existing normalized retained data and compact checkpoint/read-only source route. If truly necessary to support *future* observations, assess a **small supported, read-only, privacy-preserving per-call timing hook** at a currently allowed OpenCode integration boundary. It must not mutate the shared running OpenCode service, install a third-party plugin, intercept secrets, send paid model calls, or change another repository under this FR. Any required upstream change outside Cost Guard's authorized scope is a **clearly identified prerequisite**, never silently delivered or fabricated in this task. Keep older periods honest if such evidence could not have been recorded historically.

## UI and tone

Retain the title **Token Consumption Rate** as requested, but its help must make it immediately clear that it now represents **model output response throughput (`tok/s`)**, not the total I/C/W/O consumption of the Total Tokens card or calendar/workday activity per hour.

Preferred compact presentation (illustrative only):

```text
Token Consumption Rate

🥇  Model A                         195 tok/s
    24 measured calls
🥈  Model B                         143 tok/s
    18 measured calls
🥉  Model C                          98 tok/s
    31 measured calls
```

A short playful trait such as **“The silicon sprint podium.”** is fine after load; when no qualified data, **“No stopwatch, no medals.”** can accompany an honest explanation. Keep text selectable, headings accessible and hover/focus/touch title help concise; no new visible question-mark clutter or extra tables. Do not introduce duration, reliability or missing-source badges on every row, but sample counts and a short scoped help note must prevent falsely implying an official benchmark. Unmeasured entries stay absent, not zero-speed contestants.

## Acceptance criteria

1. **Visual contract:** On every AI Stats period, the previous token-rate three-hour rows are gone, replaced in the same Overview card by up to three ordered medal/model/`tok/s`/sample rows. AI Hourly Rate and AI Working Time remain **exactly as they were**. Total Tokens remains the unchanged source-based I/C/W/O+reasoning traffic card. Other nine Fun Facts/Overview stats and conditional matched fact stay untouched.
2. **Actual timing provenance:** Trace a typical supported V2 provider call from dispatch through returned response with **real code/schema evidence** (and a bounded read-only local observation if available), showing why the chosen timestamps bracket the desired response rather than tool, prompt or session execution. Explicitly compare a model response embedded in a long tool loop with its short real call interval. Record differences between observed request timing, proxy and unsupported releases. No invented direct-provider metrics or unverified assertion that `time.streamed - time.created` is token generation time.
3. **Independent oracle:** Multiple calls per model, different output counts/durations, parallel/overlapping models, context-cache-heavy requests, hidden reasoning, retries, aborted/incomplete and duplicate/zero-usage continuation records give correct aggregate **SUM(output)/SUM(provider-call seconds)** and ordering. Exclude invalid/missing/zero/negative duration and unsuitable implausible burst observations; don't exclude a whole model merely because another unrelated call is missing. Bound outliers through sound eligibility/evidence, not arbitrary inflated displayed rates.
4. **Period and identity:** Scope switching, repeated roots and subagents, same model at different efforts, source revisions, missing old histories and cached results never leak another period's sample or count the same physical call twice. Validate exact model/source identity, deterministic tie rules, 0–3 eligible ranked models, and sample-coverage help.
5. **Loading/performance:** Reuse current AI Stats authoritative period-ready shell, safe last-good retention, checkpointed 256-root slices/64-root batches and existing host-owned data demand. No extra full-history scan or separate paid probe, no UI stall just to resolve this novelty metric, no additional independent background loop. Warm/changed rerenders preserve focus and title help; cold/ready/failed/empty behavior stays truthful. Measure representative cold/warm and five-period payload impact; do not invent a no-overhead claim.
6. **Coverage policy:** Demonstrate one known-valid timed provider response produces a nonzero measured podium entry; historic missing timing does not force a whole-page or whole-period `Unavailable`. If source limitations prevent even one qualified call, deliver the best genuinely supported per-call measurement path within Cost Guard or report the verified dependency instead of falsely declaring a working speed leaderboard. Do not substitute whole-workflow active hours or an external benchmark to make a test pass.
7. **Regression scope:** Update `src/analysis/ai_stats.py`, `src/reports/ai_stats_evidence.py`, appropriate source/analysis identity adapters if justified, `src/application/{ai_stats,projection}.py`, `src/web/assets/ai-stats.js` and focused CSS; evolve policy/result validation, compact evidence cache dependencies and existing `test_ai_stats_tokens.py` / `test_ai_stats.py` / resume/browsers/fixtures safely. Preserve Python/JS layer boundaries, authoritative source identity, existing error recovery, unit/theme independence and accessibility. Update `docs/web-beta.md` and scoped AI Stats architecture/journal truthfully.

**Non-goals:** altering AI Hourly Rate, replacing Total Tokens, a global tokens/sec dashboard or new benchmark source, model speed inferred from entire prompt execution, time excluding TTFT (pure decoding TPS), new per-period Calendar/Workday rates, provider or account writes, credential collection, experimental paid inference, automatically changing OpenCode/another repository, or hiding genuine missing provenance behind fabricated highscore rows.

**Done means:** Token Consumption Rate is an honest, lightweight **Top 3 provider-response output tokens/sec** podium over real used models and the selected time window, **not** tokens per active workflow hour; all other existing AI Stats cards retain their behavior. Any actual upstream timing limitation is documented, not mistaken for a completed measurement.
