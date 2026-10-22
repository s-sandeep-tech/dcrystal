import json
import unittest
from unittest.mock import patch
from src.external.weather_coordinates import resolve_coordinates


class Cache:
    def __init__(self):
        self.values = {}
        self.ttls = []

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls.append(ttl)


class CoordinateTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict('os.environ', {'SALES_REGION_LOCATIONS_JSON':
            '{"GUWAHATI":{"city":"Guwahati","state_code":"IN-AS"}}'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.cache = Cache()
        self.redis = patch('src.external.sales_context.get_redis', return_value=self.cache)
        self.redis.start()
        self.addCleanup(self.redis.stop)
        self.match = {'name': 'Guwahati', 'region': 'Assam', 'country': 'India', 'lat': 26.18, 'lon': 91.75}

    def test_validated_lookup_is_cached_and_logs_do_not_contain_key(self):
        with patch('src.external.sales_context.get_json', return_value=[self.match]) as request, \
             patch('src.external.weather_coordinates.audit') as audit:
            first = resolve_coordinates('GUWAHATI', 'secret-key')
            second = resolve_coordinates('GUWAHATI', 'secret-key')
        request.assert_called_once()
        self.assertEqual(first, second)
        self.assertEqual(first['method'], 'weatherapi_search')
        self.assertEqual(self.cache.ttls, [2592000])
        self.assertNotIn('secret-key', str(audit.call_args_list))

    def test_wrong_city_state_country_or_invalid_coordinates_rejected(self):
        candidates = [{**self.match, **changes} for changes in [
            {'name': 'Another city'}, {'region': 'Kerala'}, {'country': 'Bangladesh'}, {'lat': 95}, {'lon': float('nan')}]]
        with patch('src.external.sales_context.get_json', return_value=candidates) as request:
            self.assertEqual(resolve_coordinates('GUWAHATI', 'key')['status'], 'unavailable')
            resolve_coordinates('GUWAHATI', 'key')
        request.assert_called_once()
        self.assertEqual(self.cache.ttls, [300])

    def test_ambiguous_matches_are_not_selected(self):
        with patch('src.external.sales_context.get_json', return_value=[self.match, {**self.match, 'lat': 26.2}]):
            self.assertIn('ambiguous', resolve_coordinates('GUWAHATI', 'key')['message'])

    def test_configured_coordinates_take_priority_and_all_locations_is_skipped(self):
        with patch.dict('os.environ', {'SALES_WEATHER_LOCATIONS_JSON': '{"GUWAHATI":{"lat":26.18,"lon":91.75}}'}), \
             patch('src.external.sales_context.get_json') as request:
            self.assertEqual(resolve_coordinates('GUWAHATI', 'key')['method'], 'configured')
            self.assertEqual(resolve_coordinates('All locations', 'key')['status'], 'unavailable')
        request.assert_not_called()

    def test_missing_region_and_provider_failure_remain_unavailable(self):
        with patch('src.external.sales_context.get_json', side_effect=ValueError('secret URL')) as request:
            self.assertEqual(resolve_coordinates('UNMAPPED', 'key')['status'], 'unavailable')
            request.assert_not_called()
            self.assertEqual(resolve_coordinates('GUWAHATI', 'key')['status'], 'unavailable')

    def test_redis_outage_does_not_block_lookup(self):
        with patch('src.external.sales_context.get_redis', side_effect=ConnectionError), \
             patch('src.external.sales_context.get_json', return_value=[self.match]):
            self.assertEqual(resolve_coordinates('GUWAHATI', 'key')['status'], 'available')


if __name__ == '__main__':
    unittest.main()
