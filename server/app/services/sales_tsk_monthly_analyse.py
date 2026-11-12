"""Monthly grouping matrix using the existing live sales source and conventions."""
import calendar
from datetime import date
from decimal import Decimal

from app.services import sales_tsk_performance as source

GROUPS = {
    'group': ('Group', 'group_id', 'group'),
    'purity': ('Purity', 'purity_id', 'purity'),
    'classification': ('Classification', 'classification_id', 'classification'),
    'make': ('Make', 'make_id', 'make'),
    'collection': ('Collection', 'collection_id', 'collection'),
    'section': ('Section', 'section_id', 'section'),
    'type': ('Type', 'type_id', 'type'),
    'wide_range': ('Wide Range', 'wide_range_id', 'wide_range'),
}
METRICS = ('net_weight', 'pieces', 'net_turnover', 'total_tsk', 'mcprofit')
BARCODE_TYPES = {
    'Y': ('Crystal barcode', ('y', 'yes', 't', 'true', '1')),
    'N': ('Muziris barcode', ('n', 'no', 'f', 'false', '0')),
}


def parse_filters(args):
    filters = source.parse_filters(args)
    group = args.get('group_by', 'section')
    if group not in GROUPS:
        raise ValueError('Choose a valid Group By option.')
    barcode_types = list(dict.fromkeys(value.strip().upper() for value in args.getlist('crystalbarcodeyn')
                                       if value.strip()))
    if any(value not in BARCODE_TYPES for value in barcode_types):
        raise ValueError('Choose Crystal barcode or Muziris barcode.')
    return {**filters, 'group_by': group, 'barcode_types': barcode_types}


def month_list(filters):
    months = []
    day = filters['start'].replace(day=1)
    while day <= filters['end']:
        last = day.replace(day=calendar.monthrange(day.year, day.month)[1])
        months.append({'month': day.isoformat(), 'is_partial': filters['start'] > day or filters['end'] < last})
        day = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return months


def empty_cell():
    return {**{key: Decimal(0) for key in METRICS}, 'row_count': 0}


def build_matrix(records, filters):
    months = month_list(filters)
    rows = {}
    totals = [empty_cell() for _ in months]
    indices = {m['month']: i for i, m in enumerate(months)}
    for record in records:
        key = record['id']
        if key not in rows:
            rows[key] = {'id': key, 'label': record['label'], 'months': [empty_cell() for _ in months]}
        row = rows[key]
        index = indices[record['month'].isoformat()]
        for metric in (*METRICS, 'row_count'):
            row['months'][index][metric] += record[metric]
            totals[index][metric] += record[metric]
    for cells in [r['months'] for r in rows.values()] + [totals]:
        for index, cell in enumerate(cells):
            denominator = totals[index]['net_turnover']
            cell['share'] = cell['net_turnover'] / denominator * 100 if denominator > 0 else None
            previous = cells[index - 1] if index else None
            cell['growth'] = ((cell['net_turnover'] - previous['net_turnover']) / abs(previous['net_turnover']) * 100
                              if previous and previous['net_turnover'] != 0 and previous['row_count'] and cell['row_count']
                              and not months[index]['is_partial'] and not months[index - 1]['is_partial'] else None)
    return {'group_by': filters['group_by'], 'group_label': GROUPS[filters['group_by']][0],
            'months': months, 'rows': sorted(rows.values(), key=lambda r: (-sum(c['net_turnover'] for c in r['months']), r['label'])),
            'totals': totals}


def matrix(cur, filters):
    _, key, label = GROUPS[filters['group_by']]
    cur.execute(f'SELECT * FROM {source.SOURCE} LIMIT 0')
    columns = {column.name for column in cur.description}
    required = [key, label, 'pieces', 'mcprofit']
    if filters['barcode_types']:
        required.append('crystalbarcodeyn')
    missing = [name for name in required if name not in columns]
    if missing:
        raise source.SourceDataError('Source columns missing: ' + ', '.join(missing) + '.')
    where, params = source.where_clause(filters)
    if filters['barcode_types']:
        where += ' AND LOWER(BTRIM(crystalbarcodeyn::text)) = ANY(%s)'
        params.append([flag for value in filters['barcode_types'] for flag in BARCODE_TYPES[value][1]])
    records = source.query(cur, f'''SELECT "{key}"::text AS id,
        COALESCE(MAX(NULLIF(TRIM("{label}"::text), '')), "{key}"::text, 'Unspecified') AS label,
        date_trunc('month', {source.SALES_DATE})::date AS month,
        {source.aggregates()}, COALESCE(SUM(mcprofit), 0) AS mcprofit,
        COALESCE(SUM(pieces::numeric), 0) AS pieces
        FROM {source.SOURCE} WHERE {where} GROUP BY "{key}", 3''', params)
    return build_matrix(records, filters)


def load_segment(segment, filters):
    with source.source_cursor() as cur:
        # Transaction-local budgets: spills are preferable to large per-sort
        # allocations; avoid multiplying those allocations across parallel workers.
        cur.execute("SET LOCAL work_mem = '4MB'")
        cur.execute('SET LOCAL max_parallel_workers_per_gather = 0')
        if segment == 'options':
            return {**source.options(cur, filters), 'crystalbarcodeyn': [
                {'value': value, 'label': label} for value, (label, _) in BARCODE_TYPES.items()
            ]}
        return matrix(cur, filters)
