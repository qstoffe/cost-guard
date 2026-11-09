"""Read-only Desktop-parity catalog observations; never historical execution proof."""
from dataclasses import replace
import hashlib
import json
import threading
import time

from src.domain.model_identity import ModelResolution, unverified_alias
from .errors import SourceError


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
            models = {}
            try:
                query = {"location[directory]": directory}
                providers = self.client().json("/api/provider", query=query, phase="model_identity")
                values = self.client().json("/api/model", query=query, phase="model_identity")
                if all(isinstance(v, dict) and v.get("location", {}).get("directory") == directory
                       and isinstance(v.get("data"), list) for v in (providers, values)):
                    present = any(p.get("id") == "claude-agent" for p in providers["data"] if isinstance(p, dict))
                    for model in values["data"][:20000] if present else ():
                        if (isinstance(model, dict) and model.get("providerID") == "claude-agent"
                                and model.get("status") != "deprecated" and _text(model.get("id"))
                                and _text(model.get("name"))):
                            # Desktop uses findLast, not enabled/model-family matching.
                            models[model["id"]] = (model["name"], model.get("modelID"))
            except SourceError:
                pass
            if len(self._observations) >= 256 and directory not in self._observations:
                self._observations.pop(next(iter(self._observations)))
            self._observations[directory] = (now, models)
            return models

    def lookup(self, directory, selected):
        value = self._models(directory).get(selected)
        safe = value if value and _text(value[1]) else (value[0], None) if value else None
        signature = hashlib.sha256(json.dumps(safe, ensure_ascii=False).encode()).hexdigest()
        return safe, signature

    def resolve(self, model, directory):
        if model is None or model.provider != "claude-agent" or not directory:
            return model
        selected = model.recorded_model
        if not unverified_alias(selected, model.provider):
            return model  # An explicit historical release never depends on today's catalog.
        value, signature = self.lookup(directory, selected)
        identity = ModelResolution(selected, directory, signature)
        if value is None:
            return replace(model, resolution=identity)
        label, upstream = value
        # A concrete request ID is supported pricing identity, not execution evidence.
        effective = upstream if upstream and not unverified_alias(upstream, model.provider) else label
        return replace(model, model=effective, display_name=label, resolution=identity)

    def current(self, models):
        for model in models:
            resolution = model.resolution
            if resolution is None and model.provider == 'claude-agent' and unverified_alias(model.model, model.provider):
                return False  # A prior unresolved projection has no location observation.
            if resolution is not None and (model.provider != "claude-agent"
                    or resolution.kind != "desktop-catalog-estimate"
                    or self.lookup(resolution.scope, resolution.selected_model)[1] != resolution.signature):
                return False
        return True
