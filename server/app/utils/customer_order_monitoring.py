"""Snapshot-only calculations for customer order delivery monitoring."""
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal


STAGES = [
    ('approval', 'Approval Pending', 'customer_order_approval_pending'),
    ('acceptance', 'Acceptance Pending', 'pending_to_accepted'),
    ('processing', 'Processing Pending', 'process_pending'),
    ('barcode', 'Barcode Pending', 'barcode_pending'),
    ('hallmark', 'Hallmark Pending', 'hallmark_pending'),
    ('qc_issue', 'QC Issue Pending', 'qc_issue_pending'),
    ('qc_complete', 'QC Completion Pending', 'qc_complete_pending'),
    ('invoice', 'Invoice Pending', 'invoice_pending'),
    ('receipt', 'Receipt Pending', 'receipt_pending'),
    ('customer_delivery', 'Customer Delivery Pending', 'customer_delivery_pending'),
]
STATUS = {
    'delivery pending to office by party': 'Production Pending',
    'delivered to office': 'Office Received',
    'pending from office to showroom': 'In Transit',
    'delivered to shop': 'Showroom Received / Customer Delivery Pending',
    'delivered to customer': 'Completed / Delivered',
    'estimation & advance': 'Pre-production',
    'not accepted by party': 'Party Acceptance Pending',
    'not approved by customer': 'Customer Approval Pending',
    'collection owner not approved': 'Collection Approval Pending',
    'order creation pending': 'Order Creation Pending',
    'not approved by manager': 'Manager Approval Pending',
    'cancelled/rejected by party': 'Cancelled',
    'cancelled/rejected by verifying team': 'Cancelled / Rejected',
    'cancelled/rejected by customer': 'Cancelled',
}
TERMINAL = {'delivered to customer', 'cancelled/rejected by party',
            'cancelled/rejected by verifying team', 'cancelled/rejected by customer'}
FILTERS = ['state', 'order_ro', 'location', 'customer_order_type', 'division',
           'collection', 'business_head_name', 'order_status']
RISK_LABELS = {'critical': 'Overdue', 'high': 'Due Within 0-2 Days',
               'medium': 'Due Within 3-7 Days', 'normal': 'Due After 7 Days',
               'undated': 'Missing Delivery Date'}


def number(value):
    return Decimal(str(value or 0))


def as_date(value):
    if isinstance(value, datetime):
        value = value.date()
    return value if isinstance(value, date) and value.year > 1 else None


def normalize(value):
    return ' '.join(str(value or '').split()).casefold()


def deduplicate(rows):
    """Collapse exact business duplicates; conflicting SOOCs require source repair."""
    seen, clean, duplicates = {}, [], 0
    for row in rows:
        key = str(row.get('sooc') or '').strip()
        if key:
            signature = {k: v for k, v in row.items() if k not in {'id', 'updated_at', 'snapshot_date'}}
            if key in seen:
                if seen[key] != signature:
                    raise ValueError('Conflicting rows share a SOOC. Validate the snapshot grain before using this report.')
                duplicates += 1
                continue
            seen[key] = signature
        clean.append(row)
    return clean, duplicates


def risk(due, today, high_days=2, medium_days=7):
    if not due:
        return 'undated'
    days = (due - today).days
    return 'critical' if days < 0 else 'high' if days <= high_days else 'medium' if days <= medium_days else 'normal'


def prepare(rows, today, high_days=2, medium_days=7):
    rows, duplicates = deduplicate(rows)
    due_dates = defaultdict(list)
    for row in rows:
        row['_status'] = normalize(row.get('order_status'))
        row['_classification'] = STATUS.get(row['_status'], 'Unclassified')
        row['_stages'] = [key for key, _, prefix in STAGES
                          if number(row.get(prefix + '_pcs')) > 0 or number(row.get(prefix + '_wt')) > 0]
        positive = bool(row['_stages']) or number(row.get('total_pending_pcs')) > 0 or number(row.get('total_pending_wt')) > 0
        row['_active'] = row['_status'] not in TERMINAL and (row['_status'] in STATUS or positive)
        # Match the distinct request_no KPI: each request has exactly one risk bucket.
        row['_request'] = str(row.get('request_no') or '').strip() or ('missing-request', row['id'])
        row['_due'] = as_date(row.get('expected_delivery_date'))
        if row['_active'] and row['_due']:
            due_dates[row['_request']].append(row['_due'])
    for row in rows:
        dates = due_dates[row['_request']]
        row['_request_due'] = min(dates) if dates else None
        row['_risk'] = risk(row['_request_due'], today, high_days, medium_days) if row['_active'] else 'inactive'
        row['_days'] = (row['_due'] - today).days if row['_due'] else None
    return rows, duplicates


def filter_rows(rows, args, masked=False):
    result = rows
    for field in FILTERS:
        selected = {v.strip() for v in args.get(field, '').split(',') if v.strip()}
        if selected:
            result = [r for r in result if str(r.get(field) or '') in selected]
    for field, param in [('request_date', 'request'), ('expected_delivery_date', 'delivery')]:
        for suffix, lower in [('from', True), ('to', False)]:
            value = args.get(f'{param}_{suffix}')
            if value:
                try:
                    boundary = date.fromisoformat(value)
                except ValueError as exc:
                    raise ValueError('Invalid date filter.') from exc
                result = [r for r in result if as_date(r.get(field)) and
                          ((as_date(r[field]) >= boundary) if lower else (as_date(r[field]) <= boundary))]
    if args.get('outstanding', '1') != '0':
        result = [r for r in result if r['_active']]
    if args.get('stage'):
        result = [r for r in result if r['_active'] and args['stage'] in r['_stages']]
    if args.get('risk'):
        result = [r for r in result if r['_risk'] == args['risk']]
    if args.get('branch'):
        result = [r for r in result if str(r.get('branch_id') or r.get('location') or '') == args['branch']]
    search = normalize(args.get('search'))
    if search:
        fields = ['request_no', 'sooc', 'location', 'collection', 'make'] + ([] if masked else ['party_name'])
        result = [r for r in result if any(search in normalize(r.get(k)) for k in fields)]
    return result


def summarize(rows):
    active = [r for r in rows if r['_active']]
    requests = {r['_request']: r['_risk'] for r in active if r.get('request_no')}
    stats = {
        'orders': len({str(r['request_no']).strip() for r in rows if r.get('request_no')}),
        'items': len({str(r['sooc']).strip() for r in rows if r.get('sooc')}),
        'pieces': sum(number(r.get('total_pending_pcs')) for r in active),
        'weight': sum(number(r.get('total_pending_wt')) for r in active),
        'overdue': sum(v == 'critical' for v in requests.values()),
        'approval': sum(number(r.get('customer_order_approval_pending_pcs')) for r in active),
    }
    stages = []
    branches = {}
    for key, label, prefix in STAGES:
        stages.append({'key': key, 'label': label,
                       'pcs': float(sum(number(r.get(prefix + '_pcs')) for r in active)),
                       'wt': float(sum(number(r.get(prefix + '_wt')) for r in active))})
    for r in active:
        key = str(r.get('branch_id') or r.get('location') or '')
        b = branches.setdefault(key, {'key': key, 'label': r.get('location') or 'Unspecified',
                                    'pcs': [0.0] * len(STAGES), 'wt': [0.0] * len(STAGES)})
        for i, (_, _, prefix) in enumerate(STAGES):
            for measure in ('pcs', 'wt'):
                b[measure][i] += float(number(r.get(prefix + '_' + measure)))
    counts = Counter(requests.values())
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in stats.items()}, {
        'stages': stages, 'branches': list(branches.values()),
        'risks': [{'key': k, 'label': label, 'count': counts[k]} for k, label in RISK_LABELS.items()],
    }


def sort_rows(rows, args):
    ranks = {k: i for i, k in enumerate([*RISK_LABELS, 'inactive'])}
    key = args.get('sort', 'priority')
    def value(r):
        if key == 'priority':
            return (ranks[r['_risk']], r['_request_due'] or date.max, r['_due'] or date.max)
        if key in {'expected_delivery_date', 'request_date'}:
            return as_date(r.get(key)) or date.max
        if key in {'total_pending_pcs', 'total_pending_wt'}:
            return number(r.get(key))
        return normalize(r.get(key if key in {'request_no', 'sooc', 'location', 'party_name', 'customer_order_status'} else 'request_no'))
    return sorted(rows, key=lambda r: (value(r), r['id']), reverse=args.get('direction') == 'desc')
