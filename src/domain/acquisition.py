"""Numeric-only acquisition measurements shared by source and use-case owners."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import time
from typing import Iterator


@dataclass(slots=True)
class AcquisitionMetrics:
    mode: str = "unknown"
    generation: str = "unknown"
    counts: dict[str, int] = field(default_factory=dict)
    milliseconds: dict[str, float] = field(default_factory=dict)

    def add(self, name: str, amount: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + amount

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.milliseconds[stage] = self.milliseconds.get(stage, 0.0) + (time.perf_counter() - started) * 1000

    def snapshot(self) -> dict[str, object]:
        counters = dict.fromkeys(("catalog_sessions", "catalog_roots", "analysis_candidate_roots", "dashboard_candidate_roots",
            "history_candidate_roots", "hydrated_roots", "cache_reads", "cache_hits", "cache_misses", "cache_writes",
            "revision_checks", "revision_calculations", "full_catalog_fetches", "catalog_pages", "message_operations",
            "message_pages", "analyzed_prompts", "analyzed_requests"), 0)
        stages = dict.fromkeys(("catalog", "revision", "liveness", "cache_reads", "hydration", "analysis",
                                "historical_accounting", "projection", "rendering", "watch_refresh"), 0.0)
        return {"mode": self.mode, "generation": self.generation, "counts": {**counters, **self.counts},
                "milliseconds": {key: round(value, 3) for key, value in {**stages, **self.milliseconds}.items()}}
