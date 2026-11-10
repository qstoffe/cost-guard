# FR 000664 completion

Implemented in v81.14, 2026-11-10.

- All six sort affordances retain canonical server-owned global ordering, stable
  ID ties and unknown-last semantics. Metric ordering waits for complete valid
  scalar evidence; pinned older pages are not blocked by new unrelated roots.
- Pending sorting and uncached paging use the shared determinate progress visual,
  actual counts, operation-specific Cancel help and visible bounded Retry/failure.
  Warm responses apply without a loading layout swap.
- Cancel restores the last applied sort/page/epoch, retained DOM, URL and focus,
  retiring local HTTP intent without cancelling shared source/cache work. Late
  replies cannot replace that view or renew failed expensive-sort demand.
- Sanitized cache hit/miss, attempt/retry and generation evidence supports honest
  diagnostics. No inference, global backend cancellation or transcript logging.

## Verification and limitations

- Full: all 181 files passed in 132.7 seconds; final narrow late-failure demand
  refinement additionally passed focused VM regressions. See exact ordering below.
- Catalog/detail focused suite: 40 tests passed. Synthetic 3,217-root coverage
  verifies every sort/direction, scalar reuse and exact 17-row last page.
- Real hidden browser: scoped catalog/detail/table parity passed 156 layout
  observations with zero runtime exceptions. Navigation acceptance covers the
  three available themes, four widths and two zooms (24 combinations), keyboard,
  touch, cancellation/retry, warm paths, last page and Back/Forward.
- Package validator passed with seven existing advisory warnings. No ZIP built.
- Read-only real V2 observations covered 3,090 roots and source-stage counters,
  preserved the shared OpenCode service and started no inference. This bounded
  observation did not establish complete real-catalog metric ordering; complete
  ordering and warm-reuse proof use deterministic large synthetic fixtures.

Decision Delegate authorized excluding an obsolete unrelated Token Mix prelude
from the scoped browser entrypoint and repairing the existing detail outage test
to current quiet-retention semantics. The original broad run remains FAIL; it is
not reported as passed. No product acceptance omission or hold was authorized.

[Journal: measurements, failed attempts, scoped decisions and final-tree check
ordering](../../../journal/web/sessions-navigation.md). Affected Web architecture,
code map, user guide, README/version history and maintenance progress are updated.
