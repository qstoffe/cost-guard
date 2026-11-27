"""Source-backed browsing state for hosts without an archive.

SessionCatalog owns this mode and calls it under the catalog lock. Its
leases and indexes are independent of the committed Sessions read path.
"""
from collections import OrderedDict
from heapq import nsmallest

from .session_catalog_scope import PAGE_SIZE, candidate_population, catalog_window, in_window
from .session_epoch_page import epoch_page


class SessionLeasePages:
    def __init__(self):
        self.leases = OrderedDict()
        self.orders = OrderedDict()
        self.activity_index = ()
        self.discovery = {}
        self.discovery_sequence = 0
        self.last_page = ()
        self.warm = False
        self.background_due = 0
        self.turn = 0

    def page(self, catalog, **request):
        return epoch_page(catalog, self, **request)

    def interest(self, catalog, token, visible):
        lease = self.leases.get(token)
        if lease is None:
            raise KeyError('catalog_expired')
        lease['interest_until'] = catalog.clock() + 90 if visible else catalog.clock()

    def expire(self, clock):
        for token, lease in tuple(self.leases.items()):
            if clock() - lease['touched'] > 300:
                del self.leases[token]

    def browsing(self, catalog, lease):
        return (catalog.clock() < lease['interest_until'] if 'interest_until' in lease
                else catalog.clock() - lease['touched'] <= 300)

    def has_browsing_leases(self, catalog):
        return any(self.browsing(catalog, lease) for lease in self.leases.values())

    def reset_leases(self):
        self.leases.clear()

    def invalidate(self, keys=None):
        for lease in self.leases.values():
            navigation = lease.get('navigation')
            if navigation is not None and (keys is None or navigation.roots.keys() & keys):
                navigation.invalid = True
            lease['epochs'].clear()

    def observe_roster(self, roots, activity, *, added, removed, replaced, source_changed, now):
        if source_changed:
            self.background_due = now
        elif added:
            self.background_due = min(self.background_due, now + 15)
        self.discovery = {key: age for key, age in self.discovery.items() if key in roots}
        for key in roots:
            if key not in self.discovery:
                self.discovery_sequence += 1
                self.discovery[key] = self.discovery_sequence
        if replaced:
            self.invalidate()
            self.last_page = ()
        if removed:
            for lease in self.leases.values():
                epochs = lease['epochs']
                for epoch, snapshot in tuple(epochs.items()):
                    if any(row.session_id in removed for row in snapshot.rows):
                        del epochs[epoch]
        self.activity_index = tuple(sorted((at, key) for key, at in activity.items()
                                           if key in roots and type(at) is int and at > 0))

    def population(self, catalog, period):
        window = catalog_window(period, catalog.timezone_id, catalog.clock_ms())
        lifecycle = (catalog.running_roots | catalog.recent_finishes.keys() |
            {key for key, proof in catalog.prompt_activity.items()
             if in_window(proof.finish_ms or proof.start_ms, window)})
        return window, candidate_population(catalog.roots, catalog.activity, self.activity_index,
            catalog.rows, catalog.changed_roots | catalog.active | lifecycle, window)

    def targets(self, catalog):
        browsing = [lease for lease in self.leases.values() if self.browsing(catalog, lease)]
        selected = set()
        for lease in browsing:
            # A provisional page does not rule out offscreen Live candidates.
            if not lease.get('pinned') or not lease.get('cohort_verified'):
                selected.update(catalog.active)
                selected.update(catalog.running_roots)
                selected.update(key for key, proof in catalog.prompt_activity.items()
                    if proof.ended and proof.finish_ms is None and not catalog._activity_current(key))
            navigation = lease.get('navigation')
            if navigation is not None:
                if navigation.invalid:
                    continue
                selected.update(navigation.pending)
                # A released Live lane stays eligible under repeated clicks,
                # but never admits arrivals before the first application.
                if lease.get('released'):
                    lease['candidates'] = self.population(catalog, lease['period'])[1]
                    selected.update(lease['candidates'])
                continue
            selected.update(lease.get('visible', ()))
            selected.update(lease.get('nearby', ()))
            if not lease.get('pinned') and (lease.get('sort') not in (None, 'name')
                                          or lease.get('period') != 'all'):
                lease['candidates'] = self.population(catalog, lease['period'])[1]
                selected.update(lease['candidates'])
        if browsing:
            return selected & catalog.roots.keys()
        if not self.warm or catalog.clock() < self.background_due:
            return set()
        now = catalog.clock_ms()
        return set(nsmallest(PAGE_SIZE, catalog.roots,
            key=lambda key: (-(catalog.activity.get(key) or 0)
                             if (catalog.activity.get(key) or 0) <= now else 0, key)))

    def requested(self, catalog, key, sort):
        return any(lease.get('sort') == sort and self.browsing(catalog, lease)
                   and key in lease.get('candidates', ()) for lease in self.leases.values())

    def missing_requested_scalar(self, catalog, key, row):
        if not row.running:
            if not row.context_qualified and self.requested(catalog, key, 'ctx'):
                return 'context'
            if not row.effort_qualified and self.requested(catalog, key, 'effort'):
                return 'effort'
        return None

    def navigations(self, catalog):
        return (lease['navigation'] for lease in self.leases.values()
                if self.browsing(catalog, lease)
                and lease.get('navigation') is not None and not lease['navigation'].invalid)

    def ready_navigations(self):
        return [lease['navigation'] for lease in self.leases.values()
                if lease.get('navigation') is not None and not lease['navigation'].pending
                and not lease['navigation'].invalid]

    def eligible(self, catalog, key):
        navigation_pending = any(key in nav.roots and key not in nav.facts
                                 for nav in self.navigations(catalog))
        return (navigation_pending or not catalog._current(key)
                or key in catalog.active or key in catalog.running_roots
                or not catalog.rows[key].context_qualified and self.requested(catalog, key, 'ctx')
                or not catalog.rows[key].effort_qualified and self.requested(catalog, key, 'effort')
                or not catalog._activity_current(key) and any(self.browsing(catalog, lease)
                    and key in lease.get('candidates', ()) and (
                        lease.get('sort') == 'activity' or lease.get('period') != 'all')
                    for lease in self.leases.values()))

    def candidate(self, catalog, *, extension):
        candidates = [key for key in self.targets(catalog) if catalog._eligible(key)]
        if not candidates:
            return None
        navigations = tuple(self.navigations(catalog))
        if extension and not any(nav.expanded_period and any(
                key in nav.roots and key not in nav.facts for key in candidates) for nav in navigations):
            return None
        self.turn += 1
        pending = {key for nav in navigations for key in nav.pending}
        priority = pending.intersection(candidates)
        if self.turn % 8 and priority:
            return min(priority,
                       key=lambda key: (catalog.attempted.get(key, -100), self.discovery[key]))
        visible = dict.fromkeys(key for lease in sorted(self.leases.values(), key=lambda item: -item['touched'])
                                 if self.browsing(catalog, lease) for key in lease.get('visible', ()))
        priority = [key for key in visible if key in candidates]
        if self.turn % 8 and priority:
            return min(priority, key=lambda key: (catalog._current(key), catalog.attempted.get(key, -100)))
        if self.turn % 4:
            nearby = dict.fromkeys(key for lease in self.leases.values() if self.browsing(catalog, lease)
                                   for key in lease.get('nearby', ()))
            priority = [key for key in nearby if key in candidates]
            if priority:
                return min(priority, key=lambda key: catalog.attempted.get(key, -100))
        return min(candidates, key=lambda key: (catalog.attempted.get(key, -100), self.discovery[key]))

    def defer_warm_work(self, catalog, targets):
        if not self.has_browsing_leases(catalog):
            self.background_due = catalog.clock() + (15 if any(
                not catalog._current(key) for key in targets if key in catalog.roots) else 900)
