# V2 subagent attribution

FR 000600 · 2026-11-06 · implementation based on `984d174`, with unrelated FR-only default `d8bc371` incorporated normally.

## Defect and ownership

The old causal parser accepted only `task` and metadata `sessionId`; Watch independently accepted two metadata spellings but still only `task`. A native V2 `subagent` tool could therefore leave physical child usage in full root-tree CCost without including it in the initiating prompt. The supplied incident's 109-CCost difference is a hypothesis about that missing contribution, not independently verified child pricing.

`src/analysis/child_links.py` now owns candidate interpretation, physical-call coalescing, acquired parentage, invocation windows and nested traversal. Accounting and activity consume those same windows without acquiring or pricing another session. State metadata precedes top-level metadata and exact native output envelopes; malformed structured identity does not fall back to copied text. Only actual assistant tool results qualify. Foreground descendants remain bounded; background descendants may outlive a foreground parent when their launch belongs to it. A subsequent invocation of a reused child starts a new window.

`causal.py` unions normalized invocation identities, not amounts or token fingerprints. Repeated/overlapping tool observations cannot duplicate a child request. Invisible completion notices retain existing prompt-window ownership. Missing parent usage can no longer hide a real linked child or relabel that child's model as the main model. Algorithm 16 invalidates previous derived attribution and the dependent disposable session-cost key; no registry or second accounting path is introduced.

Evidence-qualified execution duration and terminal timestamps use relevant messages/tools, not unrelated child catalog updates. CLI Watch's separate historical metadata-based Duration metric is retained for compatibility; the first Full run caught its accidental change (800ms → 700ms in the legacy fixture), and the repair preserves the existing Watch/report distinction without extending accounting windows.

## Deterministic evidence

`fixtures/subagent_sessions.py` serves sanitized current V2 data through the actual source loader. Before production edits, `test_native_incident_includes_child_once_after_canonical_loading` failed: expected 3 Calls, observed 2. With the fix it has one visible prompt, no compaction, two parent requests and one differently modelled child: unrounded reference Main 122 + Subagent 102 = 224 CCost, I 21 + E 203, 3 Calls and a 25/25/25/25 token mix. Its independently valued full root tree is also 224. Native zero cost remains separate from reference valuation.

`test_child_links.py` and `test_subagent_attribution.py` cover both tool names, both metadata spellings/levels, native envelopes, structured-over-text precedence, invalid identity/time/ancestry, copied user/tool text, latest corrections, physical duplicates, multiple/nested children, background descendants outliving foreground parents, child reuse across prompts, invisible continuations, running/terminal transitions, late source revisions, old cache invalidation and current cache reuse. Canonical report/CLI and full/Mini shared Live export checks retain linked models/efforts, details, Calls, token mix and Credits/USD conversion. A child uses its own price tier; zero, partial and unknown-price observations remain distinct.

Negative evidence is intentional: an out-of-window child request raises full root-tree CCost to 326 while the prompt stays 224; separately priced compaction stays its own row. No residual is allocated to make rows equal. Existing nested-detail fixtures now declare their real session parentage, and the linked-skill fixture places activity inside its declared tool window, without weakening their assertions.

## Real-source evidence and limits

Read-only `probe_web_live.py --watch-cards --prompt-cost --prompt-token-mix --session-cost` completed successfully against V2: raw canonical CLI/Watch cost and category reconciliation, full-session parity (4 observed/priced requests), unchanged persisted reuse (0 revaluations, no cache write), and six known token-mix rows over twelve seconds. One Live owner and two streams advanced; all owned workers closed and shared OpenCode was untouched. The phase summary also recorded two background history cancellation/error observations during shutdown; this is not a claim of exhaustive history coverage.

The selected real prompt had zero linked agents. This host check therefore does not independently reproduce the historical incident or establish its exact 109-CCost child contribution. No original private export, child transcript, credential or workstation-specific source path is committed. No paid inference, visible desktop operation, new product gate or release archive was used. This is a backend attribution change, not new browser-layout proof.
