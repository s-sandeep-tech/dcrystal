"""Customer order monitoring, reusing the authorized customer-order snapshot."""
import csv
from datetime import datetime
from functools import wraps
from io import StringIO
from math import ceil
from zoneinfo import ZoneInfo

from flask import abort, current_app, jsonify, render_template, request, Response, session
from flask_jwt_extended import jwt_required
from sqlalchemy.orm import load_only

from app.dashboard import dashboard_bp
from app.models.customer_order_analysis import CustomerOrderAnalysisSnapshot as Snapshot
from app.dashboard.routes.customer_order_analysis import apply_visibility_filter, mask_supplier_data
from app.utils.decorators import require_perm
from app.utils.customer_order_monitoring import (
    FILTERS, RISK_LABELS, STAGES, filter_rows, prepare, sort_rows, summarize,
)


def authorized(fn):
    @wraps(fn)
    @jwt_required()
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            abort(401)
        return fn(*args, **kwargs)
    return wrapped


def context(args):
    # Exclude customer names, phones and employee codes from this report's data layer.
    excluded = {'customer_name', 'customer_phone_number', 'advance_no', 'advance_date',
                'bh_emp_code', 'classification_owner_emp_code', 'make_owner_emp_code', 'collection_owner_emp_code'}
    columns = [c.name for c in Snapshot.__table__.columns if c.name not in excluded]
    query = apply_visibility_filter(Snapshot.query).options(load_only(*(getattr(Snapshot, c) for c in columns)))
    rows = [{c: getattr(r, c) for c in columns} for r in query.all()]
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    high = int(current_app.config.get('CUSTOMER_MONITOR_HIGH_DAYS', 2))
    medium = int(current_app.config.get('CUSTOMER_MONITOR_MEDIUM_DAYS', 7))
    if not 0 <= high < medium:
        raise ValueError('Invalid delivery urgency thresholds.')
    rows, duplicates = prepare(rows, today, high, medium)
    masked = mask_supplier_data()
    if masked:
        for r in rows:
            r['party_name'] = r['party_code'] = 'XXX'
    options = {}
    for field in FILTERS:
        option_rows = rows
        if field in {'order_ro', 'location'} and args.get('state'):
            option_rows = [r for r in option_rows if r.get('state') in args['state'].split(',')]
        if field == 'location' and args.get('order_ro'):
            option_rows = [r for r in option_rows if r.get('order_ro') in args['order_ro'].split(',')]
        options[field] = sorted({str(r[field]) for r in option_rows if r.get(field)})
    selected = sort_rows(filter_rows(rows, args, masked), args)
    stats, charts = summarize(selected)
    charts['risks'][1]['label'] = f'Due Within 0-{high} Days'
    charts['risks'][2]['label'] = f'Due Within {high + 1}-{medium} Days'
    charts['risks'][3]['label'] = f'Due After {medium} Days'
    warnings = []
    if duplicates:
        warnings.append(f'{duplicates} exact duplicate SOOC rows excluded.')
    missing = sum(not str(r.get('sooc') or '').strip() for r in rows)
    if missing:
        warnings.append(f'{missing} rows have no SOOC; excluded from the distinct item count.')
    unknown = sum(r['_classification'] == 'Unclassified' for r in rows)
    if unknown:
        warnings.append(f'{unknown} rows have unclassified order statuses; only positive pending quantities qualify as outstanding.')
    warnings.append('Production, approval and customer delivery are separate measures; stage quantities are not added to production totals.')
    return dict(rows=selected, stats=stats, charts=charts, options=options,
                stages=STAGES, report_date=today, warnings=warnings, masked=masked)


@dashboard_bp.route('/customer-order-performance-monitoring')
@authorized
def customer_order_monitoring():
    return render_template('customer_order_monitoring.html', stages=STAGES, filters=FILTERS)


@dashboard_bp.route('/api/customer-order-performance-monitoring/data')
@authorized
def customer_order_monitoring_data():
    try:
        data = context(request.args)
    except ValueError as exc:
        return jsonify(error=str(exc)), 409
    total = len(data['rows'])
    size = request.args.get('per_page', 25, type=int)
    size = size if size in {25, 50, 100} else 25
    pages = max(1, ceil(total / size))
    page = min(pages, max(1, request.args.get('page', 1, type=int)))
    data['rows'] = data['rows'][(page - 1) * size:page * size]
    return jsonify(html=render_template('partials/_customer_order_monitoring_table.html', **data),
                   stats=data['stats'], charts=data['charts'], options=data['options'], warnings=data['warnings'],
                   report_date=data['report_date'].isoformat(), page=page, pages=pages, total=total)


@dashboard_bp.route('/api/customer-order-performance-monitoring/export')
@authorized
@require_perm('report.export')
def customer_order_monitoring_export():
    try:
        data = context(request.args)
    except ValueError as exc:
        return jsonify(error=str(exc)), 409
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Priority', 'Expected Delivery Date', 'Days Remaining', 'Request Number', 'SOOC',
                     'Request Date', 'RO / Location', 'Division / Collection', 'Pending Stages',
                     'Production Pending Pieces', 'Production Pending Weight (g)', 'Responsibility',
                     'Customer Order Status', 'Party / Supplier'])
    labels = dict((k, label) for k, label, _ in STAGES)
    owners = [('Business Head', 'business_head_name'), ('Shop Manager', 'shop_manger'),
              ('Make Owner', 'make_owner'), ('Collection Owner', 'collection_wner'),
              ('Classification Owner', 'classification_owner')]
    for r in data['rows']:
        values = [r['_risk'], r['_due'], r['_days'], r.get('request_no'), r.get('sooc'), r.get('request_date'),
                  f"{r.get('order_ro') or ''} / {r.get('location') or ''}",
                  f"{r.get('division') or ''} / {r.get('collection') or ''}",
                  ', '.join(labels[k] for k in r['_stages']), r.get('total_pending_pcs'), r.get('total_pending_wt'),
                  '; '.join(f'{label}: {r.get(field)}' for label, field in owners if r.get(field)),
                  r.get('customer_order_status'), r.get('party_name')]
        # Neutralize spreadsheet formulas in exported text without altering numeric measures.
        writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
    return Response(output.getvalue(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=customer-order-performance.csv', 'Cache-Control': 'no-store'})
