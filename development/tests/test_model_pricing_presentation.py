"""Pricing legend/alignment, true sample sizes and independent Watch windows."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import io
import re
import tempfile
import unittest
from types import SimpleNamespace

from development.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests import test_compact_reports as compact
from development.tests.test_step6_pricing_accounts import pricing_markdown
from development.tests.test_step8_watch import MutableSource, make_service
from src.analysis.comparisons import model_comparison_rows
from src.config import load_configuration
from src.presentation import ReportRenderer, WatchRenderer
from src.pricing.catalog import PricingCatalog
from src.pricing.github_copilot import _annotate_promotions, _preserve_known_promotions, parse_pricing_markdown
from src.pricing.promotions import model_promotion, WEEK_MS
from src.reports import ReportKind, ReportProjection, ReportRequest
from src.reports.models import ModelComparisonProjection
from src.reports.semantics import active_promotion_notes, model_is_recent, recent_model_notice
from src.watch import WatchCoordinator
from src.watch.models import WatchProjection

NOW = int(datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp() * 1000)
DAY = 86_400_000
ANSI = re.compile(r"\x1b\[[0-9;]*m")
CONFIG = {"timezone": "UTC", "colors": {"modelComparisonNew": {"ansi256": 118},
                                       "modelComparisonPromotion": {"ansi256": 214}}}


def catalog(*, age=0, expiry=30, starts=True):
    model = parse_pricing_markdown(pricing_markdown())[0]
    metadata = {"release_date": "2026-10-05", "promotion_active": "true",
                "promotion_expires_ms": str(NOW + expiry * DAY)}
    if starts:
        metadata["promotion_starts_ms"] = str(NOW - age * DAY)
    return PricingCatalog((replace(model, metadata=metadata),))


class PricingPresentationTests(unittest.TestCase):
    def service(self, source):
        return compact.CompactReportTests.service(self, source, now_ms=NOW)

    def test_comparison_uses_actual_repriced_count_and_keeps_other_mix_eligibility(self):
        for available, count in ((0, 0), (47, 47), (120, 100)):
            service = self.service(SyntheticMonthSource(1, available, month_start_ms=NOW - DAY))
            report = service.build(ReportRequest(ReportKind.ALL_MODELS))
            self.assertEqual(count, report.model_comparison_sample_size)
            text = compact.rendered(report)
            if count:
                self.assertIn(f"Rel CCost: Applies Token Mix % from {count} completed prompt", text)
            else:
                self.assertIn("Rel CCost stays blank", text)
            self.assertNotIn("does not predict model behavior", text)
            self.assertNotIn("~RelCost", compact.rendered(report))
        root = next(iter(service._analyzed.values()))
        record = root.bundle.prompts[0]
        zero = replace(record, prompt_id="zero", input_tokens=0, cache_read_tokens=0,
                       cache_write_tokens=0, output_tokens=0)
        root.bundle = replace(root.bundle, prompts=(record, zero,
            replace(record, prompt_id="running", in_progress=True),
            replace(record, prompt_id="aborted", aborted=True)))
        rows, sample, *_ = service._model_comparison((root,), all_models=True)
        self.assertEqual(1, sample)
        self.assertEqual(4, len(service._latest_token_prompts((root,))))
        expected = model_comparison_rows(service._latest_prompts((root,)), service._load_catalog())
        self.assertEqual([r.relative_to_lowest for r in expected], [r.relative_cost for r in rows])

    def test_marker_regions_and_numeric_alignment_do_not_pollute_prices(self):
        for markers in ((None, None, None), (1, None, 2), (1, None, 12345)):
            rows = tuple(ModelComparisonProjection("Test", f"Model {n}", value, "1/0.1/0.2/5", "2026-10-05",
                         promotional=marker is not None, promotion_marker=marker)
                         for n, (value, marker) in enumerate(zip(map(Decimal, ("7.5", "3.2", "1.0")), markers)))
            report = ReportProjection(ReportKind.ALL_MODELS, "Test", "V2", model_comparison=rows)
            for width in (80, 120, 200):
                for color in (False, True):
                    text = compact.rendered(report, CONFIG, width=width, color=color)
                    lines = [ANSI.sub("", line) for line in text.splitlines() if line.startswith("|") and re.search(r"Model \d", line)]
                    cells = [line.split("|")[3] for line in lines]
                    self.assertEqual(1, len({line.index(f"{value:.1f}x") for line, value in zip(lines, map(Decimal, ("7.5", "3.2", "1.0")))}))
                    expected_width = max(9, max((len(f"*{m}") for m in markers if m), default=0) + (5 if any(markers) else 0))
                    self.assertEqual([expected_width + 2] * 3, list(map(len, cells)))
                    for line, cell, marker in zip(lines, cells, markers):
                        self.assertNotIn("*", line.split("|")[4])
                        if marker:
                            self.assertTrue(cell.startswith(f" *{marker}"), cell)
                    self.assertIn("Copilot CCost/M tokens I/C/W/O", text)
                    self.assertNotIn("Price I/C/W/O is", text)

    def test_notice_labels_only_are_colored_in_both_outputs_and_wrapped(self):
        new = "✦ New Models: Model A, Model B, Model C"
        promo = "*1 Price Promotion: Model A — temporary promotional pricing through 2026-11-01."
        for width in (40, 120):
            stream = io.StringIO()
            report = ReportProjection(ReportKind.ALL_MODELS, "Test", "V2", recent_model_notice=new,
                                      model_comparison_promotion_notes=(promo,))
            ReportRenderer(CONFIG, stream=stream, terminal_width=width, color_enabled=True).render(report)
            watch_stream = io.StringIO()
            WatchRenderer(CONFIG, stream=watch_stream, interactive=True, terminal_width=width).render(
                WatchProjection("Cost Guard Watch", "V2", (), recent_model_notice=new,
                                recent_promotion_notices=(promo.replace("*1", "*"),)))
            for text, marker in ((stream.getvalue(), "*1"), (watch_stream.getvalue(), "*")):
                self.assertIn("\x1b[38;5;118m✦ New Models:\x1b[0m Model", text)
                self.assertIn(f"\x1b[38;5;214m{marker} Price Promotion:\x1b[0m Model", text)
                for line in text.splitlines():
                    if "\x1b[38;5;118m" in line or "\x1b[38;5;214m" in line:
                        emphasized = re.findall(r"\x1b\[38;5;(?:118|214)m(.*?)\x1b\[0m", line)
                        self.assertTrue(all("Model A" not in part and "pricing through" not in part for part in emphasized))


class MetadataWindowTests(unittest.TestCase):
    def test_promotion_active_recent_and_expiry_boundaries(self):
        for age, expiry, report_visible, watch_visible in (
            (-1, 30, False, False), (0, 30, True, True), (6, 30, True, True),
            (7, 30, True, False), (20, 30, True, False), (6, 0, False, False), (6, -1, False, False)):
            prices = catalog(age=age, expiry=expiry)
            self.assertEqual(report_visible, bool(active_promotion_notes(prices, NOW)[1]))
            self.assertEqual(watch_visible, bool(active_promotion_notes(prices, NOW, recent_only=True)[1]))
        promotion = model_promotion(catalog().models[0])
        self.assertTrue(promotion.recent(NOW + WEEK_MS - 1))
        self.assertFalse(promotion.recent(NOW + WEEK_MS))
        unknown_start = catalog(starts=False)
        self.assertTrue(active_promotion_notes(unknown_start, NOW)[1])
        self.assertFalse(active_promotion_notes(unknown_start, NOW, recent_only=True)[1])
        self.assertFalse(active_promotion_notes(replace(unknown_start, models=(replace(unknown_start.models[0],
            metadata={"promotion_active": "true", "promotion_expires_ms": "bad"}),)), NOW)[1])

    def test_new_model_uses_existing_seven_utc_day_window(self):
        for age, expected in ((-1, False), (0, True), (6, True), (7, False), (8, False)):
            released = datetime.fromtimestamp((NOW - age * DAY) / 1000, tz=timezone.utc).date().isoformat()
            self.assertEqual(expected, model_is_recent(released, now_ms=NOW))
            prices = catalog()
            prices = replace(prices, models=(replace(prices.models[0], metadata={"release_date": released}),))
            self.assertEqual(expected, bool(recent_model_notice(prices, now_ms=NOW)))

    def test_report_new_model_notice_uses_watch_marker(self):
        from src.watch.model_discovery import WatchModelDiscovery
        prices = catalog()
        report_notice = recent_model_notice(prices, now_ms=NOW)
        observer = WatchModelDiscovery(SimpleNamespace(_load_catalog=lambda: prices))
        watch_notice = observer.notice(NOW)
        self.assertTrue(report_notice.startswith("✦ New Models: "), report_notice)
        self.assertEqual(report_notice.partition(":")[0], watch_notice.partition(":")[0])
        lines = [ANSI.sub("", line) for line in compact.rendered(
            ReportProjection(ReportKind.ALL_MODELS, "Test", "V2",
                             recent_model_notice="✦ New Models: " + ", ".join(["Model Name"] * 12)),
            CONFIG, width=60, color=False).splitlines()]
        start = next(i for i, line in enumerate(lines) if line.startswith("✦ New Models:"))
        self.assertRegex(lines[start + 1], r"^  \S", lines[start + 1])

    def test_provider_extracts_explicit_start_without_first_seen_or_release_guesses(self):
        models = parse_pricing_markdown(pricing_markdown())
        for start in ("from October 5, 2026", "starting on 2026-10-05", "effective October 5, 2026"):
            markdown = pricing_markdown(promo=True).replace("at 50% off through", f"at 50% off {start} through")
            annotated = _annotate_promotions(models, markdown)
            self.assertEqual(str(NOW), annotated[0].metadata["promotion_starts_ms"])
            self.assertTrue(all("promotion_expires_ms" not in m.metadata for m in annotated[1:]))
        previous = PricingCatalog(annotated)
        no_start = _annotate_promotions(models, pricing_markdown(promo=True))
        self.assertNotIn("promotion_starts_ms", no_start[0].metadata)
        retained = _preserve_known_promotions(no_start, previous, NOW)
        self.assertEqual(str(NOW), retained[0].metadata["promotion_starts_ms"])
        changed = _annotate_promotions(models, pricing_markdown(promo=True).replace("2026", "2027"))
        self.assertNotIn("promotion_starts_ms", _preserve_known_promotions(changed, previous, NOW)[0].metadata)

    def test_watch_notices_age_out_without_source_activity_and_report_keeps_active_offer(self):
        with tempfile.TemporaryDirectory() as td:
            config, selection, service, _ = make_service(td, MutableSource(), now_ms=NOW)
            service.pricing_provider.catalog = catalog()
            clock = [NOW]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            first = watch.initialize().projection
            self.assertTrue(first.recent_model_notice)
            self.assertTrue(first.recent_promotion_notices)
            clock[0] += WEEK_MS
            later = watch.status_projection()
            self.assertFalse(later.recent_model_notice)
            self.assertFalse(later.recent_promotion_notices)
            self.assertNotEqual(watch._visible_signature(first), watch._visible_signature(later))
            rows, _sample, notes, *_ = service._model_comparison((), all_models=True)
            self.assertTrue(rows[0].promotional)
            self.assertEqual(1, rows[0].promotion_marker)
            self.assertTrue(notes)
            clock[0] = NOW + 30 * DAY
            watch.status_projection()
            rows, _sample, notes, *_ = service._model_comparison((), all_models=True)
            self.assertFalse(rows[0].promotional)
            self.assertIsNone(rows[0].promotion_marker)
            self.assertFalse(notes)

    def test_both_wait_loops_repaint_aged_notices_before_the_next_source_poll(self):
        for method in ("_v1_wait", "_v2_wait"):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as td:
                source = MutableSource(make_root_snapshot(0, 0, month_start_ms=NOW))
                clock = [NOW + WEEK_MS - 1000]
                config, selection, service, _ = make_service(td, source, now_ms=clock[0])
                service.pricing_provider.catalog = catalog()
                monotonic = [0.0]
                def advance(seconds):
                    monotonic[0] += seconds
                    clock[0] += int(seconds * 1000)
                watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                    clock_ms=lambda: clock[0], monotonic=lambda: monotonic[0], sleep=advance)
                initial = watch.initialize().projection
                self.assertTrue(initial.recent_model_notice)
                self.assertTrue(initial.recent_promotion_notices)
                frames = []
                renderer = SimpleNamespace(render=frames.append, render_status=lambda _p: None)
                watch._event_pump = SimpleNamespace(get=lambda seconds: advance(seconds))
                hydration_count = source.load_count
                getattr(watch, method)(renderer)
                self.assertTrue(frames, "expiry must repaint, not only update the hidden projection")
                self.assertFalse(frames[-1].recent_model_notice)
                self.assertFalse(frames[-1].recent_promotion_notices)
                self.assertEqual(hydration_count, source.load_count)


class WatchDensityTests(unittest.TestCase):
    def test_startup_observation_scope_is_independent_of_visible_row_count(self):
        expected = None
        for limit in (5, 14, 50, 100):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as td:
                source = SyntheticMonthSource(30, 1, month_start_ms=NOW)
                config, selection, service, _ = make_service(td, source, now_ms=NOW)
                config.update(watchDashboardMaxRows=limit, watchRecentEventSeconds=0)
                watch = WatchCoordinator(selection=selection, report_service=service, config=config,
                                         clock_ms=lambda: NOW)
                cycle = watch.initialize()
                self.assertEqual(20, len(cycle.hydrated_roots), "bounded discovery is not a presentation limit")
                self.assertEqual(20, cycle.projection.token_mix.sample_size)
                self.assertEqual(min(limit, 20), len(cycle.projection.rows))
                if expected is None:
                    expected = cycle.projection.token_mix
                self.assertEqual(expected, cycle.projection.token_mix)

    def test_default_and_overrides_only_limit_rows_not_87_prompt_run_mix(self):
        self.assertEqual(14, load_configuration(compact.ROOT).values["watchDashboardMaxRows"])
        expected = None
        for limit in (None, 5, 14, 50, 100):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as td:
                source = MutableSource(make_root_snapshot(0, 0, month_start_ms=NOW))
                config, selection, service, _ = make_service(td, source, now_ms=NOW)
                config["watchRecentEventSeconds"] = 0
                if limit is None:
                    config.pop("watchDashboardMaxRows")
                else:
                    config["watchDashboardMaxRows"] = limit
                clock = [NOW]
                watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
                self.assertEqual(limit or 14, watch.max_rows)
                watch.initialize()
                for count in (30, 60, 87):
                    snapshot = make_root_snapshot(0, count, month_start_ms=NOW)
                    source.snapshot = replace(snapshot, source_revision=f"prompts-{count}")
                    clock[0] = NOW + count * 1000 + 500
                    current = watch.poll_once(force_resync=True).projection
                    self.assertEqual(count, current.token_mix.sample_size)
                    self.assertEqual(min(count, limit or 14), len(current.rows))
                self.assertEqual(87, current.token_mix.request_count)
                if expected is None:
                    expected = current.token_mix
                self.assertEqual(expected, current.token_mix)
                self.assertEqual(expected, watch.status_projection().token_mix)


if __name__ == "__main__":
    unittest.main()
