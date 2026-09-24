import random
import unittest

from app.services.collection_delivery_forecast import delivery_forecast


class BayesianForecastTests(unittest.TestCase):
    def test_posterior_update_and_predictive_formulas(self):
        result = delivery_forecast(10, 100, 20, [(20, 30, 1)])
        self.assertEqual(result['posterior_shape'], 11)
        self.assertEqual(result['posterior_rate_days'], 121)
        self.assertAlmostEqual(result['mean_days'], 12.1)
        self.assertAlmostEqual(result['pending_breach_pct'], 100 * (121 / 131) ** 11)
        for key, p in [('predictive_low_days', .05), ('predictive_high_days', .95)]:
            self.assertAlmostEqual((121 / (121 + result[key])) ** 11, 1 - p)

    def test_censoring_increases_expected_duration(self):
        complete = delivery_forecast(10, 100, 0, [])
        censored = delivery_forecast(10, 100, 100, [(100, 120, 1)])
        self.assertGreater(censored['mean_days'], complete['mean_days'])
        self.assertEqual(censored['posterior_shape'], complete['posterior_shape'])

    def test_individual_targets_missing_targets_and_overdue(self):
        result = delivery_forecast(10, 100, 50, [(20, 10, 2), (10, None, 1)])
        self.assertEqual(result['pending_breach_pct'], 100)
        self.assertEqual(result['expected_breaches'], 2)
        self.assertEqual(result['observed_overdue_count'], 2)
        self.assertEqual(result['missing_target_count'], 1)
        self.assertEqual(result['pending_count'], 3)

    def test_target_boundary_and_age_dependence(self):
        younger = delivery_forecast(10, 100, 20, [(5, 20, 1)])
        older = delivery_forecast(10, 100, 20, [(15, 20, 1)])
        boundary = delivery_forecast(10, 100, 20, [(20, 20, 1)])
        self.assertLess(younger['pending_breach_pct'], older['pending_breach_pct'])
        self.assertEqual(boundary['pending_breach_pct'], 100)
        self.assertEqual(boundary['observed_overdue_count'], 0)

    def test_no_fabricated_predictions_or_risk(self):
        self.assertFalse(delivery_forecast(0, 0, 100, [(100, 10, 1)])['available'])
        self.assertFalse(delivery_forecast(4, 40, 0, [])['available'])
        self.assertFalse(delivery_forecast(5, 0, 0, [])['available'])
        for buckets in [[], [(5, None, 1)], [(5, -1, 1)]]:
            result = delivery_forecast(10, 100, 5, buckets)
            self.assertIsNone(result['pending_breach_pct'])

    def test_posterior_predictive_matches_simulation(self):
        rng = random.Random(42)
        result = delivery_forecast(10, 100, 20, [(20, 30, 1)])
        samples = [rng.expovariate(rng.gammavariate(11, 1 / 121)) for _ in range(30000)]
        self.assertAlmostEqual(sum(samples) / len(samples), result['mean_days'], delta=.3)
        exceed = sum(value > 10 for value in samples) / len(samples)
        self.assertAlmostEqual(exceed, result['pending_breach_pct'] / 100, delta=.015)


if __name__ == '__main__':
    unittest.main()
