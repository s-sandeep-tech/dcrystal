import unittest
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from src.models.sales_regressors import FeatureIndex, observation_forecast
from src.models.sales_turnover import forecast_daily


class ObservationTests(unittest.TestCase):
    def fixture(self):
        days = pd.date_range('2026-01-01', periods=124)
        signal = np.random.default_rng(7).uniform(0, 20, len(days))
        features = [{'id': str(i), 'scope': 'branch:20', 'feature_group': 'weather_observations',
            'feature_date': day.date(), 'available_at': (day + timedelta(days=1)).to_pydatetime().replace(tzinfo=timezone.utc),
            'values_json': {'rain_mm': signal[i], 'max_temp_c': 30}} for i, day in enumerate(days)]
        sales = pd.Series([10000 - 300 * signal[max(0, i - 2)] for i in range(120)], index=days[:120])
        return sales, features

    def test_observation_same_day_or_after_origin_never_used(self):
        _, rows = self.fixture()
        origin = datetime(2026, 1, 10, 5, tzinfo=timezone.utc)
        index = FeatureIndex(rows)
        values, ids = index.observations(origin, ['weather_observations'])
        self.assertEqual(ids, ['8'])
        rows[9]['available_at'] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        rows[10]['available_at'] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(FeatureIndex(rows).observations(origin, ['weather_observations']), (values, ids))

    def test_retrieved_today_is_not_treated_as_available_in_past(self):
        sales, rows = self.fixture()
        for row in rows:
            row['available_at'] = datetime(2026, 10, 23, tzinfo=timezone.utc)
        result = forecast_daily([{'ds': d.date(), 'y': y} for d, y in sales.items()],
            use_prophet=False, feature_rows=rows, forecast_origin=datetime(2026, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(result['metrics']['external_features_used'], [])

    def test_holdout_values_do_not_change_prediction(self):
        sales, rows = self.fixture()
        train = sales.iloc[:-3]
        origin = datetime.combine((train.index[-1] + timedelta(days=1)).date(), datetime.min.time(), timezone.utc)
        before = observation_forecast(train, FeatureIndex(rows), ['weather_observations'], origin)
        cutoff = origin.date()
        changed = [{**r, 'values_json': {'rain_mm': 99999, 'max_temp_c': 99999}}
                   if r['feature_date'] >= cutoff else r for r in rows]
        after = observation_forecast(train, FeatureIndex(changed), ['weather_observations'], origin)
        np.testing.assert_array_equal(before, after)

    def test_each_horizon_uses_a_historical_origin(self):
        sales, rows = self.fixture()
        class RecordingIndex(FeatureIndex):
            def observations(self, origin, groups):
                self.origins.append(origin)
                return super().observations(origin, groups)
        index = RecordingIndex(rows); index.origins = []
        origin = datetime(2026, 5, 1, tzinfo=timezone.utc)
        result = observation_forecast(sales, index, ['weather_observations'], origin)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(t <= origin for t in index.origins))
        self.assertGreater(len(set(index.origins)), 100)

    def test_legacy_nasa_is_not_mistaken_for_a_weather_forecast(self):
        _, rows = self.fixture()
        row = {**rows[0], 'feature_group': 'weather', 'provider': 'NASA POWER historical observations (UTC)'}
        index = FeatureIndex([row])
        self.assertEqual(index.rows[0]['feature_group'], 'weather_observations')
        self.assertEqual(row['feature_group'], 'weather')

    def test_valid_lagged_history_can_win_backtesting(self):
        sales, rows = self.fixture()
        # Persistent regimes remain useful beyond the first forecast horizon.
        signal = np.repeat(np.random.default_rng(31).uniform(1, 20, 25), 5)
        for i, row in enumerate(rows):
            row['values_json']['rain_mm'] = float(signal[i])
        sales[:] = [10000 - 300 * signal[max(0, i - 2)] for i in range(len(sales))]
        result = forecast_daily([{'ds': d.date(), 'y': y} for d, y in sales.items()],
            use_prophet=False, feature_rows=rows,
            forecast_origin=datetime(2026, 5, 1, tzinfo=timezone.utc))
        metrics = result['metrics']
        self.assertEqual(metrics['engine'], 'external_observed_weather')
        self.assertEqual(metrics['external_features_used'], ['weather_observations'])
        self.assertLess(metrics['backtest_mae'], metrics['baseline_mae'] * .95)


if __name__ == '__main__':
    unittest.main()
