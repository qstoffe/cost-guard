"""Pure bounded sampling: two eligibility sets, activity cutoffs and ties."""
from dataclasses import replace
import unittest

from development.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.domain import TokenUsage
from src.reports.sampling import AnalyzedRoot, latest_prompts, latest_token_prompts, recent_sample_roots


def analyzed_root(session_id, at_ms, *, running=False, known=True):
    snapshot = make_snapshot()
    bundle = analyze_snapshot(snapshot, now_ms=4000)
    record = next(item for item in bundle.prompts if item.prompt_id == "u_next")
    entries = record.entries if known else tuple(replace(item, tokens=TokenUsage(known_fields=())) for item in record.entries)
    prompts = tuple(replace(record, prompt_id=f"{session_id}-{index:03d}", session_id=session_id,
                            prompt_time_ms=at_ms, in_progress=running, entries=entries) for index in range(100))
    return AnalyzedRoot(replace(snapshot.root, session_id=session_id), replace(bundle, prompts=prompts), False)


class ReportSamplingTests(unittest.TestCase):
    def test_completion_and_telemetry_eligibility_are_independent(self):
        completed = analyzed_root("completed", 100, known=False)
        running = analyzed_root("running", 200, running=True)

        comparisons = latest_prompts((completed, running))
        usage = latest_token_prompts((completed, running))

        self.assertEqual({"completed"}, {item.session_id for item in comparisons})
        self.assertEqual({"running"}, {item.session_id for item in usage})
        self.assertEqual((100, 100), (len(comparisons), len(usage)))

    def test_scan_waits_for_both_samples_and_uses_older_cutoff(self):
        items = (analyzed_root("first", 100, known=False), analyzed_root("second", 200, running=True),
                 analyzed_root("below", 50))
        values = {item.session.session_id: item for item in items}
        activity = {"first": 500, "second": 400, "below": 99}
        visited = []

        def analyze(session):
            visited.append(session.session_id)
            return values[session.session_id]

        result = recent_sample_roots(tuple(item.session for item in items), activity, analyze)

        self.assertEqual(["first", "second"], visited)
        self.assertEqual(items[:2], result)

    def test_activity_equal_to_cutoff_must_hydrate_for_stable_id_ties(self):
        first, tied, below = analyzed_root("a", 100), analyzed_root("z", 100), analyzed_root("old", 1)
        values = {item.session.session_id: item for item in (first, tied, below)}

        result = recent_sample_roots(tuple(item.session for item in (first, tied, below)),
                                     {"a": 101, "z": 100, "old": 99}, lambda session: values[session.session_id])

        self.assertEqual((first, tied), result)
        self.assertEqual({"z"}, {item.session_id for item in latest_prompts(result)})
        self.assertEqual({"z"}, {item.session_id for item in latest_token_prompts(result)})

    def test_aborted_usage_stays_visible_but_not_comparable(self):
        item = analyzed_root("root", 100)
        item.bundle = replace(item.bundle, prompts=tuple(replace(prompt, aborted=True) for prompt in item.bundle.prompts))

        self.assertEqual((), latest_prompts((item,)))
        self.assertEqual(100, len(latest_token_prompts((item,))))

    def test_empty_roots_do_not_invoke_analyzer(self):
        def forbidden(_session):
            raise AssertionError("No hydration for empty history")

        self.assertEqual((), recent_sample_roots((), {}, forbidden))
