from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PartyOrderLifecycleSnapshot
from app.extensions import db
from sqlalchemy import asc, desc, func
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


def split_filter_values(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def apply_multi_filter(query, column, value):
    values = split_filter_values(value)
    if not values:
        return query
    if len(values) == 1:
        return query.filter(column == values[0])
    return query.filter(column.in_(values))


def get_sort_params():
    allowed_columns = {
        'hierarchy',
        'order_count',
        'order_weight',
        'cancelled_weight',
        'production_weight',
        'delivered_weight',
    }
    sort_by = request.args.get('sort_by', 'hierarchy').strip().lower()
    sort_dir = request.args.get('sort_dir', 'asc').strip().lower()
    return (
        sort_by if sort_by in allowed_columns else 'hierarchy',
        sort_dir if sort_dir in {'asc', 'desc'} else 'asc',
    )


def apply_sort(query, group_cols, sort_by, sort_dir):
    model = PartyOrderLifecycleSnapshot
    sort_columns = {
        'order_count': func.count(func.distinct(model.order_number)),
        'order_weight': func.sum(model.order_weight),
        'cancelled_weight': func.sum(model.cancelled_weight),
        'production_weight': func.sum(model.production_weight),
        'delivered_weight': func.sum(model.delivered_weight),
    }
    sort_target = sort_columns.get(sort_by, group_cols[-1])
    sort_expression = desc(sort_target) if sort_dir == 'desc' else asc(sort_target)
    return query.order_by(
        sort_expression,
        *[asc(column) for column in group_cols],
    )


@dashboard_bp.route('/party-order-lifecycle-performance')
def party_order_lifecycle_performance():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Filters
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make_owner = request.args.get('make_owner', '')
        make = request.args.get('make', '')
        ornament_type = request.args.get('ornament_type', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        sort_by, sort_dir = get_sort_params()

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyOrderLifecycleSnapshot.party.ilike(f"%{search}%")) |
                    (PartyOrderLifecycleSnapshot.make.ilike(f"%{search}%")) |
                    (PartyOrderLifecycleSnapshot.make_owner.ilike(f"%{search}%")) |
                    (PartyOrderLifecycleSnapshot.ornament_type.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.party, party)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.make, make)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.ornament_type, ornament_type)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.provision_type, provision_type)
            return query

        def get_options(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        filter_options = {
            'parties': get_options(PartyOrderLifecycleSnapshot.party),
            'make_owners': get_options(PartyOrderLifecycleSnapshot.make_owner),
            'makes': get_options(PartyOrderLifecycleSnapshot.make),
            'ornament_types': get_options(PartyOrderLifecycleSnapshot.ornament_type),
            'order_types': get_options(PartyOrderLifecycleSnapshot.order_type),
            'provision_types': get_options(PartyOrderLifecycleSnapshot.provision_type),
        }

        # Global Aggregate Stats
        agg_cols = [
            func.count(func.distinct(PartyOrderLifecycleSnapshot.order_number)).label('total_orders'),
            func.sum(PartyOrderLifecycleSnapshot.order_weight).label('total_order_wt'),
            func.sum(PartyOrderLifecycleSnapshot.cancelled_weight).label('total_cancelled_wt'),
            func.sum(PartyOrderLifecycleSnapshot.production_weight).label('total_prod_wt'),
            func.sum(PartyOrderLifecycleSnapshot.delivered_weight).label('total_del_wt')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_orders': f"{int(aggs.total_orders or 0):,}",
            'order_wt': f"{float(aggs.total_order_wt or 0.0):,.3f}",
            'cancelled_wt': f"{float(aggs.total_cancelled_wt or 0.0):,.3f}",
            'production_wt': f"{float(aggs.total_prod_wt or 0.0):,.3f}",
            'delivered_wt': f"{float(aggs.total_del_wt or 0.0):,.3f}"
        }

        # Hierarchy level logic: Party -> Make (Make Owner) -> ornament_type
        if not party:
            group_cols = [PartyOrderLifecycleSnapshot.party]
            level = 'party'
        elif not make:
            group_cols = [
                PartyOrderLifecycleSnapshot.party,
                PartyOrderLifecycleSnapshot.make,
                PartyOrderLifecycleSnapshot.make_owner
            ]
            level = 'make'
        else:
            group_cols = [
                PartyOrderLifecycleSnapshot.party,
                PartyOrderLifecycleSnapshot.make,
                PartyOrderLifecycleSnapshot.make_owner,
                PartyOrderLifecycleSnapshot.ornament_type
            ]
            level = 'ornament_type'

        row_agg_cols = [
            func.count(func.distinct(PartyOrderLifecycleSnapshot.order_number)).label('order_count'),
            func.sum(PartyOrderLifecycleSnapshot.order_weight).label('ord_wt'),
            func.sum(PartyOrderLifecycleSnapshot.cancelled_weight).label('can_wt'),
            func.sum(PartyOrderLifecycleSnapshot.production_weight).label('prod_wt'),
            func.sum(PartyOrderLifecycleSnapshot.delivered_weight).label('del_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols)
        main_q = apply_sort(main_q, group_cols, sort_by, sort_dir)

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level in ('make', 'ornament_type') else '',
                'make_owner': r[2] if level in ('make', 'ornament_type') else '',
                'ornament_type': r[3] if level == 'ornament_type' else '',
                'order_count': int(r.order_count or 0),
                'order_weight': float(r.ord_wt or 0.0),
                'cancelled_weight': float(r.can_wt or 0.0),
                'production_weight': float(r.prod_wt or 0.0),
                'delivered_weight': float(r.del_wt or 0.0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('party_order_lifecycle_performance.html',
                             unread_count=unread_count,
                             sync_time=sync_time,
                             stats=stats,
                             rows=processed_rows,
                             pagination=pagination,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             filter_options=filter_options)
    except Exception as e:
        logger.error(f"Error in party_order_lifecycle_performance: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/party-order-lifecycle-performance')
@jwt_required()
def get_party_order_lifecycle_performance_partial():
    try:
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make_owner = request.args.get('make_owner', '')
        make = request.args.get('make', '')
        ornament_type = request.args.get('ornament_type', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        sort_by, sort_dir = get_sort_params()

        parent_party = request.args.get('parent_party', '')
        parent_make = request.args.get('parent_make', '')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        target_level = request.args.get('target_level', '')
        is_child_rows = request.args.get('is_child_rows', 'false') == 'true'

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyOrderLifecycleSnapshot.party.ilike(f"%{search}%")) |
                    (PartyOrderLifecycleSnapshot.make.ilike(f"%{search}%")) |
                    (PartyOrderLifecycleSnapshot.make_owner.ilike(f"%{search}%")) |
                    (PartyOrderLifecycleSnapshot.ornament_type.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.party, party)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.make, make)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.ornament_type, ornament_type)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyOrderLifecycleSnapshot.provision_type, provision_type)
            return query

        # Global Aggregate Stats
        agg_cols = [
            func.count(func.distinct(PartyOrderLifecycleSnapshot.order_number)).label('total_orders'),
            func.sum(PartyOrderLifecycleSnapshot.order_weight).label('total_order_wt'),
            func.sum(PartyOrderLifecycleSnapshot.cancelled_weight).label('total_cancelled_wt'),
            func.sum(PartyOrderLifecycleSnapshot.production_weight).label('total_prod_wt'),
            func.sum(PartyOrderLifecycleSnapshot.delivered_weight).label('total_del_wt')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_orders': f"{int(aggs.total_orders or 0):,}",
            'order_wt': f"{float(aggs.total_order_wt or 0.0):,.3f}",
            'cancelled_wt': f"{float(aggs.total_cancelled_wt or 0.0):,.3f}",
            'production_wt': f"{float(aggs.total_prod_wt or 0.0):,.3f}",
            'delivered_wt': f"{float(aggs.total_del_wt or 0.0):,.3f}"
        }

        # Hierarchy level logic
        if target_level:
            level = target_level
        elif parent_make:
            level = 'ornament_type'
        elif parent_party:
            level = 'make'
        elif not party:
            level = 'party'
        elif not make:
            level = 'make'
        else:
            level = 'ornament_type'

        if level == 'party':
            group_cols = [PartyOrderLifecycleSnapshot.party]
        elif level == 'make':
            group_cols = [
                PartyOrderLifecycleSnapshot.party,
                PartyOrderLifecycleSnapshot.make,
                PartyOrderLifecycleSnapshot.make_owner
            ]
        else:
            group_cols = [
                PartyOrderLifecycleSnapshot.party,
                PartyOrderLifecycleSnapshot.make,
                PartyOrderLifecycleSnapshot.make_owner,
                PartyOrderLifecycleSnapshot.ornament_type
            ]

        row_agg_cols = [
            func.count(func.distinct(PartyOrderLifecycleSnapshot.order_number)).label('order_count'),
            func.sum(PartyOrderLifecycleSnapshot.order_weight).label('ord_wt'),
            func.sum(PartyOrderLifecycleSnapshot.cancelled_weight).label('can_wt'),
            func.sum(PartyOrderLifecycleSnapshot.production_weight).label('prod_wt'),
            func.sum(PartyOrderLifecycleSnapshot.delivered_weight).label('del_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)

        if parent_party:
            main_q = main_q.filter(PartyOrderLifecycleSnapshot.party == parent_party)
        if parent_make and level == 'ornament_type':
            main_q = main_q.filter(PartyOrderLifecycleSnapshot.make == parent_make)

        main_q = main_q.group_by(*group_cols)
        main_q = apply_sort(main_q, group_cols, sort_by, sort_dir)

        if is_child_rows:
            items = main_q.all()
            pagination = None
        else:
            pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
            items = pagination.items

        processed_rows = []
        for r in items:
            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level in ('make', 'ornament_type') else '',
                'make_owner': r[2] if level in ('make', 'ornament_type') else '',
                'ornament_type': r[3] if level == 'ornament_type' else '',
                'order_count': int(r.order_count or 0),
                'order_weight': float(r.ord_wt or 0.0),
                'cancelled_weight': float(r.can_wt or 0.0),
                'production_weight': float(r.prod_wt or 0.0),
                'delivered_weight': float(r.del_wt or 0.0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('partials/_view_party_order_lifecycle_performance.html',
                             rows=processed_rows,
                             pagination=pagination,
                             stats=stats,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             is_child_rows=is_child_rows)
    except Exception as e:
        logger.error(f"Error in get_party_order_lifecycle_performance_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 500
