"""Region-specific calendars and strict validation of sourced calendar fallback."""
import json
import os
from datetime import date
from urllib.parse import urlsplit
from .sales_audit import audit

CATALOG = {
    'IN-KL': {'Onam': ('onam', 'thiruvonam'), 'Vishu': ('vishu',)},
    'IN-TN': {'Pongal': ('pongal',), 'Tamil New Year': ('tamil new year', 'puthandu')},
    'IN-AS': {'Bihu': ('bihu',)},
    'IN-WB': {'Durga Puja': ('durga puja',)},
    'IN-KA': {'Ugadi': ('ugadi',), 'Dasara': ('dasara', 'dussehra')},
    'IN-AP': {'Ugadi': ('ugadi',), 'Sankranti': ('sankranti',)},
    'IN-TS': {'Ugadi': ('ugadi',), 'Bathukamma': ('bathukamma',)},
    'IN-MH': {'Gudi Padwa': ('gudi padwa',), 'Ganesh Chaturthi': ('ganesh chaturthi',)},
    'IN-GJ': {'Navratri': ('navratri',), 'Uttarayan': ('uttarayan', 'makar sankranti')},
    'IN-PB': {'Baisakhi': ('baisakhi', 'vaisakhi')},
}


def region_for(location):
    region = json.loads(os.getenv('SALES_REGION_LOCATIONS_JSON', '{}')).get(location)
    if not isinstance(region, dict) or region.get('state_code') not in CATALOG:
        return None
    return {'state_code': region['state_code'], 'city': region.get('city', location),
            'timezone': 'Asia/Kolkata'}


def calendars(location, start, end):
    from .sales_context import cached, get_json
    region = region_for(location)
    def missing(message):
        return {'status': 'unavailable', 'message': message, 'events': [], 'coverage_years': []}
    if not region:
        audit('skipped', provider='regional_calendar', reason='missing_or_unsupported_region')
        return {g: missing('Regional calendar: configure SALES_REGION_LOCATIONS_JSON for this branch.')
                for g in ('regional_festivals', 'weddings')}
    result = {g: {**missing('Calendar coverage unavailable.'), 'region': region['state_code'],
                  'provider': 'Calendarific', 'source': {'title': 'Calendarific', 'url': 'https://calendarific.com/'},
                  'missing_events': []} for g in ('regional_festivals', 'weddings')}
    key = os.getenv('SALES_CALENDARIFIC_API_KEY')
    if not key:
        audit('skipped', provider='calendarific_regional', reason='missing_credentials', region=region['state_code'])
        return result
    for year in range(start.year, end.year + 1):
        try:
            raw = cached(f'intelligence:regional-calendar:v1:{region["state_code"]}:{year}', 604800,
                lambda: get_json('https://calendarific.com/api/v2/holidays',
                    {'api_key': key, 'country': 'IN', 'year': year, 'location': region['state_code'].lower()}))
            holidays = raw['response']['holidays']
            for label, aliases in CATALOG[region['state_code']].items():
                matches = [h for h in holidays if any(a in h['name'].casefold() for a in aliases)]
                if not matches:
                    result['regional_festivals']['missing_events'].append(f'{label} {year}')
                for holiday in matches:
                    day = date.fromisoformat(holiday['date']['iso'][:10])
                    if day.year != year:
                        raise ValueError('Wrong calendar year')
                    result['regional_festivals']['events'].append({'name': label, 'date': day.isoformat(),
                        'end_date': day.isoformat(), 'kind': 'festival'})
            if not any(s.endswith(str(year)) for s in result['regional_festivals']['missing_events']):
                result['regional_festivals']['coverage_years'].append(year)
            # Holiday lists are not a complete marriage calendar. Never infer wedding seasons from festivals.
            result['weddings']['missing_events'].append(f'Verified wedding calendar {year}')
        except Exception as error:
            audit('failure', provider='calendarific_regional', year=year, region=region['state_code'],
                  error_type=type(error).__name__)
    for group, value in result.items():
        expected = end.year - start.year + 1
        value['status'] = 'available' if len(value['coverage_years']) == expected else 'partial' if value['events'] else 'unavailable'
        value['message'] = f'{group.replace("_", " ").title()} ({region["state_code"]}): ' + (
            '; '.join(f"{e['name']}: {e['date']}" for e in value['events']) or 'no verified dates')
        audit('coverage', provider='calendarific_regional', feature_group=group, region=region['state_code'],
              status=value['status'], missing_events=value['missing_events'])
    return result


def validate_fallback(payload, sources, region, years):
    """Accept only requested-region dates and citations present in grounding metadata."""
    urls = {s['url'] for s in sources if urlsplit(s['url']).scheme == 'https'}
    result = {}
    for group in ('regional_festivals', 'weddings'):
        value = payload.get(group, {})
        events = []
        for event in value.get('events', []):
            try:
                start, end = date.fromisoformat(event['date']), date.fromisoformat(event.get('end_date', event['date']))
                kind = event['kind']
                if (event['region'] != region or event['source_url'] not in urls or start.year not in years
                        or end.year != start.year or not 0 <= (end - start).days <= 90):
                    raise ValueError('Invalid calendar scope or citation')
                if group == 'regional_festivals' and (kind != 'festival' or event['name'] not in CATALOG[region]):
                    raise ValueError('Unknown regional festival')
                if group == 'weddings' and (kind not in ('wedding_date', 'wedding_season')
                        or (kind == 'wedding_date' and end != start)):
                    raise ValueError('Invalid wedding interval')
                events.append({**event, 'date': start.isoformat(), 'end_date': end.isoformat()})
            except (ValueError, KeyError, TypeError):
                audit('feature_rejected', provider='gemini', feature_group=group, reason='invalid_calendar_fact')
        covered = []
        for coverage in value.get('coverage', []):
            year = coverage.get('year')
            if (year in years and coverage.get('complete_year') is True and coverage.get('source_url') in urls
                    and any(date.fromisoformat(e['date']).year == year for e in events)):
                if group == 'regional_festivals' and not set(CATALOG[region]).issubset(
                        {e['name'] for e in events if date.fromisoformat(e['date']).year == year}):
                    continue
                covered.append(year)
        if events:
            result[group] = {'status': 'available' if set(covered) == set(years) else 'partial',
                'events': events, 'coverage_years': sorted(set(covered)), 'region': region,
                'provider': 'Gemini grounded calendar', 'source': {'title': 'Calendar source', 'url': events[0]['source_url']},
                'message': f'{group.replace("_", " ").title()}: ' + '; '.join(f"{e['name']}: {e['date']} to {e['end_date']}" for e in events)}
    return result
