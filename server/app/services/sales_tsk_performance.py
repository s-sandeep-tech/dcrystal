"""Live, read-only sales aggregates. This report never reads or writes snapshots."""
import calendar
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor

SOURCE = 'ext_view.vw_item_wise_tsk_details_data'
SALES_DATE = 'COALESCE(trans_date::date, date)'
# SQL identifiers are exclusively defined here, never interpolated from requests.
FILTERS = {
    'branch_id': ('Location', 'location_name'),
    'state_name': ('State', 'state_name'),
    'location_group': ('Location group', 'location_group'),
    'make_id': ('Make', 'make'),
    'master_collection_id': ('Master collection', 'master_collection'),
    'collection_id': ('Collection', 'collection'),
    'section_id': ('Section', 'section'),
    'classification_id': ('Classification', 'classification'),
    'purity_id': ('Purity', 'purity'),
    'gender_id': ('Gender', 'gender'),
    'invoice_type': ('Invoice type', 'invoice_type'),
    'trans_type': ('Transaction type', 'trans_type'),
}
METRICS = ('invoice_turnover', 'return_turnover', 'net_turnover', 'net_weight', 'total_tsk')


class SourceDataError(Exception):
    pass


def previous_year(day):
    return day.replace(year=day.year - 1, day=min(day.day, calendar.monthrange(day.year - 1, day.month)[1]))


def defaults():
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    end = today.replace(day=1) - timedelta(days=1)
    start = date(end.year if end.month == 12 else end.year - 1, end.month % 12 + 1, 1)
    return start, end


def parse_filters(args):
    start, end = defaults()
    try:
        start = date.fromisoformat(args.get('start') or start.isoformat())
        end = date.fromisoformat(args.get('end') or end.isoformat())
    except (ValueError, TypeError):
        raise ValueError('Enter valid start and end dates.')
    if end < start or (end.year - start.year) * 12 + end.month - start.month > 11:
        raise ValueError('Choose a date range covering at most 12 calendar months.')
    selections = {}
    for key in FILTERS:
        values = list(dict.fromkeys(v.strip() for v in args.getlist(key) if v.strip()))
        if len(values) > 100 or any(len(v) > 200 for v in values):
            raise ValueError('Too many or invalid filter values.')
        if key == 'trans_type' and any(v not in {'INVOICE', 'SR'} for v in values):
            raise ValueError('Transaction type must be INVOICE or SR.')
        if values:
            selections[key] = values
    return {'start': start, 'end': end, 'selections': selections}


def where_clause(filters, start=None, end=None, omit=None):
    parts = ["trans_type IN ('INVOICE', 'SR')", f'{SALES_DATE} >= %s', f'{SALES_DATE} < %s']
    values = [start or filters['start'], (end or filters['end']) + timedelta(days=1)]
    for key, selected in filters['selections'].items():
        if key != omit:
            parts.append(f'{key}::text = ANY(%s)')
            values.append(selected)
    return ' AND '.join(parts), values


@contextmanager
def source_cursor():
    from app.utils.sync_tasks import get_external_db_connection
    conn = get_external_db_connection()
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SET LOCAL statement_timeout = 30000')
            yield cur
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def aggregates():
    sign = os.getenv('SALES_PREDICTION_RETURN_SIGN', 'signed')
    if sign not in {'signed', 'positive'}:
        raise SourceDataError('Invalid sales return-sign configuration.')
    multiplier, invalid = (1, '> 0') if sign == 'signed' else (-1, '< 0')
    invoice = "COALESCE(SUM(turn_over) FILTER (WHERE trans_type = 'INVOICE'), 0)"
    returns = f"COALESCE(SUM(turn_over) FILTER (WHERE trans_type = 'SR'), 0) * {multiplier}"
    return f'''{invoice} AS invoice_turnover, {returns} AS return_turnover,
        {invoice} + {returns} AS net_turnover,
        COALESCE(SUM(net_weight), 0) AS net_weight,
        COALESCE(SUM(total_tsk), 0) AS total_tsk,
        COUNT(*) AS row_count,
        COUNT(*) FILTER (WHERE turn_over IS NULL OR (trans_type = 'SR' AND turn_over {invalid})) AS invalid_rows,
        MAX(last_updated_at) AS source_updated_at'''


def checked(rows):
    if any(row.get('invalid_rows', 0) for row in rows):
        raise SourceDataError('Source turnover is missing or sales-return signs differ from the configured convention.')
    return rows


def query(cur, sql, params):
    cur.execute(sql, params)
    return checked([dict(row) for row in cur.fetchall()])


def totals(cur, filters):
    where, params = where_clause(filters)
    return query(cur, f'SELECT {aggregates()} FROM {SOURCE} WHERE {where}', params)[0]


def breakdown(cur, filters, dimension):
    key, label = ('section_id', 'section') if dimension == 'sections' else ('branch_id', 'location_name')
    where, params = where_clause(filters)
    rows = query(cur, f'''SELECT {key}::text AS id,
        COALESCE(MAX(NULLIF(TRIM({label}), '')), {key}::text, 'Unspecified') AS label,
        {aggregates()} FROM {SOURCE} WHERE {where}
        GROUP BY {key} ORDER BY net_turnover DESC, {key} NULLS LAST''', params)
    total = sum((r['net_turnover'] for r in rows), Decimal(0))
    for row in rows:
        row['share'] = row['net_turnover'] / total * 100 if total > 0 else None
    return rows


def monthly(cur, filters):
    current_where, current_params = where_clause(filters)
    prior_where, prior_params = where_clause(filters, previous_year(filters['start']), previous_year(filters['end']))
    # Aggregate branch/month in PostgreSQL; no item rows are transferred to the app.
    rows = query(cur, f'''SELECT 'current' AS period, date_trunc('month', {SALES_DATE})::date AS month,
        branch_id, MAX(location_name) AS location_name, {aggregates()}
        FROM {SOURCE} WHERE {current_where} GROUP BY 2, branch_id
        UNION ALL
        SELECT 'prior' AS period, date_trunc('month', {SALES_DATE})::date AS month,
        branch_id, MAX(location_name) AS location_name, {aggregates()}
        FROM {SOURCE} WHERE {prior_where} GROUP BY 2, branch_id''', current_params + prior_params)
    result = []
    month = filters['start'].replace(day=1)
    while month <= filters['end']:
        current = [r for r in rows if r['period'] == 'current' and r['month'] == month]
        prior = [r for r in rows if r['period'] == 'prior' and r['month'] == previous_year(month)]
        row = {'month': month.isoformat(), **{key: sum((r[key] for r in current), Decimal(0)) for key in METRICS}}
        row['row_count'] = sum(r['row_count'] for r in current)
        row['prior_turnover'] = sum((r['net_turnover'] for r in prior), Decimal(0)) if prior else None
        row['yoy'] = ((row['net_turnover'] - row['prior_turnover']) / row['prior_turnover'] * 100
                      if current and row['prior_turnover'] is not None and row['prior_turnover'] > 0 else None)
        leader = sorted(current, key=lambda r: (-r['net_turnover'], str(r['branch_id'])))[0] if current else None
        row['leading_branch'] = (leader['location_name'] or str(leader['branch_id'] or 'Unspecified')) if leader else None
        result.append(row)
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return result


def options(cur, filters):
    # One scan for all option lists; dates scope the lists without losing selected options.
    where, params = where_clause({**filters, 'selections': {}})
    expressions = [f'ARRAY_AGG(DISTINCT ARRAY[{key}::text, COALESCE({label}::text, {key}::text)]) '
                   f'FILTER (WHERE {key} IS NOT NULL) AS {key}' for key, (_, label) in FILTERS.items()]
    cur.execute(f"SELECT {', '.join(expressions)} FROM {SOURCE} WHERE {where}", params)
    row = cur.fetchone()
    return {key: sorted([{'value': v[0], 'label': v[1]} for v in (row[key] or [])], key=lambda v: v['label']) for key in FILTERS}


def load_segment(segment, filters):
    with source_cursor() as cur:
        if segment == 'options':
            return options(cur, filters)
        if segment == 'kpis':
            return totals(cur, filters)
        if segment in {'sections', 'branches'}:
            return breakdown(cur, filters, segment)
        return monthly(cur, filters)
