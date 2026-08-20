from math import ceil
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from datetime import datetime

from flask import jsonify, render_template, request
from sqlalchemy import distinct, func, select, union

from app.dashboard import dashboard_bp
from app.extensions import db
from app.models import (
    Notification,
    PartyDesignAverageDeliveryDaysSnapshot,
    PartyOrderAcceptCancelDeliverySnapshot,
    PartyDesignLocationAllocationSnapshot,
    PartyOrderCancellationSnapshot,
    PartyMcStoneValueAllocationSnapshot,
    PartyHallmarkPassFailSnapshot,
    PartyRoWiseDeliverySnapshot,
    PartyOrderLifecycleSnapshot,
    PartyQcPassFailSnapshot,
)


PARTY_SOURCES = [
    PartyDesignAverageDeliveryDaysSnapshot.party,
    PartyOrderAcceptCancelDeliverySnapshot.supplier,
    PartyDesignLocationAllocationSnapshot.party,
    PartyOrderCancellationSnapshot.supplier,
    PartyMcStoneValueAllocationSnapshot.party,
    PartyHallmarkPassFailSnapshot.party,
    PartyRoWiseDeliverySnapshot.party,
    PartyOrderLifecycleSnapshot.party,
    PartyQcPassFailSnapshot.party,
]

ALLOWED_MATRIX_SORTS = {
    'party', 'design_count', 'avg_delivery_days', 'allocated_designs',
    'zone_count', 'order_wt', 'acceptance_pct', 'delivery_pct',
    'cancellation_pct', 'cancelled_order_count', 'direct_cancelled_wt',
    'mc_value', 'stone_value', 'hm_pass_pct', 'hm_fail_pct', 'ro_count',
    'ro_delivered_wt', 'lifecycle_orders', 'production_wt',
    'qc_pass_pct', 'qc_fail_pct', 'performance_index',
}


def split_values(value):
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def clean_party(value):
    return ' '.join((value or '').split())


def party_key(value):
    return clean_party(value).upper()


def ratio(numerator, denominator):
    return (float(numerator or 0) / float(denominator or 0) * 100) if denominator else 0.0


def apply_common_filters(query, model, party_column, filters):
    parties = split_values(filters['party'])
    if parties:
        query = query.filter(party_column.in_(parties))
    if filters['search']:
        query = query.filter(party_column.ilike(f"%{filters['search']}%"))
    order_types = split_values(filters['order_type'])
    if order_types and hasattr(model, 'order_type'):
        query = query.filter(model.order_type.in_(order_types))
    return query


def get_party_options():
    selects = [
        select(func.trim(column).label('party')).where(
            column.isnot(None),
            func.trim(column) != '',
        )
        for column in PARTY_SOURCES
    ]
    source = union(*selects).subquery()
    return db.session.execute(
        select(source.c.party).order_by(func.lower(source.c.party), source.c.party)
    ).scalars().all()


def get_common_options(column_name):
    columns = [
        getattr(column.class_, column_name)
        for column in PARTY_SOURCES
        if hasattr(column.class_, column_name)
    ]
    selects = [
        select(func.trim(column).label('value')).where(
            column.isnot(None),
            func.trim(column) != '',
        )
        for column in columns
    ]
    source = union(*selects).subquery()
    return db.session.execute(
        select(source.c.value).order_by(func.lower(source.c.value), source.c.value)
    ).scalars().all()


def build_matrix(filters):
    matrix = {}

    def target(name):
        key = party_key(name)
        if not key:
            return None
        if key not in matrix:
            matrix[key] = {'party': clean_party(name)}
        return matrix[key]

    model = PartyDesignAverageDeliveryDaysSnapshot
    query = db.session.query(
        model.party.label('party'),
        func.count(distinct(model.design_id)).label('design_count'),
        func.avg(model.average_delivery_days).label('avg_delivery_days'),
    ).group_by(model.party)
    for row in apply_common_filters(query, model, model.party, filters).all():
        item = target(row.party)
        item.update(
            design_count=int(row.design_count or 0),
            avg_delivery_days=float(row.avg_delivery_days or 0),
        )

    model = PartyOrderAcceptCancelDeliverySnapshot
    query = db.session.query(
        model.supplier.label('party'),
        func.sum(model.order_wt).label('order_wt'),
        func.sum(model.order_pcs).label('order_pcs'),
        func.sum(model.accepted_wt).label('accepted_wt'),
        func.sum(model.accepted_pcs).label('accepted_pcs'),
        func.sum(model.cancelled_wt).label('cancelled_wt'),
        func.sum(model.cancelled_pcs).label('cancelled_pcs'),
        func.sum(model.delivered_wt).label('delivered_wt'),
        func.sum(model.delivered_pcs).label('delivered_pcs'),
    ).group_by(model.supplier)
    for row in apply_common_filters(query, model, model.supplier, filters).all():
        item = target(row.party)
        item.update(
            order_wt=float(row.order_wt or 0),
            order_pcs=int(row.order_pcs or 0),
            accepted_wt=float(row.accepted_wt or 0),
            accepted_pcs=int(row.accepted_pcs or 0),
            cancelled_wt=float(row.cancelled_wt or 0),
            cancelled_pcs=int(row.cancelled_pcs or 0),
            delivered_wt=float(row.delivered_wt or 0),
            delivered_pcs=int(row.delivered_pcs or 0),
        )

    model = PartyDesignLocationAllocationSnapshot
    allocated_design_count = func.coalesce(
        func.sum(model.total_design_count),
        func.count(distinct(model.design_id)),
    )
    query = db.session.query(
        model.party.label('party'),
        allocated_design_count.label('allocated_designs'),
        func.count(distinct(model.zone)).label('zone_count'),
        func.sum(model.delivered_weight).label('allocation_delivered_wt'),
    ).group_by(model.party)
    for row in apply_common_filters(query, model, model.party, filters).all():
        item = target(row.party)
        item.update(
            allocated_designs=int(row.allocated_designs or 0),
            zone_count=int(row.zone_count or 0),
            allocation_delivered_wt=float(row.allocation_delivered_wt or 0),
        )

    model = PartyOrderCancellationSnapshot
    query = db.session.query(
        model.supplier.label('party'),
        func.count(distinct(model.order_no)).label('cancelled_order_count'),
        func.sum(model.order_wt).label('cancellation_order_wt'),
        func.sum(model.cancelled_wt).label('direct_cancelled_wt'),
    ).group_by(model.supplier)
    for row in apply_common_filters(query, model, model.supplier, filters).all():
        item = target(row.party)
        item.update(
            cancelled_order_count=int(row.cancelled_order_count or 0),
            cancellation_order_wt=float(row.cancellation_order_wt or 0),
            direct_cancelled_wt=float(row.direct_cancelled_wt or 0),
        )

    model = PartyMcStoneValueAllocationSnapshot
    query = db.session.query(
        model.party.label('party'),
        func.sum(model.total_metal_weight).label('metal_wt'),
        func.sum(model.total_mc_value).label('mc_value'),
        func.sum(model.stone_weight).label('stone_wt'),
        func.sum(model.stone_value).label('stone_value'),
    ).group_by(model.party)
    for row in apply_common_filters(query, model, model.party, filters).all():
        item = target(row.party)
        item.update(
            metal_wt=float(row.metal_wt or 0),
            mc_value=float(row.mc_value or 0),
            stone_wt=float(row.stone_wt or 0),
            stone_value=float(row.stone_value or 0),
        )

    model = PartyHallmarkPassFailSnapshot
    query = db.session.query(
        model.party.label('party'),
        func.sum(model.hm_issue_pcs).label('hm_issue_pcs'),
        func.sum(model.hm_passed_pcs).label('hm_passed_pcs'),
        func.sum(model.hm_failed_pcs).label('hm_failed_pcs'),
        func.sum(model.hm_issue_wt).label('hm_issue_wt'),
        func.sum(model.hm_passed_wt).label('hm_passed_wt'),
        func.sum(model.hm_failed_wt).label('hm_failed_wt'),
    ).group_by(model.party)
    for row in apply_common_filters(query, model, model.party, filters).all():
        item = target(row.party)
        item.update(
            hm_issue_pcs=int(row.hm_issue_pcs or 0),
            hm_passed_pcs=int(row.hm_passed_pcs or 0),
            hm_failed_pcs=int(row.hm_failed_pcs or 0),
            hm_issue_wt=float(row.hm_issue_wt or 0),
            hm_passed_wt=float(row.hm_passed_wt or 0),
            hm_failed_wt=float(row.hm_failed_wt or 0),
        )

    model = PartyRoWiseDeliverySnapshot
    query = db.session.query(
        model.party.label('party'),
        func.count(distinct(model.delivery_ro)).label('ro_count'),
        func.sum(model.delivered_weight).label('ro_delivered_wt'),
    ).group_by(model.party)
    for row in apply_common_filters(query, model, model.party, filters).all():
        item = target(row.party)
        item.update(
            ro_count=int(row.ro_count or 0),
            ro_delivered_wt=float(row.ro_delivered_wt or 0),
        )

    model = PartyOrderLifecycleSnapshot
    query = db.session.query(
        model.party.label('party'),
        func.count(distinct(model.order_number)).label('lifecycle_orders'),
        func.sum(model.order_weight).label('lifecycle_order_wt'),
        func.sum(model.production_weight).label('production_wt'),
        func.sum(model.delivered_weight).label('lifecycle_delivered_wt'),
    ).group_by(model.party)
    for row in apply_common_filters(query, model, model.party, filters).all():
        item = target(row.party)
        item.update(
            lifecycle_orders=int(row.lifecycle_orders or 0),
            lifecycle_order_wt=float(row.lifecycle_order_wt or 0),
            production_wt=float(row.production_wt or 0),
            lifecycle_delivered_wt=float(row.lifecycle_delivered_wt or 0),
        )

    model = PartyQcPassFailSnapshot
    query = db.session.query(
        model.party.label('party'),
        func.sum(model.qc_issue_pcs).label('qc_issue_pcs'),
        func.sum(model.qc_passed_pcs).label('qc_passed_pcs'),
        func.sum(model.qc_failed_pcs).label('qc_failed_pcs'),
        func.sum(model.qc_issue_wt).label('qc_issue_wt'),
        func.sum(model.qc_passed_wt).label('qc_passed_wt'),
        func.sum(model.qc_failed_wt).label('qc_failed_wt'),
    ).group_by(model.party)
    for row in apply_common_filters(query, model, model.party, filters).all():
        item = target(row.party)
        item.update(
            qc_issue_pcs=int(row.qc_issue_pcs or 0),
            qc_passed_pcs=int(row.qc_passed_pcs or 0),
            qc_failed_pcs=int(row.qc_failed_pcs or 0),
            qc_issue_wt=float(row.qc_issue_wt or 0),
            qc_passed_wt=float(row.qc_passed_wt or 0),
            qc_failed_wt=float(row.qc_failed_wt or 0),
        )

    rows = []
    for item in matrix.values():
        order_wt = item.get('order_wt', 0)
        item['acceptance_pct'] = ratio(item.get('accepted_wt'), order_wt)
        item['delivery_pct'] = ratio(item.get('delivered_wt'), order_wt)
        item['cancellation_pct'] = ratio(item.get('cancelled_wt'), order_wt)
        item['hm_pass_pct'] = ratio(item.get('hm_passed_pcs'), item.get('hm_issue_pcs'))
        item['qc_pass_pct'] = ratio(item.get('qc_passed_pcs'), item.get('qc_issue_pcs'))
        item['hm_fail_pct'] = ratio(item.get('hm_failed_pcs'), item.get('hm_issue_pcs'))
        item['qc_fail_pct'] = ratio(item.get('qc_failed_pcs'), item.get('qc_issue_pcs'))

        components = []
        if order_wt:
            components.extend([
                (min(item['delivery_pct'], 100), 0.30),
                (min(item['acceptance_pct'], 100), 0.20),
                (max(0, 100 - item['cancellation_pct']), 0.20),
            ])
        if item.get('hm_issue_pcs'):
            components.append((min(item['hm_pass_pct'], 100), 0.15))
        if item.get('qc_issue_pcs'):
            components.append((min(item['qc_pass_pct'], 100), 0.15))
        weight = sum(component_weight for _, component_weight in components)
        item['performance_index'] = (
            sum(value * component_weight for value, component_weight in components) / weight
            if weight else 0
        )
        item['index_sources'] = len(components)
        item['status'] = (
            'Limited' if len(components) < 2 else
            'Strong' if item['performance_index'] >= 85 else
            'Stable' if item['performance_index'] >= 70 else
            'Watch' if item['performance_index'] >= 50 else
            'Critical'
        )
        rows.append(item)
    return rows


def aggregate_stats(rows):
    order_wt = sum(row.get('order_wt', 0) for row in rows)
    accepted_wt = sum(row.get('accepted_wt', 0) for row in rows)
    delivered_wt = sum(row.get('delivered_wt', 0) for row in rows)
    hm_issue = sum(row.get('hm_issue_pcs', 0) for row in rows)
    hm_passed = sum(row.get('hm_passed_pcs', 0) for row in rows)
    qc_issue = sum(row.get('qc_issue_pcs', 0) for row in rows)
    qc_passed = sum(row.get('qc_passed_pcs', 0) for row in rows)
    design_count = sum(row.get('design_count', 0) for row in rows)
    weighted_days = sum(
        row.get('avg_delivery_days', 0) * row.get('design_count', 0)
        for row in rows
    )
    return {
        'party_count': len(rows),
        'design_count': design_count,
        'order_wt': order_wt,
        'acceptance_pct': ratio(accepted_wt, order_wt),
        'delivery_pct': ratio(delivered_wt, order_wt),
        'hm_pass_pct': ratio(hm_passed, hm_issue),
        'qc_pass_pct': ratio(qc_passed, qc_issue),
        'avg_delivery_days': weighted_days / design_count if design_count else 0,
    }


def get_matrix_report_context(args, include_page_options=True):
    filters = {
        'search': args.get('search', '').strip(),
        'party': args.get('party', '').strip(),
        'order_type': args.get('order_type', '').strip(),
    }
    sort_by = args.get('sort_by', 'order_wt').strip()
    sort_dir = args.get('sort_dir', 'desc').strip().lower()
    if sort_by not in ALLOWED_MATRIX_SORTS:
        sort_by = 'order_wt'
    if sort_dir not in {'asc', 'desc'}:
        sort_dir = 'desc'

    rows = build_matrix(filters)
    stats = aggregate_stats(rows)
    rows.sort(
        key=lambda row: (
            row.get(sort_by, '') if sort_by == 'party' else row.get(sort_by, 0),
            row['party'],
        ),
        reverse=sort_dir == 'desc',
    )

    chart_rows = rows[:10]
    chart_data = {
        'labels': [row['party'] for row in chart_rows],
        'order_weight': [round(row.get('order_wt', 0), 3) for row in chart_rows],
        'accepted_weight': [round(row.get('accepted_wt', 0), 3) for row in chart_rows],
        'delivered_weight': [round(row.get('delivered_wt', 0), 3) for row in chart_rows],
        'cancelled_weight': [round(row.get('cancelled_wt', 0), 3) for row in chart_rows],
        'hm_fail_rate': [
            round(ratio(row.get('hm_failed_pcs'), row.get('hm_issue_pcs')), 1)
            for row in chart_rows
        ],
        'qc_fail_rate': [
            round(ratio(row.get('qc_failed_pcs'), row.get('qc_issue_pcs')), 1)
            for row in chart_rows
        ],
        'delivery_days': [round(row.get('avg_delivery_days', 0), 1) for row in chart_rows],
    }

    page = max(args.get('page', 1, type=int), 1)
    per_page = args.get('per_page', 50, type=int)
    if per_page not in {25, 50, 100}:
        per_page = 50
    total = len(rows)
    pages = ceil(total / per_page) if total else 0
    if pages and page > pages:
        page = pages
    start = (page - 1) * per_page
    page_rows = rows[start:start + per_page]
    pagination = SimpleNamespace(
        page=page,
        pages=pages,
        total=total,
        per_page=per_page,
        has_prev=page > 1,
        has_next=page < pages,
        prev_num=page - 1,
        next_num=page + 1,
    )

    context = {
        'unread_count': Notification.query.filter_by(is_read=False).count(),
        'sync_time': datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p'),
        'rows': page_rows,
        'stats': stats,
        'chart_data': chart_data,
        'pagination': pagination,
        'sort_by': sort_by,
        'sort_dir': sort_dir,
    }
    if include_page_options:
        context['filter_options'] = {
            'parties': get_party_options(),
            'order_types': get_common_options('order_type'),
        }
    return context


@dashboard_bp.route('/party-performance-matrix')
def party_performance_matrix():
    sort_by = request.args.get('sort_by', 'order_wt').strip()
    sort_dir = request.args.get('sort_dir', 'desc').strip().lower()
    if sort_by not in ALLOWED_MATRIX_SORTS:
        sort_by = 'order_wt'
    if sort_dir not in {'asc', 'desc'}:
        sort_dir = 'desc'

    per_page = request.args.get('per_page', 50, type=int)
    if per_page not in {25, 50, 100}:
        per_page = 50

    return render_template(
        'party_performance_matrix.html',
        unread_count=Notification.query.filter_by(is_read=False).count(),
        sync_time=datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p'),
        rows=[],
        stats={
            'party_count': 0,
            'design_count': 0,
            'order_wt': 0,
            'delivery_pct': 0,
            'hm_pass_pct': 0,
            'qc_pass_pct': 0,
        },
        chart_data={
            'labels': [],
            'order_weight': [],
            'accepted_weight': [],
            'delivered_weight': [],
            'cancelled_weight': [],
            'hm_fail_rate': [],
            'qc_fail_rate': [],
            'delivery_days': [],
        },
        pagination=SimpleNamespace(
            page=1,
            pages=0,
            total=0,
            per_page=per_page,
            has_prev=False,
            has_next=False,
            prev_num=0,
            next_num=2,
        ),
        sort_by=sort_by,
        sort_dir=sort_dir,
        initial_loading=True,
        filter_options={
            'parties': get_party_options(),
            'order_types': get_common_options('order_type'),
        },
    )


@dashboard_bp.route('/partial/party-performance-matrix')
def party_performance_matrix_partial():
    context = get_matrix_report_context(request.args, include_page_options=False)
    return jsonify({
        'html': render_template(
            'partials/_party_performance_matrix_table.html',
            **context,
        ),
        'chart_data': context['chart_data'],
        'stats': context['stats'],
    })
