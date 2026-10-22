import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.models.sales_turnover import forecast_daily
from src.models.sales_regressors import FeatureIndex
from src.external.sales_features import context_features, validate_feature


class FeatureTests(unittest.TestCase):
    def fixture(self):
        dates = pd.date_range('2026-01-01', periods=123)
        rain = np.random.default_rng(42).uniform(0, 30, 123)
        rows = [{'ds': d.date(), 'y': 10000 + 100 * d.dayofweek - 200 * rain[i]} for i, d in enumerate(dates[:120])]
        features = [{'id': str(i), 'scope': 'branch:2', 'feature_group': 'weather', 'feature_date': d.date(),
                     'available_at': (d - timedelta(days=4)).to_pydatetime().replace(tzinfo=timezone.utc),
                     'values_json': {'rain_mm': rain[i], 'max_temp_c': 30}} for i, d in enumerate(dates)]
        return rows, features

    def test_weather_can_change_prediction_after_backtest_improvement(self):
        rows, features = self.fixture()
        result = forecast_daily(rows, use_prophet=False, feature_rows=features)
        self.assertEqual(result['metrics']['engine'], 'external_weather')
        self.assertLess(result['metrics']['backtest_mae'], result['metrics']['baseline_mae'] * .95)
        self.assertEqual(result['metrics']['external_features_used'], ['weather'])

    def test_future_information_is_excluded_and_baseline_retained(self):
        rows, features = self.fixture()
        for feature in features:
            feature['available_at'] = datetime(2027, 1, 1, tzinfo=timezone.utc)
        result = forecast_daily(rows, use_prophet=False, feature_rows=features)
        self.assertEqual(result['metrics']['engine'], 'weekday_average')
        self.assertEqual(result['metrics']['external_features_used'], [])

    def test_festival_features_can_be_selected(self):
        rows, features = self.fixture()
        for feature in features:
            strength = feature['values_json']['rain_mm'] / 30
            feature['feature_group'] = 'festivals'
            feature['values_json'] = {'dhanteras_proximity': strength, 'akshaya_proximity': 0}
        result = forecast_daily(rows, use_prophet=False, feature_rows=features)
        self.assertEqual(result['metrics']['engine'], 'external_festivals')

    def test_gold_candidate_is_evaluated_with_lagged_history(self):
        rows, features = self.fixture()
        for i, feature in enumerate(features):
            feature['feature_group'] = 'gold'
            feature['feature_date'] -= timedelta(days=1)
            feature['available_at'] = datetime.combine(feature['feature_date'], datetime.min.time(), tzinfo=timezone.utc)
            feature['values_json'] = {'price_usd_oz': 3000 + i * 10}
        for i, row in enumerate(rows):
            row['y'] = 10000 + i * 500
        result = forecast_daily(rows, use_prophet=False, feature_rows=features)
        self.assertIn('external_gold', result['metrics']['candidate_mae'])
        self.assertEqual(result['metrics']['engine'], 'external_gold')

    def test_missing_forecast_weather_falls_back(self):
        rows, features = self.fixture()
        result = forecast_daily(rows, use_prophet=False, feature_rows=features[:120])
        self.assertEqual(result['metrics']['engine'], 'weekday_average')
        self.assertIn('could not produce', result['metrics']['fallback_reason'])

    def test_gold_uses_only_known_lagged_prices(self):
        row = {'id': 'g', 'feature_group': 'gold', 'feature_date': '2026-01-01',
               'available_at': '2026-01-01T12:00:00+00:00', 'values_json': {'price_usd_oz': 4000}}
        index = FeatureIndex([row])
        origin = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.assertEqual(index.vector(pd.Timestamp('2026-01-03'), origin, ['gold'], future=True), [4000])
        self.assertIsNone(index.vector(pd.Timestamp('2026-01-01'), origin, ['gold']))

    def test_fetched_calendar_is_not_backdated(self):
        context = {'retrieved_at': '2026-10-22T12:00:00+00:00', 'parameters': {'festivals': {
            'status': 'available', 'provider': 'Calendarific', 'source': {'url': 'https://calendarific.com'},
            'events': [{'name': 'Dhanteras', 'date': '2026-11-06'}, {'name': 'Akshaya Tritiya', 'date': '2026-04-19'}]}}}
        rows = context_features(context, 2)
        self.assertEqual(len(rows), 365)
        self.assertTrue(all(r['available_at'].month == 10 for r in rows))
        index = FeatureIndex(rows)
        self.assertIsNone(index.vector(pd.Timestamp('2026-04-19'), datetime(2026, 4, 1, tzinfo=timezone.utc), ['festivals']))

    def test_fetch_logs_exclude_query_keys(self):
        from src.external.sales_context import get_json
        with patch('src.external.sales_context.urlopen', side_effect=ValueError('secret')), \
             patch('src.external.sales_context.audit') as audit:
            with self.assertRaises(ValueError):
                get_json('https://provider.example/forecast', {'key': 'secret'})
        self.assertNotIn('secret', str(audit.call_args_list))
        self.assertEqual(audit.call_args_list[0].args[0], 'request')
        self.assertEqual(audit.call_args_list[-1].args[0], 'failure')


if __name__ == '__main__':
    unittest.main()
