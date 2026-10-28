"""Revision-keyed compact comparison samples in the existing disposable cache.

No independent source/ledger: deleted roots disappear on the next catalog read;
cache loss rebuilds from canonical analysis. Hydrated deep roots are released.
"""
from dataclasses import asdict

from src.analysis.cache import dependency_signature
from src.analysis.workload_mix import PromptMix, WorkloadSamples, prompt_mix
from src.domain.progress import WorkProgress

_NAMESPACE = "comparison-prompt-samples"
_VERSION = "model-publisher-1"


def _decode(payload):
    try:
        items = tuple(PromptMix(int(p["at_ms"]), str(p["session"]), str(p["prompt"]),
            tuple((str(m), str(pub), tuple(int(v) for v in tokens)) for m, pub, tokens in p["groups"]))
            for p in payload)
        if any(not p.groups or any(len(tokens) != 4 or min(tokens) < 0 or not sum(tokens)
                                  for _m, _pub, tokens in p.groups) for p in items):
            return None
        return items
    except (ValueError, TypeError, KeyError):
        return None


def comparison_samples(service):
    catalog = service._load_comparison_catalog()
    roots, _activity = service._ordered_roots(service.session_catalog())
    signature = dependency_signature((service._dependencies(service._load_catalog()),
                                      catalog.models, _VERSION))
    result = WorkloadSamples()
    stable = WorkloadSamples()
    repository = service.cache_repository
    batch = getattr(service.source, "get_session_tree_revisions", None)
    revisions = batch(tuple(root.session_id for root in roots)) if callable(batch) else {}
    current = {dependency_signature((root.provenance, root.session_id)):
               (root, revisions[root.session_id] if root.session_id in revisions
                else service.source.get_session_tree_revision(root.session_id)) for root in roots}
    if not roots:
        return result
    provenance = roots[0].provenance
    aggregate_key = dependency_signature((provenance.source_type, provenance.source_generation, provenance.source_instance))
    aggregate = repository.get("comparison-stable-samples", aggregate_key)
    stable_revisions = {}
    if aggregate and aggregate.algorithm_version == signature and isinstance(aggregate.payload, dict):
        previous = aggregate.payload.get("revisions", {})
        unstable = aggregate.payload.get("unstable", [])
        items = _decode(aggregate.payload.get("items"))
        if (isinstance(previous, dict) and isinstance(unstable, list) and items is not None
                and set(current) == set(previous) | set(unstable)
                and all(key in current and current[key][1] == revision and current[key][0].active is not True
                        for key, revision in previous.items())):
            stable_revisions = previous
            for item in items:
                stable.add(item)
                result.add(item)
            for key in previous:
                root, revision = current[key]
                service._acquisition.revisions[root.session_id] = revision
    for index, root in enumerate(roots):
        key = dependency_signature((root.provenance, root.session_id))
        if key in stable_revisions:
            continue
        service.progress(WorkProgress("Collecting model/publisher evidence", "history", index, len(roots)))
        revision = current[key][1]
        cached = repository.get(_NAMESPACE, key)
        items = None
        if (root.active is not True and cached and cached.source_revision == revision
                and cached.algorithm_version == signature):
            items = _decode(cached.payload)
        cacheable = items is not None
        if items is None:
            retained = root.session_id in service._analyzed
            # Revalidate retained snapshots on a new catalog observation too.
            old = service._analyzed.get(root.session_id)
            if old and (old.bundle.source_revision != revision or not old.bundle.cacheable):
                service.invalidate_roots((root.session_id,))
            bundle = service._analyze(root).bundle
            local = WorkloadSamples()
            for prompt in bundle.prompts:
                item = prompt_mix(prompt, catalog)
                if item is not None:
                    local.add(item)
            items = local.compact()
            cacheable = (bundle.cacheable and root.active is not True
                         and revision == bundle.source_revision == service.source.get_session_tree_revision(root.session_id))
            if cacheable:
                repository.put(_NAMESPACE, key, [asdict(p) for p in items], source_revision=revision,
                               algorithm_version=signature)
            if not retained:
                service._analyzed.pop(root.session_id, None)
        else:
            service._acquisition.revisions[root.session_id] = revision
        for item in items:
            result.add(item)
            if cacheable:
                stable.add(item)
        if cacheable:
            stable_revisions[key] = revision
    repository.put("comparison-stable-samples", aggregate_key, {
        "revisions": stable_revisions, "unstable": sorted(set(current) - set(stable_revisions)),
        "items": [asdict(p) for p in stable.compact()],
    }, algorithm_version=signature)
    return result
