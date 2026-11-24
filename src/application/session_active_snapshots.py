"""One-way, single-use Watch inputs for the active Sessions scalar lane."""

ACTIVE_SNAPSHOT_MAX_AGE_MS = 5_000


class ActiveSnapshotOffers:
    """The Sessions catalog lock owns offers and consumed observation times."""

    def __init__(self):
        self.pending = {}
        self.used = {}

    def clear(self):
        self.pending.clear()
        self.used.clear()

    def replace(self, snapshots, cutoff_ms):
        # Watch replaces rather than appends: absent captures convey no offer.
        self.used = {key: at for key, at in self.used.items() if key in snapshots}
        self.pending = {key: (at, snapshot) for key, (at, snapshot) in snapshots.items()
                        if at > max(cutoff_ms, self.used.get(key, 0))}

    def take(self, root, revision, now_ms):
        offer = self.pending.pop(root.session_id, None)
        if offer is not None:
            at, snapshot = offer
            if (revision is not None and snapshot.source_revision == revision
                    and snapshot.root.session_id == root.session_id
                    and snapshot.root.provenance == root.provenance
                    and 0 <= now_ms - at <= ACTIVE_SNAPSHOT_MAX_AGE_MS):
                self.used[root.session_id] = at
                return at, snapshot
        return now_ms, None

    def has_unchanged_scalar(self, row, proof, revision, now_ms):
        offer = self.pending.get(row.session_id)
        fresh_offer = offer is not None and 0 <= now_ms - offer[0] <= ACTIVE_SNAPSHOT_MAX_AGE_MS
        return (not fresh_offer and row.running and proof.revision == revision
                and (row.prompt_started_ms, row.activity_prompt_id) == proof.identity
                and 0 <= now_ms - proof.observed_ms <= ACTIVE_SNAPSHOT_MAX_AGE_MS)
