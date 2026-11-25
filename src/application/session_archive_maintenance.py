"""Advance catalog archive recovery and bounded effort backfill on its writer lane."""
from functools import partial
from itertools import islice

EFFORT_BACKFILL_BATCH = 4


def advance_archive_maintenance(catalog):
    archive = catalog.archive
    if archive is None:
        return
    with catalog.lock:
        now = catalog.clock()
        if catalog.archive_stopping.is_set() or catalog.archive_job is not None:
            return
        if archive.loaded:
            if not archive.effort_backfill or now < catalog.effort_backfill_due:
                return
            candidates = tuple((key, archive.authorities[key])
                               for key in islice(archive.effort_backfill, EFFORT_BACKFILL_BATCH))
            catalog.archive_job = job = catalog.archive_pool.submit(archive.upgrade_efforts, candidates)
            complete = _effort_backfill_complete
        else:
            if now < catalog.archive_retry_at:
                return
            catalog.archive_attempts += 1
            catalog.archive_job = job = catalog.archive_pool.submit(archive.load)
            complete = _archive_complete
    # A completed future calls back immediately; never attach under the catalog lock.
    job.add_done_callback(partial(complete, catalog))


def _archive_complete(catalog, job):
    if job.cancelled():
        return
    saved = job.result()
    with catalog.lock:
        catalog.archive_job = None
        if catalog.archive_stopping.is_set():
            return
        if saved is None:
            backoff = min(60, 5 * 2 ** min(4, catalog.archive_attempts - 1))
            catalog.archive_retry_at = catalog.clock() + backoff
        else:
            catalog.archive.loaded = True
            catalog.archive.partition = catalog.archive_target
            catalog.archive.rows, catalog.archive.authorities = saved
            catalog.archive_revision += 1
            catalog._restore_archived_rows()
        catalog._archive_publication()


def _effort_backfill_complete(catalog, job):
    if job.cancelled():
        return
    results = job.result()
    with catalog.lock:
        catalog.archive_job = None
        if catalog.archive_stopping.is_set():
            return
        archive = catalog.archive
        # Back off after storage contention; do not load the same failed batch every turn.
        catalog.effort_backfill_due = catalog.clock() + (1 if results else 30)
        for key, (authority, upgraded, needs_source) in results.items():
            if archive.authorities.get(key) != authority:
                continue
            archive.effort_backfill.discard(key)
            if upgraded is not None:
                prior = archive.rows[key]
                archive.rows[key] = upgraded
                if catalog.rows.get(key) is prior:
                    catalog.rows[key] = upgraded
            if needs_source:
                archive.effort_refresh.add(key)
                if key in catalog.roots and catalog._archive_needs_capture(key):
                    catalog.history_pending[key] = catalog.activity.get(key)
                    catalog._schedule_history(key)
