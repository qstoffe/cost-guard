# FR 000694 — Default effort tooltips: show `default (effective-level)` without changing the selected setting

**Owner-approved Ready to Develop, 2026-11-13.** Permanent FR ID **000694**, priority **000002**, immediately **after** Cost Guard FR000693 (priority **000001**) in the current Ready queue. **FR-only publication now:** the owner has expressly required source changes to go through implementation FR/PR workflow; create this specification and research attachment, but change **NO** production code, tests, installed OpenCode/Toolkit files, product version, runtime cache or historical data in this authoring commit.

## Owner request — exactly one presentation-only enrichment

Whenever Cost Guard shows a **model reasoning effort** inside a **tooltip / hover/focus/tap help**, and the **user-selected** effort for that specific model/request was **default**, retain the word **`default`** but append the effective concrete effort in **one space and parentheses**:

```text
Selected: default  + effective: medium   =>  default (medium)
Selected: default  + effective: high     =>  default (high)
Selected: default  + effective: low      =>  default (low)
Selected: default  + effective: none     =>  default (none)
Selected: high     + effective: high     =>  high   (unchanged; it was not default)
```

The owner explicitly does **NOT** want the selection `default` replaced with `medium` or `high`. A tooltip must continue to convey **what was actually selected** and add **what that selection resolves to**. Preserve raw per-request `provider/model` help from completed FR000687 and its separate catalog-estimate provenance. Make this **consistent across every relevant model/effort-bearing tooltip**, including linked subagents and mixed contributors, not just one visible Model cell.

**Only tooltips change.** Do not add the parenthesized level to visible grid/table cells, Model/Effort columns, badges, session titles, CLI reports, chart labels, JSON exports intended as original selection, GitHub reference pricing table, Terminal-Bench benchmark effort values or any other non-tooltip text. Keep the current friendly visible model naming.

## Source-first investigation — OpenCode's `default` is not always a single fixed model constant

Inspect the **installed OpenCode version and currently effective project/provider/model/agent/command configuration** using the supported read-only source. Its documented model/variant semantics are:

- [OpenCode model/variant guide](https://opencode.ai/docs/models): `provider/model#variant` selects a specific named variant; `default` selects **no variant**, letting effective provider/model settings apply. Provider settings, then model settings, then selected variant settings are merged. Local aliases may specify `modelID`. Availability, config and provider differ by project/location.
- [OpenCode resolver `withVariant`](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/model-resolver.ts) treats variant `"default"` like undefined and applies no variant override. [OpenCode `Model.Info` schema](https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/model.ts) exposes selected provider/catalog ID, concrete modelID, provider/model settings, variants and capabilities, **not a universal numeric default for every installed backend**.
- Current `src/analysis/effort.py::interpret_effort` already distinguishes `EXPLICIT`, `RESOLVED_DEFAULT`, `DEFAULT` and `NONE`: request-attached concrete variants can resolve a default on compatible same-prompt evidence. `src/analysis/comparisons.py::effort_model_parts` reduces this to user-visible title-case `Default`, `Medium`, etc. **The selected-default versus concrete-effective distinction can be lost** when `RESOLVED_DEFAULT` is reduced to just `Medium` in downstream value-help copy.
- `src/reports/prompt_costs.py::prompt_cost_parts` groups actual per-request `entry.variant` and `src/application/prompt_costs.py::detail_tokens` composes text such as `Main prompt — provider/model · Default` for Model/CCost/Calls tooltips. `src/web/assets/mini.js::View.promptDetails` independently creates `Effort: Default`; `src/application/comparisons.py` and `src/application/ai_stats.py::response_tokens` also export model/effort contributor labels. Audit them together rather than fixing only one UI string.
- The current [GitHub Copilot price list](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing) is **a roster of priced models and pricing tiers**. Its column named `Tier: Default` is **NOT** a model's reasoning-effort default and must never be used to infer one.

**Effective defaults can change by model release, provider route, package/API, exact session location, explicit provider/model settings, agent or command, and time.** They may also be adaptive or omitted for a model that has no supported numeric effort control. A model's default on the vendor API may **not** be the default imposed by an OpenCode or GitHub Copilot integration. Historical current-catalog settings are not proof of the configuration that ran a past request.

## Resolution precedence and requirements

1. **Preserve the selected effort explicitly.** Carry a request-/session-/subagent-qualified fact like `selected_effort=default`, separate from `effective_effort`, `effective_effort_source` and source/revision identity where available. Distinguish a user explicitly choosing `#default`, absent variant treated as OpenCode default, a true explicit `#medium`, and a missing/unattributable effort record. Don't use display string splitting to infer it.
2. **Highest priority — actual request evidence.** If a normalized request or provider metadata establishes the selected default and a concrete effective effort (e.g. request-attached concrete reasoning `medium` with exact model/session/call provenance), display **`default (medium)`**. Ensure it belongs to the **same physical model request**, not a different turn, contributor, old prompt, sibling/child or previous retry. `interpret_effort`'s `RESOLVED_DEFAULT` path is an existing starting point, but it must retain selected-vs-effective provenance.
3. **Next — actual OpenCode package and config.** Evaluate supported, read-only effective provider/model settings and provider-package defaults on the actual selected location/model/API route, including `reasoningEffort`, `reasoning.effort`, `effort`, `thinkingLevel`, `thinkingConfig.thinkingLevel`, named variants and Claude Agent SDK options, **only when mapping to one actual request is defensible**. Provider-level and model-level settings override vendor API defaults. If a current configuration is mutable and no historical run-bound snapshot survives, qualify it as an *estimate*, not proven historical execution.
4. **Last — static documented vendor defaults.** If the installed OpenCode source does not expose a concrete effort and there is no known conflicting override, use a **shipped, small, versioned, reviewed fallback mapping** for the exact underlying model/provider route, sourced from official model/provider documentation. This FR includes the complete [31-model research attachment](MODEL-DEFAULT-EFFORT-RESEARCH.json) as a starting inventory, with date, URLs and evidence classifications. Implementers must translate these **public vendor defaults** to the exact authenticated `providerID/modelID` only where route behavior is supported; don't blindly apply an Anthropic default to a Copilot proxy that explicitly sets another level.
5. **If still unresolvable, say so — don't lie.** Prefer `default (unknown)` (or `default (not applicable)` **only if the source explicitly establishes no numeric effort control**) instead of guessing a concrete level. The parenthesized qualifier keeps the owner's requested visual `default (...)` structure while making the limitation truthful. Do not invent a `medium` simply because an official document *recommends* medium; **recommendation is not API default**. Aim to resolve the great majority through native config/verified static coverage; unknown should be a documented residual, not a default shortcut.
6. **Don't rewrite semantics or billing.** Display enrichment must not change request variants, model selection, provider route, actual thinking settings, canonical attribution, CCost, I/C/W/O, usage, pricing, token mix, effort selection stored in the source, model group/dedup identity, timestamps, benchmark sorting or original native history. Never replay past paid calls just to derive an effort label. The current GitHub price list updates dynamically; this is not a mandate for runtime web scraping or extra requests at tooltip open.

### Precise formatting

- Tooltip-only standardized token: **`default (<lowercase effective level>)`** with exactly one ASCII space before `(`, e.g. `default (medium)`, `default (xhigh)`; valid levels are `none, minimal, low, medium, high, xhigh, max` or an authenticated, source-supported open-ended level.
- Non-default selected efforts (`low`, `medium`, `high`, custom named variants) remain exactly as previously presented. If the user selected `#high`, do not relabel it `default (high)`.
- No duplicate suffixes (`default (medium) (medium)`), no `Default (Medium)` in one surface and `default (medium)` in another, no confusing `high (default)` reversal. Preserve existing provider/model and request-effort provenance lines; do not truncate source-qualified contributor identities.
- For mixed-model and linked-agent tooltips, **resolve each group independently**. A `claude-agent/opus` default may be `medium` while `claude-agent/sonnet` default is `high` even within one parent prompt. A single group with conflicting effective defaults must retain per-request distinctions or report a scoped uncertainty, not silently pick one.
- If an API response already contains a literal title such as `Default` in a model name or GitHub pricing tier, do not mistakenly transform it; this applies **only to a field semantically identified as selected reasoning effort**.
- Do not show the appended effort in visible Models tables, benchmark Effort filters, Sessions detail Effort column, Watch Effort column, Mini row title or AI Stats podium speed label. The `default (...)` string lives in hover/focus/tap **help content only**. Avoid a tooltip's accessible-text path bypassing the change.

## Mandatory UI coverage audit (all existing model/effort help)

- **Full Watch Running/Earlier:** Model value help; prompt CCost help (main/child model group headers); Calls help; any effort help containing actual request selection.
- **Mini Watch PiP:** prompt CCost tooltip `Effort: ...`, its main-model/subagent section and any secondary tooltip reusing model or cost details.
- **Sessions list and Session detail:** single/multiple-model contributor help, linked-agent information, Model/Calls/CCost value help, and compaction/tool continuation **only when an actual request effort is attributable**. Keep visible Effort cells unchanged.
- **Comparisons:** request/contributor model/effort provenance help, including mixed models. Keep table numeric/sort/filter and visible effort unchanged.
- **AI Stats:** sampled response-output-TPS podium model/effort help and other actual model-effort tooltips (no card metric or podium label change).
- **Other future/shared help:** search all call sites of `ContextHelp`, `model_detail_help`, `cost_detail_help`, `calls_help`, `model_help`, `effort_model_parts`, `watch_effort` and `default`. Add one shared model-effort tooltip formatter/data contract rather than repeating string substitutions per page. Do not introduce effort into generic heading definitions or reference pricing/benchmark tooltips that don't describe an individual model's selected request effort.

## Static research appendix — public GitHub Copilot roster, 2026-11-13

The accompanying **[MODEL-DEFAULT-EFFORT-RESEARCH.json](MODEL-DEFAULT-EFFORT-RESEARCH.json)** is the requested static research material and contains **all 31 distinct current text/code model names** from GitHub Copilot's pricing table, excluding duplicate long-context *price tiers*, empty GitHub Fine-tuned rows and image-only models. It includes every row's manufacturer, vendor/API default where known, first-party evidence IDs and URL map, and one of:
- **`documented`** — explicit vendor API default in cited first-party documentation (still conditional on **which runtime route/config** actually served the request);
- **`conditional`** — credible provider-package/source/support evidence, but not verified as the effective default for GitHub Copilot/OpenCode (must be checked against installed route);
- **`unresolved`** — no reliable numeric default found for that particular older/unknown model (cannot be filled with a fabricated effort).

As a readable review index (the JSON is the machine-readable attachment):

| Publisher | Model in GitHub price list | Documented/researched API or package default | Evidence class | Static source IDs |
| --- | --- | --- | --- | --- |
| OpenAI | GPT-5.3-Codex | `medium` | conditional | `opencode_openai`, `openai_gpt53` |
| OpenAI | GPT-5.4 nano | `none` | documented | `openai_nano` |
| OpenAI | GPT-5.6 Luna | `medium` | documented | `openai_reasoning` |
| OpenAI | GPT-5.6 Sol | `medium` | documented | `openai_reasoning` |
| OpenAI | GPT-5.6 Terra | `medium` | documented | `openai_reasoning` |
| OpenAI | GPT-6 Astra | `medium` | conditional | `openai_astra_support`, `openai_reasoning` |
| OpenAI | GPT-6 Luna | `medium` | documented | `openai_reasoning`, `openai_latest` |
| OpenAI | GPT-6 Sol | `medium` | documented | `openai_reasoning`, `openai_latest` |
| OpenAI | GPT-6.1 Sol | `medium` | documented | `openai_reasoning`, `openai_latest` |
| OpenAI | GPT-6.1 Terra | `medium` | documented | `openai_latest` |
| Anthropic | Claude Haiku 4.5 | **unknown** | unresolved | `anthropic_effort` |
| Anthropic | Claude Haiku 5.5 | `medium` | documented | `anthropic_effort` |
| Anthropic | Claude Sonnet 4 | **unknown** | unresolved | `anthropic_effort` |
| Anthropic | Claude Sonnet 4.6 | `high` | documented | `anthropic_effort` |
| Anthropic | Claude Opus 4.8 | `high` | documented | `anthropic_effort` |
| Anthropic | Claude Opus 5 | `high` | documented | `anthropic_effort` |
| Anthropic | Claude Opus 5.5 | `medium` | documented | `anthropic_effort` |
| Anthropic | Claude Sonnet 5 | `high` | documented | `anthropic_effort` |
| Anthropic | Claude Sonnet 5.5 | `high` | documented | `anthropic_effort` |
| Anthropic | Claude Opus 4.8 (fast mode) (preview) | `high` | conditional | `anthropic_effort` |
| Anthropic | Claude Fable 5 | `high` | documented | `anthropic_effort` |
| Anthropic | Claude Fable 5.1 | `high` | documented | `anthropic_effort` |
| Anthropic | Claude Fable 5.2 | `high` | documented | `anthropic_effort` |
| Google | Gemini 3.8 Flash | `medium` | documented | `google_thinking` |
| Google | Gemini 4 Argon | `medium` | documented | `google_thinking` |
| Google | Gemini 4 Carbon | `medium` | documented | `google_thinking` |
| Microsoft | MAI-Code-1.1-Flash | **unknown** | unresolved | `github_pricing` |
| xAI | Grok 4.5 | `high` | documented | `xai_reasoning` |
| xAI | Grok 4.6 | `high` | documented | `xai_reasoning` |
| xAI | Grok 4.7 | `high` | documented | `xai_reasoning` |
| Moonshot AI | Kimi K3 | `max` | documented | `moonshot_k3` |

**Specific research caveats:**
- **Claude:** current [Anthropic effort documentation](https://platform.claude.com/docs/en/build-with-claude/effort) explicitly gives **Opus 5.5 and Haiku 5.5 = medium**, **Sonnet 5.5 = high**, most other effort-enabled Claude models = high. That older Haiku 4.5 and Sonnet 4 have prices does **not** establish that their old API supported the same effort field. **Opus 4.8 fast mode** is a distinct Copilot-pricing entry; inherited high must be checked on its actual fast route.
- **OpenAI:** [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning) gives **GPT-5.6 family and GPT-6.1 Sol/6 Sol/6 Luna = medium**. The [GPT-6.1 Terra guide](https://developers.openai.com/api/docs/guides/latest-model) says medium; [GPT-5.4 nano model page](https://developers.openai.com/api/docs/models/gpt-5.4-nano) says **none**, not medium. For **GPT-5.3-Codex**, medium is recommended and injected by OpenCode's GPT-5 provider package, but recommendation alone is not proof of native Copilot default. **GPT-6 Astra** medium is described in an October 23 2026 OpenAI Support Community answer, with route verification required.
- **Google:** [Google Cloud Thinking documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking) records **Gemini 3.8 Flash, Gemini 4 Argon and Gemini 4 Carbon = medium**; Gemini auto/dynamic thinking depth does not mean that the selected numeric thinking_level is observed on every request.
- **xAI:** [xAI reasoning docs](https://docs.x.ai/developers/model-capabilities/text/reasoning) list Grok 4.5, 4.6 and 4.7 default **high**. [Moonshot's Kimi K3 repository](https://github.com/MoonshotAI/Kimi-K3) states API default **max**. **Microsoft MAI-Code-1.1-Flash** lacks a reliably documented numerical default in the researched public material: keep unresolved until source capability/config evidence establishes it.
- This table is **not a snapshot of the owner's installed OpenCode models** and is not proof of what every already-finished historical request executed. The implementer must compare the actual source catalog, additional models/aliases and available provider routes against the static inventory rather than treating this list as an exhaustive set of OpenCode installations.

## Tests and acceptance

1. **Exact examples:** case pairs prove tooltip `default (medium)` for Opus 5.5, Haiku 5.5, GPT-6.1 Sol and Gemini 4 Carbon; `default (high)` for Sonnet 5.5 / Grok 4.7; `default (max)` for Kimi K3; `default (none)` for GPT-5.4 nano when route supports it; an unknown provider returns `default (unknown)`. Explicit selected `medium` stays unchanged. Source override `default + model.settings.reasoningEffort=low` must display **`default (low)`**, beating the static vendor default.
2. **Rendered vs tooltip distinction:** for every modified route (full Watch, PiP, Sessions list/detail, Comparisons, Stats podium), assert **visible text unchanged** and **hover/focus/touch help updated**. Use real shipped DOM including PiP, keyboard and accessible help; check both Classic and Web dark/light, narrow/large views, retained help and mixed subagents. No duplicated suffix.
3. **Request attribution:** two models and two efforts in one prompt, one explicit and one default, replayed/clone tool calls, subagent, compaction without request, missing selected effort, conflicting request evidence. Only legitimate *selected default* changes help; never borrow another model's, prior turn's or another provider's value.
4. **Native config precedence:** supported OpenCode selected `providerID/modelID` plus same-directory effective model setting wins over vendor fallback; `#default` uses no variant; explicit `#high` overrides; provider/model settings and native request metadata are honored. A stale/missing config, relocated project, provider mismatch or known different Copilot adapter must **not** inherit a wrong historical effort. Include a first-run after Cost Guard restart with safe read-only installed source evidence when available.
5. **All 31 baseline models:** validate the static research attachment against the dated GitHub roster; include all six publishers, verify source URL provenance and mark unknowns honestly. No assumption that the GitHub pricing `Default` tier is a reasoning level. Newly added/unpriced OpenCode models must continue to work via source-first resolution or truthful unknown. Version/algorithm cache migration must rebuild affected **tooltip text**, not alter historical CCost/summaries.
6. **Performance/security:** no new paid model calls, no per-hover HTTP, no repeated global model scans, no raw credential/config dumping, no tool invocation changes, no unbounded log/tooltip payload or browser storage. Reuse shared, bounded source observations and versioned static fallback. Show a source/provenance note only in the appropriate existing help when materially necessary; **don't change the user's requested concise `default (x)` format**.

**Likely owners:** `src/analysis/effort.py::EffortSelection/interpret_effort/prompt_effort`; `src/reports/{prompt_rows,prompt_costs,matched_runs}.py`; `src/analysis/comparisons.py::effort_model_parts`; `src/application/{prompt_costs,model_help,comparisons,ai_stats,session_catalog}.py`; `src/application/live_projection.py`; `src/web/assets/{watch,mini,session,sessions,comparisons,ai-stats}.js`, shared `ContextHelp` and bounded display DTOs. Tests `development/tests/test_prompt_cost_detail.py`, `test_recorded_model_help.py`, effort/cost attribution, browser help/PiP matrix, Session catalog/detail, Comparisons and AI Stats podium; docs `docs/{web-beta,web-mini-watch}.md`, `development/architecture/modules/{analysis,web,web-help}.md`, relevant journaling. Keep unrelated development/backlog states unchanged.

**Non-goals:** modifying visible effort, changing any user's actual OpenCode effort selection, guessing defaults from benchmark/pricing tiers, retroactively asserting a mutable current value as old executed proof, weakening FR000692's model identity/cost verification, adding user-facing settings or updating the SDK, adding a network scraper/price refresh for effort.

**Done means:** all actual **model-effort tooltips** preserve the word `default` when selected and append the best correctly resolved concrete value in parentheses, e.g. **`default (medium)`**, using request/active OpenCode configuration before the researched static fallback, across all UI surfaces, with truly unresolved cases marked honestly — while visible values, cost, history and model choice remain unchanged.
