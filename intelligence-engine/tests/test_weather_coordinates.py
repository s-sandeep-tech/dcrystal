import json
import unittest
from unittest.mock import patch
from src.external.weather_coordinates import resolve_coordinates
from src.external.sales_audit import fetch_scope


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
    def test_database_metadata_resolves_branch_without_env_mapping(self):
        token = fetch_scope.set({'branch_details': {'branch_id': 2,
            'location_name': 'THRISSUR ROUND', 'state_name': 'KERALA'}})
        try:
            with patch.dict('os.environ', {}, clear=True), \
                 patch('src.external.sales_context.get_json', return_value=[
                    {'name': 'Thrissur', 'region': 'Kerala', 'country': 'India', 'lat': 10.5, 'lon': 76.2}]) as request:
                result = resolve_coordinates('THRISSUR ROUND', 'key')
            self.assertEqual(result['status'], 'available')
            self.assertEqual(request.call_args.args[1]['q'], 'THRISSUR, India')
        finally:
            fetch_scope.reset(token)

    def test_database_state_wins_over_environment_mapping(self):
        token = fetch_scope.set({'branch_details': {'branch_id': 140,
            'location_name': 'GUWAHATI', 'state_name': 'Kerala'}})
        try:
            with patch('src.external.sales_context.get_json', return_value=[self.match]):
                self.assertEqual(resolve_coordinates('GUWAHATI', 'key')['status'], 'unavailable')
        finally:
            fetch_scope.reset(token)

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
