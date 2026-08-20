from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PartyDesignLocationAllocationSnapshot
from app.extensions import db
from sqlalchemy import asc, desc, func
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


def design_count_expression():
    model = PartyDesignLocationAllocationSnapshot
    return func.coalesce(
        func.sum(model.total_design_count),
        func.count(func.distinct(model.design_id)),
    )


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
    allowed_columns = {'hierarchy', 'design_count', 'delivered_weight'}
    sort_by = request.args.get('sort_by', 'hierarchy').strip().lower()
    sort_dir = request.args.get('sort_dir', 'asc').strip().lower()
    return (
        sort_by if sort_by in allowed_columns else 'hierarchy',
        sort_dir if sort_dir in {'asc', 'desc'} else 'asc',
    )


def apply_sort(query, group_cols, sort_by, sort_dir):
    model = PartyDesignLocationAllocationSnapshot
    sort_columns = {
        'design_count': design_count_expression(),
        'delivered_weight': func.sum(model.delivered_weight),
    }
    sort_target = sort_columns.get(sort_by, group_cols[-1])
    sort_expression = desc(sort_target) if sort_dir == 'desc' else asc(sort_target)
    return query.order_by(
        sort_expression,
        *[asc(column) for column in group_cols],
    )


@dashboard_bp.route('/party-design-location-allocation')
def party_design_location_allocation():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Filters
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make = request.args.get('make', '')
        zone = request.args.get('zone', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        sort_by, sort_dir = get_sort_params()

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyDesignLocationAllocationSnapshot.party.ilike(f"%{search}%")) |
                    (PartyDesignLocationAllocationSnapshot.zone.ilike(f"%{search}%")) |
                    (PartyDesignLocationAllocationSnapshot.make.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.party, party)
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.make, make)
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.zone, zone)
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.provision_type, provision_type)
            return query

        def get_options(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        filter_options = {
            'parties': get_options(PartyDesignLocationAllocationSnapshot.party),
            'makes': get_options(PartyDesignLocationAllocationSnapshot.make),
            'zones': get_options(PartyDesignLocationAllocationSnapshot.zone),
            'order_types': get_options(PartyDesignLocationAllocationSnapshot.order_type),
            'provision_types': get_options(PartyDesignLocationAllocationSnapshot.provision_type),
        }

        # Global Aggregate Stats
        agg_cols = [
            design_count_expression().label('total_design_count'),
            func.sum(PartyDesignLocationAllocationSnapshot.delivered_weight).label('total_delivered_weight')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_design_count': f"{int(aggs.total_design_count or 0):,}",
            'delivered_weight': f"{float(aggs.total_delivered_weight or 0):,.3f}"
        }

        # Hierarchy level logic: Party -> Zone -> Make
        if not party:
            group_cols = [PartyDesignLocationAllocationSnapshot.party]
            level = 'party'
        elif party and not zone:
            group_cols = [
                PartyDesignLocationAllocationSnapshot.party,
                PartyDesignLocationAllocationSnapshot.zone
            ]
            level = 'zone'
        else:
            group_cols = [
                PartyDesignLocationAllocationSnapshot.party,
                PartyDesignLocationAllocationSnapshot.zone,
                PartyDesignLocationAllocationSnapshot.make
            ]
            level = 'make'

        row_agg_cols = [
            design_count_expression().label('design_cnt'),
            func.sum(PartyDesignLocationAllocationSnapshot.delivered_weight).label('del_wt')
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
                'zone': r[1] if level in ['zone', 'make'] else '',
                'make': r[2] if level == 'make' else '',
                'total_design_count': int(r.design_cnt or 0),
                'delivered_weight': float(r.del_wt or 0.0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('party_design_location_allocation.html',
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
        logger.error(f"Error in party_design_location_allocation: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/party-design-location-allocation')
@jwt_required()
def get_party_design_location_allocation_partial():
    try:
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
        make = request.args.get('make', '')
        zone = request.args.get('zone', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')
        sort_by, sort_dir = get_sort_params()

        parent_party = request.args.get('parent_party', '')
        parent_zone = request.args.get('parent_zone', '')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        target_level = request.args.get('target_level', '')
        is_child_rows = request.args.get('is_child_rows', 'false') == 'true'

        def apply_filters(query):
            if search:
                query = query.filter(
                    (PartyDesignLocationAllocationSnapshot.party.ilike(f"%{search}%")) |
                    (PartyDesignLocationAllocationSnapshot.zone.ilike(f"%{search}%")) |
                    (PartyDesignLocationAllocationSnapshot.make.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.party, party)
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.make, make)
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.zone, zone)
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyDesignLocationAllocationSnapshot.provision_type, provision_type)
            return query

        # Global Aggregate Stats
        agg_cols = [
            design_count_expression().label('total_design_count'),
            func.sum(PartyDesignLocationAllocationSnapshot.delivered_weight).label('total_delivered_weight')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'total_design_count': f"{int(aggs.total_design_count or 0):,}",
            'delivered_weight': f"{float(aggs.total_delivered_weight or 0):,.3f}"
        }

        # Hierarchy level logic
        if target_level:
            level = target_level
        elif parent_zone and parent_party:
            level = 'make'
        elif parent_party:
            level = 'zone'
        elif not party:
            level = 'party'
        elif party and not zone:
            level = 'zone'
        else:
            level = 'make'

        if level == 'party':
            group_cols = [PartyDesignLocationAllocationSnapshot.party]
        elif level == 'zone':
            group_cols = [
                PartyDesignLocationAllocationSnapshot.party,
                PartyDesignLocationAllocationSnapshot.zone
            ]
        else:
            group_cols = [
                PartyDesignLocationAllocationSnapshot.party,
                PartyDesignLocationAllocationSnapshot.zone,
                PartyDesignLocationAllocationSnapshot.make
            ]

        row_agg_cols = [
            design_count_expression().label('design_cnt'),
            func.sum(PartyDesignLocationAllocationSnapshot.delivered_weight).label('del_wt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)

        if parent_party:
            main_q = main_q.filter(PartyDesignLocationAllocationSnapshot.party == parent_party)
        if parent_zone:
            main_q = main_q.filter(PartyDesignLocationAllocationSnapshot.zone == parent_zone)

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
                'zone': r[1] if level in ['zone', 'make'] else '',
                'make': r[2] if level == 'make' else '',
                'total_design_count': int(r.design_cnt or 0),
                'delivered_weight': float(r.del_wt or 0.0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('partials/_view_party_design_location_allocation.html',
                             rows=processed_rows,
                             pagination=pagination,
                             stats=stats,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             is_child_rows=is_child_rows)
    except Exception as e:
        logger.error(f"Error in get_party_design_location_allocation_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 500
