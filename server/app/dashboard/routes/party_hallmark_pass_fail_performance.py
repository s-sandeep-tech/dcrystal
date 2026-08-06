from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from flask import render_template, request
from flask_jwt_extended import jwt_required
from sqlalchemy import asc, case, desc, func, or_

from app.dashboard import dashboard_bp
from app.extensions import db
from app.models import Notification, PartyHallmarkPassFailSnapshot


logger = logging.getLogger(__name__)

MONTH_LIST = [
    'April', 'May', 'June', 'July', 'August', 'September',
    'October', 'November', 'December', 'January', 'February', 'March'
]

METRICS = [
    ('HM ISSUE TOTAL', 'issue_pcs', 'issue_wt'),
    ('HM PASSED TOTAL', 'passed_pcs', 'passed_wt'),
    ('HM FAILED TOTAL', 'failed_pcs', 'failed_wt'),
]


def split_filter_values(value):
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def apply_multi_filter(query, column, value):
    values = split_filter_values(value)
    if not values:
        return query
    return query.filter(column == values[0]) if len(values) == 1 else query.filter(column.in_(values))


def get_request_filters():
    return {
        'search': request.args.get('search', '').strip(),
        'party': request.args.get('party', ''),
        'hallmarking_center': request.args.get('hallmarking_center', ''),
        'order_type': request.args.get('order_type', ''),
        'provision_type': request.args.get('provision_type', ''),
        'failed_only': request.args.get('failed_only', '').strip().lower()
        in {'1', 'true', 'yes', 'on'},
    }


def apply_filters(query, filters):
    search = filters['search']
    if search:
        pattern = f'%{search}%'
        query = query.filter(or_(
            PartyHallmarkPassFailSnapshot.party.ilike(pattern),
            PartyHallmarkPassFailSnapshot.hallmarking_center.ilike(pattern),
        ))
    query = apply_multi_filter(query, PartyHallmarkPassFailSnapshot.party, filters['party'])
    query = apply_multi_filter(
        query,
        PartyHallmarkPassFailSnapshot.hallmarking_center,
        filters['hallmarking_center'],
    )
    query = apply_multi_filter(query, PartyHallmarkPassFailSnapshot.order_type, filters['order_type'])
    query = apply_multi_filter(
        query,
        PartyHallmarkPassFailSnapshot.provision_type,
        filters['provision_type'],
    )
    if filters['failed_only']:
        query = query.filter(or_(
            func.coalesce(PartyHallmarkPassFailSnapshot.hm_failed_pcs, 0) > 0,
            func.coalesce(PartyHallmarkPassFailSnapshot.hm_failed_wt, 0) > 0,
        ))
    return query


def apply_conditions(query, conditions):
    for condition in conditions:
        query = query.filter(condition)
    return query


def get_options(column):
    return [
        row[0]
        for row in db.session.query(column)
        .filter(column.isnot(None), column != '')
        .distinct()
        .order_by(column)
        .all()
        if row[0]
    ]


def get_filter_options():
    return {
        'parties': get_options(PartyHallmarkPassFailSnapshot.party),
        'hallmarking_centers': get_options(PartyHallmarkPassFailSnapshot.hallmarking_center),
        'order_types': get_options(PartyHallmarkPassFailSnapshot.order_type),
        'provision_types': get_options(PartyHallmarkPassFailSnapshot.provision_type),
    }


def get_months(filters):
    query = db.session.query(PartyHallmarkPassFailSnapshot.month).filter(
        PartyHallmarkPassFailSnapshot.month.isnot(None),
        PartyHallmarkPassFailSnapshot.month != '',
    ).distinct()
    values = [row[0] for row in apply_filters(query, filters).all()]
    months = [month for month in MONTH_LIST if month in values]
    return months or values or ['April', 'May', 'June', 'July', 'August']


def get_stats(filters):
    query = db.session.query(
        func.sum(PartyHallmarkPassFailSnapshot.hm_issue_pcs).label('issue_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_issue_wt).label('issue_wt'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_passed_pcs).label('passed_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_passed_wt).label('passed_wt'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_failed_pcs).label('failed_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_failed_wt).label('failed_wt'),
    )
    totals = apply_filters(query, filters).first()
    return {
        'hm_issue_pcs': f'{int(totals.issue_pcs or 0):,}',
        'hm_issue_wt': f'{float(totals.issue_wt or 0):,.3f}',
        'hm_passed_pcs': f'{int(totals.passed_pcs or 0):,}',
        'hm_passed_wt': f'{float(totals.passed_wt or 0):,.3f}',
        'hm_failed_pcs': f'{int(totals.failed_pcs or 0):,}',
        'hm_failed_wt': f'{float(totals.failed_wt or 0):,.3f}',
    }


def hierarchy_query(group_columns, months, filters, conditions, sort_by, sort_dir):
    month_sort = sort_by in [month.lower() for month in months]
    if month_sort:
        sort_expression = func.sum(case(
            (
                func.lower(PartyHallmarkPassFailSnapshot.month) == sort_by,
                PartyHallmarkPassFailSnapshot.hm_issue_wt,
            ),
            else_=0,
        ))
        query = db.session.query(*group_columns, sort_expression.label('sort_wt'))
        order_target = sort_expression
    else:
        query = db.session.query(*group_columns)
        order_target = group_columns[-1]

    query = apply_conditions(apply_filters(query, filters), conditions).group_by(*group_columns)
    direction = desc if sort_dir == 'desc' else asc
    return query.order_by(direction(order_target), *[asc(column) for column in group_columns])


def build_summary_rows(keys, group_columns, level, months, filters, conditions):
    if not keys:
        return []

    query = db.session.query(
        *group_columns,
        PartyHallmarkPassFailSnapshot.month,
        func.sum(PartyHallmarkPassFailSnapshot.hm_issue_pcs).label('issue_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_issue_wt).label('issue_wt'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_passed_pcs).label('passed_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_passed_wt).label('passed_wt'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_failed_pcs).label('failed_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_failed_wt).label('failed_wt'),
    )
    query = apply_conditions(apply_filters(query, filters), conditions)
    records = query.group_by(*group_columns, PartyHallmarkPassFailSnapshot.month).all()

    data_map = {}
    for record in records:
        key = tuple(record[index] for index in range(len(group_columns)))
        data_map.setdefault(key, {})[record.month] = {
            'issue_pcs': int(record.issue_pcs or 0),
            'issue_wt': float(record.issue_wt or 0),
            'passed_pcs': int(record.passed_pcs or 0),
            'passed_wt': float(record.passed_wt or 0),
            'failed_pcs': int(record.failed_pcs or 0),
            'failed_wt': float(record.failed_wt or 0),
        }

    rows = []
    for key in keys:
        normalized_key = key if isinstance(key, tuple) else (key,)
        rows.append({
            'party': normalized_key[0],
            'hallmarking_center': normalized_key[1] if len(normalized_key) > 1 else '',
            'months_data': data_map.get(normalized_key, {}),
            'level': level,
        })
    return rows


def build_metric_rows(parent_party, parent_center, months, filters):
    query = db.session.query(
        PartyHallmarkPassFailSnapshot.month,
        func.sum(PartyHallmarkPassFailSnapshot.hm_issue_pcs).label('issue_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_issue_wt).label('issue_wt'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_passed_pcs).label('passed_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_passed_wt).label('passed_wt'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_failed_pcs).label('failed_pcs'),
        func.sum(PartyHallmarkPassFailSnapshot.hm_failed_wt).label('failed_wt'),
    )
    query = apply_filters(query, filters).filter(
        PartyHallmarkPassFailSnapshot.party == parent_party,
        PartyHallmarkPassFailSnapshot.hallmarking_center == parent_center,
    )
    month_map = {
        record.month: record
        for record in query.group_by(PartyHallmarkPassFailSnapshot.month).all()
    }

    rows = []
    for metric_name, pcs_field, wt_field in METRICS:
        month_values = {}
        for month in months:
            record = month_map.get(month)
            month_values[month] = {
                'pcs': int(getattr(record, pcs_field) or 0) if record else 0,
                'wt': float(getattr(record, wt_field) or 0) if record else 0,
            }
        rows.append({
            'party': parent_party,
            'hallmarking_center': parent_center,
            'metric_name': metric_name,
            'months_data': month_values,
            'level': 'metric',
        })
    return rows


def main_report_context():
    filters = get_request_filters()
    months = get_months(filters)
    sort_by = request.args.get('sort_by', 'party').strip().lower()
    sort_dir = request.args.get('sort_dir', 'asc').strip().lower()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    group_columns = [PartyHallmarkPassFailSnapshot.party]
    query = hierarchy_query(group_columns, months, filters, [], sort_by, sort_dir)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    keys = [record[0] for record in pagination.items]

    return {
        'stats': get_stats(filters),
        'rows': build_summary_rows(
            keys,
            group_columns,
            'party',
            months,
            filters,
            [PartyHallmarkPassFailSnapshot.party.in_(keys)] if keys else [],
        ),
        'months': months,
        'pagination': pagination,
        'current_level': 'party',
        'sort_by': sort_by,
        'sort_dir': sort_dir,
        'filter_options': get_filter_options(),
    }


@dashboard_bp.route('/party-hallmark-pass-fail-performance')
def party_hallmark_pass_fail_performance():
    try:
        context = main_report_context()
        context.update({
            'unread_count': Notification.query.filter_by(is_read=False).count(),
            'sync_time': datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p'),
        })
        return render_template('party_hallmark_pass_fail_performance.html', **context)
    except Exception as exc:
        logger.exception('Party hallmark pass/fail report failed')
        return f'Error: {exc}', 500


@dashboard_bp.route('/partial/party-hallmark-pass-fail-performance')
@jwt_required()
def get_party_hallmark_pass_fail_performance_partial():
    try:
        filters = get_request_filters()
        months = get_months(filters)
        stats = get_stats(filters)
        sort_by = request.args.get('sort_by', 'party').strip().lower()
        sort_dir = request.args.get('sort_dir', 'asc').strip().lower()
        parent_party = request.args.get('parent_party', '').strip()
        parent_center = request.args.get('parent_center', '').strip()
        target_level = request.args.get('target_level', 'party').strip()
        is_child_rows = request.args.get('is_child_rows', 'false') == 'true'

        pagination = None
        if is_child_rows and target_level == 'hallmarking_center' and parent_party:
            group_columns = [
                PartyHallmarkPassFailSnapshot.party,
                PartyHallmarkPassFailSnapshot.hallmarking_center,
            ]
            conditions = [PartyHallmarkPassFailSnapshot.party == parent_party]
            query = hierarchy_query(
                group_columns, months, filters, conditions, sort_by, sort_dir
            )
            keys = [(record[0], record[1]) for record in query.all()]
            rows = build_summary_rows(
                keys, group_columns, 'hallmarking_center', months, filters, conditions
            )
            current_level = 'hallmarking_center'
        elif is_child_rows and target_level == 'metric' and parent_party and parent_center:
            rows = build_metric_rows(parent_party, parent_center, months, filters)
            current_level = 'metric'
        else:
            context = main_report_context()
            rows = context['rows']
            pagination = context['pagination']
            current_level = context['current_level']

        return render_template(
            'partials/_view_party_hallmark_pass_fail_performance.html',
            rows=rows,
            months=months,
            pagination=pagination,
            stats=stats,
            current_level=current_level,
            sort_by=sort_by,
            sort_dir=sort_dir,
            is_child_rows=is_child_rows,
        )
    except Exception as exc:
        logger.exception('Party hallmark pass/fail partial failed')
        return f'<div class="p-4 text-red-500">Error: {exc}</div>', 500
