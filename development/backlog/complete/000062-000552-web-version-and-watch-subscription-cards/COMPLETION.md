# FR 000552 completion

Implemented in **v80.130**, 2026-11-03.

- The authenticated status supplies the process-loaded canonical CLI product version;
  the persistent Web header displays it after Web Beta without a new polling loop.
- Watch title bands center full identifying account names with theme-aware colors;
  aligned Today/primary tracks and all body values remain left aligned.
- Each quota carries its own canonical native-period CCost and optional native pace.
  Monthly acquisition reuses the supported UTC native-month resolver, existing background
  lane and revision cache. Unsupported boundaries remain unavailable, never last-30-days
  or Today substitutions. Model scope associations do not depend on unique labels.
- Primary reset/Remaining rows stay above a divider; only real secondaries create a
  lower section. Today loses only its visible estimate suffix; canonical provenance,
  daily scope, unknown/unlimited and empty/reset/stale semantics remain intact.
- History coverage is independent per scope. Pending month/weekly history no longer
  erases a separately acquired Today. Credits/USD switches CCost, not native Remaining.

## Verification

- `py -3 development/tools/run_tests.py --suite full`: **126/126 files passed**, 58.5s.
  Initial causal failures were repaired; older global-history assertions now explicitly
  preserve independent Today plus truthful provider-estimate/ambiguous-account metadata.
- `py -3 development/tools/validate_package.py --working-tree`: **passed**, zero failures
  and four pre-existing design-budget warnings. File caps were preserved; older prose was compacted,
  not dropped or rebaselined. No release archive was generated.
- `probe_watch_summary.cjs` against `serve_watch_summary.py`: **nine cases passed**,
  Classic/Web light/Web dark at 360/1366/1920px. Actual headless Edge screenshots and
  geometry verify title bands, long names, left-aligned body/common tracks, no document
  overflow and no secondary divider for monthly/weekly-only cards. Synthetic pixels,
  not live-provider or physical-desktop acceptance. Integrated DOM/CSS evidence also
  succeeded; integrated screenshot capture was unavailable despite focusing its tab.
- Real V2 read-only Watch probe: first run observed reconciled daily cost and cards but
  **failed** owned shutdown (`web_shutdown_timeout`). A diagnostic rerun **passed**:
  920 requests, 44 initiating prompts (attribution incomplete), one owner/two streams,
  three accounts, preserved origin, one-row card bounds, and complete owned shutdown
  in 3.728s (card close 3.260s), without changing production deadlines. No post-stop
  history batch was observed. The original intermittent failure remains unexplained.
- A separate service sampled one real root/30 requests and three available accounts.
  Copilot native Monthly resolved correctly and exported canonical pace; actual Claude
  five-hour/weekly and OpenAI weekly scopes remained distinct. The sample did **not**
  establish complete monthly history, so active-period costs stayed unavailable.

## Explicit verification limitation and decision

Decision Delegate authorized the narrower task-focused provider/source verification
plus deterministic all-month acquisition/reuse tests instead of requiring complete
real-installation month valuation. Full real-month cost completeness remains unperformed.
The Delegate required shutdown investigation, **not** a shutdown waiver; the subsequent
diagnostic run met the unchanged shutdown checks. Successful rerun does not explain the
first failure or prove every future lifecycle. No user approval or broad live PASS is
claimed. No model inference, credential change or shared OpenCode shutdown occurred.

Current architecture owners, Web guide, code map, version/history/README and
`development/journal/account-periods.md` are updated. Ordinary progress uses the queue's
proposed v2 state and counts only when merged. The original specification moved intact.
