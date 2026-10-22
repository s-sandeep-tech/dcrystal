"""Structured public API context, without model-generated adjustments."""
import hashlib
import json
import math
import os
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import redis
from ..config import settings
from ..utils.logger import logger
from .sales_gemini_fallback import gemini_fallback

_redis_client = None
TZ = ZoneInfo('Asia/Kolkata')


def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
            db=settings.REDIS_DB, password=settings.REDIS_PASSWORD, decode_responses=True,
            socket_timeout=5, socket_connect_timeout=5)
    return _redis_client


def cached(key, ttl, fetch):
    try:
        value = get_redis().get(key)
        if value:
            return json.loads(value)
    except Exception:
        pass
    value = fetch()
    try:
        get_redis().setex(key, ttl, json.dumps(value))
    except Exception:
        pass
    return value


def get_json(url, params=None):
    request = Request(url + ('?' + urlencode(params) if params else ''),
                      headers={'User-Agent': 'DCrystal-SalesContext/1.0'})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def unavailable(message):
    return {'status': 'unavailable', 'message': message}


def weather(location, start, end):
    key = os.getenv('SALES_WEATHER_API_KEY')
    if not key:
        return unavailable('Weather: configure SALES_WEATHER_API_KEY (WeatherAPI.com).')
    # Branch labels are not reliable city names; require verified coordinates.
    points = json.loads(os.getenv('SALES_WEATHER_LOCATIONS_JSON', '{}'))
    point = points.get(location)
    if not point:
        return unavailable('Weather: no coordinates configured for this location; all-location weather is not aggregated.')
    lat, lon = float(point['lat']), float(point['lon'])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid coordinates')
    today = datetime.now(TZ).date()
    if start < today or start > today + timedelta(days=2):
        return unavailable('Weather: requested dates are outside the free three-day forecast window.')
    raw = cached(f'intelligence:weather:v1:{lat}:{lon}:{today}', 1800,
        lambda: get_json('https://api.weatherapi.com/v1/forecast.json',
                         {'key': key, 'q': f'{lat},{lon}', 'days': 3, 'aqi': 'no', 'alerts': 'no'}))
    rows = []
    for item in raw['forecast']['forecastday']:
        if start <= date.fromisoformat(item['date']) <= end:
            day = item['day']
            rows.append({'date': item['date'], 'min_temp_c': day['mintemp_c'],
                'max_temp_c': day['maxtemp_c'], 'rain_mm': day['totalprecip_mm'],
                'rain_chance_pct': day['daily_chance_of_rain'], 'condition': day['condition']['text']})
    if not rows:
        return unavailable('Weather: provider returned no dates in the requested window.')
    complete = len({r['date'] for r in rows}) == (end - start).days + 1
    return {'status': 'available' if complete else 'partial', 'provider': 'WeatherAPI.com',
        'latitude': lat, 'longitude': lon, 'days': rows,
        'message': 'Weather: ' + '; '.join(f"{r['date']}: {r['min_temp_c']}-{r['max_temp_c']} C, {r['rain_mm']} mm rain" for r in rows)
            + ('' if complete else '. Some requested dates are unavailable on the free plan.'),
        'source': {'title': 'WeatherAPI.com', 'url': 'https://www.weatherapi.com/'}}


def gold(start, end):
    if end < datetime.now(TZ).date():
        return unavailable('Gold: current spot prices are not substituted for historical prices.')
    raw = cached('intelligence:gold:v1:XAU:USD', 300,
                 lambda: get_json('https://api.gold-api.com/price/XAU'))
    price = float(raw['price'])
    if raw.get('symbol') != 'XAU' or raw.get('currency', 'USD') != 'USD' or not math.isfinite(price) or price <= 0:
        raise ValueError('Invalid gold quote')
    observed = datetime.fromisoformat(raw['updatedAt'].replace('Z', '+00:00'))
    if observed.tzinfo is None:
        raise ValueError('Gold quote has no timezone')
    return {'status': 'available', 'provider': 'Gold API', 'price': price, 'currency': 'USD',
        'unit': 'troy ounce', 'observed_at': observed.isoformat(), 'kind': 'spot_observation',
        'message': f'Gold spot: USD {price:,.2f}/troy ounce, updated {observed.isoformat()}. Not an Indian retail rate or a future price forecast.',
        'source': {'title': 'Gold API', 'url': 'https://gold-api.com/'}}


def festivals(start, end):
    key = os.getenv('SALES_CALENDARIFIC_API_KEY')
    if not key:
        return unavailable('Festivals: configure SALES_CALENDARIFIC_API_KEY. No dates are inferred.')
    rows, missing = [], []
    for year in range(start.year, end.year + 1):
        raw = cached(f'intelligence:festivals:v1:IN:{year}', 604800,
            lambda: get_json('https://calendarific.com/api/v2/holidays',
                             {'api_key': key, 'country': 'IN', 'year': year}))
        holidays = raw['response']['holidays']
        for label, aliases in [('Dhanteras', ('dhanteras', 'dhantrayodashi')),
                               ('Akshaya Tritiya', ('akshaya tritiya', 'akshaya trithiya', 'akshaya trutiya'))]:
            matches = [h for h in holidays if any(a in h['name'].lower() for a in aliases)]
            if not matches:
                missing.append(f'{label} {year}')
            for h in matches:
                festival_date = date.fromisoformat(h['date']['iso'][:10])
                rows.append({'name': label, 'date': festival_date.isoformat(),
                    'in_forecast_window': start <= festival_date <= end,
                    'days_from_forecast_start': (festival_date - start).days})
    return {'status': 'partial' if rows and missing else 'available' if rows else 'unavailable',
        'provider': 'Calendarific', 'events': rows, 'missing_events': missing,
        'message': 'Festival dates: ' + ('; '.join(f"{r['name']}: {r['date']}" for r in rows) or 'none verified')
            + ('. Not supplied by provider: ' + ', '.join(missing) if missing else ''),
        'source': {'title': 'Calendarific', 'url': 'https://calendarific.com/'}}


def sales_context(location, start_date, end_date, allow_gemini_fallback=False):
    start, end = date.fromisoformat(str(start_date)), date.fromisoformat(str(end_date))
    if end < start or (end - start).days > 7:
        return {**unavailable('Invalid external-context date range.'), 'affects_forecast': False}
    retrieved = datetime.now(TZ).isoformat()
    # Isolate both location and forecast period, and never reuse old Gemini entries.
    identity = [location, start.isoformat(), end.isoformat(), retrieved[:10],
                os.getenv('SALES_WEATHER_LOCATIONS_JSON', '{}'),
                bool(os.getenv('SALES_WEATHER_API_KEY')), bool(os.getenv('SALES_CALENDARIFIC_API_KEY')),
                allow_gemini_fallback, settings.GEMINI_MODEL if allow_gemini_fallback else None]
    digest = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    def fetch():
        parameters = {}
        for name, provider in [('weather', lambda: weather(location, start, end)),
                               ('gold', lambda: gold(start, end)), ('festivals', lambda: festivals(start, end))]:
            try:
                parameters[name] = provider()
            except Exception as exc:
                # Exceptions may contain credential-bearing URLs; log only their type.
                logger.warning('Sales context %s unavailable (%s)', name, type(exc).__name__)
                parameters[name] = unavailable(f'{name.capitalize()}: provider unavailable; no values inferred.')
        available = any(p['status'] in ('available', 'partial') for p in parameters.values())
        result = {'status': 'available' if available else 'unavailable',
            'summary': '\n\n'.join(p['message'] for p in parameters.values()),
            'message': 'External API parameters are unavailable.' if not available else '',
            'sources': [p['source'] for p in parameters.values() if 'source' in p],
            'parameters': parameters, 'location': location, 'start_date': start.isoformat(),
            'end_date': end.isoformat(), 'retrieved_at': retrieved, 'affects_forecast': False}
        missing = [name for name, value in parameters.items() if value['status'] != 'available']
        result['gemini_fallback'] = {'status': 'disabled' if not allow_gemini_fallback else 'not_needed'}
        if allow_gemini_fallback and missing:
            fallback = gemini_fallback(location, start.isoformat(), end.isoformat(), missing)
            result['gemini_fallback'] = fallback
            if fallback['status'] == 'available':
                result['status'] = 'available'
                result['message'] = ''
                result['summary'] += '\n\nGemini fallback (sourced commentary):\n' + fallback['summary']
                result['sources'].extend(fallback['sources'])
                result['search_suggestions_html'] = fallback.get('search_suggestions_html')
            else:
                result['summary'] += '\n\n' + fallback['message']
        return result
    return cached(f'intelligence:sales_context:api-v2:{digest}', 300, fetch)
