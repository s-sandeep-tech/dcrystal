import unittest
from unittest.mock import patch
import pandas as pd
from src.models.sales_turnover import forecast_daily
from src.external.sales_context import sales_context


class SalesTurnoverTests(unittest.TestCase):
    def history(self):
        return [{'ds': d.date(), 'y': 1000 + d.dayofweek * 100}
                for d in pd.date_range('2026-04-01', periods=100)]

    def test_three_day_forecast_preserves_dates_and_weekday_pattern(self):
        result = forecast_daily(self.history(), use_prophet=False)
        self.assertEqual(len(result['forecast']), 3)
        self.assertEqual(result['forecast'][0]['ds'], '2026-07-10')
        self.assertEqual(result['forecast'][2]['ds'], '2026-07-12')
        self.assertEqual(result['metrics']['backtest_mae'], 0)
        self.assertEqual(result['three_day_total'], 4500)

    def test_missing_days_and_negative_net_sales_are_preserved(self):
        rows = self.history()
        rows.pop(10)
        rows[15]['y'] = -200
        result = forecast_daily(rows, use_prophet=False)
        self.assertEqual(result['metrics']['zero_filled_days'], 1)
        self.assertIn(-200, [r['y'] for r in result['history']])

    def test_insufficient_duplicate_or_nonfinite_history_rejected(self):
        for rows in (self.history()[:20], self.history() + [self.history()[0]],
                     self.history()[:-1] + [{'ds': '2026-07-09', 'y': float('nan')}]):
            with self.assertRaises(ValueError):
                forecast_daily(rows, use_prophet=False)

    def test_prophet_failure_keeps_validated_baseline(self):
        with patch('src.models.sales_turnover.prophet_forecast', side_effect=RuntimeError('unavailable')):
            result = forecast_daily(self.history())
        self.assertEqual(result['metrics']['engine'], 'weekday_average')
        self.assertIn('prophet', result['metrics']['unavailable_methods'])

    def test_external_context_without_credentials_is_unavailable(self):
        with patch('src.external.sales_context.settings') as config:
            config.active_gemini_api_key = None
            result = sales_context('India', '2026-10-23', '2026-10-25')
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('impact_multiplier', result)


if __name__ == '__main__':
    unittest.main()
