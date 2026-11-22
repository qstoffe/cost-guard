"""Pin already observed model identity evidence for one background mix build."""
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
import json

from src.cache.display_mix_identity import MixIdentity, MixReferenceStamp
from src.domain.model_identity import unverified_alias
from src.pricing.publishers import model_publisher


@dataclass(frozen=True, slots=True)
class MixReference:
    catalog: object
    stamp: MixReferenceStamp

    def identify(self, models):
        facts = {}
        for model in models:
            match = self.catalog.resolve_reference(model)
            if match is not None:
                facts[model] = MixIdentity(match.model.display_name or match.model.model, model_publisher(match))
        return facts


def qualified_mix_reference(catalog, now_ms):
    """No route inference or use of an unproven or expired catalog."""
    if catalog is None:
        return None
    observed_at = getattr(catalog, "retrieved_at_ms", 0)
    valid_until = getattr(catalog, "refresh_not_after_ms", None)
    if (not 0 < observed_at <= now_ms or not getattr(catalog, "source_revision", "") or
            getattr(catalog, "reference_stale", True) or valid_until is not None and now_ms >= valid_until):
        return None
    values = sorted((row.model.model, row.model.display_name or "", model_publisher(row) or "")
                    for row in catalog.models)
    digest = sha256(json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return MixReference(catalog, MixReferenceStamp(observed_at, digest))


def identity_key(entry):
    # A provider-specific moving alias cannot inherit an exact release label
    # persisted for a different interpretation of the same spelling.
    return entry.model if entry.model and not unverified_alias(entry.model, entry.provider) else None


class ArchiveMixIdentities:
    """The durable dimension grows per observed exact model, not per request."""

    def __init__(self, reference, *, capacity=1024):
        self.reference = reference
        self.capacity = capacity
        self._recent = OrderedDict()

    def collect(self, history, source, batch, eligible):
        keys = {key for entry in batch.entries if (key := identity_key(entry)) is not None}
        missing = keys.difference(self._recent)
        if missing:
            candidates = self.reference.identify(missing) if self.reference else {}
            values = history.mix_identities(
                source, batch.version, tuple(sorted(missing)), candidates=candidates,
                observed_at=self.reference.stamp.observed_at if candidates else None, eligible=eligible)
            if values is None:
                return None
            self._recent.update((key, values.get(key)) for key in missing)
        result = {}
        for key in keys:
            evidence = self._recent[key]
            if evidence is not None:
                result[key] = evidence
            self._recent.move_to_end(key)
        while len(self._recent) > self.capacity:
            self._recent.popitem(last=False)
        return result
