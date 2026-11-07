"""Source-neutral bounded history batches with explicit unavailable-root coverage."""
from src.domain.progress import WorkProgress


def load(service, roots):
    ids = tuple(root.session_id for root in roots)
    progress = lambda step, done, total: service.progress(WorkProgress(
        'Loading history batch', 'history', done, total, stage='date-' + step))
    available = getattr(service.source, 'load_session_snapshots_available', None)
    observed = getattr(service.source, 'load_session_snapshots_observed', None)
    batch = getattr(service.source, 'load_session_snapshots', None)
    if getattr(service, 'allow_partial_history', False) and callable(available):
        snapshots = available(ids, progress)
    elif callable(observed):
        snapshots = observed(ids, progress)
    elif callable(batch):
        snapshots = batch(ids)
    else:
        snapshots = {sid: service.source.load_session_snapshot(sid) for sid in ids}
    if not set(snapshots) <= set(ids):
        raise ValueError('foreign_history_snapshot')
    return snapshots


def warnings(unavailable):
    return ((f'Partial history: {len(unavailable)} changing root(s) could not be verified and were omitted; '
             'totals and groups do not cover the full source.',) if unavailable else ())
