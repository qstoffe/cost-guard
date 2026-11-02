# FR 000545 — Make Watch cards compact, remove session totals and restore CLI visual roles

## Owner goal, final decisions and scope

Refine the delivered Web Beta Watch page so it stays compact and readable during live use: one prompt per card, one-line table rows, a flexible ellipsized Prompt column, distinct running/activity/warning colors, and no full-session totals or repeatedly flashing total-loading text.

The owner approved this follow-up on 2026-11-02 after inspecting the first Watch overhaul. Permanent identity: **000545**. Ready priority: **000110**. Implement on top of delivered **FR000542** and **FR000543**. Related **FR000546** separately fixes Web/CLI terminal-lifecycle correctness and has higher priority; **FR000544** adds Mini Watch afterward.

The final owner decisions explicitly supersede the earlier five-row cards/full-session totals and the intermediate ideas of three historical rows, history-only totals on separate lines, and pausing history while collapsed:

| Area | Final behavior |
| --- | --- |
| Active card | One focal prompt row only. |
| Earlier Prompts | Five most recent eligible distinct sessions; one latest actual prompt row in each card. |
| Session totals | No Session Total CCost or Session Total Duration on Watch, in either section. |
| Collapsed history | Continue maintaining it through the shared bounded live pipeline. |
| Table rows | One line; only Prompt may truncate, using ellipsis. |

Do not implement any of the superseded alternatives or rewrite the completed FRs. This is Watch page refinement; preserve FR000543's account cards, Total Today accounting and context-warning semantics. Sessions-page changes are deferred.

## 1. Card membership, row count and history frame

Keep one active card per genuinely running prompt, including separate concurrent prompts belonging to the same session. Display **only that focal prompt** in its table, followed by its existing relevant tool/skill/running activity and conditional warning footer. During the existing terminal highlight/grace period, retain that same focal row with its actual terminal state; do not add older context rows.

Keep active cards ordered by oldest start first. Preserve the existing terminal grace (default 30 seconds), canonical lifecycle and transition to history. FR000546 owns the reported lifecycle defect; this UI cleanup must not replace canonical terminal detection with a timer.

Earlier Prompts continues to select the **five most recent eligible distinct sessions**, ordered newest first by the latest actual user prompt's start time. Show exactly **one latest actual prompt** from each selected session. Exclude sessions with active/grace cards before applying the five-session limit. Do not change this into the five latest prompts globally, restrict it to activity observed since Watch started, or use compaction/synthetic events as new user-prompt rows.

The expanded Earlier Prompts region gets a **subtle but clearly visible enclosing border/frame** in the current theme, with appropriate padding and optionally modest corner rounding. This deliberately refines the previous completely unframed historical container so users can distinguish history from active work. Individual cards stay visually simple; active cards remain unframed.

Preserve the disclosure's default collapsed state, bounded viewport-aware height and internal vertical scroll. Active cards still grow/shrink with their count and use the page's vertical scroll. The old rough height estimate based on 3.5 five-row cards is obsolete; choose an appropriate cap for these shorter cards, retaining the goal that expanding history at 1920×1080 does not unnecessarily consume all visible active content. Do not add filters or pagination.

## 2. Exact column content and compact one-line layout

Use this column order and content for both sections:

| Header | Active card | Earlier Prompts card |
| --- | --- | --- |
| **Started** | `Prompt N HH:mm` | `Prompt N YYYY-MM-DD HH:mm` |
| **Prompt** | Actual prompt preview text only | Actual prompt preview text only |
| **Model** | Existing canonical model | Existing canonical model |
| **Effort** | Existing canonical effort | Existing canonical effort |
| **CCost** | Current prompt cost in the effective unit | Prompt cost in the effective unit |
| **Model Calls** | Canonical call count | Canonical call count |
| **Duration** | Canonical prompt duration | Canonical prompt duration |
| **Δ Ctx** | Existing Watch delta-context value | Existing Watch delta-context value |
| **Context** | Existing next-incoming-context value | Existing next-incoming-context value |

For example, Started is **Prompt 3 19:53** while active and **Prompt 3 2026-11-02 19:53** in history. Use the real session prompt sequence number, not the current row index. Use the canonical start timestamp and existing configured-timezone formatting; do not show the latest activity time instead. Both sections use the Started header despite the deliberately different date detail.

All headers and cell values stay on **one line**. Size non-Prompt columns compactly to their complete header/value content without losing information. Prompt alone takes the remaining available width, with a sensible implementation-selected minimum width. It has no arbitrary maximum width such as the current 44ch cap, but long content must not force the table wider instead of truncating.

Whenever the preview exceeds its allocated width, show a visible ellipsis (`...` or the standard rendered ellipsis). This holds at its minimum and at very wide layouts, including long words, URLs and previews containing line breaks. Do not wrap, expand a row to several lines or truncate numeric/date/model values to make room. When the complete non-Prompt columns plus the Prompt minimum cannot fit, allow the table's existing horizontal overflow rather than wrapping or shrinking text unreadably. Do not introduce an internal vertical table scrollbar.

The Prompt cell must not prepend the prompt number or play icon, or append generated lifecycle wording such as **Completed**, **Running** or **provisional**. The sequence number is now in Started. Keep actual user-authored preview content intact; do not strip the word “completed” when it was literally in the user's prompt. Preserve meaningful accessible state information and a proportionate way to inspect the full preview, such as the normal title/accessibility affordance or existing session navigation.

The current renderer can append an “Additional model contribution” detail span. Preserve any necessary canonical attribution information through an appropriate existing field/accessible detail, without violating the one-line row or preview-only Prompt cell. This is not permission to silently drop real cost or model attribution.

## 3. Remove Watch session totals and their dedicated acquisition

Remove **Session Total CCost** and **Session Total Duration** from the header of both active and historical cards. The header contains the existing linked session title; these aggregate values can be designed on the Sessions page later. Remove the accompanying visible **Provisional** label and the totals' recurring Loading placeholders.

Remove the dedicated Watch-card full-session total calculation/publication phase and its now-unused DTO/state. Merely hiding labels while still computing those unwanted aggregates does not meet the owner's performance goal. Keep ordinary asynchronous/bounded acquisition; do not move slow source analysis onto the live/UI loop.

One displayed row does not mean only one raw source record may be read. Preserve the predecessor anchors, context epochs, compaction evidence, causal children and other canonical data required to compute that row's CCost, duration and context correctly. Also preserve the independent full-day/account acquisition required by FR000543 and any totals used by other routes.

Use **CCost** as one word everywhere in changed Watch/Mini labels and documentation, never **C Cost** or **C-Cost**. Existing effective Credits/USD formatting remains authoritative; this terminology correction does not change valuation.

The final design keeps Earlier Prompts updated **even while collapsed**. Do not add expansion-triggered loading, stop/start history acquisition, or reintroduce the abandoned staged full-session-total loading flow. Reuse revision-aware scheduling/caches and bounded workers; “kept updated” does not mean scanning every complete history on every one-second presentation tick.

For all remaining Watch metrics, once a valid value exists, retain it through an ordinary refresh and replace it when a new coherent value arrives. Do not swap it repeatedly to Loading while recomputing. First acquisition may show a loading state. Genuine source failure, partial data, changed identity/period or invalidated context still needs truthful existing freshness/unavailable handling; retaining yesterday's or another session's value is not acceptable. Do not expose raw Provisional jargon or disguise incomplete data as exact.

## 4. CLI-faithful semantic colors

Separate running, normal activity, context warnings and failures instead of using the warning color for everything.

| Meaning | Required Watch presentation | Inspected CLI role/reference |
| --- | --- | --- |
| Truly running prompt | Yellow prompt row and yellow linked session title | `watchRunningWarning`, Yellow / ANSI foreground 93 |
| Tool and skill activity | Gold/brown normal fragments in summaries and expanded details | `watchToolActivity`, `watchSkillActivity`, ANSI256 136 |
| Long-running tool/background activity | Same gold/brown activity role | CLI activity role |
| Context price warning | Its established gold/orange warning role | `nextIctxWarning`, ANSI256 172 |
| Recent successful terminal prompt | Existing lime/green terminal grace style | `watchRecentCompleted`, ANSI256 118 |
| Failures/cancellations | Existing red terminal style and individually red failed activity fragments | `costQuotaCritical` |
| Historical session title | Neutral table-header foreground; retain heading weight/size and link behavior | Web historical table-heading ink, not cyan accent |

Use the CLI role distinction faithfully in Classic. Use readable corresponding yellow/activity/warning roles in Web light and dark; terminal palette numbers are semantic references, not a guarantee of one universal RGB. The implementation can choose suitable theme tokens and contrast. Do not leave running rows gold/orange or historical titles cyan by inheriting general warning/accent styles.

Only truly running titles remain yellow. When a card becomes terminal, stop presenting its title as running; a neutral header/title is a reasonable consistent choice while its row carries the terminal grace color. Historical titles keep the neutral table-heading color and their existing navigation to the selected session.

Failed/cancelled tool or skill fragments must be independently red within otherwise gold/brown activity. A flattened plain-text summary cannot meet this requirement if it prevents styling the failure count/name separately. Preserve accessible severity text, not color alone.

## 5. Label and preserve current tool/background activity

Keep the existing tool-call and custom-skill totals, five named groups plus “other”, and expandable one-group-per-line details. Do not change canonical counts or restore built-in skills merely to match a visual example.

Each current long-running activity line must explicitly start with **Running:**, for example **Running: shell 41s** or **Running: subagent 55s**. Show actual tool/background/subagent activity when the canonical source supports it, including both lines where appropriate. Do not present bare tool names and durations without saying they are running.

Reuse the CLI's existing activity threshold and formatting logic (currently 10 seconds for the relevant long-running tool indicator). Carry canonical background activity into the card projection where needed; the inspected card DTO omits background fields that ordinary Watch rows already carry. Do not infer a subagent from an arbitrary tool label. Clear live indicators when their work or prompt becomes terminal, subject to correct canonical child/background attribution.

## 6. Preserve context warnings as card footers

The owner saw threshold text inside Prompt cells in an installed version. **FR000543 already specifies and the inspected current code already implements the footer.** Keep this as a regression requirement rather than create a competing warning design:

- Active card: linked title, one-row table, current activity, conditional context-warning footer.
- Historical card: linked title, one-row table, conditional context-warning footer.
- No context-price warning prose/icons/stars/reference numbers or threshold-specific coloring inside Prompt/Context cells.
- Derive the warning from the valid latest/focal continuation and retain FR000543's exact threshold, multiplier and compaction semantics. Reducing context removes/downgrades the warning; an invalidated older warning must not return.
- Keep gold/orange warnings distinct from yellow running rows and red failures. No empty footer is needed without a warning.

Do not alter the global Total Today/account-card work or replace context warnings with lifecycle outcome text. These are separate concerns.

## Inspected baseline and implementation pointers

Inspected main: `389f9881bc4e00e4c0cbd0f6245fe2af86e037c2`.

- `src/web/assets/watch.js::Card` currently renders five-row data, Date / Time, Δ Context, literal Session Total C Cost, loading/provisional totals, and generated Prompt decorations. It already appends `context_warning` as a final separate section.
- `src/web/assets/app.css` currently lets Prompt wrap, caps it at 44ch, uses `--warn` for running rows and general link accent for titles/activity. Existing table horizontal overflow and history vertical cap are useful to retain.
- `src/watch/cards.py::_card` slices preceding rows for active cards and the last five for history. `historical_ids` already owns the five eligible distinct-session policy.
- `src/watch/card_workers.py::_capture` publishes rows and then unconditionally calls `capture_totals`; `src/reports/watch_capture.py::capture_totals` computes a full prompt block. Remove the dedicated totals phase while preserving necessary row/context analysis and bounded workers.
- `src/application/live_projection.py` owns card DTOs and the background-activity gap. `src/application/display.py` already supplies timezone-correct `clock` and `date_time` tokens.
- `config/default-config.jsonc`, `src/presentation/watch_activity.py` and `src/watch/tracker.py` provide CLI semantic color and activity references.

## Acceptance evidence

1. **One row per card:** many previous prompts and concurrent prompts in one session produce one focal row per active card. Terminal grace keeps that same row. History selects five eligible distinct sessions with one latest prompt each, including old pre-Watch sessions; no duplicates or synthetic prompt slots appear.
2. **Compact table:** long multiline prompts, unbroken URLs, large metrics and narrow/wide viewports keep every row/header on one line. Prompt alone flexes and ellipsizes; other columns retain their full values. Horizontal overflow is used only as needed, without internal vertical table scrolling.
3. **Exact content:** Started uses canonical `Prompt N HH:mm` for active and `Prompt N YYYY-MM-DD HH:mm` for history, in the configured timezone. Headers are Started and Δ Ctx/Context. No generated play marker, prompt number or outcome suffix remains in the Prompt cell; real prompt text is preserved.
4. **No Watch totals work:** neither section displays session aggregate cost/duration, Provisional or their Loading placeholders; no dedicated full-session Watch-card totals phase still runs. Canonical row context/valuation, account CCost Today and Total Today remain correct. CCost is consistently joined.
5. **Stable refresh:** known current values remain readable through refreshes, replaced by new results without Loading flashes. Collapsed history stays maintained and expands with current data. Partial/failure/identity/day/context changes remain truthful; worker count and acquisition stay bounded.
6. **Colors and activity:** running rows/titles are yellow; historical titles use neutral heading ink; normal tool/skill/background activity is CLI-like gold/brown; individual failures are red; context warnings retain gold/orange. Verify Classic and Web light/dark plus focus/accessible state. Running prefixes and canonical tool/subagent durations appear and clear correctly.
7. **History distinction and stability:** expanded history has a visible restrained frame and sensible bounded height at 1920×1080 and smaller viewports; active content uses page scroll. Live updates preserve disclosure, focus and scroll instead of recreating the whole page.
8. **Warnings and prior work:** no threshold text/stars enter table cells. Both card types retain conditional warning footers with compaction/reset correctness. FR000543 account layout/daily accounting and FR000546 lifecycle correctness remain intact.

Use proportionate existing card/projection/Web visual tests and update the relevant Web Beta help. Record the actual verification; no new permanent product gate is introduced. This backlog publication does not implement product changes or a Sessions-page redesign.
