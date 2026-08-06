from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PartyRoWiseDeliverySnapshot
from app.extensions import db
from sqlalchemy import func
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


@dashboard_bp.route('/party-ro-wise-delivery-performance')
def party_ro_wise_delivery_performance():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Filters
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make = request.args.get('make', '')
        make_owner = request.args.get('make_owner', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyRoWiseDeliverySnapshot.party.ilike(f"%{search}%")) |
                    (PartyRoWiseDeliverySnapshot.make.ilike(f"%{search}%")) |
                    (PartyRoWiseDeliverySnapshot.make_owner.ilike(f"%{search}%")) |
                    (PartyRoWiseDeliverySnapshot.delivery_ro.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.party, party)
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.make, make)
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.provision_type, provision_type)
            return query

        def get_options(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        filter_options = {
            'parties': get_options(PartyRoWiseDeliverySnapshot.party),
            'makes': get_options(PartyRoWiseDeliverySnapshot.make),
            'make_owners': get_options(PartyRoWiseDeliverySnapshot.make_owner),
            'order_types': get_options(PartyRoWiseDeliverySnapshot.order_type),
            'provision_types': get_options(PartyRoWiseDeliverySnapshot.provision_type),
        }

        # Global Aggregate Stats
        agg_cols = [
            func.count(func.distinct(PartyRoWiseDeliverySnapshot.delivery_ro)).label('total_ro_count'),
            func.sum(PartyRoWiseDeliverySnapshot.delivered_weight).label('total_delivered_wt')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_ro_count': f"{int(aggs.total_ro_count or 0):,}",
            'total_delivered_wt': f"{float(aggs.total_delivered_wt or 0.0):,.3f}"
        }

        # Hierarchy level logic: Party -> Make (Make Owner)
        if not party:
            group_cols = [PartyRoWiseDeliverySnapshot.party]
            level = 'party'
        else:
            group_cols = [
                PartyRoWiseDeliverySnapshot.party,
                PartyRoWiseDeliverySnapshot.make,
                PartyRoWiseDeliverySnapshot.make_owner
            ]
            level = 'make'

        row_agg_cols = [
            func.string_agg(func.distinct(PartyRoWiseDeliverySnapshot.delivery_ro), ', ').label('delivery_ros'),
            func.sum(PartyRoWiseDeliverySnapshot.delivered_weight).label('del_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)
        main_q = main_q.group_by(*group_cols).order_by(*group_cols)

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            ros_str = r.delivery_ros or ''
            ros_list = [ro.strip() for ro in ros_str.split(',') if ro.strip()]
            
            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level == 'make' else '',
                'make_owner': r[2] if level == 'make' else '',
                'delivery_ros': ros_list,
                'delivered_weight': float(r.del_wt or 0.0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('party_ro_wise_delivery_performance.html',
                             unread_count=unread_count,
                             sync_time=sync_time,
                             stats=stats,
                             rows=processed_rows,
                             pagination=pagination,
                             current_level=level,
                             filter_options=filter_options)
    except Exception as e:
        logger.error(f"Error in party_ro_wise_delivery_performance: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/party-ro-wise-delivery-performance')
@jwt_required()
def get_party_ro_wise_delivery_performance_partial():
    try:
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make = request.args.get('make', '')
        make_owner = request.args.get('make_owner', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')

        parent_party = request.args.get('parent_party', '')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        target_level = request.args.get('target_level', '')
        is_child_rows = request.args.get('is_child_rows', 'false') == 'true'

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyRoWiseDeliverySnapshot.party.ilike(f"%{search}%")) |
                    (PartyRoWiseDeliverySnapshot.make.ilike(f"%{search}%")) |
                    (PartyRoWiseDeliverySnapshot.make_owner.ilike(f"%{search}%")) |
                    (PartyRoWiseDeliverySnapshot.delivery_ro.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.party, party)
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.make, make)
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyRoWiseDeliverySnapshot.provision_type, provision_type)
            return query

        # Global Aggregate Stats
        agg_cols = [
            func.count(func.distinct(PartyRoWiseDeliverySnapshot.delivery_ro)).label('total_ro_count'),
            func.sum(PartyRoWiseDeliverySnapshot.delivered_weight).label('total_delivered_wt')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_ro_count': f"{int(aggs.total_ro_count or 0):,}",
            'total_delivered_wt': f"{float(aggs.total_delivered_wt or 0.0):,.3f}"
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
            group_cols = [PartyRoWiseDeliverySnapshot.party]
        else:
            group_cols = [
                PartyRoWiseDeliverySnapshot.party,
                PartyRoWiseDeliverySnapshot.make,
                PartyRoWiseDeliverySnapshot.make_owner
            ]

        row_agg_cols = [
            func.string_agg(func.distinct(PartyRoWiseDeliverySnapshot.delivery_ro), ', ').label('delivery_ros'),
            func.sum(PartyRoWiseDeliverySnapshot.delivered_weight).label('del_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)

        if parent_party:
            main_q = main_q.filter(PartyRoWiseDeliverySnapshot.party == parent_party)

        main_q = main_q.group_by(*group_cols).order_by(*group_cols)

        if is_child_rows:
            items = main_q.all()
            pagination = None
        else:
            pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
            items = pagination.items

        processed_rows = []
        for r in items:
            ros_str = r.delivery_ros or ''
            ros_list = [ro.strip() for ro in ros_str.split(',') if ro.strip()]

            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level == 'make' else '',
                'make_owner': r[2] if level == 'make' else '',
                'delivery_ros': ros_list,
                'delivered_weight': float(r.del_wt or 0.0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('partials/_view_party_ro_wise_delivery_performance.html',
                             rows=processed_rows,
                             pagination=pagination,
                             stats=stats,
                             current_level=level,
                             is_child_rows=is_child_rows)
    except Exception as e:
        logger.error(f"Error in get_party_ro_wise_delivery_performance_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 500
