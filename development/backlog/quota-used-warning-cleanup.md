# FR000525 temporary warning cleanup

Recorded 2026-10-28. Implementation merge UTC and exact global sunset: pending the actual implementation PR merge; the FR-authorized post-merge metadata commit must fill both before delivery is claimed. Until then `MERGED_AT_UTC = None` disables the warning.

After that verified 60-day sunset, deliberately remove:

- `src/presentation/quota_migration.py`: eligibility, fixed merge/deadline, notice text and the user-local first-shown SQLite reader/writer/path (one timestamp row, no identities, credentials or usage).
- `WatchRenderer` notice import/owner, rendering, warning-role use and expiry-driven status redraw wiring in `src/presentation/watch.py`. No special Web notice wiring/assets exist; preserve the general warning style and New Models lifecycle.
- Only the temporary `MigrationNoticeTests` in `development/tests/test_quota_used.py`, plus this note and obsolete notice-specific architecture/release documentation. Keep permanent Used presentation tests and routing.
- The now-unused `CostGuard/quota-used-notice.sqlite3` state may be removed by an explicit later maintenance operation; this delivery never deletes user state.

Keep permanent Used bars/percentages/native and dollar fractions, Unlimited distinctions and Remaining pace unchanged. The expiration check hides text automatically; it does not delete code or schedule cleanup.

The personal window starts only after a successful interactive CLI Watch frame, not construction, initialization, a redirected/hidden process, Normal, Diagnostics or Web engine acquisition. Existing local state survives restart/update and remembers expiry. Corrupt/unwritable state or clock rollback fails closed for that process; the application never blocks or changes account/source status. If persistence fails after the first visible frame, that process suppresses subsequent notices; repeated launches with permanently unwritable storage can each show one frame. Genuine local-state loss can restart the personal window only before the immutable global sunset. No implementation can remember deleted local state without storing additional history elsewhere; no such ledger is added.
