import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from src.external.regional_calendar import calendars, validate_fallback
from src.external.sales_features import context_features
from src.models.sales_turnover import forecast_daily
from src.models.sales_regressors import FeatureIndex
import numpy as np
import pandas as pd


class RegionalCalendarTests(unittest.TestCase):
    def test_free_api_precedes_optional_fallback_and_preserves_successful_group(self):
        from src.external import sales_context as ctx
        calendar = {'regional_festivals': {'status': 'available', 'message': 'API dates',
                        'events': [], 'coverage_years': [2026]},
                    'weddings': {'status': 'unavailable', 'message': 'Missing wedding calendar', 'events': []}}
        supplement = {'weddings': {'status': 'available', 'message': 'Sourced wedding dates',
                        'events': [], 'coverage_years': [2026], 'provider': 'Gemini grounded calendar'}}
        api = {'status': 'available', 'message': 'API value'}
        order = []
        def fetch_calendar(*args):
            order.append('api')
            return calendar
        def fetch_fallback(*args):
            order.append('fallback')
            return supplement
        with patch.dict('os.environ', {}, clear=True), \
             patch.object(ctx, 'cached', side_effect=lambda key, ttl, fetch: fetch()), \
             patch.object(ctx, 'weather', return_value=api), patch.object(ctx, 'gold', return_value=api), \
             patch.object(ctx, 'festivals', return_value=api), patch.object(ctx, 'calendars', side_effect=fetch_calendar), \
             patch.object(ctx, 'calendar_fallback', side_effect=fetch_fallback) as fallback:
            ctx.sales_context('A', '2026-10-23', '2026-10-25', False)
            fallback.assert_not_called()
            result = ctx.sales_context('A', '2026-10-23', '2026-10-25', True)
        self.assertEqual(order, ['api', 'api', 'fallback'])
        self.assertEqual(fallback.call_args.args[-1], ['weddings'])
        self.assertEqual(result['parameters']['regional_festivals']['message'], 'API dates')
        self.assertEqual(result['parameters']['weddings']['provider'], 'Gemini grounded calendar')

    def test_api_filters_region_and_weddings_remain_missing(self):
        raw = {'response': {'holidays': [
            {'name': 'Onam', 'date': {'iso': '2026-08-26'}},
            {'name': 'Vishu', 'date': {'iso': '2026-04-14'}}]}}
        env = {'SALES_REGION_LOCATIONS_JSON': '{"THRISSUR ROUND":{"state_code":"IN-KL"}}',
               'SALES_CALENDARIFIC_API_KEY': 'test'}
        with patch.dict('os.environ', env, clear=True), \
             patch('src.external.sales_context.cached', side_effect=lambda key, ttl, fetch: fetch()), \
             patch('src.external.sales_context.get_json', return_value=raw) as fetch:
            result = calendars('THRISSUR ROUND', date(2026, 10, 23), date(2026, 10, 25))
        self.assertEqual(fetch.call_args.args[1]['location'], 'in-kl')
        self.assertEqual(result['regional_festivals']['coverage_years'], [2026])
        self.assertEqual(result['weddings']['status'], 'unavailable')

    def test_unknown_region_does_not_call_calendar_api(self):
        with patch.dict('os.environ', {}, clear=True), patch('src.external.sales_context.get_json') as fetch:
            result = calendars('All locations', date(2026, 1, 1), date(2026, 1, 3))
        fetch.assert_not_called()
        self.assertEqual(result['weddings']['status'], 'unavailable')

    def test_fallback_rejects_wrong_region_and_unmatched_source(self):
        event = {'name': 'Wedding season', 'kind': 'wedding_season', 'date': '2026-11-01',
                 'end_date': '2026-11-30', 'region': 'IN-KL', 'source_url': 'https://example.com/calendar'}
        sources = [{'url': event['source_url']}]
        payload = {'weddings': {'events': [event], 'coverage': [
            {'year': 2026, 'complete_year': True, 'source_url': event['source_url']}]}}
        self.assertEqual(validate_fallback(payload, sources, 'IN-KL', [2026])['weddings']['status'], 'available')
        self.assertEqual(validate_fallback(payload, sources, 'IN-AS', [2026]), {})
        self.assertEqual(validate_fallback(payload, [], 'IN-KL', [2026]), {})

    def test_partial_fallback_is_not_expanded_into_training_features(self):
        value = {'status': 'partial', 'provider': 'fixture', 'region': 'IN-KL',
                 'source': {'url': 'https://example.com'}, 'coverage_years': [],
                 'events': [{'name': 'Wedding date', 'kind': 'wedding_date', 'date': '2026-11-06'}]}
        rows = context_features({'retrieved_at': '2026-10-22T08:00:00+00:00', 'parameters': {'weddings': value}}, 2)
        self.assertEqual(rows, [])

    def test_wedding_features_and_point_in_time_availability(self):
        value = {'status': 'available', 'provider': 'fixture', 'region': 'IN-KL',
                 'source': {'url': 'https://example.com'}, 'coverage_years': [2026],
                 'events': [{'name': 'Wedding date', 'kind': 'wedding_date', 'date': '2026-11-06'},
                            {'name': 'Wedding season', 'kind': 'wedding_season', 'date': '2026-11-01', 'end_date': '2026-11-30'}]}
        rows = context_features({'retrieved_at': '2026-10-22T08:00:00+00:00', 'parameters': {'weddings': value}}, 2)
        index = FeatureIndex(rows)
        row = next(r for r in rows if r['feature_date'] == date(2026, 11, 1))
        self.assertEqual(row['values_json'], {'wedding_season': 1, 'days_to_wedding': 5, 'wedding_dates_next_7': 1})
        self.assertIsNone(index.vector(pd.Timestamp('2026-04-01'), datetime(2026, 3, 31, tzinfo=timezone.utc), ['weddings']))
        self.assertEqual(context_features({'retrieved_at': '2026-10-22T08:00:00+00:00', 'parameters': {'weddings': value}}, None), [])

    def test_calendar_models_can_win_backtesting(self):
        dates = pd.date_range('2026-01-01', periods=123)
        signal = np.random.default_rng(42).integers(0, 2, 123)
        sales = [{'ds': d.date(), 'y': 10000 + 5000 * signal[i]} for i, d in enumerate(dates[:120])]
        for group, values, method in [
            ('regional_festivals', lambda v: {'festival_day': v, 'festival_lead_7': 0, 'festival_after_7': 0}, 'external_regional_festivals'),
            ('weddings', lambda v: {'wedding_season': v, 'days_to_wedding': 31, 'wedding_dates_next_7': 0}, 'external_weddings')]:
            features = [{'id': str(i), 'feature_group': group, 'feature_date': d.date(),
                'available_at': datetime(2025, 12, 1, tzinfo=timezone.utc), 'values_json': values(int(signal[i]))}
                for i, d in enumerate(dates)]
            result = forecast_daily(sales, use_prophet=False, feature_rows=features)
            self.assertEqual(result['metrics']['engine'], method)


if __name__ == '__main__':
    unittest.main()
