"""Immutable feature vintages. Availability is never backdated to the event date."""
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from ..db.models import SalesExternalFeature, SalesForecastFeatureInput
from .sales_audit import audit

FIELDS = {'weather': ('rain_mm', 'max_temp_c'), 'gold': ('price_usd_oz',),
          'festivals': ('dhanteras_proximity', 'akshaya_proximity'),
          'regional_festivals': ('festival_day', 'festival_lead_7', 'festival_after_7'),
          'weddings': ('wedding_season', 'days_to_wedding', 'wedding_dates_next_7')}


def validate_feature(row):
    group = row['feature_group']
    if group not in FIELDS or set(row['values_json']) != set(FIELDS[group]):
        raise ValueError('Unknown feature schema')
    row = dict(row)
    row.pop('id', None)
    row['feature_date'] = date.fromisoformat(str(row['feature_date']))
    for key in ('available_at', 'retrieved_at'):
        value = row[key]
        row[key] = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
        if row[key].tzinfo is None:
            raise ValueError('Feature timestamps must include timezone')
    if row['available_at'] > row['retrieved_at']:
        raise ValueError('Feature availability cannot follow retrieval')
    if not row['source'].startswith('https://') or not row['provider']:
        raise ValueError('Verified source and provider are required')
    values = {k: float(v) for k, v in row['values_json'].items()}
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError('Non-finite feature')
    if group == 'weather' and (values['rain_mm'] < 0 or not -90 <= values['max_temp_c'] <= 65):
        raise ValueError('Invalid weather feature')
    if group == 'gold' and values['price_usd_oz'] <= 0:
        raise ValueError('Invalid gold price')
    if group == 'festivals' and not all(0 <= v <= 1 for v in values.values()):
        raise ValueError('Invalid festival proximity')
    if group == 'regional_festivals' and not all(0 <= v <= 1 for v in values.values()):
        raise ValueError('Invalid regional festival values')
    if group == 'weddings' and not (values['wedding_season'] in (0, 1) and 0 <= values['days_to_wedding'] <= 31
            and 0 <= values['wedding_dates_next_7'] <= 7):
        raise ValueError('Invalid wedding values')
    if group in ('weather', 'regional_festivals', 'weddings') and not row['scope'].startswith('branch:'):
        raise ValueError('Regional features require a branch scope')
    row['values_json'] = values
    row['id'] = hashlib.sha256(json.dumps(row, default=str, sort_keys=True).encode()).hexdigest()
    return row


def context_features(context, branch_id):
    retrieved = context.get('retrieved_at')
    if not retrieved:
        return []
    rows = []
    for group, data in context.get('parameters', {}).items():
        if data.get('status') not in ('available', 'partial'):
            continue
        common = {'feature_group': group, 'available_at': retrieved, 'retrieved_at': retrieved,
                  'provider': data['provider'], 'source': data['source']['url']}
        if group == 'weather' and branch_id is not None:
            for day in data['days']:
                rows.append({**common, 'scope': f'branch:{branch_id}', 'feature_date': day['date'],
                             'values_json': {k: day[k] for k in FIELDS['weather']}})
        elif group == 'gold':
            observed = datetime.fromisoformat(data['observed_at'])
            rows.append({**common, 'scope': 'global', 'feature_date': observed.date().isoformat(),
                         'values_json': {'price_usd_oz': data['price']}})
        elif group in ('regional_festivals', 'weddings') and branch_id is not None:
            covered = set(data.get('coverage_years', []))
            events = [(e, date.fromisoformat(e['date']), date.fromisoformat(e.get('end_date', e['date'])))
                      for e in data['events']]
            for year in covered:
                day = date(year, 1, 1)
                while day.year == year:
                    lookahead = 7 if group == 'regional_festivals' else 30
                    if (day + timedelta(days=lookahead)).year not in covered:
                        day += timedelta(days=1)
                        continue
                    if group == 'regional_festivals':
                        values = {'festival_day': float(any(a <= day <= b for _, a, b in events)),
                            'festival_lead_7': max([0] + [max(0, 1 - (a - day).days / 8) for _, a, _ in events if 1 <= (a - day).days <= 7]),
                            'festival_after_7': max([0] + [max(0, 1 - (day - b).days / 8) for _, _, b in events if 1 <= (day - b).days <= 7])}
                    else:
                        upcoming = {(a - day).days for e, a, _ in events if e['kind'] == 'wedding_date' and 0 <= (a - day).days <= 30}
                        values = {'wedding_season': float(any(a <= day <= b for e, a, b in events if e['kind'] == 'wedding_season')),
                            'days_to_wedding': min(upcoming, default=31),
                            'wedding_dates_next_7': sum(0 <= days < 7 for days in upcoming)}
                    rows.append({**common, 'scope': f'branch:{branch_id}', 'feature_date': day.isoformat(), 'values_json': values})
                    day += timedelta(days=1)
        elif group == 'festivals' and not data.get('missing_events'):
            for year in {date.fromisoformat(e['date']).year for e in data['events']}:
                events = {e['name']: date.fromisoformat(e['date']) for e in data['events']
                          if date.fromisoformat(e['date']).year == year}
                if not all(name in events and events[name].year == year for name in ('Dhanteras', 'Akshaya Tritiya')):
                    continue
                day = date(year, 1, 1)
                while day.year == year:
                    values = {key: max(0, 1 - abs((day - events[name]).days) / 8)
                              for key, name in [('dhanteras_proximity', 'Dhanteras'), ('akshaya_proximity', 'Akshaya Tritiya')]}
                    rows.append({**common, 'scope': 'global', 'feature_date': day.isoformat(), 'values_json': values})
                    day += timedelta(days=1)
    valid = []
    for row in rows:
        try:
            valid.append(validate_feature(row))
        except (ValueError, TypeError):
            audit('feature_rejected', provider=row['provider'], feature_group=row['feature_group'])
    return valid


def store_context(session, context, branch_id):
    rows = context_features(context, branch_id)
    if rows:
        session.execute(insert(SalesExternalFeature).values(rows).on_conflict_do_nothing(index_elements=['id']))
    return len(rows)


def load_features(session, branch_id, first_date, last_date):
    query = select(SalesExternalFeature).where(
        SalesExternalFeature.scope.in_(['global', f'branch:{branch_id}']),
        SalesExternalFeature.feature_date >= first_date - timedelta(days=7),
        SalesExternalFeature.feature_date <= last_date)
    return [{c.name: getattr(row, c.name) for c in SalesExternalFeature.__table__.columns}
            for row in session.scalars(query)]


def save_inputs(session, task_id, rows, metrics):
    # This audit captures the complete vintage pool used by selection/backtesting.
    value = {'features': json.loads(json.dumps(rows, default=str)), 'selection': metrics}
    session.execute(insert(SalesForecastFeatureInput).values(task_id=task_id,
        created_at=datetime.now(timezone.utc), inputs_json=value).on_conflict_do_nothing(index_elements=['task_id']))
