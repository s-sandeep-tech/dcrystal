import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import jsonify, render_template, request, session
from flask_jwt_extended import jwt_required
from sqlalchemy import case, func

from app.dashboard import dashboard_bp
from app.extensions import db
from app.models import Notification, WeeklyDeliveryOrderSummarySnapshot


logger = logging.getLogger(__name__)

HIERARCHY = (
    ('classification', WeeklyDeliveryOrderSummarySnapshot.classification),
    ('make', WeeklyDeliveryOrderSummarySnapshot.make),
    ('collection', WeeklyDeliveryOrderSummarySnapshot.collection),
    ('purity', WeeklyDeliveryOrderSummarySnapshot.purity),
    ('party', WeeklyDeliveryOrderSummarySnapshot.party),
)


def ensure_weekly_delivery_table():
    WeeklyDeliveryOrderSummarySnapshot.__table__.create(db.engine, checkfirst=True)


def get_week_windows():
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    first_monday = today - timedelta(days=today.weekday())
    return [
        {
            'key': f'week_{index + 1}',
            'title': f'Week {index + 1}',
            'start': first_monday + timedelta(weeks=index),
            'end': first_monday + timedelta(weeks=index, days=6),
        }
        for index in range(5)
    ]


def apply_report_filters(query):
    filter_columns = {
        'classification': WeeklyDeliveryOrderSummarySnapshot.classification,
        'make': WeeklyDeliveryOrderSummarySnapshot.make,
        'collection': WeeklyDeliveryOrderSummarySnapshot.collection,
        'purity': WeeklyDeliveryOrderSummarySnapshot.purity,
        'party': WeeklyDeliveryOrderSummarySnapshot.party,
        'order_type': WeeklyDeliveryOrderSummarySnapshot.order_type,
        'order_request_type': WeeklyDeliveryOrderSummarySnapshot.order_request_type,
    }

    for parameter, column in filter_columns.items():
        value = request.args.get(parameter, '').strip()
        if value:
            query = query.filter(column == value)

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            WeeklyDeliveryOrderSummarySnapshot.classification.ilike(f'%{search}%') |
            WeeklyDeliveryOrderSummarySnapshot.make.ilike(f'%{search}%') |
            WeeklyDeliveryOrderSummarySnapshot.collection.ilike(f'%{search}%') |
            WeeklyDeliveryOrderSummarySnapshot.purity.ilike(f'%{search}%') |
            WeeklyDeliveryOrderSummarySnapshot.party.ilike(f'%{search}%')
        )

    return query


def apply_week_window(query, week_windows):
    return query.filter(
        WeeklyDeliveryOrderSummarySnapshot.delivery_week.between(
            week_windows[0]['start'], week_windows[-1]['end']
        )
    )


def aggregate_columns(week_windows):
    columns = [
        func.coalesce(func.sum(WeeklyDeliveryOrderSummarySnapshot.weight), 0).label('total_weight'),
        func.coalesce(
            func.sum(WeeklyDeliveryOrderSummarySnapshot.hallmark_completed_weight), 0
        ).label('hallmark_weight'),
        func.coalesce(
            func.sum(WeeklyDeliveryOrderSummarySnapshot.qc_completed_weight), 0
        ).label('qc_weight'),
    ]
    columns.extend(
        func.coalesce(
            func.sum(case(
                (
                    WeeklyDeliveryOrderSummarySnapshot.delivery_week.between(
                        week['start'], week['end']
                    ),
                    WeeklyDeliveryOrderSummarySnapshot.weight,
                ),
                else_=0,
            )),
            0,
        ).label(week['key'])
        for week in week_windows
    )
    return columns


def format_stats(query, week_windows):
    aggregates = query.with_entities(
        *aggregate_columns(week_windows),
        func.count(func.distinct(WeeklyDeliveryOrderSummarySnapshot.party)).label('party_count'),
    ).first()

    total_weight = float(aggregates.total_weight or 0)
    week_total = sum(float(getattr(aggregates, week['key']) or 0) for week in week_windows)

    def percentage(value):
        if total_weight <= 0:
            return 0
        return min(100, round((float(value or 0) / total_weight) * 100, 1))

    return {
        'total_weight': f'{total_weight:,.3f}',
        'hallmark_weight': f'{float(aggregates.hallmark_weight or 0):,.3f}',
        'hallmark_percentage': percentage(aggregates.hallmark_weight),
        'qc_weight': f'{float(aggregates.qc_weight or 0):,.3f}',
        'qc_percentage': percentage(aggregates.qc_weight),
        'current_week_weight': f'{float(aggregates.week_1 or 0):,.3f}',
        'current_week_percentage': percentage(aggregates.week_1),
        'party_count': f'{int(aggregates.party_count or 0):,}',
        'week_total': f'{week_total:,.3f}',
        **{
            week['key']: f'{float(getattr(aggregates, week["key"]) or 0):,.3f}'
            for week in week_windows
        },
    }


def filter_options():
    def distinct_values(column):
        return [
            row[0]
            for row in db.session.query(column).filter(
                column.isnot(None),
                func.trim(column) != '',
            ).distinct().order_by(column).all()
        ]

    return {
        'classifications': distinct_values(WeeklyDeliveryOrderSummarySnapshot.classification),
        'makes': distinct_values(WeeklyDeliveryOrderSummarySnapshot.make),
        'collections': distinct_values(WeeklyDeliveryOrderSummarySnapshot.collection),
        'purities': distinct_values(WeeklyDeliveryOrderSummarySnapshot.purity),
        'parties': distinct_values(WeeklyDeliveryOrderSummarySnapshot.party),
        'order_types': distinct_values(WeeklyDeliveryOrderSummarySnapshot.order_type),
        'order_request_types': distinct_values(
            WeeklyDeliveryOrderSummarySnapshot.order_request_type
        ),
    }


def parse_hierarchy_path():
    try:
        path = json.loads(request.args.get('path', '{}'))
    except (TypeError, ValueError):
        return {}
    allowed_keys = {name for name, _ in HIERARCHY}
    return {
        key: str(value).strip()
        for key, value in path.items()
        if key in allowed_keys and str(value).strip()
    }


@dashboard_bp.route('/weekly-delivery-order-summary')
def weekly_delivery_order_summary():
    try:
        ensure_weekly_delivery_table()
        return render_template(
            'weekly_delivery_order_summary.html',
            unread_count=Notification.query.filter_by(is_read=False).count(),
            sync_time=datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p'),
            stats=None,
            filter_options=filter_options(),
            week_windows=get_week_windows(),
        )
    except Exception as exc:
        logger.exception('Unable to load Weekly Delivery Order Summary')
        return f'Error: {exc}', 500


@dashboard_bp.route('/partial/weekly-delivery-order-summary')
@jwt_required()
def weekly_delivery_order_summary_partial():
    try:
        ensure_weekly_delivery_table()
        week_windows = get_week_windows()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        parent_level = request.args.get('parent_level', '').strip()
        parent_value = request.args.get('parent_value', '').strip()
        hierarchy_path = parse_hierarchy_path()

        hierarchy_names = [name for name, _ in HIERARCHY]
        if parent_level in hierarchy_names and parent_value:
            hierarchy_path[parent_level] = parent_value
            target_index = hierarchy_names.index(parent_level) + 1
        else:
            target_index = 0

        if target_index >= len(HIERARCHY):
            return ''

        base_query = apply_week_window(
            apply_report_filters(db.session.query(WeeklyDeliveryOrderSummarySnapshot)),
            week_windows,
        )
        for level_name, level_column in HIERARCHY:
            if hierarchy_path.get(level_name):
                base_query = base_query.filter(level_column == hierarchy_path[level_name])

        target_level, target_column = HIERARCHY[target_index]
        report_query = base_query.with_entities(
            target_column.label('label'),
            *aggregate_columns(week_windows),
        ).group_by(target_column).order_by(target_column)

        is_child_rows = bool(parent_level)
        if is_child_rows:
            result_rows = report_query.all()
            pagination = None
        else:
            pagination = report_query.paginate(
                page=page,
                per_page=per_page,
                error_out=False,
            )
            result_rows = pagination.items

        rows = []
        for result in result_rows:
            label = result.label or 'Unknown'
            row_path = dict(hierarchy_path)
            row_path[target_level] = label
            rows.append({
                'label': label,
                'level': target_level,
                'path': row_path,
                'total_weight': float(result.total_weight or 0),
                'hallmark_weight': float(result.hallmark_weight or 0),
                'qc_weight': float(result.qc_weight or 0),
                **{
                    week['key']: float(getattr(result, week['key']) or 0)
                    for week in week_windows
                },
            })

        stats_query = apply_week_window(
            apply_report_filters(db.session.query(WeeklyDeliveryOrderSummarySnapshot)),
            week_windows,
        )
        stats = format_stats(stats_query, week_windows)

        return render_template(
            'partials/_view_weekly_delivery_order_summary.html',
            rows=rows,
            pagination=pagination,
            current_level=target_level,
            is_child_rows=is_child_rows,
            stats=stats,
            week_windows=week_windows,
        )
    except Exception as exc:
        logger.exception('Unable to load Weekly Delivery Order Summary rows')
        return (
            '<div class="p-8 text-center text-red-500 font-bold">'
            f'Backend Error: {exc}</div>'
        ), 200


@dashboard_bp.route('/settings/sync-weekly-delivery-order-summary', methods=['POST'])
def settings_sync_weekly_delivery_order_summary():
    roles = {str(role).upper() for role in session.get('roles', [])}
    if not session.get('user_id') or not ({'ADMIN', 'DATA_SYNC_USER'} & roles):
        return {'status': 'error', 'message': 'Unauthorized: Admin or Data Sync role required'}, 401

    from app.utils.sync_manager import sync_weekly_delivery_order_summary_data

    result = sync_weekly_delivery_order_summary_data(session.get('user_id'))
    return jsonify(result), 200 if result.get('status') == 'success' else 500
