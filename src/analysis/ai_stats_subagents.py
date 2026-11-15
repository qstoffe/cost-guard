"""Proven execution ancestry only; filtering never prices or duplicates requests."""


def child_requests(roots, entries, values):
    proven, candidates = set(), set()
    for root in roots:
        parents = {}
        for sid, parent in (*root.session_parents,
                            *((e.session_id, e.parent_session_id) for e in root.entries)):
            parents.setdefault(sid, set()).add(parent)
        resolved = {root.session_id: True}
        for sid in parents:
            current, trail = sid, set()
            while current not in resolved and current not in trail:
                trail.add(current)
                links = parents.get(current, ())
                if len(links) != 1:
                    break
                current = next(iter(links))
            linked = resolved.get(current, False)
            resolved.update((item, linked) for item in trail)
        for entry in root.entries:
            if entry.session_id == root.session_id:
                continue
            identity = (entry.source_instance, entry.session_id, entry.root_session_id)
            candidates.add(identity)
            source_matches = not root.source_instance or entry.source_instance == root.source_instance
            if source_matches and entry.root_session_id == root.session_id and resolved.get(entry.session_id):
                proven.add(identity)
    children, amounts, unknown = [], [], False
    for entry, value in zip(entries, values):
        identity = (entry.source_instance, entry.session_id, entry.root_session_id)
        if identity in proven:
            children.append(entry)
            amounts.append(value)
        elif identity in candidates:
            unknown = True
    return children, amounts, unknown
