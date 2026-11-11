"""Source-shaped Claude Agent request through canonical pricing/account projections."""
from dataclasses import replace
from decimal import Decimal as D

from development.tests.fixtures.claude_alias import snapshot
from src.analysis.causal import trace_entries
from src.analysis.timezones import local_day_start_ms, local_month_start_ms
from src.domain import AccountRef, AccountSnapshot, ModelRef, ModelPricing, TokenUsage, QuotaComponent
from src.pricing.catalog import PricingCatalog
from src.reports.accounts import account_projections
from src.sources.opencode_v2_model_identity import DesktopModelCatalog


def claude_account_frame(frame):
    now = frame.now_ms
    class CatalogSource:
        def json(self, route, **_):
            return dict(location=dict(directory='/synthetic'), data=[dict(id='claude-agent')]
                if route == '/api/provider' else [dict(providerID='claude-agent', id='opus',
                    modelID='opus', name='Opus 5.5')])
    model = DesktopModelCatalog(CatalogSource).resolve(ModelRef('claude-agent', 'opus'), '/synthetic')
    raw = snapshot(model='opus')
    raw = replace(raw, invocations=tuple(replace(item, model=model, completed_at_ms=now - 1,
        tokens=TokenUsage(input=15000, output=0, cache_read=0, cache_write=0)) for item in raw.invocations))
    entries = trace_entries(raw)
    catalog = PricingCatalog((ModelPricing(ModelRef('github-copilot', 'claude-opus-5-5', 'Claude Opus 5.5'),
        'USD', D(4), D('.2'), D(4), D(20), metadata={'publisher': 'Anthropic'}),),
        retrieved_at_ms=now, source_revision='synthetic-price-source')
    native = AccountSnapshot(AccountRef('synthetic', 'claude-code', account_id='one'), now,
        'Claude Code', 'Pro', quotas=tuple(QuotaComponent(label, 'rolling', remaining_fraction=D('.99'),
            duration_seconds=duration, reset_at_ms=now + 3600000) for label, duration in
            (('5-hour', 18000), ('weekly', 604800))), observations=dict(account_kind='subscription',
                auth_status='authenticated', backend_status='first_party'))
    accounts = account_projections((native,), entries, catalog, now_ms=now,
        today_start_ms=local_day_start_ms('UTC', now_ms=now),
        month_start_ms=local_month_start_ms('UTC', now_ms=now), watch=True,
        observed_start_ms=now - 604800000)
    return replace(frame, quota=replace(frame.quota, accounts=accounts))
