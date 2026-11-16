"""One bounded navigation cohort per lease; facts are historical, not live keys."""
from dataclasses import dataclass, field, replace

from .session_catalog_scope import row_in_window


@dataclass
class Navigation:
    sequence: int
    intent: tuple
    window: object
    roots: dict
    source_epoch: object
    facts: dict = field(default_factory=dict)
    authorities: dict = field(default_factory=dict)
    invalid: bool = False

    def check(self, catalog, window):
        # Revision advancement is deliberately NOT an invalidation. Identity,
        # deletion, calendar and authority changes must never reuse old proof.
        if (window.identity != self.window.identity or catalog.last_observation is None
                or catalog.last_observation.source_epoch != self.source_epoch
                or any(key not in catalog.roots or root.provenance != catalog.roots[key].provenance
                       for key, root in self.roots.items())):
            self.invalid = True
        if self.invalid:
            raise KeyError("catalog_expired")

    def capture(self, catalog, memberships=None, keys=None):
        sort = self.intent[0]
        for key in self.roots if keys is None else keys:
            root = self.roots[key]
            if key in self.facts:
                continue
            row = catalog._rows((key,))[0]
            # Fresh source-qualified lifecycle/start fixes running-first order and
            # period membership independently of mutable scalar revision keys.
            # Candidate/active booleans alone never set row.running.
            if not row.running and (not (sort == 'name' or catalog._key_current(key, sort))
                                    or not catalog._activity_current(key)):
                continue
            if self.window.period == 'all':
                member = True
            elif row.running and row_in_window(row, self.window):
                member = True
            elif memberships is not None and key in memberships:
                member = memberships[key]
            elif (row.activity_latest_ms or row.last_activity_ms) is None or (
                    row.activity_latest_ms or row.last_activity_ms) < self.window.end_ms:
                member = row_in_window(row, self.window)
            else:
                # Latest activity after admission does not prove absence of an
                # earlier in-window prompt. The existing summary read resolves it.
                continue
            at = row.last_activity_ms
            self.facts[key] = (replace(row, title=root.title or "Untitled session",
                                      last_activity_ms=at if type(at) is int and 0 < at <= catalog.clock_ms() else None,
                                      archived=root.archived_at_ms is not None),
                               catalog.revisions[key] if catalog._current(key) else None, member)
            self.authorities[key] = tuple(catalog.model_dependencies.get(key, ()))

    @property
    def pending(self):
        return self.roots.keys() - self.facts.keys()

    @property
    def rows(self):
        return tuple(row for row, _, member in self.facts.values() if member)
