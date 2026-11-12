# Recorded provider/model help — FR000687, scoped P2

2026-11-12; implementation baseline `b3e6cb436bd735c556b563cec31fb4f8efb0d293`,
reconciled with documentation-only default `696eaba`. Product v81.33.

## Delivered scope and decisions

The foreground Decision Delegate authorized **P2-only delivery**, not full FR
acceptance. The latest owner privacy boundary excludes other sessions' private
records, including historical HTTP retrieval. P0 historical reproduction is **NOT
RUN**; P1 historical diagnosis/retroactive identity and CCost repair is **not
delivered**; historical cold/warm/restart rechecks are **NOT RUN**. No private
harness, foreign session history, SQLite, transcript or other worker scratch was
used. Existing scoped catalog estimates remain estimates, not recovered execution.

Inference is stopped; all six submitted selectors are frozen. No paid replay,
retry, increased cap, alternate provider or worker-model switch was performed.
The Delegate required the live gap to remain in [Suggestion000676](../backlog/suggestions/000676-controlled-claude-agent-live-cost-proof/SUGGESTION.md)
and the independent historical gap in [Suggestion000691](../backlog/suggestions/000691-authorized-historical-claude-identity-recovery/SUGGESTION.md).
Neither proposal is Ready or implementation authority. Known FR000686/FR000688
do not strictly depend on resolving these gaps; no hold was warranted.

The receiving worker's foreground Delegate additionally examined the native
failure's absent usage. **An empty observed aggregate remains numeric zero and
complete (`0 == 0` observed/priced requests), not known zero consumption.** It
authorized retaining that numerical display as a nonblocking P2 limitation,
provided model help says **Usage unavailable; cost unknown**, does not invent a
request or contribution, and the future proof/display gap is published in 000676.
This is the Delegate's scoped decision, not a fabricated human waiver or PASS.

## Causal presentation fixes and boundaries

- `application/model_help.py` owns provider/recorded-selector copy. It does not
  parse friendly labels, match models, price or acquire. Raw selections lead help;
  **Catalog modelID** and current-catalog/historical-execution qualification are
  separate. Negative catalog lookups do not manufacture a positive catalog label.
- Prompt parts preserve recorded selection in their grouping key, independently
  of effective pricing identity. Main/child roles, effort, agents, distinct prompt
  counts, physical calls, tiers, exact category sums and omission bounds survive.
  Compactions now expose their own entries, not a root-wide provider guess.
- Single-model Model/Calls help is no longer suppressed. Full Running/Earlier,
  Mini prompt cost and session-detail Model/Calls/CCost consume prepared tokens.
  Exact catalog Claude family labels regain `Claude` branding in visible cells.
- Scalar Sessions retain sorted raw contributors (64, 256-character existing
  bounds), including child entries. Prepared help distinguishes incomplete coverage.
  Old resolved scalar summaries without the raw-help marker rebuild lazily;
  pinned summary reuse and source/catalog/pricing contracts remain unchanged.
- Comparisons retain raw selectors **per provider/effective-model/effort group**,
  including concrete and alias selections sharing one price. Legacy compact runs
  lacking that evidence rebuild; no global dependency list substitutes for a
  contributor. Codec admission checks the exact contributor mapping.
- AI Stats model podium help uses selectors from its existing <=32-call sample.
  Ranking, sampling, weighting, response timing and all other metrics are unchanged.
- Failed saved replies without usage retain **recorded selection** independently
  from cost parts, joined by exact session/parent prompt. They establish neither
  executed-model nor contribution proof; no call, usage or cost part is synthesized.
- Audit: shared `model_detail_help`, `cost_detail_help`, `calls_help`, Mini
  `promptDetails`, Sessions list/detail, Comparisons provenance and Stats model
  ContextHelp targets. Publisher/reference catalog rows have no recorded request
  provider and were deliberately left unchanged. No on-hover HTTP, browser pricing,
  native configuration mutation, dependency, question cue or global history clear.

## Native evidence and saved-request reconciliation

Installed OpenCode **2.2.7**; exact owned acceptance location; enabled Claude Agent
native provider; non-secret current official CLI metadata reported first-party
Claude.ai Pro. This metadata alone is not request route proof. Task-local guarded
AISDK-native streaming observed each admitted dispatch and response metadata;
final saved assistant selection retained `claude-agent/<selector>`. Inputs had no
project/files/tools; output cap32, <=60 seconds/call, <=13 minutes overall,
single forwarding, retries/title/auxiliary calls suppressed, exact-owned cancellation
and idle settlement. Configuration was task-local and is disarmed; shared OpenCode
was never stopped or reconfigured. Preflight fakes were segregated from real logs.

**13 selectable; six submissions; five native completions; one native failure;
seven NOT RUN. P3 incomplete, never full-catalog PASS.**

Offline replay used saved **owned** wire payloads, pure production normalization,
the exact-location DesktopModelCatalog and freshly fetched public reference prices.
Observer execution fields were **not injected** into production identities. The
five known-usage requests reconcile to nonzero reference CCost; that is saved-request
replay proof, not historical acquisition, billing or fresh end-to-end UI acceptance.

| Recorded selector (all `claude-agent/`) | Native state | Observer executed model | Production effective reference identity | I/C/W/O | Reference CCost |
| --- | --- | --- | --- | --- | --- |
| `opus` | RUN; replay reconciled | `claude-opus-5-5` | `Claude Opus 5.5` (catalog estimate) | 2/658/1600/3 | 0.81996000 |
| `sonnet` | RUN; replay reconciled | `claude-sonnet-5-5` | `claude-sonnet-5-5` (catalog estimate) | 2/658/1528/3 | 0.39198000 |
| `claude-fable-5-2` | RUN; replay reconciled | `claude-fable-5-2` | recorded concrete ID | 2/658/1687/3 | 1.71376000 |
| `haiku` | RUN; replay reconciled | `claude-haiku-5-5` | `Claude Haiku 5.5` (catalog estimate) | 2/658/2329/3 | 0.029940500 |
| `fable` | RUN; replay reconciled | `claude-fable-5-1` | `Claude Fable 5.1` (catalog estimate) | 2/658/3435/3 | 4.32720000 |
| `claude-haiku-4-5-20251001` | FAIL | same concrete ID in four metadata events | saved selection; no usage invocation | unknown | unknown |
| `claude-sonnet-5` | NOT RUN | unknown | not reconciled | unknown | unknown |
| `claude-opus-5` | NOT RUN | unknown | not reconciled | unknown | unknown |
| `claude-fable-5` | NOT RUN | unknown | not reconciled | unknown | unknown |
| `claude-opus-4-8` | NOT RUN | unknown | not reconciled | unknown | unknown |
| `claude-opus-4-7` | NOT RUN | unknown | not reconciled | unknown | unknown |
| `claude-opus-4-6` | NOT RUN | unknown | not reconciled | unknown | unknown |
| `claude-sonnet-4-6` | NOT RUN | unknown | not reconciled | unknown | unknown |

The failed Haiku4.5 case forwarded once. Native SDK produced four distinct persisted
response identities, then output-cap/provider error with no final usage. This is
not four owner submissions, proven billed usage or an established Cost Guard defect.
Omitted effort persisted as `default`, not provider substitution. Normalization
produced **zero observed requests**, and the actual unchanged aggregate is **0**;
acceptance reference cost is **unknown/null**, not an invented zero consumption.

## Verification record

Focused regression checks cover alias versus concrete under a shared price,
same-label routes, compaction ownership, comparison codec/cold caches, sampled Stats,
single-model help and failed no-usage versus explicitly recorded zero usage. The
first Full run exposed six obsolete friendly-copy assertion groups; those were
repaired against the intentional raw-copy contract, not waived. Browser fixture
repairs also replace obsolete combined Mini cost-column selectors and isolate a
virtual-clock simulation's observation state from subsequent cases.

The raw-model browser probe **passed** in headless Chrome157, through shipped
HTTP/CSP/SSE and an actual Document PiP window. Its 24 matrix groups cover Full
Running/Earlier Model/Calls/CCost and Mini Running/Earlier prompt cost with owned
Sonnet replay, plus synthetic Sessions/detail/Comparisons/AI Stats. Classic/Web
light/Web dark, 1280/360px and 100/150% zoom each pass keyboard focus, pointer hover,
touch, ARIA association and clamped Popover bounds. Additional actual detail checks
cover mixed parent/child routes, independently attributed compaction and failed saved
selection with unknown usage; same-friendly-label Copilot remains a distinct route.
Two synthetic browser restarts each retain the branded scoped-catalog alias and
the unverified alias labels, with raw identity and truthful qualification.

The initial browser failures were probe defects, not waived acceptance: duplicate
synthetic active session keys caused alternating keyed redraws to reset horizontal
scroll; client-only replay injection was overwritten by normal publication; finite
Session detail omitted its normal `prompt_details=True` projection. The controlled
server now publishes consistent replay wires with unique synthetic card keys.
No shipping browser behavior was changed to accommodate the probe.

All browser evidence is hidden/headless Chromium with actual DOM/input/Popover/ARIA;
native replay remains labelled replay and finite report examples synthetic. Physical
desktop, assistive-technology and historical recovery proof are not claimed.

Final Full: **185 files, zero failures**, 154.9s. Working-tree validator: **11 passes,
zero failures, seven existing advisory budgets**. The broader help audit passed in
headless Edge157: **54 layout cases, zero browser errors**, including rich child
cost/Calls groups, omissions, live units, stable totals, keyboard/hover/touch and
dismissal, hostile plain-text titles and other report routes. Its virtual-clock
fixture now restores the controller's publication/epoch as well as observations;
older real-time publications are correctly rejected by production Mini, so restoring
only observation state had invalidated later probe cases. Obsolete header-copy
assertions now match the shipped prompt-reference-cost wording. No acceptance was
waived to obtain these results. Detailed private evidence remains in owned scratch;
only the sanitized results above are published.
