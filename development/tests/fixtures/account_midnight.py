"""Synthetic source requests and explicit reference rates, never live inference."""
from dataclasses import replace
from decimal import Decimal as D

from development.tests.fixtures.account_periods import subscription
from development.tests.fixtures.synthetic_month import make_root_snapshot
from src.domain import ModelRef, ModelPricing, TokenUsage
from src.pricing.catalog import PricingCatalog

ROUTES = ('github-copilot', 'openai', 'claude-agent')
EXPECTED = (D(1), D(2), D(12))  # 10K/20K at $1/M; 30K Opus at $4/M, in credits.
CATALOG = PricingCatalog(tuple(ModelPricing(ModelRef('github-copilot', name), 'USD',
    D(rate), D(0), D(0), D(0)) for name, rate in (('gpt-test', 1), ('claude-opus-5-5', 4))),
    retrieved_at_ms=1, source_revision='midnight-synthetic-rates')


def accounts():
    return tuple(replace(subscription(provider), plan=plan, observations=observations)
        for provider, plan, observations in (
            ('github-copilot', 'Pro+', {}), ('openai', 'Pro Light', {}),
            ('claude-code', 'Pro', dict(account_kind='subscription', auth_status='authenticated', backend_status='first_party'))))


def snapshot(index, completed, provider, *, amount=10000, account_ref=None, model=None, started=None, active=None):
    raw = make_root_snapshot(index, 1, month_start_ms=completed - 300 - index * 60000)
    model = ModelRef(provider, model or ('claude-opus-5-5' if provider == 'claude-agent' else 'gpt-test'))
    started = raw.root.created_at_ms if started is None else started
    root = replace(raw.root, created_at_ms=started, active=active)
    return replace(raw, root=root, sessions=(root,), messages=tuple(replace(message, created_at_ms=started,
        model=model if message.model else None) for message in raw.messages),
        events=tuple(replace(event, created_at_ms=started, metadata=dict(provider_id=provider, model_id=model.model)) for event in raw.events),
        invocations=tuple(replace(request, model=model, tokens=TokenUsage(input=amount, output=0, cache_read=0, cache_write=0),
            created_at_ms=started, cost=None, account_ref=account_ref) for request in raw.invocations))


def midnight_frame(frame, phase):
    """Canonical request→account/global→application fixture for actual browser views."""
    from src.analysis.causal import trace_entries
    from src.analysis.daily_usage import daily_usage
    from src.analysis.timezones import local_day_start_ms, local_month_start_ms
    from src.reports.accounts import account_projections
    now = frame.now_ms
    day = local_day_start_ms('Europe/Stockholm', now_ms=now)
    native = accounts()
    records = tuple(entry for i, route in enumerate(ROUTES) for entry in trace_entries(
        snapshot(i, day - 1 if phase == 'old' else day + 1, route,
            amount=(i + 1) * 10000, model='unpriced' if phase == 'unknown' else None)))
    if phase == 'partial':
        records += tuple(replace(entry, message_id=entry.message_id + '-unpriced', model=replace(entry.model, model='unpriced')) for entry in records)
    if phase.startswith('zero'):
        records = ()
    if phase.endswith('stale'):
        native = tuple(replace(account, availability='stale') for account in native)
    rows = account_projections(native, records, CATALOG, now_ms=now, today_start_ms=day,
        month_start_ms=local_month_start_ms('Europe/Stockholm', now_ms=now), observed_start_ms=day,
        watch=True, require_history=True)
    daily = daily_usage(records, {}, day_start_ms=day, now_ms=now,
        valuation=CATALOG.reference_valuation, category_valuation=CATALOG.reference_category_valuation)
    return replace(frame, quota=replace(frame.quota, accounts=rows), daily_usage=daily,
        quota_stale=phase.endswith('stale'), daily_state='observed')
