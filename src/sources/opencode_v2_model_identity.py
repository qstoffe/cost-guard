"""Read-only Desktop-parity catalog observations; never historical execution proof."""
from dataclasses import replace
import hashlib
import json
import threading
import time

from src.domain.model_identity import ModelResolution, desktop_catalog_candidate
from .errors import SourceError
from .opencode_v2_effort import observation


def _text(value):
    return isinstance(value, str) and 0 < len(value) <= 1024 and value.isprintable()


class DesktopModelCatalog:
    """One bounded observation per location/30s, shared by requests and cache validation.

    Failure is a negative observation, not authority to guess another location or
    invoke the CLI. Only relevant provider+alias mapping content is fingerprinted.
    """

    def __init__(self, client, *, clock=time.monotonic):
        self.client, self.clock = client, clock
        self._observations = {}
        self._lock = threading.RLock()

    def _models(self, directory):
        with self._lock:
            now = self.clock()
            cached = self._observations.get(directory)
            if cached is not None and now - cached[0] < 30:
                return cached[1]
            models, defaults = {}, {}
            try:
                query = {"location[directory]": directory}
                providers = self.client().json("/api/provider", query=query, phase="model_identity")
                values = self.client().json("/api/model", query=query, phase="model_identity")
                if all(isinstance(v, dict) and isinstance(v.get("location"), dict)
                       and v["location"].get("directory") == directory
                       and isinstance(v.get("data"), list) for v in (providers, values)):
                    by_provider = {p["id"]: p for p in providers["data"][:2000]
                                   if isinstance(p, dict) and _text(p.get("id"))}
                    present = "claude-agent" in by_provider
                    for model in values["data"][:20000]:
                        if (isinstance(model, dict) and _text(model.get("providerID"))
                                and _text(model.get("id")) and model.get("status") != "deprecated"):
                            defaults[model["providerID"], model["id"]] = observation(
                                directory, model["id"], by_provider.get(model["providerID"]), model)
                        if (isinstance(model, dict) and model.get("providerID") == "claude-agent"
                                and present
                                and model.get("status") != "deprecated" and _text(model.get("id"))
                                and _text(model.get("name"))):
                            # Desktop uses findLast, not enabled/model-family matching.
                            models[model["id"]] = (model["name"], model.get("modelID"))
            except SourceError:
                pass
            if len(self._observations) >= 256 and directory not in self._observations:
                self._observations.pop(next(iter(self._observations)))
            self._observations[directory] = (now, (models, defaults))
            return models, defaults

    def lookup(self, directory, selected):
        value = self._models(directory)[0].get(selected)
        safe = value if value and _text(value[1]) else (value[0], None) if value else None
        # Qualify short SDK names since resolver v2. Invalidate only dependent
        # mutable projections, including previously unresolved/short-name costs.
        signature = hashlib.sha256(json.dumps([2, safe], ensure_ascii=False).encode()).hexdigest()
        return safe, signature

    def resolve(self, model, directory):
        if model is None or not directory:
            return model
        defaults = self._models(directory)[1]
        model = replace(model, effort_default=defaults.get((model.provider, model.recorded_model)) or
            observation(directory, model.recorded_model, None, None))
        if model.provider != "claude-agent":
            return model
        selected = model.recorded_model
        if not desktop_catalog_candidate(selected, model.provider):
            return model  # An explicit historical release never depends on today's catalog.
        value, signature = self.lookup(directory, selected)
        identity = ModelResolution(selected, directory, signature)
        if value is None:
            return replace(model, resolution=identity)
        label, upstream = value
        # A concrete request ID is supported pricing identity, not execution evidence.
        concrete = upstream and not desktop_catalog_candidate(upstream, model.provider)
        # SDK displayName may omit the provider's brand (Opus 5.5). Qualify that
        # exact observed label, never substitute a family/version or guess rates.
        effective = upstream if concrete else label if label.startswith('Claude ') else 'Claude ' + label
        return replace(model, model=effective, display_name=label, resolution=identity)

    def current(self, models):
        for model in models:
            effort = model.effort_default
            if effort is not None:
                actual = self._models(effort.scope)[1].get((model.provider, effort.selected_model)) or observation(
                    effort.scope, effort.selected_model, None, None)
                if actual.signature != effort.signature:
                    return False
            resolution = model.resolution
            if resolution is None and desktop_catalog_candidate(model.model, model.provider):
                return False  # A prior unresolved projection has no location observation.
            if resolution is not None and (model.provider != "claude-agent"
                    or resolution.kind != "desktop-catalog-estimate"
                    or self.lookup(resolution.scope, resolution.selected_model)[1] != resolution.signature):
                return False
        return True
