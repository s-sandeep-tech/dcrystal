from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from flask import render_template, request
from flask_jwt_extended import jwt_required
from sqlalchemy import asc, case, desc, func, or_

from app.dashboard import dashboard_bp
from app.extensions import db
from app.models import Notification, PartyOrderAcceptCancelDeliverySnapshot


logger = logging.getLogger(__name__)

REPORT_MONTHS = [
    'January 2026', 'February 2026', 'March 2026', 'April 2026',
    'May 2026', 'June 2026', 'July 2026', 'August 2026',
]

METRICS = {
    'ordered': ('order_wt', 'order_pcs'),
    'accepted': ('accepted_wt', 'accepted_pcs'),
    'cancelled': ('cancelled_wt', 'cancelled_pcs'),
    'delivered': ('delivered_wt', 'delivered_pcs'),
}


def split_filter_values(value):
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def apply_multi_filter(query, column, value):
    values = split_filter_values(value)
    if not values:
        return query
    return query.filter(column == values[0]) if len(values) == 1 else query.filter(column.in_(values))


def report_filters():
    return {
        'search': request.args.get('search', '').strip(),
        'party': request.args.get('party', ''),
        'party_type': request.args.get('party_type', ''),
        'make': request.args.get('make', ''),
        'month': request.args.get('month', ''),
        'order_type': request.args.get('order_type', ''),
        'provision_type': request.args.get('provision_type', ''),
    }


def report_sort():
    sort_by = request.args.get('sort_by', 'party').strip().lower()
    sort_dir = request.args.get('sort_dir', 'asc').strip().lower()
    allowed_sort_columns = {'party', 'grand_total'} | {
        f"month_{month.lower()}" for month in REPORT_MONTHS
    }
    return (
        sort_by if sort_by in allowed_sort_columns else 'party',
        sort_dir if sort_dir in {'asc', 'desc'} else 'asc',
    )


def apply_filters(query, filters):
    model = PartyOrderAcceptCancelDeliverySnapshot
    if filters['search']:
        term = f"%{filters['search']}%"
        query = query.filter(or_(
            model.supplier.ilike(term),
            model.party_type.ilike(term),
            model.make.ilike(term),
            model.month.ilike(term),
        ))
    query = apply_multi_filter(query, model.supplier, filters['party'])
    query = apply_multi_filter(query, model.party_type, filters['party_type'])
    query = apply_multi_filter(query, model.make, filters['make'])
    query = apply_multi_filter(query, model.month, filters['month'])
    query = apply_multi_filter(query, model.order_type, filters['order_type'])
    query = apply_multi_filter(query, model.provision_type, filters['provision_type'])
    return query


def get_options(column, calendar_order=False):
    values = [
        row[0] for row in db.session.query(column)
        .filter(column.isnot(None), column != '')
        .distinct().all()
        if row[0]
    ]
    if calendar_order:
        return [month for month in REPORT_MONTHS if month in values]
    return sorted(values)


def aggregate_stats(filters):
    model = PartyOrderAcceptCancelDeliverySnapshot
    query = db.session.query(
        func.sum(model.order_wt).label('ordered_wt'),
        func.sum(model.order_pcs).label('ordered_pcs'),
        func.sum(model.accepted_wt).label('accepted_wt'),
        func.sum(model.accepted_pcs).label('accepted_pcs'),
        func.sum(model.cancelled_wt).label('cancelled_wt'),
        func.sum(model.cancelled_pcs).label('cancelled_pcs'),
        func.sum(model.delivered_wt).label('delivered_wt'),
        func.sum(model.delivered_pcs).label('delivered_pcs'),
    )
    values = apply_filters(query, filters).first()
    ordered_wt = float(values.ordered_wt or 0)

    def percentage(value):
        return round((float(value or 0) / ordered_wt) * 100, 1) if ordered_wt else 0.0

    return {
        'ordered_wt': f"{ordered_wt:,.3f}",
        'ordered_pcs': f"{int(values.ordered_pcs or 0):,}",
        'accepted_wt': f"{float(values.accepted_wt or 0):,.3f}",
        'accepted_pcs': f"{int(values.accepted_pcs or 0):,}",
        'accepted_perc': percentage(values.accepted_wt),
        'cancelled_wt': f"{float(values.cancelled_wt or 0):,.3f}",
        'cancelled_pcs': f"{int(values.cancelled_pcs or 0):,}",
        'cancelled_perc': percentage(values.cancelled_wt),
        'delivered_wt': f"{float(values.delivered_wt or 0):,.3f}",
        'delivered_pcs': f"{int(values.delivered_pcs or 0):,}",
        'delivered_perc': percentage(values.delivered_wt),
    }


def empty_metric_values():
    return {
        metric: {'wt': 0.0, 'pcs': 0}
        for metric in METRICS
    }


def build_matrix(
    filters,
    level,
    page,
    per_page,
    parent_party='',
    paginate=True,
    sort_by='party',
    sort_dir='asc',
):
    model = PartyOrderAcceptCancelDeliverySnapshot
    group_columns = [model.supplier] if level == 'party' else [model.supplier, model.make]

    group_query = apply_filters(db.session.query(*group_columns), filters)
    if parent_party:
        group_query = group_query.filter(model.supplier == parent_party)
    group_query = group_query.group_by(*group_columns)

    if sort_by == 'grand_total':
        sort_target = func.sum(model.order_wt)
    elif sort_by.startswith('month_'):
        month_name = sort_by.removeprefix('month_').title()
        sort_target = func.sum(case(
            (model.month == month_name, model.order_wt),
            else_=0,
        ))
    else:
        sort_target = group_columns[-1]

    sort_expression = desc(sort_target) if sort_dir == 'desc' else asc(sort_target)
    group_query = group_query.order_by(
        sort_expression,
        *[asc(column) for column in group_columns],
    )

    pagination = None
    if paginate:
        pagination = group_query.paginate(page=page, per_page=per_page, error_out=False)
        group_items = pagination.items
    else:
        group_items = group_query.all()

    selected_keys = {
        (row[0], row[1] if level == 'make' else '')
        for row in group_items
    }

    rows_by_key = {}
    for party, make in selected_keys:
        rows_by_key[(party, make)] = {
            'level': level,
            'party': party,
            'make': make,
            'months': {month: empty_metric_values() for month in REPORT_MONTHS},
            'total': empty_metric_values(),
        }

    if selected_keys:
        aggregate_columns = []
        for metric, (weight_field, pieces_field) in METRICS.items():
            aggregate_columns.extend([
                func.sum(getattr(model, weight_field)).label(f'{metric}_wt'),
                func.sum(getattr(model, pieces_field)).label(f'{metric}_pcs'),
            ])

        data_query = apply_filters(
            db.session.query(*group_columns, model.month, *aggregate_columns),
            filters,
        )
        if parent_party:
            data_query = data_query.filter(model.supplier == parent_party)
        if level == 'party':
            data_query = data_query.filter(model.supplier.in_([key[0] for key in selected_keys]))
        else:
            data_query = data_query.filter(model.make.in_([key[1] for key in selected_keys]))
        data_query = data_query.group_by(*group_columns, model.month)

        for result in data_query.all():
            party = result[0]
            make = result[1] if level == 'make' else ''
            month = result[2] if level == 'make' else result[1]
            key = (party, make)
            if key not in rows_by_key or month not in REPORT_MONTHS:
                continue

            for metric in METRICS:
                weight = float(getattr(result, f'{metric}_wt') or 0)
                pieces = int(getattr(result, f'{metric}_pcs') or 0)
                rows_by_key[key]['months'][month][metric] = {'wt': weight, 'pcs': pieces}
                rows_by_key[key]['total'][metric]['wt'] += weight
                rows_by_key[key]['total'][metric]['pcs'] += pieces

    ordered_rows = [
        rows_by_key[(row[0], row[1] if level == 'make' else '')]
        for row in group_items
    ]
    return ordered_rows, pagination


def build_month_totals(filters):
    model = PartyOrderAcceptCancelDeliverySnapshot
    aggregate_columns = []
    for metric, (weight_field, pieces_field) in METRICS.items():
        aggregate_columns.extend([
            func.sum(getattr(model, weight_field)).label(f'{metric}_wt'),
            func.sum(getattr(model, pieces_field)).label(f'{metric}_pcs'),
        ])

    query = apply_filters(db.session.query(model.month, *aggregate_columns), filters)
    totals = {month: empty_metric_values() for month in REPORT_MONTHS}
    grand_total = empty_metric_values()

    for result in query.group_by(model.month).all():
        if result.month not in REPORT_MONTHS:
            continue
        for metric in METRICS:
            weight = float(getattr(result, f'{metric}_wt') or 0)
            pieces = int(getattr(result, f'{metric}_pcs') or 0)
            totals[result.month][metric] = {'wt': weight, 'pcs': pieces}
            grand_total[metric]['wt'] += weight
            grand_total[metric]['pcs'] += pieces
    return totals, grand_total


def report_context(is_partial=False):
    model = PartyOrderAcceptCancelDeliverySnapshot
    filters = report_filters()
    sort_by, sort_dir = report_sort()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    parent_party = request.args.get('parent_party', '')
    is_child_rows = request.args.get('is_child_rows', 'false') == 'true'
    level = 'make' if is_child_rows else 'party'

    rows, pagination = build_matrix(
        filters,
        level,
        page,
        per_page,
        parent_party=parent_party,
        paginate=not is_child_rows,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    month_totals, grand_total = build_month_totals(filters)

    context = {
        'stats': aggregate_stats(filters),
        'rows': rows,
        'months': REPORT_MONTHS,
        'month_totals': month_totals,
        'grand_total': grand_total,
        'pagination': pagination,
        'current_level': level,
        'is_child_rows': is_child_rows,
        'sort_by': sort_by,
        'sort_dir': sort_dir,
    }
    if not is_partial:
        context.update({
            'unread_count': Notification.query.filter_by(is_read=False).count(),
            'sync_time': datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p'),
            'filter_options': {
                'parties': get_options(model.supplier),
                'party_types': get_options(model.party_type),
                'makes': get_options(model.make),
                'months': get_options(model.month, calendar_order=True),
                'order_types': get_options(model.order_type),
                'provision_types': get_options(model.provision_type),
            },
        })
    return context


@dashboard_bp.route('/party-order-accept-cancel-delivery-performance')
def party_order_accept_cancel_delivery_performance():
    try:
        return render_template(
            'party_order_accept_cancel_delivery_performance.html',
            **report_context(),
        )
    except Exception as error:
        logger.exception('Party order frequency report failed')
        return f"Error: {error}", 500


@dashboard_bp.route('/partial/party-order-accept-cancel-delivery-performance')
@jwt_required()
def get_party_order_accept_cancel_delivery_performance_partial():
    try:
        return render_template(
            'partials/_view_party_order_accept_cancel_delivery_performance.html',
            **report_context(is_partial=True),
        )
    except Exception as error:
        logger.exception('Party order frequency partial failed')
        return f'<div class="p-4 text-red-500">Error: {error}</div>', 500
