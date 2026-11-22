"""Group the same canonical physical requests as archive Token Mix totals."""
from dataclasses import dataclass, field
from decimal import Decimal

from src.cache.display_mix_groups import MixGroupRow
from src.domain import ModelRef
from src.domain.model_identity import UNKNOWN_MODEL, UNKNOWN_PUBLISHER
from src.reports.history_mix_identity import history_model_key

from .archive_token_mix import MixAccumulator
from .archive_mix_identity import identity_key


@dataclass(slots=True)
class GroupAccumulator:
    """Membership keys and input qualification remain distinct from labels."""
    label: str
    publisher: str
    valued_label: bool = False
    totals: MixAccumulator = field(default_factory=MixAccumulator)

    def describe(self, label, publisher, valued_label):
        if (valued_label, label) > (self.valued_label, self.label):
            self.label = label
            self.valued_label = valued_label
        if self.publisher != publisher:
            self.publisher = UNKNOWN_PUBLISHER

    def values(self):
        totals = self.totals
        return (self.label, self.publisher, self.valued_label, totals.known, totals.requests, totals.priced,
                totals.observed_any, totals.stale_prices, *map(str, totals.counts), *map(str, totals.observed),
                *(str(cost.amount()) for cost in totals.costs))

    def row(self, key, prompts):
        mix = self.totals.mix(prompts)
        return MixGroupRow(*key, self.label, self.publisher, mix.sample_size, mix.request_count, mix.priced_requests,
                           mix.known_total_tokens, mix.totals, mix.costs)

    @classmethod
    def load(cls, values):
        label, publisher, authoritative, known, calls, priced, seen, stale, *vector = values
        totals = MixAccumulator(counts=list(map(int, vector[:4])), observed=list(map(int, vector[4:8])),
                                known=known, requests=calls, priced=priced, observed_any=bool(seen), stale_prices=stale)
        for cost, stored in zip(totals.costs, vector[8:]):
            cost.add(Decimal(stored))
        return cls(label, publisher, bool(authoritative), totals)


class ArchiveMixGroups:
    """Only one input slice is collected in memory; the caller persists it."""
    def __init__(self, periods, *, pricing=None):
        self.periods = periods
        self.pricing = pricing

    @staticmethod
    def _identity(item, identities):
        model = ModelRef(item.provider, item.model)
        facts = identities.get(identity_key(item))
        publisher = facts.publisher if facts and facts.publisher else UNKNOWN_PUBLISHER
        label = facts.label if facts else item.recorded_model or item.model or UNKNOWN_MODEL
        return history_model_key(model) or "unknown", (label, publisher, facts is not None)

    def collect(self, entries, identities):
        groups, prompts = {}, set()
        for item in entries:
            model_key, identity = self._identity(item, identities)
            label, publisher, named = identity
            for scope in self.periods(item.clock_ms):
                for key, facts in (((scope, "model", model_key), identity),
                                  ((scope, "publisher", publisher), (publisher, publisher, False))):
                    group = groups.get(key)
                    if group is None:
                        group = groups[key] = GroupAccumulator(*facts)
                    elif key[1] == "model":
                        group.describe(label, publisher, named)
                    group.totals.add(item, self.pricing)
                    if item.logical_prompt_id:
                        prompts.add((*key, item.session_id, item.logical_prompt_id))
        return groups, prompts


class MixGroupStage:
    """Disk-backed grouped reductions; each update touches only a slice's keys."""
    def __init__(self, db, periods, *, pricing=None):
        self.db = db
        self.input = ArchiveMixGroups(periods, pricing=pricing)
        db.executescript("""
            CREATE TABLE groups (
                period TEXT NOT NULL, kind TEXT NOT NULL, identity TEXT NOT NULL,
                label TEXT NOT NULL, publisher TEXT NOT NULL, verified_label INTEGER NOT NULL,
                known INTEGER NOT NULL, calls INTEGER NOT NULL, priced INTEGER NOT NULL,
                observed_any INTEGER NOT NULL, stale INTEGER NOT NULL,
                i TEXT NOT NULL, c TEXT NOT NULL, w TEXT NOT NULL, o TEXT NOT NULL,
                oi TEXT NOT NULL, oc TEXT NOT NULL, ow TEXT NOT NULL, oo TEXT NOT NULL,
                ci TEXT NOT NULL, cc TEXT NOT NULL, cw TEXT NOT NULL, co TEXT NOT NULL,
                prompts INTEGER NOT NULL, PRIMARY KEY(period,kind,identity)
            ) WITHOUT ROWID;
            CREATE TABLE group_prompts (
                period TEXT NOT NULL, kind TEXT NOT NULL, identity TEXT NOT NULL,
                session TEXT NOT NULL, prompt TEXT NOT NULL,
                PRIMARY KEY(period,kind,identity,session,prompt)
            ) WITHOUT ROWID;
        """)

    def add(self, entries, identities=None):
        groups, keys = self.input.collect(entries, identities or {})
        counts = dict.fromkeys(groups, 0)
        for prompt in keys:
            counts[prompt[:3]] += self.db.execute("INSERT OR IGNORE INTO group_prompts VALUES(?,?,?,?,?)", prompt).rowcount
        for key, group in groups.items():
            row = self.db.execute("SELECT * FROM groups WHERE (period,kind,identity)=(?,?,?)", key).fetchone()
            prompts = counts[key]
            if row is not None:
                previous = GroupAccumulator.load(row[3:-1])
                previous.describe(group.label, group.publisher, group.valued_label)
                previous.totals.merge(group.totals)
                group, prompts = previous, prompts + row[-1]
            values = (*key, *group.values(), prompts)
            marks = ",".join("?" for _ in values)
            self.db.execute(f"INSERT OR REPLACE INTO groups VALUES({marks})", values)

    def page(self, after, limit):
        for row in self.db.execute("""
            SELECT * FROM groups WHERE (period,kind,identity)>(?,?,?)
            ORDER BY period,kind,identity LIMIT ?
        """, (*after, limit)):
            yield row[:3], GroupAccumulator.load(row[3:-1]), row[-1]
