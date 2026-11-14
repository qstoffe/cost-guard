"""Shared account-period scopes, provenance, incremental reuse and Watch geometry."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import tempfile
import re
import unittest
from unittest.mock import patch

from development.tests.fixtures.account_periods import DAY, MONTH, NOW, HOUR, request, subscription, project
from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.quota_rendering import quotas, report_text, watch_text
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.analysis.period_ccost import PeriodCCostIndex, quota_window
from src.analysis.valuation import ComparisonCost
from src.domain import QuotaComponent, CostDisposition
from src.domain.acquisition import AcquisitionMetrics
from src.presentation.accounts import account_ccost_lines, account_ccost_text, capacity_lines
from src.presentation.token_mix import comparison_cost_text
from src.presentation.terminal import AnsiStyler
from src.reports.accounts import WatchAccountProjection, account_projections

D = Decimal


def strip_ansi(value):
    return re.sub(r"\x1b\[[0-9;]*m", "", value)


class AccountPeriodCCostTests(unittest.TestCase):
    def test_claude_agent_route_joins_only_qualified_subscription_reference_scopes(self):
        native = replace(subscription(), plan='Pro', observations=dict(account_kind='subscription',
            auth_status='authenticated', backend_status='first_party'))
        entry = replace(request('agent', NOW, provider='claude-agent', amount=60000),
            cost_disposition=CostDisposition.UNKNOWN, reported_cost=D(0))
        # Canonical fixture rate is $1/M: $0.06 == 6 CCost credits, not native 1%.
        native = replace(native, quotas=tuple(replace(q, remaining_fraction=D('.99')) for q in native.quotas))
        row = project((native,), (entry,), observed_start_ms=MONTH)[0]
        for name in ('today', '5-hour', 'weekly'):
            self.assertEqual(D(6), dict(row.ccost_scopes)[name].ccost)
            self.assertIn(name, row.ccost_estimated_scopes)
        self.assertIsNone(row.billed_today)
        for excluded in (replace(entry, cost_disposition=CostDisposition.BILLED),
                         replace(entry, model=replace(entry.model, provider='anthropic'))):
            self.assertEqual(0, dict(project((native,), (excluded,), observed_start_ms=MONTH)[0].ccost_scopes)['today'].ccost)
        for observations in ({}, dict(account_kind='api_or_external'),
                             dict(account_kind='subscription', auth_status='authenticated', backend_status='external')):
            other = replace(native, observations=observations)
            self.assertEqual(0, dict(project((other,), (entry,), observed_start_ms=MONTH)[0].ccost_scopes)['today'].ccost)
        second = replace(native, ref=replace(native.ref, account_id='second'))
        ambiguous = project((native, second), (entry,), observed_start_ms=MONTH)
        self.assertTrue(all(dict(item.ccost_scopes)['today'] is None for item in ambiguous))
        proven = replace(entry, account_ref=native.ref)
        rows = project((native, second), (proven, replace(proven, session_id='fork')), observed_start_ms=MONTH)
        self.assertEqual([D(6), D(0)], [dict(item.ccost_scopes)['today'].ccost for item in rows])
        foreign = replace(entry, account_ref=replace(native.ref, provider_id='anthropic'))
        self.assertEqual(0, dict(project((native,), (foreign,), observed_start_ms=MONTH)[0].ccost_scopes)['today'].ccost)
        signed_out = replace(native, observations={})
        self.assertEqual(D(6), dict(project((signed_out,), (proven,), observed_start_ms=MONTH)[0].ccost_scopes)['today'].ccost)

    def test_agent_windows_dedup_partial_prices_and_account_rebinding_keep_exact_boundaries(self):
        native = replace(subscription(), observations=dict(account_kind='subscription',
            auth_status='authenticated', backend_status='first_party'))
        start = native.quotas[0].reset_at_ms - 18000000
        base = replace(request('agent', NOW, provider='claude-agent', amount=60000),
            cost_disposition=CostDisposition.UNKNOWN, reported_cost=D(0))
        entries = tuple(replace(base, message_id=str(i), completed_at_ms=when)
            for i, when in enumerate((start - 1, start, NOW, NOW + 1)))
        row = project((native,), entries, watch=True, observed_start_ms=MONTH)[0]
        self.assertEqual(D(12), dict(row.ccost_scopes)['5-hour'].ccost)
        self.assertEqual(D(18), dict(row.ccost_scopes)['weekly'].ccost)
        partial = replace(base, message_id='unknown', completed_at_ms=NOW - 1,
            model=replace(base.model, model='unpriced'))
        row = project((native,), (*entries, replace(base, session_id='fork'), partial),
            watch=True, observed_start_ms=MONTH)[0]
        cost = dict(row.ccost_scopes)['5-hour']
        self.assertEqual((D(12), 3, 2), (cost.known_ccost, cost.observed_requests, cost.priced_requests))
        self.assertIsNone(cost.ccost)
        reset = replace(native, quotas=tuple(replace(q, reset_at_ms=q.reset_at_ms + HOUR) for q in native.quotas))
        self.assertEqual(D(6), dict(project((reset,), entries, watch=True, observed_start_ms=MONTH)[0].ccost_scopes)['5-hour'].ccost)

    def test_month_is_calendar_history_not_sum_of_overlapping_windows(self):
        monthly = replace(subscription("github-copilot"), quotas=(QuotaComponent("Month", "monthly"),))
        entries = tuple(request(name, when, provider=provider) for provider in ("claude-code", "github-copilot")
                        for name, when in ((provider + "old", MONTH - 1), (provider + "month", MONTH),
                                           (provider + "week", NOW - 2 * 86_400_000),
                                           (provider + "hour", NOW - HOUR)))
        claude, copilot = sorted(project((subscription(), monthly), entries), key=lambda row: row.account.ref.provider_id)
        scopes = dict(claude.ccost_scopes)
        self.assertEqual(D(300), scopes["this month"].ccost)
        self.assertEqual(D(100), scopes["today"].ccost)
        self.assertEqual(D(100), scopes["5-hour"].ccost)
        self.assertEqual(D(200), scopes["weekly"].ccost)
        self.assertEqual(scopes["this month"].ccost, dict(copilot.ccost_scopes)["this month"].ccost)
        self.assertNotIn("this month", dict(project((subscription(),), entries, watch=True)[0].ccost_scopes))
        report = "\n".join(account_ccost_lines(claude))
        self.assertIn("CCost this month: 300", report)
        self.assertEqual(("CCost today: 100", "CCost this month: 300"), account_ccost_lines(claude))
        notes = "\n".join(claude.ccost_notes)
        self.assertNotIn("trailing lookback", notes)
        self.assertIn("native reset window", notes)
        self.assertIn("not verified account/billing attribution", notes)

    def test_partial_agent_reference_estimates_require_matching_history_account_and_model_scope(self):
        from src.application.display import with_display
        from src.application.watch_accounts import watch_account
        native = replace(subscription(), observations=dict(account_kind='subscription',
            auth_status='authenticated', backend_status='first_party'))
        primary, weekly = (replace(q, remaining_fraction=D('.93')) for q in native.quotas)
        later = replace(weekly, label='Model weekly', scope='model', model_id='gpt-test', reset_at_ms=NOW + 2 * HOUR)
        native = replace(native, quotas=(primary, weekly, later))
        base = replace(request('one', NOW, provider='claude-agent', amount=5100000),
            cost_disposition=CostDisposition.UNKNOWN, reported_cost=D(0))
        unknown = replace(base, message_id='unpriced', model=replace(base.model, model='unpriced'))
        old = replace(base, message_id='old', completed_at_ms=NOW - 2 * 86400000, tokens=replace(base.tokens, input=1000000))
        entries = (base, replace(base, message_id='two'), unknown, old)

        row = project((native,), entries, watch=True, observed_start_ms=MONTH)[0]
        wire = with_display(watch_account(row), now_ms=NOW).to_json()

        self.assertEqual((D(1020), 3, 2), tuple(getattr(row.quota_periods[0].cost, key)
            for key in ('known_ccost', 'observed_requests', 'priced_requests')))
        quotas = (wire['primary']['quota'], *(slot['quota'] for slot in wire['secondary']))
        self.assertEqual([D(1020), D(1120), D(1120)], [D(q['period_ccost']['cost']['known_ccost']) for q in quotas])
        self.assertTrue(all(q['display']['capacity_basis'] == 'ratio' for q in quotas))
        self.assertTrue(all('Account attribution uncertain.' in q['display']['capacity_help'] for q in quotas))
        self.assertIn('Partial pricing / attribution.', quotas[1]['display']['capacity_help'])
        self.assertNotIn('Partial pricing / attribution.', quotas[2]['display']['capacity_help'], 'model-specific numerator excludes the unpriced other model')
        missing = account_projections((native,), entries, FakePricingProvider().catalog,
            now_ms=NOW, today_start_ms=DAY, month_start_ms=MONTH, watch=True,
            observed_start_ms=DAY, require_history=True)[0]
        missing_wire = with_display(watch_account(missing), now_ms=NOW).to_json()['secondary'][0]['quota']
        self.assertEqual('?', missing_wire['display']['ccost_capacity'])
        self.assertIn('waiting for complete period history', missing_wire['display']['capacity_help'])
        peer = replace(native, ref=replace(native.ref, account_id='second'))
        for row in project((native, peer), entries, watch=True, observed_start_ms=MONTH):
            quota = with_display(watch_account(row), now_ms=NOW).to_json()['secondary'][0]['quota']
            self.assertEqual('?', quota['display']['ccost_capacity'])
            self.assertIn('multiple compatible accounts', quota['display']['capacity_help'])

    def test_provider_is_request_source_not_publisher_and_direct_api_stays_separate(self):
        entries = (request("gpt-via-copilot", NOW, provider="github-copilot-enterprise"),
                   request("direct-anthropic", NOW, provider="anthropic"),
                   request("codex-alias", NOW, provider="openai-codex"))
        rows = project((subscription(), subscription("github-copilot"), subscription("openai")), entries)
        values = {row.account.ref.provider_id: dict(row.ccost_scopes)["today"] for row in rows}
        self.assertIsNone(values["claude-code"])
        self.assertEqual(D(100), values["github-copilot"].ccost)
        self.assertEqual(D(100), values["openai"].ccost)

    def test_two_accounts_never_duplicate_unassigned_usage_and_provider_total_is_explained_once(self):
        one, two = subscription(identity="one"), subscription(identity="two")
        proven = request("proven", NOW, ref=one.ref)
        rows = project((one, two), (proven,))
        self.assertEqual(D(100), dict(rows[0].ccost_scopes)["today"].ccost)
        self.assertIsNone(dict(rows[1].ccost_scopes)["today"])
        rows = project((one, two), (proven, request("unknown", NOW)))
        self.assertTrue(all(dict(row.ccost_scopes)["today"] is None for row in rows))
        notes = "\n".join(note for row in rows for note in row.ccost_notes)
        self.assertEqual(1, notes.count("Provider-only CCost today: 200"))
        self.assertIn("multiple compatible accounts", notes)
        from src.application.display import with_display
        from src.application.projection import account
        dto = with_display(account(rows[0])).to_json()
        provider_note = next(item for item in dto["provider_ccost_notes"] if item["name"] == "today")
        self.assertIn("Provider-only CCost today: 200", dto["ccost_notes"][provider_note["index"]])
        self.assertEqual("$2.00", provider_note["cost"]["display_units"]["usd"]["known_ccost"])
        self.assertEqual(D(200), D(provider_note["cost"]["known_ccost"]))
        text = "\n".join(capacity_lines(rows[0], AnsiStyler({}, enabled=False), "UTC", width=240, now_ms=NOW, watch=True))
        self.assertIn("CCost: account unknown", text)
        self.assertNotIn("(200)", text)

    def test_single_account_estimate_excludes_history_proven_to_another_account(self):
        current, removed = subscription(), subscription(identity="removed")
        row = project((current,), (request("unknown", NOW), request("other", NOW, ref=removed.ref)))[0]
        self.assertEqual(D(100), dict(row.ccost_scopes)["today"].ccost)

    def test_partial_pricing_dedup_and_model_scopes_match_canonical_valuation(self):
        known = request("known", NOW)
        clone = replace(known, session_id="fork")
        unknown = request("unknown", NOW, model="unpriced")
        row = project((subscription(),), (known, clone, unknown))[0]
        value = dict(row.ccost_scopes)["today"]
        self.assertEqual((D(100), 2, 1), (value.known_ccost, value.observed_requests, value.priced_requests))
        self.assertIn("CCost today: 100", account_ccost_lines(row))
        self.assertFalse(value.complete)
        scoped = replace(subscription(), quotas=(replace(subscription().quotas[1], scope="model", model_id="claude-test"),))
        self.assertIsNone(dict(project((scoped,), (known,))[0].ccost_scopes)["weekly"])

    def test_window_requires_a_valid_anchor_or_explicit_not_started(self):
        component = subscription().quotas[1]
        self.assertIsNone(quota_window(replace(component, reset_at_ms=None), NOW))
        self.assertIsNone(quota_window(replace(component, reset_at_ms=NOW), NOW))
        self.assertIsNone(quota_window(replace(component, reset_at_ms=NOW + 8 * 86_400_000), NOW))
        inactive = replace(subscription().quotas[0], window_active=False, reset_at_ms=None)
        self.assertEqual((NOW, NOW, "provider-confirmed empty window"), quota_window(inactive, NOW))

    def test_established_empty_periods_are_zero_for_every_provider_and_both_surfaces(self):
        for provider in ("openai", "github-copilot", "claude-code", "anthropic"):
            with self.subTest(provider=provider):
                native = subscription(provider)
                row = project((native,), (), observed_start_ms=MONTH)[0]
                self.assertTrue(all(value is not None and value.ccost == 0 for _, value in row.ccost_scopes))
                self.assertEqual(("CCost today: 0", "CCost this month: 0"), account_ccost_lines(row)[:2])
                watch = project((native,), (), watch=True, observed_start_ms=MONTH)[0]
                text = "\n".join(capacity_lines(watch, AnsiStyler({}, enabled=False), "UTC",
                                               width=160, now_ms=NOW, watch=True))
                self.assertIn("0% used (0)", text)
                self.assertIn("43% used (0)", text)

    def test_empty_periods_require_history_not_just_account_attribution(self):
        native = replace(subscription(), usage_attribution_complete=True)
        missing = project((native,), ())[0]
        self.assertTrue(all(value is None for _, value in missing.ccost_scopes))
        partial_history = project((native,), (), observed_start_ms=DAY)[0]
        self.assertEqual(0, dict(partial_history.ccost_scopes)["today"].ccost)
        self.assertIsNone(dict(partial_history.ccost_scopes)["this month"])
        self.assertIsNone(dict(partial_history.ccost_scopes)["weekly"])
        no_anchor = replace(native, quotas=(replace(native.quotas[1], reset_at_ms=None),))
        self.assertIsNone(dict(project((no_anchor,), (), observed_start_ms=MONTH)[0].ccost_scopes)["weekly"])
        ambiguous = project((native, subscription(identity="two")), (request("unassigned", NOW),),
                            observed_start_ms=MONTH)
        self.assertTrue(all(dict(row.ccost_scopes)["today"] is None for row in ambiguous))

    def test_account_formatter_rounds_known_subtotal_without_changing_global_markers(self):
        for value, expected in ((None, "—"), (ComparisonCost(), "0"), (ComparisonCost(D(0), 1, 0), "—"),
                                (ComparisonCost(D("37.2"), 2, 1), "38"),
                                (ComparisonCost(D("0.15"), 2, 1), "0.2"),
                                (ComparisonCost(D("0.01"), 2, 1), "<0.1"),
                                (ComparisonCost(D("37.2"), 1, 1), "38")):
            with self.subTest(expected=expected):
                self.assertEqual(expected, account_ccost_text(value))
        self.assertEqual("38", comparison_cost_text(ComparisonCost(D("37.2"), 2, 1)))
        unpriced = project((subscription(),), (request("unknown", NOW, model="unpriced"),),
                           observed_start_ms=MONTH)[0]
        self.assertIn("CCost today: —", account_ccost_lines(unpriced))

    def test_partial_subtotal_is_plain_in_report_watch_and_compact_fallbacks(self):
        value = ComparisonCost(D("37.2"), 2, 1)
        row = project((subscription(),), (request("known", NOW),))[0]
        row = replace(row, ccost_scopes=tuple((name, value) for name, _ in row.ccost_scopes))
        for width in (65, 160):
            for color in (False, True):
                with self.subTest(width=width, color=color):
                    styler = AnsiStyler({}, enabled=color)
                    for watch in (False, True):
                        text = "\n".join(strip_ansi(line) for line in capacity_lines(
                            row, styler, "UTC", width=width, now_ms=NOW, watch=watch))
                        self.assertIn("0% used (38)", text)
                        self.assertIn("43% used (38)", text)
                        self.assertNotIn("≥", text)
                        self.assertNotIn("?", text)
                    text = strip_ansi(report_text(replace(quotas(row), now_ms=NOW), width=width))
                    self.assertEqual(1, text.count("CCost today: 38"))
                    self.assertEqual(1, text.count("CCost this month: 38"))
                    fallback = replace(row, account=replace(row.account, quotas=(), billing=()))
                    text = "\n".join(capacity_lines(fallback, styler, "UTC", width=width, now_ms=NOW, watch=True))
                    self.assertIn("CCost today: 38", text)
        no_percent = replace(row, account=replace(row.account, quotas=(replace(
            row.account.quotas[0], remaining_fraction=None),)))
        text = "\n".join(capacity_lines(no_percent, AnsiStyler({}, enabled=False), "UTC",
                                       width=160, now_ms=NOW, watch=True))
        self.assertIn("N/A · CCost: 38", text)
        self.assertEqual((D("37.2"), 2, 1, False),
                         (value.known_ccost, value.observed_requests, value.priced_requests, value.complete))

    def test_compact_report_keeps_distinct_values_inline_without_prose_or_footer(self):
        row = project((subscription(),), (request("week", NOW - 2 * 86_400_000),
                                          request("today", NOW)), observed_start_ms=MONTH)[0]
        for width in (80, 120, 160):
            for color in (False, True):
                with self.subTest(width=width, color=color):
                    lines = capacity_lines(row, AnsiStyler({}, enabled=color), "UTC", width=width,
                                           force_vertical=True, now_ms=NOW)
                    text = "\n".join(strip_ansi(line) for line in lines)
                    self.assertIn("0% used (100)", text)
                    self.assertIn("43% used (200)", text)
                    self.assertTrue(all(len(strip_ansi(line)) <= width for line in lines))
            text = report_text(replace(quotas(row), now_ms=NOW), width=width)
            self.assertIn("CCost today: 100", text)
            self.assertIn("CCost this month: 200", text)
            for unwanted in ("CCost in ", "configured local", "native reset window", "provider-attributed",
                             "Account CCost values", "Overlapping windows", "?"):
                self.assertNotIn(unwanted, text)

    def test_monthly_empty_today_precedes_remaining_and_report_does_not_duplicate_scope(self):
        native = replace(subscription("github-copilot"), quotas=(QuotaComponent(
            "Month", "fixed", remaining=D(200), limit=D(300), remaining_fraction=D("0.67"),
            unit="AI credits", reset_at_ms=NOW + 86_400_000),))
        row = project((native,), (), watch=True, observed_start_ms=DAY)[0]
        text = watch_text(replace(quotas(row), now_ms=NOW), width=160)
        self.assertIn("Today: 0 · Remaining:", text)
        self.assertNotIn("?", text)
        report = project((native,), (), observed_start_ms=MONTH)[0]
        text = report_text(replace(quotas(report), now_ms=NOW))
        self.assertEqual(1, text.count("CCost today: 0"))
        self.assertNotIn("Today: 0", text)

    def test_watch_zero_is_published_only_after_successful_history_and_failed_report_stays_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = MutableSource(replace(make_snapshot(), sessions=()))
            _, _, service, _ = make_service(directory, source, now_ms=NOW)
            self.addCleanup(service.close_accounts)
            native = subscription("openai")
            before = service.project_watch_accounts((native,))[0].accounts[0]
            self.assertTrue(all(value is None for _, value in before.ccost_scopes))
            service.watch_history_candidates(())
            service.publish_watch_history()
            after = service.project_watch_accounts((native,))[0].accounts[0]
            self.assertTrue(all(value is not None and value.ccost == 0 for _, value in after.ccost_scopes))
            report = service._account_history((native,), (), {}).accounts[0]
            self.assertTrue(all(value is not None and value.ccost == 0 for _, value in report.ccost_scopes))
            with patch.object(service, "prepare_roots", side_effect=OSError("history unavailable")):
                with self.assertRaisesRegex(OSError, "history unavailable"):
                    service._account_history((native,), (), {})

    def test_local_month_boundary_uses_stockholm_midnight_across_dst(self):
        self.assertEqual(int(datetime(2026, 9, 30, 22, tzinfo=timezone.utc).timestamp() * 1000), MONTH)
        self.assertEqual(14 * HOUR, NOW - DAY)  # 25-hour autumn day, not a fixed UTC day

    def test_watch_percentage_parentheses_and_daily_placement_preserve_width_and_status(self):
        row = project((subscription(),), (request("one", NOW),), watch=True)[0]
        for width in (35, 65, 120, 240):
            for color in (False, True):
                lines = capacity_lines(row, AnsiStyler({}, enabled=color), "UTC", width=width, now_ms=NOW, watch=True)
                text = "\n".join(strip_ansi(line) for line in lines)
                self.assertIn("0% used (100)", text)
                self.assertIn("43% used (100)", text)
                self.assertNotIn("not started", " ".join(text.split()))
                self.assertTrue(all(len(strip_ansi(line)) <= width for line in lines))
                self.assertNotIn("this month", text)
        native = replace(subscription("github-copilot"), quotas=(QuotaComponent("Month", "fixed", remaining=D(2483),
                         limit=D(7000), remaining_fraction=D("0.35"), unit="AI credits", reset_at_ms=NOW + 5 * 86_400_000),))
        monthly = project((native,), (request("copilot", NOW, provider="github-copilot"),), watch=True)[0]
        text = "\n".join(capacity_lines(monthly, AnsiStyler({}, enabled=False), "UTC", width=240, now_ms=NOW, watch=True))
        self.assertIn("4517/7000 · Today: 100 · Remaining:", text)
        no_percent = replace(row, account=replace(row.account, quotas=(replace(row.account.quotas[0], remaining_fraction=None),)))
        text = "\n".join(capacity_lines(no_percent, AnsiStyler({}, enabled=False), "UTC", width=240, now_ms=NOW, watch=True))
        self.assertIn("N/A · CCost: 100", text)
        self.assertNotIn("█", text)

    def test_prefix_queries_and_quota_updates_never_revalue_unchanged_history(self):
        entries = (request("one", NOW),)
        catalog = FakePricingProvider().catalog
        index = PeriodCCostIndex(entries, catalog.reference_valuation)
        self.assertEqual(D(100), index.cost("claude-code", "provider", DAY, NOW + 1).ccost)
        projector = WatchAccountProjection(AcquisitionMetrics())
        options = dict(now_ms=NOW, day_start_ms=DAY, month_start_ms=MONTH, timezone_id="UTC", workday_calendar="")
        first = projector.project((subscription(),), entries, catalog, **options)[0]
        with patch("src.analysis.period_ccost.comparison_cost", side_effect=AssertionError("revaluation")):
            second = projector.project((replace(subscription(), fetched_at_ms=NOW + 1),), entries, catalog, **options)[0]
        self.assertEqual(first.accounts[0].ccost_scopes, second.accounts[0].ccost_scopes)

    def test_watch_expands_history_for_week_then_retains_deleted_observations_without_month_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            source = MutableSource(make_snapshot())
            _, _, service, _ = make_service(directory, source, now_ms=4000)
            self.addCleanup(service.close_accounts)
            native = subscription("github-copilot")
            native = replace(native, quotas=(replace(native.quotas[1], reset_at_ms=5000),))
            service.project_watch_accounts((native,))
            roots = service.watch_history_candidates(service.session_catalog())
            service.watch_history_batch(roots)
            service.publish_watch_history()
            first = service.project_watch_accounts((native,))[0].accounts[0]
            self.assertGreater(dict(first.ccost_scopes)["weekly"].observed_requests, 0)
            source.snapshot = replace(source.snapshot, sessions=(), source_revision="deleted")
            service.watch_history_candidates(())
            service.publish_watch_history()
            after = service.project_watch_accounts((native,))[0].accounts[0]
            self.assertEqual(first.ccost_scopes, after.ccost_scopes)
            self.assertNotIn("this month", dict(after.ccost_scopes))

    def test_watch_week_and_report_month_acquire_independent_available_history_scopes(self):
        source = SyntheticMonthSource(0, 1, month_start_ms=MONTH)
        source.snapshots = {f"root-{index:04d}": make_root_snapshot(index, 1, month_start_ms=when - index * 60_000)
                            for index, when in enumerate((MONTH, NOW - 2 * 86_400_000, NOW - HOUR))}
        native = replace(subscription("github-copilot"), quotas=(subscription("github-copilot").quotas[1],))
        with tempfile.TemporaryDirectory() as directory:
            _, _, service, _ = make_service(directory, source, now_ms=NOW)
            service.config["timezone"] = "Europe/Stockholm"
            self.addCleanup(service.close_accounts)
            service.project_watch_accounts((native,))
            roots = service.watch_history_candidates(service.session_catalog())
            self.assertEqual({"root-0001", "root-0002"}, {root.session_id for root in roots})
            service.watch_history_batch(roots)
            service.publish_watch_history()
            watch_row = service.project_watch_accounts((native,))[0].accounts[0]
            self.assertEqual(2, dict(watch_row.ccost_scopes)["weekly"].observed_requests)
            ordered, activity = service._ordered_roots(service.session_catalog())
            report_row = service._account_history((native,), ordered, activity).accounts[0]
            self.assertEqual(3, dict(report_row.ccost_scopes)["this month"].observed_requests)
            self.assertEqual(dict(watch_row.ccost_scopes)["weekly"], dict(report_row.ccost_scopes)["weekly"])
            self.assertEqual(dict(watch_row.ccost_scopes)["today"], dict(report_row.ccost_scopes)["today"])


if __name__ == "__main__":
    unittest.main()
