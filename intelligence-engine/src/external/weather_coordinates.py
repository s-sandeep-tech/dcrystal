"""Resolve a configured branch city to a unique Indian city/state match."""
import hashlib
import json
import math
import os
import unicodedata
from .sales_audit import audit

STATES = {
    'IN-AP': ('Andhra Pradesh',), 'IN-AR': ('Arunachal Pradesh',), 'IN-AS': ('Assam',),
    'IN-BR': ('Bihar',), 'IN-CT': ('Chhattisgarh',), 'IN-GA': ('Goa',), 'IN-GJ': ('Gujarat',),
    'IN-HR': ('Haryana',), 'IN-HP': ('Himachal Pradesh',), 'IN-JH': ('Jharkhand',),
    'IN-KA': ('Karnataka',), 'IN-KL': ('Kerala',), 'IN-MP': ('Madhya Pradesh',),
    'IN-MH': ('Maharashtra',), 'IN-MN': ('Manipur',), 'IN-ML': ('Meghalaya',),
    'IN-MZ': ('Mizoram',), 'IN-NL': ('Nagaland',), 'IN-OR': ('Odisha', 'Orissa'),
    'IN-PB': ('Punjab',), 'IN-RJ': ('Rajasthan',), 'IN-SK': ('Sikkim',),
    'IN-TN': ('Tamil Nadu',), 'IN-TS': ('Telangana',), 'IN-TR': ('Tripura',),
    'IN-UP': ('Uttar Pradesh',), 'IN-UT': ('Uttarakhand', 'Uttaranchal'),
    'IN-WB': ('West Bengal',), 'IN-DL': ('Delhi', 'National Capital Territory of Delhi'),
    'IN-CH': ('Chandigarh',), 'IN-JK': ('Jammu and Kashmir',), 'IN-LA': ('Ladakh',),
    'IN-PY': ('Puducherry', 'Pondicherry'), 'IN-AN': ('Andaman and Nicobar Islands',),
    'IN-LD': ('Lakshadweep',), 'IN-DH': ('Dadra and Nagar Haveli and Daman and Diu',),
}


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).casefold() if c.isalnum())


def point_valid(value):
    try:
        lat, lon = float(value['lat']), float(value['lon'])
        return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
    except (KeyError, TypeError, ValueError):
        return False


def resolve_coordinates(location, key):
    from .sales_context import get_json, get_redis
    def unavailable(reason):
        audit('skipped', provider='weatherapi_geocoding', reason=reason)
        return {'status': 'unavailable', 'message': f'Weather coordinates: {reason}.'}
    if normalized(location) in ('alllocations', 'india'):
        return unavailable('select a branch; all-location weather is not aggregated')
    points = json.loads(os.getenv('SALES_WEATHER_LOCATIONS_JSON', '{}'))
    if location in points:
        if not point_valid(points[location]):
            return unavailable('invalid configured coordinates')
        audit('coordinates_configured', provider='weatherapi_geocoding')
        return {'status': 'available', 'lat': float(points[location]['lat']),
                'lon': float(points[location]['lon']), 'method': 'configured'}
    mapping = json.loads(os.getenv('SALES_REGION_LOCATIONS_JSON', '{}')).get(location, {})
    city, state = mapping.get('city'), mapping.get('state_code')
    if not isinstance(city, str) or not city.strip() or state not in STATES:
        return unavailable('configure city and state_code in SALES_REGION_LOCATIONS_JSON')
    aliases = mapping.get('city_aliases', [])
    if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
        return unavailable('invalid city_aliases configuration')
    cities = {normalized(name) for name in [city] + aliases}
    states = {normalized(name) for name in STATES[state]}
    identity = json.dumps([city, state, aliases, 'India'], sort_keys=True)
    cache_key = 'intelligence:weather-coordinates:v1:' + hashlib.sha256(identity.encode()).hexdigest()
    try:
        saved = get_redis().get(cache_key)
        if saved:
            result = json.loads(saved)
            if result.get('status') == 'unavailable' or (point_valid(result) and
                    normalized(result.get('city')) in cities and normalized(result.get('state')) in states
                    and normalized(result.get('country')) == 'india'):
                audit('cache_hit', provider='weatherapi_geocoding', cache_key=cache_key)
                return result
    except Exception:
        pass
    audit('cache_miss', provider='weatherapi_geocoding', cache_key=cache_key)
    audit('geocode_lookup', provider='weatherapi_geocoding', city=city, state_code=state, country='India')
    try:
        candidates = get_json('https://api.weatherapi.com/v1/search.json', {'key': key, 'q': f'{city}, India'})
        if not isinstance(candidates, list):
            raise ValueError('Invalid geocoding response')
        matches = {}
        for item in candidates:
            if (not isinstance(item, dict) or normalized(item.get('name')) not in cities
                    or normalized(item.get('region')) not in states or normalized(item.get('country')) != 'india'
                    or not point_valid(item)):
                audit('geocode_rejected', provider='weatherapi_geocoding', reason='city_state_country_or_coordinates_mismatch')
                continue
            lat, lon = float(item['lat']), float(item['lon'])
            matches[(lat, lon)] = {'status': 'available', 'lat': lat, 'lon': lon,
                'city': item['name'], 'state': item['region'], 'country': item['country'], 'method': 'weatherapi_search'}
        if len(matches) == 1:
            result = next(iter(matches.values()))
            audit('geocode_resolved', provider='weatherapi_geocoding', city=result['city'], state=result['state'], country=result['country'])
        else:
            result = unavailable('ambiguous city matches' if matches else 'no matching Indian city and state returned')
        try:
            get_redis().setex(cache_key, 2592000 if result['status'] == 'available' else 300, json.dumps(result))
        except Exception:
            pass
        return result
    except Exception as error:
        audit('failure', provider='weatherapi_geocoding', error_type=type(error).__name__)
        return {'status': 'unavailable', 'message': 'Weather coordinates: search provider unavailable.'}
