# FR000525 temporary warning cleanup

Recorded 2026-10-28 from [implementation PR #98](https://github.com/qstoffe/cost-guard/pull/98), verified merged as `ebd3dce5212e8d7aaca1929335a191957678c0e7`. GitHub `merged_at`: **2026-10-28T21:35:22Z**. Immutable global sunset (60 elapsed days): **2026-12-27T21:35:22Z**. The FR-authorized narrow metadata update fixes `MERGED_AT_UTC` to that implementation merge, never to a later update/launch.

After that verified 60-day sunset, deliberately remove:

- `src/presentation/quota_migration.py`: eligibility, fixed merge/deadline, notice text and the user-local first-shown SQLite reader/writer/path (one timestamp row, no identities, credentials or usage).
- `WatchRenderer` notice import/owner, rendering, warning-role use and expiry-driven status redraw wiring in `src/presentation/watch.py`. No special Web notice wiring/assets exist; preserve the general warning style and New Models lifecycle.
- Only the temporary `MigrationNoticeTests` in `development/tests/test_quota_used.py`, plus this note and obsolete notice-specific architecture/release documentation. Keep permanent Used presentation tests and routing.
- The now-unused `CostGuard/quota-used-notice.sqlite3` state may be removed by an explicit later maintenance operation; this delivery never deletes user state.

Keep permanent Used bars/percentages/native and dollar fractions, Unlimited distinctions and Remaining pace unchanged. The expiration check hides text automatically; it does not delete code or schedule cleanup.

The personal window starts only after a successful interactive CLI Watch frame, not construction, initialization, a redirected/hidden process, Normal, Diagnostics or Web engine acquisition. Existing local state survives restart/update and remembers expiry. Corrupt/unwritable state or clock rollback fails closed for that process; the application never blocks or changes account/source status. If persistence fails after the first visible frame, that process suppresses subsequent notices; repeated launches with permanently unwritable storage can each show one frame. Genuine local-state loss can restart the personal window only before the immutable global sunset. No implementation can remember deleted local state without storing additional history elsewhere; no such ledger is added.
