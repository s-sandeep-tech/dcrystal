"""Download real historical weather and generate SQL without changing any database."""
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

OUTPUT = Path(__file__).resolve().parent
PARAMS = dict(parameters='T2M_MAX,PRECTOTCORR', community='AG', longitude=76.30,
              latitude=9.98, start='20260401', end='20261022', format='JSON', **{'time-standard': 'UTC'})
URL = 'https://power.larc.nasa.gov/api/temporal/daily/point?' + urlencode(PARAMS)


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    with urlopen(URL, timeout=45) as response:
        raw = json.load(response)
    retrieved = datetime.now(timezone.utc).isoformat()
    (OUTPUT / 'weather_source.json').write_text(json.dumps(raw, indent=2))
    units = raw['parameters']
    if units['T2M_MAX']['units'] != 'C' or units['PRECTOTCORR']['units'] != 'mm/day':
        raise ValueError('Unexpected source units')
    data = raw['properties']['parameter']
    fill = raw['header']['fill_value']
    rows, missing, extreme = [], [], []
    day = date(2026, 4, 1)
    while day <= date(2026, 10, 22):
        key = day.strftime('%Y%m%d')
        rain, temp = data['PRECTOTCORR'].get(key), data['T2M_MAX'].get(key)
        if rain in (None, fill) or temp in (None, fill):
            missing.append(day.isoformat())
        elif not all(math.isfinite(float(v)) for v in (rain, temp)) or rain < 0 or not -90 <= temp <= 65:
            raise ValueError(f'Invalid weather values on {day}')
        else:
            values = {'rain_mm': float(rain), 'max_temp_c': float(temp)}
            if rain > 500:
                extreme.append({'date': day.isoformat(), **values})
                day += timedelta(days=1)
                continue
            identity = json.dumps(['NASA POWER observation UTC', 'branch:20', day.isoformat(), values], sort_keys=True)
            identifier = hashlib.sha256(identity.encode()).hexdigest()
            rows.append('(' + ', '.join(map(quote, [identifier, 'branch:20', day.isoformat(), 'weather_observations',
                retrieved, retrieved, 'NASA POWER historical observations (UTC)', json.dumps(values), URL])) + ')')
        day += timedelta(days=1)
    sql = '''-- ERNAKULAM branch_id=20; city representative point 9.98 N, 76.30 E.
-- NASA POWER retrospective daily gridded observations, UTC daily intervals.
-- NOT historical weather forecasts; NOT identical to WeatherAPI local-day data.
-- Availability is conservatively retrieval time. Do not backdate it to force model eligibility.
-- Source fill values and rainfall above 500 mm/day are excluded for review.
-- Existing rows are not updated or deleted.
BEGIN;
INSERT INTO sales_external_features
(id, scope, feature_date, feature_group, available_at, retrieved_at, provider, values_json, source)
VALUES
''' + ',\n'.join(rows) + '\nON CONFLICT (id) DO NOTHING;\nCOMMIT;\n'
    (OUTPUT / 'ernakulam_weather.sql').write_text(sql)
    report = {'branch_id': 20, 'location': 'ERNAKULAM', 'coordinates': {'lat': 9.98, 'lon': 76.30},
        'requested_start': '2026-04-01', 'requested_end': '2026-10-22', 'retrieved_at': retrieved,
        'weather_rows': len(rows), 'missing_weather_dates': missing, 'extreme_rainfall_for_review': extreme,
        'gold_rows': 0, 'gold_status': 'Historical endpoint requires x-api-key; no key available in this workspace.',
        'source': URL, 'sql_sha256': hashlib.sha256(sql.encode()).hexdigest()}
    (OUTPUT / 'manifest.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
