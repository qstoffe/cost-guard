"""Synthetic current V2 wire, pinned reference rates and isolated history services."""
from dataclasses import replace
from decimal import Decimal as D

from development.tests.fixtures.compact_reports import Availability, report_service, START
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.domain import ModelPricing, ModelRef, Provenance
from src.pricing.catalog import PricingCatalog
from src.reports import ReportService
from src.sources.opencode_v2_normalization import normalize_invocations, normalize_message_bundle
from src.sources.opencode_v2_wire import current_union_message_to_legacy_bundle
from src.sources.opencode_v2_model_identity import DesktopModelCatalog

LABEL = 'Claude Sonnet (version unverified)'


def catalog(*, reverse=False):
    models = tuple(ModelPricing(ModelRef('github-copilot', identity, name), 'USD',
        D(2), D('.2'), D(3), D(10), metadata={'publisher': 'Anthropic'})
        for identity, name in (('claude-sonnet-4', 'Claude Sonnet 4'),
                               ('claude-sonnet-5-5', 'Claude Sonnet 5.5'),
                               ('claude-sonnet-4-5', 'Claude Sonnet 4.5')))
    return PricingCatalog(tuple(reversed(models)) if reverse else models,
        retrieved_at_ms=1, source_revision='acquired-synthetic-rates')


def snapshot(index=0, model='sonnet', provider='claude-agent'):
    base = make_root_snapshot(index, 1, month_start_ms=START)
    sid, at = base.root.session_id, base.root.created_at_ms
    root = replace(base.root, provenance=Provenance('opencode', 'v2', 'alias-fixture', sid),
                   archived_at_ms=at + 1000, active=False)
    session = {'id': sid, 'model': {'providerID': provider, 'id': 'claude-sonnet-5-5'}}
    raw = [dict(id='u', type='user', text='same synthetic task', time={'created': at}),
           dict(id='a', type='assistant', agent='build', time={'created': at + 100, 'completed': at + 300},
                model={'providerID': provider, 'id': model, 'variant': 'default'}, finish='stop', content=[],
                tokens={'input': 1000, 'output': 50, 'reasoning': 0,
                        'cache': {'read': 2000, 'write': 22000}})]
    provenance = lambda session_id, event_id=None: replace(root.provenance,
        source_session_id=session_id, source_event_id=event_id)
    messages, parts = [], []
    for ordinal, value in enumerate(raw):
        bundle = current_union_message_to_legacy_bundle(value, session=session, ordinal=ordinal)
        if value['type'] == 'assistant':
            bundle['info']['parentID'] = 'u'
        message, normalized = normalize_message_bundle(bundle, provenance)
        messages.append(message)
        parts.extend(normalized)
    events = (replace(base.events[0], event_id='u', text='same synthetic task', metadata={},
                      provenance=provenance(sid, 'u')),)
    invocations = tuple(item for message in messages for item in normalize_invocations(message, provenance))
    return replace(base, root=root, sessions=(root,), messages=tuple(messages), parts=tuple(parts),
        events=events, invocations=invocations, complete=True)


def service(test, *, snapshots=None):
    source = SyntheticMonthSource(0, 1, month_start_ms=START)
    source.snapshots = {value.root.session_id: value for value in (snapshots or (snapshot(), snapshot(1, 'claude-sonnet-4-5')))}
    result = report_service(test, source, availability=Availability(None))
    result.selection = replace(result.selection, warnings=())
    result.pricing_provider.catalog = catalog()
    return result


def reopen(original, *, shared=False):
    result = ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
        account_provider=None, cache_repository=original.cache_repository, config=original.config,
        now_ms=original.now_ms, model_availability_source=original.model_availability_source,
        cache_token_mix_history=shared)
    result.shared_web_evidence = shared
    return result


class DesktopSource(SyntheticMonthSource):
    """Unchanged raw history; mutable exact catalog, including negative dependencies."""
    def __init__(self, snapshots, *, model='claude-sonnet-5-5', label='Sonnet 5.5'):
        super().__init__(0, 1, month_start_ms=START)
        self.snapshots = {value.root.session_id: value for value in snapshots}
        self.model, self.label, self.clock, self.catalog_reads = model, label, 0, 0
        self.identities = DesktopModelCatalog(lambda: self, clock=lambda: self.clock)

    def json(self, route, **_kwargs):
        self.catalog_reads += 1
        return dict(location=dict(directory='/synthetic'), data=[dict(id='claude-agent')] if route == '/api/provider'
            else [dict(providerID='claude-agent', id='sonnet', name=self.label, modelID=self.model)] if self.model else [])

    def model_identities_current(self, models):
        return self.identities.current(models)

    def load_session_snapshot(self, session_id):
        raw = super().load_session_snapshot(session_id)
        resolve = lambda model: self.identities.resolve(model, '/synthetic')
        return replace(raw, messages=tuple(replace(m, model=resolve(m.model)) for m in raw.messages),
            invocations=tuple(replace(r, model=resolve(r.model)) for r in raw.invocations))


def desktop_service(test, snapshots=None):
    source = DesktopSource(snapshots or (snapshot(), snapshot(1, 'claude-sonnet-4-5')))
    result = report_service(test, source, availability=Availability(None))
    result.selection = replace(result.selection, warnings=())
    result.pricing_provider.catalog = catalog()
    return result
