"""Share decoded history between background display projections."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from threading import Lock
from time import monotonic
from types import MappingProxyType, SimpleNamespace

from src.analysis.ai_stats import StatsRoot
from src.analysis.cache import decode_trace_entry
from src.analysis.models import TraceEntry
from src.domain import AccountRef, CostDisposition, ModelRef, TokenUsage

from .ai_stats_evidence import INVALID, decoded
from .web_history_evidence import DOMAIN


@dataclass(frozen=True, slots=True)
class UsageEvidence:
    revision: str
    observed_ms: int
    report: tuple | None
    accounts: tuple | None
    report_rank: tuple = ()
    account_rank: tuple = ()
    causal_prompts: dict | None = None
    last_request_ms: int = 0


class ArchivedUsage:
    def __init__(self, archive, *, retain_account_entries=True):
        self.archive = archive
        self.retain_account_entries = retain_account_entries
        self.lock = Lock()
        self.cursor = 0
        self.facts = MappingProxyType({})
        self.complete_generation = None

    def snapshot(self, *, seconds=0.2):
        """Called on projection workers only. No consumer holds the shared lock while aggregating."""
        with self.lock:
            generation = self.archive.generation(DOMAIN)
            if generation == self.complete_generation:
                return self.cursor, self.facts, False
            deadline = monotonic() + seconds
            next_facts = None
            cursor = self.cursor
            for _ in range(32):
                cursor, facts, more = self.archive.history_changes(DOMAIN, cursor)
                if facts and next_facts is None:
                    next_facts = dict(self.facts)
                for key, fact in facts:
                    old = next_facts.get(key)
                    decoded = self._decode(key, fact)
                    if old is None:
                        next_facts[key] = decoded
                    else:
                        report = decoded if decoded.report is not None and decoded.report_rank >= old.report_rank else old
                        accounts = decoded if decoded.account_rank and decoded.account_rank >= old.account_rank else old
                        latest = max((old, decoded), key=lambda item: max(item.report_rank, item.account_rank))
                        next_facts[key] = UsageEvidence(latest.revision, latest.observed_ms,
                            report.report, accounts.accounts, report.report_rank, accounts.account_rank,
                            report.causal_prompts, report.last_request_ms)
                if not more or monotonic() >= deadline:
                    break
            if next_facts is not None:
                self.facts = MappingProxyType(next_facts)
            self.cursor = cursor
            if not more:
                self.complete_generation = generation
            return self.cursor, self.facts, more

    def _decode(self, key, fact):
        if 'legacy_requests' in fact.value:
            return _decode_legacy(key, fact, retain_account_entries=self.retain_account_entries)
        try:
            root = SimpleNamespace(session_id=key, title=fact.value['title'],
                                   provenance=SimpleNamespace(source_instance='shared-history'))
            report = decoded(fact.value['stats'], root, now=fact.observed_ms, verified_archive=True)
        except INVALID:
            report = None
        accounts, account_rank = None, ()
        # A valid Accounts-only fact still advances the shared revision. Validate
        # it if necessary for coverage, without keeping a second decoded history
        # in a process that only renders the report evidence.
        if self.retain_account_entries or report is None:
            try:
                entries = map(_account_entry, fact.value['account_usage'])
                if self.retain_account_entries:
                    accounts = tuple(entries)
                else:
                    for _ in entries:
                        pass
                account_rank = fact.history_rank
            except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
                pass
        return UsageEvidence(fact.revision, fact.observed_ms, report, accounts,
                              fact.history_rank if report is not None else (),
                              account_rank,
                             fact.value.get('causal_prompts'),
                             max((entry.completed_at_ms for entry, *_ in report[1]), default=0) if report else 0)


def _account_entry(value):
    entry = decode_trace_entry(value)
    if entry.account_ref:
        entry.account_ref.key  # Validate before using this fact in an account projection.
    return entry


def _amount(value):
    amount = Decimal(value) if value is not None else None
    return amount if amount is not None and amount.is_finite() and amount >= 0 else None


def _decode_legacy(key, fact, *, retain_account_entries):
    value = fact.value
    names = 'input', 'cache_read', 'cache_write', 'output', 'reasoning'
    requests = []
    for item in value['legacy_requests']:
        try:
            if not isinstance(item['request_key'], str) or not item['request_key']:
                continue
            costs = tuple(_amount(item.get(name + '_cost')) for name in names[:4])
            mask = item['known_fields']
            tokens = TokenUsage(*(item[name + '_tokens'] for name in names),
                                known_fields=tuple(name for count, name in enumerate(names) if mask & (1 << count)))
            account = (AccountRef('legacy-history', item['provider'] or 'Unknown',
                                  source_account=item['account_key']) if item['account_key'] else None)
            prompt = item['logical_prompt_id']
            entry = TraceEntry(item['session_id'], None, item['request_key'], None, item['clock_ms'] or 0,
                item['request_ordinal'], ModelRef(item['provider'], item['model'], item['recorded_model'] or None),
                item['effort'], tokens, _amount(item['billed']) or Decimal(0), summary=bool(item['summary']),
                cost_disposition=CostDisposition._value2member_map_.get(item['disposition'], CostDisposition.UNKNOWN),
                source_instance=fact.partition, account_ref=account, logical_prompt_id=prompt,
                root_session_id=key, invocation_id=item['request_key'],
                parent_session_id=key if item['session_id'] != key and item['dedup_tree'] == key else None,
                reported_cost_currency=item['currency'])
        except INVALID:
            continue
        requests.append((entry, (entry.session_id, prompt) if prompt and not entry.summary else None,
                         costs if all(cost is not None for cost in costs) else None))
    entries = tuple(entry for entry, *_ in requests)
    intervals = tuple((start, duration, bool(provisional)) for start, duration, provisional in value['legacy_intervals']
                      if type(start) is int and start > 0 and type(duration) is int and duration >= 0)
    root = StatsRoot(key, value['title'], entries, intervals, source_complete=False,
                     session_parents=tuple(tuple(pair) for pair in value['legacy_parents']), source_instance=fact.partition)
    return UsageEvidence(fact.revision, fact.observed_ms, (root, requests, None),
                         entries if retain_account_entries else None,
                         fact.history_rank, fact.history_rank, value['legacy_attribution'],
                         max((entry.completed_at_ms for entry in entries), default=0))
