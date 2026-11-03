# FR 000563 — delivery with a scoped verification exception

2026-11-03; Windows/Python 3.14; **v80.143**. Product baseline
`f737a3f44f8d61fcf433062e7b89aa946fb23bf9` (v80.142); tested implementation
`de6a645`. Later changes merge unrelated backlog authoring and update only
probe/development reporting. The PR/squash commit identifies the delivered tree.

## Delivered repair and evidence

- Date-only V2 batches overlap at most four independent tree reads/futures,
  rather than serializing every source wait. All eligible roots remain; shared
  normalization is serialized, workers join, full before/after revision checks
  and changed-tree-only bounded retries are unchanged. Daily/Watch, accounts,
  transport cancellation, the Web 120s/8 MiB limits and attribution stay intact.
- Safe cache/read/catalog/analysis stages expose actual work, distinguish
  unverified tree reads from a finished report, and retain last progress on
  timeout. The browser gives CLI guidance without substituting empty results.
- The 872-root production-report/V2 fixture is RED on the old serial read owner
  (cannot reach four gated reads), GREEN on the repair. The independent exact
  result case passes before/after: 872 prompts/requests/revisions and 12.20800
  canonical CCost credits. A **synthetic** 140ms/root model exceeds 120s serially
  (122.08s before catalog costs); four lanes model 30.52s plus brackets. It is
  not measured HTTP time. Early fixture setup mistakes were corrected before
  the final one-failure/zero-error causal RED result.
- Actual loopback HTTP tests retain stable neighbors while retrying only a
  changed tree; serial/parallel DST-range, child, archive and partial-price/token
  projections agree. Production process tests reach held V2 HTTP reads before
  cancellation/deadline, retain the first failure/progress and reap workers.
  Existing Daily batching, real header/body read cancellation, idle account
  reaping and primary-plus-cleanup failure tests remain green.

## Commands and actual results

All commands ran in this worker's isolated clone. `..` denotes its own scratch
evidence; no source payloads/private prompts are exported. No inference occurred.

```text
py -3 -m unittest development.tests.test_historical_reports -v
py -3 -m unittest development.tests.test_historical_reports development.tests.test_source_history_loading development.tests.test_web_daily_lifecycle development.tests.test_web_shutdown -q
py -3 development/tools/run_tests.py --suite full --json-report ..\final-full.json
py -3 development/tools/validate_package.py --working-tree
py -3 -u development/tests/integration/probe_web_live.py --watch-cards --daily --detail --reports --report-timings
```

The pre-edit final causal run had two tests: correctness PASS, overlap FAIL,
zero errors, 33.913s. Candidate focused matrix initially 17 tests OK; expanded
historical tests 8 OK in 30.186s, with the additional partial/DST parity test
included in final Full. Full: **136 file/case groups, 1,608 passed, zero
failures/errors, one macOS-only zsh/PTY skip**, 85.7s. Validation: zero failures,
11 passes, six existing advisory prose/design-budget warnings; hard caps unchanged.
After removing the experimental load flag, the historical small-case, shutdown
and Web-runtime matrix passed **30 tests in 12.841s**; final validation again
reported zero failures. Product source is unchanged from the Full/live-tested commit.

| Real campaign | Outcome / historical-date seconds | Other retained evidence |
| --- | --- | --- |
| Pre-repair baseline, broad read-only path | PASS / 101.811s | 880 roots; 914 session reads; hydration 75.600s, six catalogs 11.688s, analysis 0.507s; Daily 45.416s; max HTTP 0.8007s; close 0.1421s; zero residual owned resources |
| First candidate, concurrent editing/source churn | **FAILED revision guard**, 46.471s | Hydration 36.232s; final source stage `revision_changed`; not a timeout or accepted successful report; close 0.1357s, zero residual owned resources |
| Final ordinary path, no concurrent editing | PASS / **30.448s** | 880 roots; 912 session reads; hydration 21.242s; Daily 3.594s; Normal/All-models/Sessions 5.903/2.468/2.346s; max HTTP 0.2347s; close 0.0934s; zero residual owned resources |

Final ordinary integration also passed cards/detail, two authenticated SSE
sequence checks, continuing Live with the same owner/run origin, and actual deep
Token Mix cancellation. Nested timings are not additive. Warm-cache/load differences
prevent a universal speedup claim; the gated fixture establishes the removed
serialization mechanism. The original FR 000555 868/872 timeout remains FAILED;
no old per-operation trace proves precisely which request exhausted that budget.
The new 880-root campaign establishes a relevant source-wait mechanism and repair,
not retroactive proof of every detail of that earlier failure.

## Explicit exception, failed campaign and remaining uncertainty

The experimental command above plus `--competing` on implementation `de6a645`
used a continuous same-interpreter CPU/JSON thread and exceeded the **shell's
180s deadline**, leaving an empty log. This is **not** a measured product
`report_timeout` or PASS. Historical-date completion/HTTP responsiveness under
the intended CPU load are unavailable; whether that invocation's processes exited
or left owned resources is **indeterminate**. Own-session API tool metadata
established only `completed`/`timeout: true`, without a shell ID, retained process
handle or explicit tree-termination result. No broad process inspection or guessed
termination was used. The experimental flag was removed before delivery; it was
not replaced with repeated live runs until green. Synthetic competing cycles
exercise extra SSE/report cancellation, not equivalent CPU-load acceptance.

**Actual decision-maker: Decision Delegate, 2026-11-03, this FR only.** After a
first decision requiring ownership recovery, and the supported recovery's concrete
failure to provide a handle, the delegate explicitly waived the remaining
**ordinary AND reasonable competing-load** real campaign requirement, including
its missing cleanup census, and permitted completion/merge under existing delivery
authority. This superseded the earlier no-exception-yet decision; it is not user
approval. The delegate directed no further live-load campaign or ownership search
for this obstacle. Access/privacy/Git boundaries and truthful reporting remain.

Thus this delivery does **not** establish all requested load acceptance in full,
universal completion within 120s, or leak-free cleanup of the aborted campaign.
Continuously changing roots/slow sources still fail explicitly. No native desktop
or macOS UI proof, shared-service restart, installation, release ZIP/tag or GitHub
Release was performed. The sole Full skip is macOS shell execution unavailable on
Windows, not a failed runtime check. No other acceptance exception was granted.

[Reusable diagnosis, precise limits and decision](../../../journal/web/historical-reports.md).
Affected module/code-map/user docs, README and version history are updated.
The original FR bundle is moved intact; ordinary progress 13 → 14 takes effect
only with this same merged delivery.
