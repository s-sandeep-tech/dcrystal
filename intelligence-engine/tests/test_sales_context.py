import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from src.external import sales_context as ctx


class MemoryCache:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self.data[key] = value


class SalesContextTests(unittest.TestCase):
    def setUp(self):
        self.cache = MemoryCache()
        self.redis = patch.object(ctx, 'get_redis', return_value=self.cache)
        self.redis.start()
        self.addCleanup(self.redis.stop)
        self.env = patch.dict('os.environ', {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_cache_isolates_dates_and_locations(self):
        with patch.object(ctx, 'gold', return_value=ctx.unavailable('not available')) as gold:
            ctx.sales_context('A', '2026-10-23', '2026-10-25')
            ctx.sales_context('A', '2026-10-23', '2026-10-25')
            ctx.sales_context('A', '2026-10-24', '2026-10-26')
            ctx.sales_context('B', '2026-10-23', '2026-10-25')
        self.assertEqual(gold.call_count, 3)
        self.assertEqual(len(self.cache.data), 3)

    def test_optional_fallback_only_requests_gaps_and_has_separate_cache(self):
        api_gold = {'status': 'available', 'message': 'Spot quote', 'price': 4000}
        fallback_result = {'status': 'available', 'summary': 'Verified weather context',
                           'sources': [{'title': 'Source', 'url': 'https://example.com'}]}
        with patch.object(ctx, 'gold', return_value=api_gold), \
             patch.object(ctx, 'gemini_fallback', return_value=fallback_result) as fallback:
            free = ctx.sales_context('A', '2026-10-23', '2026-10-25')
            fallback.assert_not_called()
            enabled = ctx.sales_context('A', '2026-10-23', '2026-10-25', True)
            ctx.sales_context('A', '2026-10-23', '2026-10-25', True)
            again = ctx.sales_context('A', '2026-10-23', '2026-10-25')
        fallback.assert_called_once_with('A', '2026-10-23', '2026-10-25', ['weather', 'festivals'])
        self.assertEqual(free['gemini_fallback']['status'], 'disabled')
        self.assertEqual(again, free)
        self.assertEqual(enabled['parameters']['gold'], api_gold)
        self.assertFalse(enabled['affects_forecast'])

    def test_complete_apis_skip_gemini_even_when_enabled(self):
        result = {'status': 'available', 'message': 'API result'}
        with patch.object(ctx, 'gold', return_value=result), \
             patch.object(ctx, 'weather', return_value=result), \
             patch.object(ctx, 'festivals', return_value=result), \
             patch.object(ctx, 'gemini_fallback') as fallback:
            context = ctx.sales_context('A', '2026-10-23', '2026-10-25', True)
        fallback.assert_not_called()
        self.assertEqual(context['gemini_fallback']['status'], 'not_needed')

    def test_failed_fallback_keeps_api_results(self):
        with patch.object(ctx, 'gold', return_value={'status': 'available', 'message': 'Spot quote'}), \
             patch.object(ctx, 'gemini_fallback', return_value=ctx.unavailable('No Gemini key')):
            result = ctx.sales_context('A', '2026-10-23', '2026-10-25', True)
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['gemini_fallback']['status'], 'unavailable')

    def test_provider_failure_does_not_expose_credentials_or_fail_others(self):
        with patch.object(ctx, 'gold', side_effect=ValueError('https://provider/?key=secret')), \
             patch.object(ctx, 'logger') as logger:
            result = ctx.sales_context('A', '2026-10-23', '2026-10-25')
        self.assertEqual(result['parameters']['gold']['status'], 'unavailable')
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('secret', str(logger.warning.call_args))
        self.assertFalse(result['affects_forecast'])

    def test_weather_filters_dates_and_reports_partial_coverage(self):
        today = datetime.now(ctx.TZ).date()
        raw = {'forecast': {'forecastday': [
            {'date': (today + timedelta(days=i)).isoformat(), 'day': {
                'mintemp_c': 22, 'maxtemp_c': 30, 'totalprecip_mm': 2,
                'daily_chance_of_rain': 40, 'condition': {'text': 'Rain'}}} for i in range(3)]}}
        with patch.dict('os.environ', {'SALES_WEATHER_API_KEY': 'test',
                  'SALES_WEATHER_LOCATIONS_JSON': '{"A":{"lat":10,"lon":76}}'}), \
             patch.object(ctx, 'get_json', return_value=raw):
            result = ctx.weather('A', today + timedelta(days=1), today + timedelta(days=3))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['days']), 2)
        self.assertNotIn(today.isoformat(), [r['date'] for r in result['days']])

    def test_festivals_do_not_invent_missing_dates(self):
        raw = {'response': {'holidays': [{'name': 'Dhanteras', 'date': {'iso': '2026-11-06'}}]}}
        with patch.dict('os.environ', {'SALES_CALENDARIFIC_API_KEY': 'test'}), \
             patch.object(ctx, 'get_json', return_value=raw) as fetch:
            result = ctx.festivals(ctx.date(2026, 10, 23), ctx.date(2026, 10, 25))
            ctx.festivals(ctx.date(2026, 11, 1), ctx.date(2026, 11, 3))
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['missing_events'], ['Akshaya Tritiya 2026'])
        self.assertFalse(result['events'][0]['in_forecast_window'])

    def test_gold_is_observation_not_forecast_and_rejects_historical_substitution(self):
        today = datetime.now(ctx.TZ).date()
        raw = {'symbol': 'XAU', 'currency': 'INR', 'price': 380000, 'updatedAt': '2026-10-22T08:00:00Z'}
        with patch.object(ctx, 'get_json', return_value=raw) as fetch:
            result = ctx.gold(today, today + timedelta(days=2))
            past = ctx.gold(today - timedelta(days=3), today - timedelta(days=1))
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result['kind'], 'spot_observation')
        self.assertEqual(result['currency'], 'INR')
        self.assertEqual(result['unit'], 'gram')
        self.assertAlmostEqual(result['price'], 380000 / 31.1034768)
        self.assertEqual(result['source_price'], 380000)
        self.assertEqual(fetch.call_args.args[0], 'https://api.gold-api.com/price/XAU/INR')
        self.assertEqual(past['status'], 'unavailable')

    def test_gold_rejects_wrong_or_missing_currency(self):
        today = datetime.now(ctx.TZ).date()
        for currency in ('USD', None):
            with patch.object(ctx, 'get_json', return_value={'symbol': 'XAU', 'price': 4000,
                    'currency': currency, 'updatedAt': '2026-10-22T08:00:00Z'}):
                with self.assertRaises(ValueError):
                    ctx.gold(today, today)


if __name__ == '__main__':
    unittest.main()
