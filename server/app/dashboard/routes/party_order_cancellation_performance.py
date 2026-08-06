from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PartyOrderCancellationSnapshot
from app.extensions import db
from sqlalchemy import func, asc, desc
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


@dashboard_bp.route('/party-order-cancellation-performance')
def party_order_cancellation_performance():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Filters
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make_owner = request.args.get('make_owner', '')
        make = request.args.get('make', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        sort_by = request.args.get('sort_by', 'party').strip().lower()
        sort_dir = request.args.get('sort_dir', 'asc').strip().lower()

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyOrderCancellationSnapshot.supplier.ilike(f"%{search}%")) |
                    (PartyOrderCancellationSnapshot.make_owner.ilike(f"%{search}%")) |
                    (PartyOrderCancellationSnapshot.make.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.supplier, party)
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.make, make)
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.provision_type, provision_type)
            return query

        def get_options(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        filter_options = {
            'parties': get_options(PartyOrderCancellationSnapshot.supplier),
            'make_owners': get_options(PartyOrderCancellationSnapshot.make_owner),
            'makes': get_options(PartyOrderCancellationSnapshot.make),
            'order_types': get_options(PartyOrderCancellationSnapshot.order_type),
            'provision_types': get_options(PartyOrderCancellationSnapshot.provision_type),
        }

        # Global Aggregate Stats
        agg_cols = [
            func.sum(PartyOrderCancellationSnapshot.order_wt).label('total_order_wt'),
            func.sum(PartyOrderCancellationSnapshot.cancelled_wt).label('total_cancelled_wt')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        tot_ord_wt = float(aggs.total_order_wt or 0.0)
        tot_can_wt = float(aggs.total_cancelled_wt or 0.0)
        tot_can_pct = (tot_can_wt / tot_ord_wt * 100.0) if tot_ord_wt > 0 else 0.0

        stats = {
            'order_wt': f"{tot_ord_wt:,.3f}",
            'cancelled_wt': f"{tot_can_wt:,.3f}",
            'cancelled_pct': f"{tot_can_pct:.2f}%"
        }

        # Hierarchy level logic: Party -> Make (Make Owner)
        if not party:
            group_cols = [PartyOrderCancellationSnapshot.supplier]
            level = 'party'
        else:
            group_cols = [
                PartyOrderCancellationSnapshot.supplier,
                PartyOrderCancellationSnapshot.make,
                PartyOrderCancellationSnapshot.make_owner
            ]
            level = 'make'

        row_agg_cols = [
            func.sum(PartyOrderCancellationSnapshot.order_wt).label('ord_wt'),
            func.sum(PartyOrderCancellationSnapshot.cancelled_wt).label('can_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols)

        cancellation_pct = (
            func.sum(PartyOrderCancellationSnapshot.cancelled_wt)
            / func.nullif(func.sum(PartyOrderCancellationSnapshot.order_wt), 0)
        )
        sort_column_map = {
            'party': group_cols[-1],
            'make': group_cols[-1],
            'order_weight': func.sum(PartyOrderCancellationSnapshot.order_wt),
            'cancelled_weight': func.sum(PartyOrderCancellationSnapshot.cancelled_wt),
            'cancelled_pct': cancellation_pct,
        }
        order_target = sort_column_map.get(sort_by, group_cols[-1])
        order_expression = desc(order_target) if sort_dir == 'desc' else asc(order_target)
        main_q = main_q.order_by(order_expression, *[asc(column) for column in group_cols])

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            ord_wt = float(r.ord_wt or 0.0)
            can_wt = float(r.can_wt or 0.0)
            can_pct = (can_wt / ord_wt * 100.0) if ord_wt > 0 else 0.0

            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level == 'make' else '',
                'make_owner': r[2] if level == 'make' else '',
                'order_wt': ord_wt,
                'cancelled_wt': can_wt,
                'cancelled_pct': can_pct,
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('party_order_cancellation_performance.html',
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
        logger.error(f"Error in party_order_cancellation_performance: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/party-order-cancellation-performance')
@jwt_required()
def get_party_order_cancellation_performance_partial():
    try:
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make_owner = request.args.get('make_owner', '')
        make = request.args.get('make', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        sort_by = request.args.get('sort_by', 'party').strip().lower()
        sort_dir = request.args.get('sort_dir', 'asc').strip().lower()

        parent_party = request.args.get('parent_party', '')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        target_level = request.args.get('target_level', '')
        is_child_rows = request.args.get('is_child_rows', 'false') == 'true'

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyOrderCancellationSnapshot.supplier.ilike(f"%{search}%")) |
                    (PartyOrderCancellationSnapshot.make_owner.ilike(f"%{search}%")) |
                    (PartyOrderCancellationSnapshot.make.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.supplier, party)
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.make, make)
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyOrderCancellationSnapshot.provision_type, provision_type)
            return query

        # Global Aggregate Stats
        agg_cols = [
            func.sum(PartyOrderCancellationSnapshot.order_wt).label('total_order_wt'),
            func.sum(PartyOrderCancellationSnapshot.cancelled_wt).label('total_cancelled_wt')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        tot_ord_wt = float(aggs.total_order_wt or 0.0)
        tot_can_wt = float(aggs.total_cancelled_wt or 0.0)
        tot_can_pct = (tot_can_wt / tot_ord_wt * 100.0) if tot_ord_wt > 0 else 0.0

        stats = {
            'order_wt': f"{tot_ord_wt:,.3f}",
            'cancelled_wt': f"{tot_can_wt:,.3f}",
            'cancelled_pct': f"{tot_can_pct:.2f}%"
        }

        # Hierarchy level logic
        if target_level:
            level = target_level
        elif parent_party:
            level = 'make'
        elif not party:
            level = 'party'
        else:
            level = 'make'

        if level == 'party':
            group_cols = [PartyOrderCancellationSnapshot.supplier]
        else:
            group_cols = [
                PartyOrderCancellationSnapshot.supplier,
                PartyOrderCancellationSnapshot.make,
                PartyOrderCancellationSnapshot.make_owner
            ]

        row_agg_cols = [
            func.sum(PartyOrderCancellationSnapshot.order_wt).label('ord_wt'),
            func.sum(PartyOrderCancellationSnapshot.cancelled_wt).label('can_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)

        if parent_party:
            main_q = main_q.filter(PartyOrderCancellationSnapshot.supplier == parent_party)

        main_q = main_q.group_by(*group_cols)

        cancellation_pct = (
            func.sum(PartyOrderCancellationSnapshot.cancelled_wt)
            / func.nullif(func.sum(PartyOrderCancellationSnapshot.order_wt), 0)
        )
        sort_column_map = {
            'party': group_cols[-1],
            'make': group_cols[-1],
            'order_weight': func.sum(PartyOrderCancellationSnapshot.order_wt),
            'cancelled_weight': func.sum(PartyOrderCancellationSnapshot.cancelled_wt),
            'cancelled_pct': cancellation_pct,
        }
        order_target = sort_column_map.get(sort_by, group_cols[-1])
        order_expression = desc(order_target) if sort_dir == 'desc' else asc(order_target)
        main_q = main_q.order_by(order_expression, *[asc(column) for column in group_cols])

        if is_child_rows:
            items = main_q.all()
            pagination = None
        else:
            pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
            items = pagination.items

        processed_rows = []
        for r in items:
            ord_wt = float(r.ord_wt or 0.0)
            can_wt = float(r.can_wt or 0.0)
            can_pct = (can_wt / ord_wt * 100.0) if ord_wt > 0 else 0.0

            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level == 'make' else '',
                'make_owner': r[2] if level == 'make' else '',
                'order_wt': ord_wt,
                'cancelled_wt': can_wt,
                'cancelled_pct': can_pct,
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('partials/_view_party_order_cancellation_performance.html',
                             rows=processed_rows,
                             pagination=pagination,
                             stats=stats,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             is_child_rows=is_child_rows)
    except Exception as e:
        logger.error(f"Error in get_party_order_cancellation_performance_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 500
