#!/usr/bin/env python3
"""Deterministic large-month benchmark for Cost Guard report/cache scaling.

This is a developer benchmark, not a runtime dependency or release gate based on
fragile millisecond thresholds.  It reports durations plus source operation
counts so accidental O(N^2) or cache-regression behavior is observable.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import argparse
import json
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from development.fixtures.synthetic_month import SyntheticMonthSource
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import IntegrationHealth, ModelPricing, ModelRef, PricingTier, ProviderCapabilities
from src.pricing.catalog import PricingCatalog
from src.reports import ReportRequest, ReportService
from src.sources.selection import SourceSelection

NOW_MS = 1_790_510_400_000
MONTH_START_MS = 1_788_220_800_000


class _Pricing:
    provider_id = "github-copilot"
    capabilities = ProviderCapabilities(model_pricing=True, long_context_pricing=True)

    def __init__(self) -> None:
        tier = PricingTier(
            per_million_input=Decimal("1"), per_million_cache_read=Decimal("0.1"),
            per_million_output=Decimal("4"),
        )
        self.catalog = PricingCatalog((
            ModelPricing(ModelRef("github-copilot", "gpt-test", "GPT Test"), "USD", tiers=(tier,), metadata={"publisher":"Synthetic"}),
        ), retrieved_at_ms=1, source_revision="synthetic-prices")

    def probe(self): return IntegrationHealth(True, True, "synthetic")
    def get_model_pricing(self): return self.catalog.models
    def get_catalog(self, force=False): return self.catalog


def _service(source, repo, config):
    return ReportService(
        selection=SourceSelection(source, "v1", (), source.probe()),
        pricing_provider=_Pricing(), account_provider=None,
        cache_repository=repo, config=config, now_ms=NOW_MS,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", type=int, default=100)
    parser.add_argument("--prompts", type=int, default=50)
    args = parser.parse_args()
    if args.roots <= 0 or args.prompts <= 0:
        parser.error("--roots and --prompts must be positive")

    source = SyntheticMonthSource(args.roots, args.prompts, month_start_ms=MONTH_START_MS)
    config = dict(load_configuration(ROOT).values)
    config["timezone"] = "UTC"
    with tempfile.TemporaryDirectory() as td:
        db = CacheDatabase(Path(td)); db.initialize()
        repo = CacheRepository(db)
        started = time.perf_counter()
        first = _service(source, repo, config).build(ReportRequest())
        first_seconds = time.perf_counter() - started
        loads_after_first = source.load_count
        revisions_after_first = source.revision_count

        started = time.perf_counter()
        second = _service(source, repo, config).build(ReportRequest())
        second_seconds = time.perf_counter() - started
        result = {
            "roots": args.roots,
            "prompts_per_root": args.prompts,
            "total_prompts": args.roots * args.prompts,
            "first_seconds": round(first_seconds, 4),
            "second_seconds": round(second_seconds, 4),
            "first_source_hydrations": loads_after_first,
            "second_additional_hydrations": source.load_count - loads_after_first,
            "first_revision_checks": revisions_after_first,
            "second_revision_checks": source.revision_count - revisions_after_first,
            "sample_prompts_first": first.pricing_diagnostics["relcost_sample_prompts"],
            "sample_prompts_second": second.pricing_diagnostics["relcost_sample_prompts"],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        if result["second_additional_hydrations"] != 0:
            print("FAIL: stable second run rehydrated source history", file=sys.stderr)
            return 1
        if result["second_revision_checks"] > args.roots:
            print("FAIL: stable second run exceeded O(root) revision checks", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
