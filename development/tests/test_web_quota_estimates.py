"""Decimal-only presentation tolerance, precision edges and honest small USD amounts."""
from decimal import Decimal as D, localcontext
from copy import deepcopy
import unittest

from development.tests.fixtures.watch_summary import estimated_allowances, summary_watch
from development.tests.integration.probe_web_live import check_estimate_quotas
from src.application.live_projection import project_live
from src.application.quota_estimates import estimate_amount, estimate_help, rounded_estimate, within_tolerance
from src.numbers import ccost_amount, ccost_display


class QuotaEstimateTests(unittest.TestCase):
    def test_coarsest_significant_digits_and_usd_after_credit_rounding(self):
        for raw, rounded, dollars in (
                ('613', '600', '$6.00'), ('2343', '2300', '$23.00'), ('49000', '50000', '$500.00'),
                ('51000', '50000', '$500.00'), ('52343', '50000', '$500.00'), ('250', '250', '$2.50'),
                ('149', '150', '$1.50'), ('0', '0', '$0.00'), ('350', '350', '$3.50'),
                ('550', '600', '$6.00'),
                ('245', '250', '$2.50'), ('1000', '1000', '$10.00'), ('999', '1000', '$10.00'),
                ('0.25', '.25', '<$0.01'), ('0.0000613', '.00006', '<$0.01'),
                ('1.49', '1.5', '$0.02')):
            value = D(raw)
            with self.subTest(raw=raw):
                self.assertEqual(D(rounded), rounded_estimate(value))
                if value:
                    self.assertLessEqual(abs(rounded_estimate(value) - value) / value, D('.1'))
                with ccost_display('credits'):
                    credits = estimate_amount(value)
                    self.assertEqual(D(rounded), D(credits))
                with ccost_display('usd'):
                    self.assertEqual(dollars, estimate_amount(value))
                with ccost_display('credits'):
                    self.assertEqual(credits, estimate_amount(value))

    def test_inclusive_exact_tolerance_and_just_over_without_context_drift(self):
        self.assertTrue(within_tolerance(D(1000), D(900)))
        self.assertFalse(within_tolerance(D('1000.000000000000000000000000001'), D(900)))
        # The exact nearest-one-digit threshold 200 / .9 repeats: straddle it
        # with supported finite Decimals, rather than claiming an exact finite input.
        with localcontext() as context:
            context.prec = 6
            self.assertEqual(D(200), rounded_estimate(D('222.22222222222222222222222222')))
            self.assertEqual(D(220), rounded_estimate(D('222.22222222222222222222222223')))
            self.assertEqual(D('6E+80'), rounded_estimate(D('6.13E+80')))
            self.assertEqual(D('6E-80'), rounded_estimate(D('6.13E-80')))

    def test_missing_invalid_nonfinite_negative_and_known_zero(self):
        for value in (None, '', 'invalid', True, D('-1'), D('NaN'), D('sNaN'), D('Infinity'), D('-Infinity')):
            with self.subTest(value=value):
                self.assertIsNone(rounded_estimate(value))
                self.assertEqual('?', estimate_amount(value))
                self.assertEqual('', estimate_help(value))
        self.assertEqual(D(0), rounded_estimate(D('-0')))

    def test_full_fractional_raw_help_and_small_currency_limit_do_not_change_generic_formatter(self):
        raw = D('613.1234567890123456789012345678')
        with ccost_display('credits'):
            self.assertIn(str(raw) + ' Credits', estimate_help(raw))
            self.assertEqual('600', estimate_amount(raw))
            self.assertEqual('614', ccost_amount(raw))
            self.assertEqual('0.00006', estimate_amount(D('.0000613')))
        with ccost_display('usd'):
            self.assertIn('613.1234567890123456789012345678 Credits ($6.13)', estimate_help(raw))
            self.assertIn('cannot retain the 10%', estimate_help(D('.25')))
            self.assertEqual('$6.13', ccost_amount(raw))

    def test_count_only_installation_oracle_covers_independent_fields_and_rejects_wrong_display(self):
        accounts = project_live(estimated_allowances(summary_watch())).to_json()['accounts']

        result = check_estimate_quotas(accounts)

        self.assertEqual({'checked_amounts': 7}, result)
        wrong = deepcopy(accounts)
        wrong['accounts'][0]['primary']['quota']['display_units']['credits']['ccost_remaining'] = '0'
        with self.assertRaisesRegex(AssertionError, 'estimate display tolerance'):
            check_estimate_quotas(wrong)


if __name__ == '__main__':
    unittest.main()
