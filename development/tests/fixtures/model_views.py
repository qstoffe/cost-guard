"""Canonical Models fixtures shared by DOM regression and explicit browser probes."""
from decimal import Decimal as D
from types import SimpleNamespace

from development.tests.fixtures.compact_reports import Availability
from src.analysis.comparisons import model_comparison_rows
from src.analysis.token_mix import TokenMix
from src.domain import ModelPricing, ModelRef, PricingTier
from src.pricing.catalog import PricingCatalog
from src.reports.model_comparison import price_summary, selectable_catalog
from src.reports.models import ModelComparisonProjection, ReportKind, ReportProjection


def model_report(*, all_models=False, fallback=False, availability="verified"):
    def tier(price, minimum=None, operator=None):
        return PricingTier(min_input_tokens=minimum, input_threshold_operator=operator,
            per_million_input=D(price), per_million_cache_read=D(price),
            per_million_cache_write=D(price), per_million_output=D(price))

    models = tuple(ModelPricing(ModelRef("github-copilot", name, name), "USD", tiers=levels,
        metadata={"publisher": "OpenAI", "release_date": "2026-10-01"}) for name, levels in (
            ("A", (tier("8.01"),)), ("Z", (tier("8.04"),)),
            ("GPT-5.1", (tier("8"), tier("16", 200001, ">"), tier("32", 1000000, "≥"))),
            ("GPT-5.2", (tier("8"), tier("20", 200001, ">"))),
            ("Reference", (tier("1"),)),
            ("Precision-" + "Long-model-name-" * 8, (tier("2.1234567890123456789"),)),
            ("Unknown", (PricingTier(per_million_input=D("5")),)),
            ("Unselectable", (tier("100"),))))
    catalog = PricingCatalog(models)
    warnings = ()
    if not all_models:
        ids = tuple(m.model.model for m in models[:-1])
        catalog, warnings = selectable_catalog(catalog, availability_source=Availability(
            None if availability == "unverified" else () if availability == "empty" else ids))
    sample = () if fallback else (SimpleNamespace(input_tokens=20, cache_read_tokens=60,
        cache_write_tokens=10, output_tokens=10),)
    rows = model_comparison_rows(sample, catalog)
    items = tuple(ModelComparisonProjection(row.publisher, row.model_name, row.relative_to_lowest,
        price_summary(catalog, row.model_name), row.release_date,
        promotional=row.model_name == "GPT-5.1", promotion_marker=1 if row.model_name == "GPT-5.1" else None,
        recent=row.model_name == "Z", relative_levels=row.relative_levels) for row in rows)
    return ReportProjection(ReportKind.ALL_MODELS if all_models else ReportKind.NORMAL,
        "Models", "V2 fixture", model_comparison=items, model_comparison_sample_size=0 if fallback else 1,
        token_mix=TokenMix(), source_warnings=warnings,
        model_comparison_promotion_notes=("*1 Fixture promotional terms",), recent_model_notice="Recent models: Z")
