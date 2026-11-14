"""Read and rank one set of sibling rows in the live sales hierarchy."""
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor

SOURCE = 'ext_view.vw_item_wise_tsk_details_data'
LEVELS = (
    ('section_id', 'section', 'Section'),
    ('purity_id', 'purity', 'Purity'),
    ('range_weight', 'range_weight', 'Weight Range'),
    ('classification_id', 'classification', 'Classification'),
    ('sub_classification_id', 'sub_classification', 'Sub-classification'),
    ('make_id', 'make', 'Make'),
    ('collection_id', 'collection', 'Collection'),
    ('sub_section_id', 'sub_section', 'Subsection'),
)
DETAILS = (('type_id', 'type', 'Type'), ('wide_range_id', 'wide_range', 'Wide Range'))
SECTION, PURITY, RANGE_WEIGHT, *_, MAKE, COLLECTION, SUBSECTION = LEVELS
TYPE, WIDE_RANGE = DETAILS
HIERARCHIES = {
    'default': (SECTION, PURITY, RANGE_WEIGHT, MAKE, COLLECTION, SUBSECTION),
    '1': (MAKE, PURITY, COLLECTION, SUBSECTION, TYPE, SECTION, TYPE, RANGE_WEIGHT),
    '2': (SECTION, TYPE, WIDE_RANGE, PURITY, MAKE, COLLECTION, SUBSECTION, RANGE_WEIGHT),
    '3': (SECTION, PURITY, TYPE, WIDE_RANGE, MAKE, COLLECTION, SUBSECTION, RANGE_WEIGHT),
    '4': (SECTION, PURITY, TYPE, WIDE_RANGE, MAKE, COLLECTION, SUBSECTION, RANGE_WEIGHT),
}
FILTERS = {
    'branch_id': ('location_name', 'Location'),
    'branch_type': ('branch_type', 'Branch Type'),
    'state_name': ('state_name', 'State'),
    'location_group': ('location_group', 'Location Group'),
    **{key: (label, title) for key, label, title in (*LEVELS, *DETAILS)},
    'master_collection_id': ('master_collection', 'Master Collection'),
    'gender_id': ('gender', 'Gender'),
    'invoice_type': ('invoice_type', 'Invoice Type'),
    'trans_type': ('trans_type', 'Transaction Type'),
}
EXCLUDED_MAKES = ('KMU 999 COIN', 'CUSTOM', 'KMU-COIN')
DEFAULT_BRANCH_TYPES = {'SHOP': 'SHOP', 'FRANCHISE_SHOP': 'FRANCHISE_SHOP'}
METRICS = ('pieces', 'weight', 'turnover', 'profit')
ABC_METRICS = ('pieces', 'weight', 'turnover', 'tsk')
MAX_SIBLINGS = 20000


class SourceDataError(Exception):
    pass


def defaults():
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    return date(today.year - (today.month < 4), 4, 1), today


def parse_filters(args):
    start, end = defaults()
    start = date.fromisoformat(args.get('start') or start.isoformat())
    end = date.fromisoformat(args.get('end') or end.isoformat())
    if end < start or (end.year - start.year) * 12 + end.month - start.month > 11:
        raise ValueError('Choose a date range covering at most 12 calendar months.')

    selections = {}
    for field in FILTERS:
        values = list(dict.fromkeys(value for value in args.getlist(field) if value.strip()))
        if len(values) > 100 or any(len(value) > 200 for value in values):
            raise ValueError('Too many or invalid filter values.')
        if values:
            selections[field] = values
    if 'branch_type' in selections:
        # Support links saved when Franchise used a shorter filter value.
        selections['branch_type'] = list(dict.fromkeys(
            'FRANCHISE_SHOP' if value == 'FRANCHISE' else value for value in selections['branch_type']
        ))
    elif not args.get('branch_type_set'):
        selections['branch_type'] = list(DEFAULT_BRANCH_TYPES)
    if set(selections.get('trans_type', ())) - {'INVOICE', 'SR'}:
        raise ValueError('Choose Invoice or Sales Return.')
    exclusions = list(dict.fromkeys(value.strip().upper() for value in args.getlist('exclude_make')))
    if not exclusions and not args.get('exclude_make_set'):
        exclusions = list(EXCLUDED_MAKES)
    if set(exclusions) - set(EXCLUDED_MAKES):
        raise ValueError('Choose a valid Make exclusion.')
    hierarchy = args.get('hierarchy', 'default')
    if hierarchy not in HIERARCHIES:
        raise ValueError('Choose a valid drill-down order.')
    return {'start': start, 'end': end, 'selections': selections, 'exclusions': exclusions, 'hierarchy': hierarchy}


def parse_parent(value, hierarchy='default'):
    try:
        path = json.loads(value)
    except ValueError:
        raise ValueError('Invalid drill-down path.') from None
    if (not isinstance(path, list) or len(path) > len(HIERARCHIES[hierarchy])
            or any(part is not None and (not isinstance(part, str) or len(part) > 200) for part in path)):
        raise ValueError('Invalid drill-down path.')
    return path


@contextmanager
def source_cursor():
    from app.utils.sync_tasks import get_external_db_connection

    connection = get_external_db_connection()
    try:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute("SET LOCAL work_mem = '4MB'")
            cur.execute('SET LOCAL max_parallel_workers_per_gather = 0')
            yield cur
    finally:
        connection.close()


def validate_columns(cur, required):
    cur.execute(f'SELECT * FROM {SOURCE} LIMIT 0')
    missing = sorted(required - {column.name for column in cur.description})
    if missing:
        raise SourceDataError('Source columns missing: ' + ', '.join(missing) + '.')


def where_clause(filters, parent=(), *, options=False):
    sales_date = 'COALESCE(trans_date::date, date)'
    conditions = ["trans_type IN ('INVOICE', 'SR')", f'{sales_date} >= %s', f'{sales_date} < %s']
    params = [filters['start'], filters['end'] + timedelta(days=1)]
    if filters['exclusions']:
        conditions.append("NOT (UPPER(TRIM(COALESCE(make::text, ''))) = ANY(%s))")
        params.append(filters['exclusions'])
    if not options:
        for field, values in filters['selections'].items():
            conditions.append(f'"{field}"::text = ANY(%s)')
            params.append(values)
        for (field, _, _), part in zip(HIERARCHIES[filters['hierarchy']], parent):
            conditions.append(f'"{field}"::text IS NOT DISTINCT FROM %s')
            params.append(part)
    return ' AND '.join(conditions), params


def options(cur, filters, field):
    if field not in FILTERS:
        raise ValueError('Choose a valid filter.')
    label, _ = FILTERS[field]
    validate_columns(cur, {field, label, 'trans_type', 'trans_date', 'date', 'make'})
    where, params = where_clause(filters, options=True)
    cur.execute(f"""SELECT "{field}"::text AS value,
        COALESCE(MIN(NULLIF(BTRIM("{label}"::text), '')), "{field}"::text) AS label
        FROM {SOURCE} WHERE {where} AND "{field}" IS NOT NULL
        GROUP BY "{field}"::text ORDER BY label, value""", params)
    return [dict(row) for row in cur.fetchall()]


def assign_categories(rows):
    totals = {metric: sum(row[metric] for row in rows) for metric in METRICS}
    for row in rows:
        row['categories'] = {}
    for metric in ABC_METRICS:
        category_total = sum(row[metric] for row in rows)
        ranked = sorted(rows, key=lambda row: (-row[metric], row['label'], str(row['id'])))
        running = 0
        for row in ranked:
            value = row[metric]
            category = 'Unclassified'
            if value > 0 and category_total > 0:
                if running * 100 < category_total * 80:
                    category = 'A'
                elif running * 100 < category_total * 95:
                    category = 'B'
                else:
                    category = 'C'
            row['categories'][metric] = category
            running += value
    rows.sort(key=lambda row: (-row['pieces'], row['label'], str(row['id'])))
    return totals


def drilldown(cur, filters, parent):
    levels = HIERARCHIES[filters['hierarchy']]
    depth = len(parent)
    leaf = depth == len(levels)
    dimensions = DETAILS if leaf else levels[depth:depth + 1]
    required = {'pieces', 'net_weight', 'turn_over', 'tsk', 'trans_type', 'trans_date', 'date', 'make'}
    required.update(filters['selections'])
    required.update(key for key, _, _ in levels[:depth])
    required.update(column for key, label, _ in dimensions for column in (key, label))
    validate_columns(cur, required)

    sign = os.getenv('SALES_PREDICTION_RETURN_SIGN', 'signed')
    if sign not in {'signed', 'positive'}:
        raise SourceDataError('Invalid sales return-sign configuration.')
    multiplier, invalid_sign = (1, '> 0') if sign == 'signed' else (-1, '< 0')
    where, params = where_clause(filters, parent)
    groups = [f'"{key}"::text' for key, _, _ in dimensions]
    columns = []
    for index, ((_, label, _), key) in enumerate(zip(dimensions, groups)):
        columns.extend((f'{key} AS id_{index}',
                        f"""COALESCE(MIN(NULLIF(BTRIM("{label}"::text), '')), {key}, 'Unspecified') AS label_{index}"""))
    cur.execute(f"""SELECT {', '.join(columns)},
        COALESCE(SUM(pieces::numeric) FILTER (WHERE trans_type = 'INVOICE'), 0) AS pieces,
        COALESCE(SUM(net_weight::numeric) FILTER (WHERE trans_type = 'INVOICE'), 0) / 1000 AS weight,
        COALESCE(SUM(turn_over::numeric) FILTER (WHERE trans_type = 'INVOICE'), 0)
          + COALESCE(SUM(turn_over::numeric) FILTER (WHERE trans_type = 'SR'), 0) * {multiplier} AS turnover,
        COALESCE(SUM(tsk::numeric), 0) AS tsk,
        COUNT(*) FILTER (WHERE turn_over IS NULL OR (trans_type = 'SR' AND turn_over {invalid_sign})) AS invalid_rows
        FROM {SOURCE} WHERE {where} GROUP BY {', '.join(groups)} LIMIT {MAX_SIBLINGS + 1}""", params)
    records = cur.fetchall()
    if len(records) > MAX_SIBLINGS:
        raise SourceDataError('Too many rows at this level. Narrow the date range or filters.')
    if any(record['invalid_rows'] for record in records):
        raise SourceDataError('Source turnover is missing or sales-return signs differ from configuration.')

    rows = []
    for record in records:
        row = {metric: record[metric] for metric in METRICS if metric != 'profit'}
        row['profit'] = record['tsk']
        row['tsk'] = record['tsk']
        if leaf:
            row.update(id=[record['id_0'], record['id_1']], label=f"{record['label_0']} / {record['label_1']}",
                       type=record['label_0'], wide_range=record['label_1'])
        else:
            row.update(id=record['id_0'], label=record['label_0'])
        rows.append(row)
    totals = assign_categories(rows)
    for row in rows:
        row['contributions'] = {
            metric: row[metric] * 100 / totals[metric] if totals[metric] > 0 else None
            for metric in METRICS
        }
    return {'rows': rows, 'totals': totals, 'level': 'Detail' if leaf else dimensions[0][2], 'leaf': leaf}
