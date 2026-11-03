# FR 000555 — completion evidence

Completed 2026-11-03 on Windows/Python 3.14; product **v80.136**.
Baseline: `8c96f5c9f7e41ed7dd205e1471294d13780df776` (v80.135).
Final tested implementation: `6a0631d7eccd5cf77b6f26911045034b641888cd`,
including implementation commit `87ae8dcf63101968955d80364710b3c5cf00eb4c`.
The subsequent completion commit changes only documentation/backlog state; the PR
and squash commit identify the final delivered tree.

## Supported causes and repairs

1. **Daily source-work amplification:** Web history forced one root per slice,
   repeatedly fetching full V2 catalogs instead of sharing authoritative brackets
   through the existing bounded four-root acquisition. A real baseline probe
   spent 71.432s in its first history plan and commonly 1–2s per catalog operation.
   The 64-root causal fixture executes actual V2 snapshots/revision checks:
   baseline requires 64 catalogs, or 128s when charged the observed two-second
   work cost; the repaired owner requires 16/32s with all 64 requests/prompts.
   A separate actual-HTTP gate on the redundant second catalog blocks baseline
   Daily publication, but the candidate publishes all four requests/prompts
   without that request. Both baseline-owner tests were RED, both final tests GREEN.
   The 128s is a controlled work model, **not** a claimed real-source timeout.
2. **Uncancellable owned source reads:** stop flags preceded executor joins but
   could not interrupt in-flight header/body reads or a continued tree capture.
   Baseline real closes spent 4.968/6.030s in card-pool joins. The production-host
   regression holds an actual V2 HTTP response: pre-fix close misses the two-second
   assertion until release; post-fix header and detached HTTP/1.0 body cases close
   within it, including history/cards/detail, reports and one/two subscribers.
   Cross-thread socket shutdown/close alone also stayed RED on this Windows
   runtime. Owner cancellation now reaches the buffered transport's raw readiness
   wait before joins, retaining the original read timeout and response ownership.
3. **Idle quota-worker cleanup:** the improved census found workers still in their
   100ms queue wait after host close. Its focused regression was RED before the
   repair and GREEN afterward. Account close now reaps idle workers with one
   shared 200ms budget, not a per-provider multiplied wait. Existing bounded
   daemon behavior for already-busy external-provider HTTP remains unchanged.
4. **Failure-reporting ownership:** probe cleanup could replace its primary error.
   The probe now retains both original exception objects, separate sanitized
   phases/classifications, pending work and before/after resource observations.
   A genuinely blocked authenticated HTTP request is tested separately as a real
   timeout; failed Daily remains unavailable/None, never empty success.

Daily/native-period attribution, retained freshness, revision proofs, one Live
owner, SSE instance/sequence checks and security remain covered. No production
timeout increase, shared-service operation, extra retry or daemon executor escape
was introduced. The Daily 120s, authenticated probe HTTP 3s and host join 10s bounds
are unchanged. [Reusable investigation](../../../journal/web/live-lifecycle.md).

## Commands and final results

Commands below run from the isolated repository clone. `..` outputs were owned
scratch evidence, never packaged source. No provider inference/model call occurs.

```text
py -3 -m unittest development.tests.test_web_shutdown.WebShutdownTests.test_stop_interrupts_pending_history_and_card_http_reads_before_join
py -3 -m unittest development.tests.test_web_shutdown.WebShutdownTests.test_close_joins_owned_idle_account_workers_before_returning
py -3 -u ..\baseline_daily_red.py
py -3 -m unittest development.tests.test_web_shutdown development.tests.test_web_daily_lifecycle development.tests.test_web_repeatability development.tests.test_account_acquisition -q
py -3 development/tests/integration/probe_web_repeat.py --cycles 10
py -3 development/tests/integration/probe_web_repeat.py --cycles 10 --competing
py -3 development/tools/run_tests.py --suite full --json-report ..\final-full.json
py -3 development/tools/validate_package.py --working-tree
py -3 development/tools/run_tests.py --profile native-web --json-report ..\final-native.json
py -3 -u development/tests/integration/probe_web_live.py --watch-cards --daily --detail
py -3 -u development/tests/integration/probe_web_live.py --watch-cards --daily --detail --reports
py -3 -u development/tests/integration/probe_web_live.py --watch-cards --daily --detail --models
```

The first two named tests established pre-edit shutdown/idle-worker RED outcomes.
The temporary baseline runner extracted only `_account_history` via AST from the
exact baseline Git object and ran the two new Daily fixtures against that owner,
without resetting source; **2 expected assertion failures, 0 unittest errors**,
2.516s. Focused candidate matrix: **31 tests OK, 11.079s**. The final Full run
also includes the tightened probe checks and all these regression files.

| Final verification | Actual outcome |
| --- | --- |
| Full, overlapped with the broad real report run | 130 files; 1,575 passed, 0 failures/errors, 1 skip; 74.3s |
| Windows native-web profile | 28/28 tests, 12 file/case groups, no skips; 15.3s |
| Working-tree validation | 0 failures, 11 passes, 6 advisory prose/design-budget warnings; hard caps unchanged; Python 3.11 syntax compatibility passed |
| Ten serial deterministic end-to-end cycles | 10/10 PASS, 4.864s; Daily 0.4211–0.4392s, close 0.0516–0.0623s, max HTTP 0.0206s |
| Ten competing deterministic cycles | 10/10 PASS, 9.308s; Daily 0.4220–0.4552s, close 0.0494–0.0600s, max HTTP 0.0269s |

Every cycle reconciles six real synthetic requests/prompts/costs through production
owners and authenticated HTTP/SSE, with zero residual owned threads/processes.
Competing cycles add CPU/JSON work, two subscribers and a pending real report
process/cancellation. The focused matrix additionally covers failed Daily, actual
HTTP timeout, blocked source reads, active detail/report stop and repeated close.
These explicit finite campaigns are not twenty new recurring CI runs.

### Real read-only V2 integration on the final implementation

| Run | Daily seconds | Host close seconds | Max authenticated HTTP seconds | Result |
| --- | ---: | ---: | ---: | --- |
| Full serial 1 | 14.176 | 0.3012 | 0.0591 | PASS |
| Full serial 2 | 12.291 | 0.1757 | 0.1161 | PASS |
| Full serial 3 | 7.001 | 0.1364 | 0.1134 | PASS |
| Full path plus Normal/All-models reports | 6.432 | 0.1009 | 0.5337 | PASS |

The three serial full `--watch-cards --daily --detail` runs were consecutive, with
eligible actual history, coherent cost reconciliation, truthful incomplete prompt
coverage, cards/detail and actual two-stream IDs/sequence checks. Elapsed times
were 22.9903/28.0049/19.1046s. The representative report run took 29.667s; Normal
completed in 9.575s and All-models in 4.930s sequentially **beside Live**, with
continued Daily publication and the same Live owner/run origin. Each run ended
with zero owned threads/processes, no pending observations or cleanup failures.
Phase evidence includes publication, HTTP and every owned shutdown stage.

## Failures retained, decisions and limits

- Baseline serial and contended real controls both passed; warm cache/eligible
  scope and repeated full-catalog work explain why serial reruns can fit the old
  margins without removing the demonstrated mechanisms. Historical summaries
  cannot identify the exact request behind every old incident; that is not claimed.
- Initial fixture setup mistakes (context-manager argument/session de-duplication,
  already-drained history future, fallback progress mistaken for running work)
  were corrected before the causal results. The ineffective socket-shutdown-only
  repair was rejected, not accepted from a lucky real rerun.
- Three earlier candidate real passes left 3/3/1 idle quota threads. Those runs
  were rejected as leak-free acceptance; they prompted the idle-worker repair and
  stronger final probe census. Earlier 10+10 cycles were repeated on final source.
- **The broad `--reports` run FAILED overall**, despite successful Daily at
  17.856s, coherent cards/detail/SSE and completed Normal/All-models/Sessions
  reports (51.479/8.137/5.976s). Its fixed historical-date report reached the
  existing 120s job limit at history 868/872 roots. Deep-history cancellation was
  therefore **not reached in that run**. Max HTTP was 0.5131s; failure cleanup
  still closed the host in 0.0884s with zero owned resources and no cleanup error
  (total 239.3455s). The primary failure and source-read pending state survived.
  A complete cause for that date-report slowdown, or proof it predates this
  change, is **not established**; it is not relabeled PASS or claimed repaired.
- **Scoped Decision Delegate decision, 2026-11-03:** after independent inspection,
  the existing `--models` alternative is representative competing report work
  under FR §3.4, not a deviation/owner waiver. The bounded whole-run success above
  supplies that required integration instead of rerunning the failed broad date
  campaign. Synthetic failure/stop tests separately prove pending report cleanup.
- Full's sole skip was macOS `test_command_activity_and_exit_codes_without_native_or_browser_work`:
  zsh/PTY unavailable on Windows; native macOS CI owns shell execution. Physical
  desktop, tray clicks, accessibility and macOS-native behavior were not tested
  locally. No visible desktop was operated, shared OpenCode stopped/reconfigured,
  session/history/credential edited, release ZIP/tag or GitHub Release created.
- No universal guarantee against arbitrary provider outages is claimed. Busy
  provider HTTP retains its prior bounded contract; actual source/API faults stay
  visible. Headless Windows ownership evidence is not native macOS/UI proof.

Affected ownership docs, bounded probe runbook, release history and README were
updated. The original FR bytes were preserved; ordinary progress advances from
6 to 7 only with this same merged delivery. No acceptance exception was granted.
