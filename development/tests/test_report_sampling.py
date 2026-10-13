"""Pure bounded sampling: priceable eligibility, two sample sets, activity cutoffs and ties."""
from dataclasses import replace
import unittest

from development.fixtures.pricing_catalog import catalog
from development.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.analysis.token_mix import priceable_request
from src.domain import ModelRef, TokenUsage
from src.reports.sampling import AnalyzedRoot, latest_prompts, latest_token_prompts, recent_sample_roots

VALUATION = catalog().reference_category_valuation
UNPRICED = ModelRef("github-copilot", "unknown-model")


def priceable(entry):
    return priceable_request(entry.model, entry.tokens, VALUATION)


def analyzed_root(session_id, at_ms, *, running=False, known=True, priced=True, count=100):
    snapshot = make_snapshot()
    bundle = analyze_snapshot(snapshot, now_ms=4000)
    record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
    entries = record.entries
    if not known:
        entries = tuple(replace(item, tokens=TokenUsage(known_fields=())) for item in entries)
    if not priced:
        entries = tuple(replace(item, model=UNPRICED) for item in entries)
    prompts = tuple(replace(record, prompt_id=f"{session_id}-{index:03d}", session_id=session_id,
                            prompt_time_ms=at_ms, in_progress=running, entries=entries) for index in range(count))
    return AnalyzedRoot(replace(snapshot.root, session_id=session_id), replace(bundle, prompts=prompts), False)


def scan(items, activity):
    values = {item.session.session_id: item for item in items}
    visited = []

    def analyze(session):
        visited.append(session.session_id)
        return values[session.session_id]

    return recent_sample_roots(tuple(item.session for item in items), activity, analyze, priceable), visited


class ReportSamplingTests(unittest.TestCase):
    def test_completion_and_telemetry_eligibility_are_independent(self):
        completed = analyzed_root("completed", 100, known=False)
        running = analyzed_root("running", 200, running=True)

        comparisons = latest_prompts((completed, running), priceable)
        usage = latest_token_prompts((completed, running), priceable)

        self.assertEqual((), comparisons, "unknown telemetry is never priced usage")
        self.assertEqual({"running"}, {item.session_id for item in usage})
        self.assertEqual(100, len(usage))

    def test_scan_waits_for_both_samples_and_uses_older_cutoff(self):
        items = (analyzed_root("first", 300, running=True), analyzed_root("second", 200),
                 analyzed_root("below", 50))

        result, visited = scan(items, {"first": 500, "second": 400, "below": 99})

        self.assertEqual(["first", "second"], visited)
        self.assertEqual(items[:2], result)

    def test_activity_equal_to_cutoff_must_hydrate_for_stable_id_ties(self):
        first, tied, below = analyzed_root("a", 100), analyzed_root("z", 100), analyzed_root("old", 1)

        result, _visited = scan((first, tied, below), {"a": 101, "z": 100, "old": 99})

        self.assertEqual((first, tied), result)
        self.assertEqual({"z"}, {item.session_id for item in latest_prompts(result, priceable)})
        self.assertEqual({"z"}, {item.session_id for item in latest_token_prompts(result, priceable)})

    def test_aborted_usage_stays_visible_but_not_comparable(self):
        item = analyzed_root("root", 100)
        item.bundle = replace(item.bundle, prompts=tuple(replace(prompt, aborted=True) for prompt in item.bundle.prompts))

        self.assertEqual((), latest_prompts((item,), priceable))
        self.assertEqual(100, len(latest_token_prompts((item,), priceable)))

    def test_empty_roots_do_not_invoke_analyzer(self):
        def forbidden(_session):
            raise AssertionError("No hydration for empty history")

        self.assertEqual((), recent_sample_roots((), {}, forbidden, priceable))


class PriceableSampleTests(unittest.TestCase):
    def test_latest_100_all_priceable_stop_like_before(self):
        items = (analyzed_root("new", 300), analyzed_root("old", 100))

        result, visited = scan(items, {"new": 300, "old": 100})

        self.assertEqual(["new"], visited)
        self.assertEqual({"new"}, {p.session_id for p in latest_prompts(result, priceable)})

    def test_unpriceable_newest_history_backfills_from_older_priceable_prompts(self):
        items = (analyzed_root("unpriced-a", 500, priced=False), analyzed_root("unpriced-b", 400, priced=False, count=50),
                 analyzed_root("priced-old", 100, count=60), analyzed_root("priced-older", 50, count=60))

        result, visited = scan(items, {"unpriced-a": 500, "unpriced-b": 400, "priced-old": 100, "priced-older": 50})

        self.assertEqual(["unpriced-a", "unpriced-b", "priced-old", "priced-older"], visited,
                         "150 unpriceable prompts never fill the sample")
        for sample in (latest_prompts(result, priceable), latest_token_prompts(result, priceable)):
            self.assertEqual(100, len(sample))
            self.assertEqual(60, sum(p.session_id == "priced-old" for p in sample))
            self.assertEqual(40, sum(p.session_id == "priced-older" for p in sample))

    def test_more_than_100_unpriceable_then_fewer_than_100_eligible_scans_all_history(self):
        items = (*(analyzed_root(f"unpriced-{n}", 1000 - n, priced=False) for n in range(12)),
                 analyzed_root("priced", 10, count=37))

        result, visited = scan(items, {item.session.session_id: item.bundle.prompts[0].prompt_time_ms for item in items})

        self.assertEqual(13, len(visited))
        self.assertEqual(37, len(latest_prompts(result, priceable)))
        self.assertEqual(37, len(latest_token_prompts(result, priceable)))

    def test_no_eligible_prompts_produce_empty_samples(self):
        items = (analyzed_root("unpriced", 200, priced=False), analyzed_root("unknown", 100, known=False))

        result, visited = scan(items, {"unpriced": 200, "unknown": 100})

        self.assertEqual(2, len(visited))
        self.assertEqual((), latest_prompts(result, priceable))
        self.assertEqual((), latest_token_prompts(result, priceable))

    def test_one_priceable_request_makes_a_mixed_prompt_eligible_once(self):
        item = analyzed_root("mixed", 100, count=1)
        record = item.bundle.prompts[0]
        unpriced = tuple(replace(entry, model=UNPRICED) for entry in record.entries)
        priced = next(entry for entry in record.entries if priceable(entry))
        item.bundle = replace(item.bundle, prompts=(replace(record, entries=(*unpriced, priced)),
                                                    replace(record, prompt_id="none", entries=unpriced)))

        self.assertEqual(["mixed-000"], [p.prompt_id for p in latest_prompts((item,), priceable)])
        self.assertEqual(["mixed-000"], [p.prompt_id for p in latest_token_prompts((item,), priceable)])

    def test_deterministic_order_across_roots_with_timestamp_ties(self):
        roots = (analyzed_root("b", 100, count=60), analyzed_root("a", 100, count=60))

        first = latest_token_prompts(roots, priceable)
        second = latest_token_prompts(tuple(reversed(roots)), priceable)

        self.assertEqual(first, second)
        self.assertEqual(60, sum(p.session_id == "b" for p in first), "ties break by descending session id")


if __name__ == "__main__":
    unittest.main()
