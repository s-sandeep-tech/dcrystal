"""Keyless historical gold conversion using dated GoldPrice.com and ECB data."""
import csv
import hashlib
import io
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import urlopen
import subprocess
from xml.etree import ElementTree

OUTPUT = Path(__file__).resolve().parent
GOLD_URL = 'https://goldprice.com/gold-price-history.csv'
FX_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'
FX_DAILY_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
START, END = '2026-04-01', '2026-10-22'


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def download(url, path):
    data = subprocess.check_output(['curl', '--fail', '--silent', '--show-error', '--location', '--max-time', '50', url])
    path.write_bytes(data)
    return data


def main():
    gold_raw = download(GOLD_URL, OUTPUT / 'gold_source.csv').decode('utf-8-sig')
    fx_raw = download(FX_URL, OUTPUT / 'ecb_fx_source.xml')
    fx_daily_raw = download(FX_DAILY_URL, OUTPUT / 'ecb_fx_daily_source.xml')
    if '# Source:' not in gold_raw:
        raise ValueError('Gold source attribution missing')
    gold = {}
    for row in csv.DictReader(line for line in gold_raw.splitlines() if not line.startswith('#')):
        if START <= row['date'] <= END:
            day = date.fromisoformat(row['date']).isoformat()
            price = float(row['close_usd_per_troy_oz'])
            if not math.isfinite(price) or price <= 0 or day in gold:
                raise ValueError('Invalid or duplicated gold close')
            gold[day] = price
    fx = {}
    for cube in list(ElementTree.fromstring(fx_raw).iter()) + list(ElementTree.fromstring(fx_daily_raw).iter()):
        day = cube.attrib.get('time')
        if day and START <= day <= END:
            rates = {r.attrib['currency']: float(r.attrib['rate']) for r in cube if 'currency' in r.attrib}
            if 'INR' in rates and 'USD' in rates:
                value = rates['INR'] / rates['USD']
                if not math.isfinite(value) or value <= 0:
                    raise ValueError('Invalid ECB exchange rate')
                fx[day] = value
    matched = sorted(gold.keys() & fx.keys())
    if len(matched) < 42:
        raise ValueError(f'Insufficient matched data: {len(matched)} dates')
    retrieved = datetime.now(timezone.utc).isoformat()
    records, rows = [], []
    for day in matched:
        value = gold[day] * fx[day] / 31.1034768
        values = {'price_inr_g': value}
        identifier = hashlib.sha256(json.dumps(['GoldPrice ECB INR gram', day, values], sort_keys=True).encode()).hexdigest()
        record = {'date': day, 'gold_usd_oz': gold[day], 'usd_inr': fx[day], 'price_inr_g': value}
        records.append(record)
        rows.append('(' + ', '.join(map(quote, [identifier, 'global', day, 'gold', retrieved, retrieved,
            'GoldPrice.com + ECB historical reference', json.dumps(values), GOLD_URL])) + ')')
    sql = '''-- Historical gold reference applicable to ERNAKULAM branch 20 and other branches.
-- INR/gram = GoldPrice.com USD daily close/oz * same-date ECB INR/USD / 31.1034768.
-- ECB cross rate = INR per EUR / USD per EUR. No GST, duty, purity or retail premium.
-- Source attribution: https://goldprice.com/gold-price-history and European Central Bank.
-- Only matching dates are inserted. No weekend/holiday values are invented.
-- Availability is retrieval time; this does not assert historical release timestamps.
-- Existing data is not updated or deleted; no database insert was executed by the generator.
BEGIN;
INSERT INTO sales_external_features
(id, scope, feature_date, feature_group, available_at, retrieved_at, provider, values_json, source)
VALUES
''' + ',\n'.join(rows) + '\nON CONFLICT (id) DO NOTHING;\nCOMMIT;\n'
    (OUTPUT / 'ernakulam_gold.sql').write_text(sql)
    (OUTPUT / 'gold_converted.json').write_text(json.dumps(records, indent=2))
    manifest = {'gold_rows': len(rows), 'requested_start': START, 'requested_end': END,
        'first_date': matched[0], 'last_date': matched[-1], 'retrieved_at': retrieved,
        'gold_source': GOLD_URL, 'fx_source': FX_URL, 'fx_daily_source': FX_DAILY_URL, 'scope': 'global', 'unit': 'INR/gram',
        'gold_dates_without_fx': sorted(gold.keys() - fx.keys()),
        'fx_dates_without_gold': sorted(fx.keys() - gold.keys()),
        'gold_source_sha256': hashlib.sha256(gold_raw.encode()).hexdigest(),
        'fx_source_sha256': hashlib.sha256(fx_raw).hexdigest(), 'sql_sha256': hashlib.sha256(sql.encode()).hexdigest()}
    (OUTPUT / 'gold_manifest.json').write_text(json.dumps(manifest, indent=2))
    (OUTPUT / 'ernakulam_history.sql').write_text((OUTPUT / 'ernakulam_weather.sql').read_text() + '\n' + sql)
    print(json.dumps({k: manifest[k] for k in ('gold_rows', 'first_date', 'last_date', 'unit')}, indent=2))


if __name__ == '__main__':
    main()
