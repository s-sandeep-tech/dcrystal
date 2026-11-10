"""Independent, read-only quantity ABC analysis over the live external sales view."""
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor

SOURCE = 'ext_view.vw_item_wise_tsk_details_data'
SALES_DATE = 'COALESCE(trans_date::date, date)'
LEVELS = (
    ('make_id', 'make', 'Make'), ('purity_id', 'purity', 'Purity'),
    ('collection_id', 'collection', 'Collection'),
    ('sub_section_id', 'sub_section', 'Subsection'), ('section_id', 'section', 'Section'),
    ('type_id', 'type', 'Type'), ('wide_range_id', 'wide_range', 'Weight Range'),
)
FILTERS = {
    'branch_id': ('Location', 'location_name'), 'state_name': ('State', 'state_name'),
    'location_group': ('Location group', 'location_group'),
    **{key: (title, label) for key, label, title in LEVELS},
    'master_collection_id': ('Master collection', 'master_collection'),
    'classification_id': ('Classification', 'classification'),
    'gender_id': ('Gender', 'gender'), 'invoice_type': ('Invoice type', 'invoice_type'),
    'trans_type': ('Transaction type', 'trans_type'),
}
METRICS = ('sold_qty', 'sold_weight', 'net_turnover', 'mcprofit')
MAX_LEAVES = 20000


class SourceDataError(Exception):
    pass


def defaults():
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    return date(today.year if today.month >= 4 else today.year - 1, 4, 1), today


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


def where_clause(filters, options=False):
    clauses = ["trans_type IN ('INVOICE', 'SR')", f'{SALES_DATE} >= %s', f'{SALES_DATE} < %s']
    params = [filters['start'], filters['end'] + timedelta(days=1)]
    if not options:
        for key, values in filters['selections'].items():
            clauses.append(f'"{key}"::text = ANY(%s)')
            params.append(values)
    return ' AND '.join(clauses), params


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


def validate_schema(cur):
    cur.execute(f'SELECT * FROM {SOURCE} LIMIT 0')
    columns = {c.name for c in cur.description}
    required = {'barcode', 'trans_type', 'trans_date', 'date', 'net_weight', 'turn_over', 'mcprofit'}
    required.update(key for key, _, _ in LEVELS)
    required.update(label for _, label, _ in LEVELS)
    required.update(FILTERS)
    required.update(label for _, label in FILTERS.values())
    missing = sorted(required - columns)
    if missing:
        raise SourceDataError('Source columns missing: ' + ', '.join(missing) + '.')


def options(cur, filters):
    where, params = where_clause(filters, options=True)
    expressions = [f'ARRAY_AGG(DISTINCT ARRAY["{key}"::text, COALESCE("{label}"::text, "{key}"::text)]) '
                   f'FILTER (WHERE "{key}" IS NOT NULL) AS "{key}"' for key, (_, label) in FILTERS.items()]
    cur.execute(f"SELECT {', '.join(expressions)} FROM {SOURCE} WHERE {where}", params)
    row = cur.fetchone()
    return {key: sorted([{'value': v[0], 'label': v[1]} for v in row[key] or []], key=lambda v: v['label'])
            for key in FILTERS}


def build_tree(records):
    root = {'children': {}, **{metric: Decimal(0) for metric in METRICS}}
    for record in records:
        parent = root
        for metric in METRICS:
            root[metric] += record[metric]
        for depth, (key, label, title) in enumerate(LEVELS):
            identity = record[key]
            node = parent['children'].setdefault(identity, {
                'id': identity, 'label': record[label] or 'Unspecified', 'level': title,
                'depth': depth, 'children': {}, **{metric: Decimal(0) for metric in METRICS},
            })
            # Labels may differ across source rows: choose a deterministic representative.
            node['label'] = min(node['label'], record[label] or 'Unspecified')
            for metric in METRICS:
                node[metric] += record[metric]
            parent = node
    total = root['sold_qty']

    def finish(parent):
        children = sorted(parent['children'].values(), key=lambda n: (-n['sold_qty'], n['label'], str(n['id'])))
        running = Decimal(0)
        for rank, node in enumerate(children, 1):
            qty, denominator = node['sold_qty'], parent['sold_qty']
            prior = running / denominator * 100 if denominator > 0 else None
            running += qty
            node.update(rank=rank, contribution=qty / denominator * 100 if denominator > 0 else None,
                        cumulative=running / denominator * 100 if denominator > 0 else None,
                        overall=qty / total * 100 if total > 0 else None,
                        category=('A' if prior < 80 else 'B' if prior < 95 else 'C')
                        if qty > 0 and prior is not None else 'Unclassified')
            finish(node)
        parent['children'] = children
    finish(root)
    return {'rows': root.pop('children'), 'totals': root, 'levels': [v[2] for v in LEVELS]}


def hierarchy(cur, filters):
    sign = os.getenv('SALES_PREDICTION_RETURN_SIGN', 'signed')
    if sign not in {'signed', 'positive'}:
        raise SourceDataError('Invalid sales return-sign configuration.')
    multiplier, invalid = (1, '> 0') if sign == 'signed' else (-1, '< 0')
    where, params = where_clause(filters)
    keys = ', '.join(f'"{key}"' for key, _, _ in LEVELS)
    labels = ', '.join(f'COALESCE(MAX(NULLIF(TRIM("{label}"::text), \'\')), "{key}"::text, \'Unspecified\') AS "{label}"'
                       for key, label, _ in LEVELS)
    cur.execute(f'''SELECT {keys}, {labels},
        COUNT(DISTINCT barcode) FILTER (WHERE trans_type = 'INVOICE')
          + COUNT(*) FILTER (WHERE trans_type = 'INVOICE' AND barcode IS NULL) AS sold_qty,
        COALESCE(SUM(net_weight) FILTER (WHERE trans_type = 'INVOICE'), 0) / 1000.0 AS sold_weight,
        COALESCE(SUM(turn_over) FILTER (WHERE trans_type = 'INVOICE'), 0)
          + COALESCE(SUM(turn_over) FILTER (WHERE trans_type = 'SR'), 0) * {multiplier} AS net_turnover,
        COALESCE(SUM(mcprofit), 0) AS mcprofit,
        COUNT(*) FILTER (WHERE turn_over IS NULL OR (trans_type = 'SR' AND turn_over {invalid})) AS invalid_rows
        FROM {SOURCE} WHERE {where} GROUP BY {keys} LIMIT {MAX_LEAVES + 1}''', params)
    records = [dict(row) for row in cur.fetchall()]
    if len(records) > MAX_LEAVES:
        raise SourceDataError('Too many hierarchy groups. Narrow the date range or product/location filters.')
    if any(row['invalid_rows'] for row in records):
        raise SourceDataError('Source turnover is missing or sales-return signs differ from configuration.')
    return build_tree(records)


def load_segment(segment, filters):
    with source_cursor() as cur:
        validate_schema(cur)
        return options(cur, filters) if segment == 'options' else hierarchy(cur, filters)
