"""Ephemeral cross-period facts still revalidate live roots and source bindings."""
from dataclasses import replace
import json
import time
import unittest
from unittest.mock import patch

from development.tests.fixtures.compact_reports import report_service, START
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.pricing.catalog import PricingCatalog
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports import token_mix_reuse
from src.web.jobs import ReportJobs


def ipc_report(sender, request):
    """Owned subprocess with fresh source/cache; only transferred facts can hit."""
    case = unittest.TestCase()
    try:
        source = SyntheticMonthSource(4, 2, month_start_ms=START)
        service = report_service(case, source)
        service.cache_token_mix_history = True
        if request.token_mix_evidence:
            service.token_mix_reuse = json.loads(request.token_mix_evidence)
        service.publish_token_mix_reuse = lambda value: sender.send(('token-mix-evidence', value))
        service.build_token_mix_history(scope=request.token_mix_scope)
        sender.send(('result', json.dumps(dict(error=None, source=dict(status='acquired'),
            view=dict(loads=source.load_count, hits=source.metrics.counts.get('token_mix_ephemeral_hits', 0)))).encode()))
    finally:
        case.doCleanups()
        sender.close()


class TokenMixReuseTests(unittest.TestCase):
    def service(self, roots=8):
        source = SyntheticMonthSource(roots, 3, month_start_ms=START)
        service = report_service(self, source)
        service.cache_token_mix_history = True
        return service, source

    def fresh(self, original):
        service = ReportService(selection=original.selection, pricing_provider=original.pricing_provider,
            account_provider=None, cache_repository=original.cache_repository, config=original.config,
            now_ms=original.now_ms, model_availability_source=original.model_availability_source,
            cache_token_mix_history=True)
        service.token_mix_reuse = json.loads(json.dumps(original.token_mix_reuse))
        return service

    def test_periods_use_transferred_facts_with_no_disposable_cache_reads_or_repricing(self):
        original, source = self.service(520)
        original.build_token_mix_history(scope='all')
        for scope in ('7-days', '30-days', 'all', 'today', 'month'):
            service = self.fresh(original)
            baseline = self.fresh(original)
            baseline.token_mix_reuse = None
            expected = baseline.build_token_mix_history(scope=scope)
            labels = []
            with patch.object(service.cache_repository, 'get_many', side_effect=AssertionError('cache reread')), \
                    patch.object(source, 'load_session_snapshot', side_effect=AssertionError('hydration')), \
                    patch.object(PricingCatalog, 'reference_category_valuation', side_effect=AssertionError('repricing')):
                report = service.build_token_mix_history(lambda label, _: labels.append(str(label)), scope=scope)
            self.assertEqual(scope, report.token_mix_period['period'])
            self.assertNotIn('Checking history cache', labels)
            self.assertEqual(expected, report)
        self.assertEqual(520, source.load_count)
        self.assertEqual(2600, source.metrics.counts['token_mix_ephemeral_hits'])

    def test_only_changed_new_roots_read_cache_and_deleted_roots_never_survive(self):
        original, source = self.service()
        original.build_token_mix_history(scope='all')
        source.snapshots['root-0001'] = replace(source.snapshots['root-0001'], source_revision='changed')
        del source.snapshots['root-0002']
        added = make_root_snapshot(99, 2, month_start_ms=START)
        source.snapshots[added.root.session_id] = added
        service = self.fresh(original)
        with patch.object(service.cache_repository, 'get_many', wraps=service.cache_repository.get_many) as reads:
            report = service.build_token_mix_history(scope='7-days')
        self.assertEqual(2, len(reads.call_args.args[1]))
        self.assertEqual(10, source.load_count)
        self.assertEqual(23, report.token_mix.request_count)
        self.assertNotIn('root-0002', service.token_mix_reuse['roots'])

    def test_expiry_timezone_calendar_day_and_pricing_change_disqualify_ephemeral_facts(self):
        original, _source = self.service()
        original.build_token_mix_history(scope='all')
        for change in ('expiry', 'timezone', 'day', 'pricing'):
            service = self.fresh(original)
            if change == 'expiry':
                service.token_mix_reuse['created'] -= 61
            elif change == 'timezone':
                service.config = {**service.config, 'timezone': 'Europe/Stockholm'}
            elif change == 'day':
                service.now_ms += 86400000
            else:
                service.pricing_provider.catalog = PricingCatalog(())
            with patch.object(service.cache_repository, 'get_many', wraps=service.cache_repository.get_many) as reads:
                service.build_token_mix_history(scope='all')
            self.assertTrue(reads.called, change)

    def test_availability_reprojects_without_repricing_or_reusing_an_old_period_result(self):
        original, source = self.service()
        original.build_token_mix_history(scope='all')
        service = self.fresh(original)
        service.model_availability_source.ids = ()
        with patch.object(service.cache_repository, 'get_many', side_effect=AssertionError('cache reread')):
            report = service.build_token_mix_history(scope='today')
        self.assertEqual((), report.model_token_mix)
        self.assertEqual(0, report.token_mix.request_count)
        self.assertEqual(8, source.load_count)
        self.assertEqual(2, service.model_availability_source.calls)

    def test_failed_validation_does_not_publish_new_evidence_and_recovers(self):
        service, source = self.service()
        service.build_token_mix_history(scope='all')
        publish = service.publish_token_mix_reuse = unittest.mock.Mock()
        with patch.object(source, 'get_session_tree_revisions', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                service.build_token_mix_history(scope='7-days')
        publish.assert_not_called()
        report = service.build_token_mix_history(scope='7-days')
        self.assertEqual(24, report.token_mix.request_count)
        self.assertEqual(8, source.load_count)

    def test_payload_byte_and_fact_limits_drop_reuse_not_product_results(self):
        service, _ = self.service()
        with patch.object(token_mix_reuse, 'MAX_BYTES', 1):
            report = service.build_token_mix_history(scope='all')
        self.assertEqual(24, report.token_mix.request_count)
        self.assertIsNone(service.token_mix_reuse)
        with patch.object(token_mix_reuse, 'MAX_FACTS', 1):
            report = service.build_token_mix_history(scope='all')
        self.assertEqual(24, report.token_mix.request_count)
        self.assertIsNone(service.token_mix_reuse)

    def test_real_owned_process_transfers_facts_only_inside_host_and_clears_on_close(self):
        jobs = ReportJobs(target=ipc_report)
        self.addCleanup(jobs.close)
        for scope, loads, hits in [('all', 4, 0), ('7-days', 0, 4), ('30-days', 0, 4)]:
            key = jobs.submit(ReportRequest(ReportKind.TOKEN_MIX, token_mix_scope=scope))
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                jobs.tick()
                value = jobs.snapshot(key)
                if value['status'] not in ('queued', 'running'):
                    break
                time.sleep(.01)
            self.assertEqual('complete', value['status'], value)
            self.assertEqual(dict(loads=loads, hits=hits), value['result']['view'])
            self.assertNotIn('token-mix-evidence', json.dumps(value))
        self.assertIsNotNone(jobs._token_mix_evidence)
        jobs.close()
        self.assertIsNone(jobs._token_mix_evidence)


if __name__ == '__main__':
    unittest.main()
