from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PartyMcStoneValueAllocationSnapshot
from app.extensions import db
from sqlalchemy import func, desc, asc
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


@dashboard_bp.route('/party-mc-stone-value-allocation')
def party_mc_stone_value_allocation():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Filters & Sorting
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
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
                    (PartyMcStoneValueAllocationSnapshot.party.ilike(f"%{search}%")) |
                    (PartyMcStoneValueAllocationSnapshot.make.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyMcStoneValueAllocationSnapshot.party, party)
            query = apply_multi_filter(query, PartyMcStoneValueAllocationSnapshot.make, make)
            query = apply_multi_filter(query, PartyMcStoneValueAllocationSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyMcStoneValueAllocationSnapshot.provision_type, provision_type)
            return query

        def get_options(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        filter_options = {
            'parties': get_options(PartyMcStoneValueAllocationSnapshot.party),
            'makes': get_options(PartyMcStoneValueAllocationSnapshot.make),
            'order_types': get_options(PartyMcStoneValueAllocationSnapshot.order_type),
            'provision_types': get_options(PartyMcStoneValueAllocationSnapshot.provision_type),
        }

        # Global Aggregate Stats
        agg_cols = [
            func.count(PartyMcStoneValueAllocationSnapshot.id).label('total_design_count'),
            func.sum(PartyMcStoneValueAllocationSnapshot.total_metal_weight).label('total_metal_weight'),
            func.sum(PartyMcStoneValueAllocationSnapshot.total_mc_value).label('total_mc_value'),
            func.sum(PartyMcStoneValueAllocationSnapshot.stone_weight).label('total_stone_weight'),
            func.sum(PartyMcStoneValueAllocationSnapshot.stone_value).label('total_stone_value')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'design_count': f"{int(aggs.total_design_count or 0):,}",
            'metal_weight': f"{float(aggs.total_metal_weight or 0.0):,.3f}",
            'mc_value': f"₹{float(aggs.total_mc_value or 0.0):,.2f}",
            'stone_weight': f"{float(aggs.total_stone_weight or 0.0):,.3f}",
            'stone_value': f"₹{float(aggs.total_stone_value or 0.0):,.2f}"
        }

        # Hierarchy level logic: Party -> Make
        if not party:
            group_cols = [PartyMcStoneValueAllocationSnapshot.party]
            level = 'party'
        else:
            group_cols = [
                PartyMcStoneValueAllocationSnapshot.party,
                PartyMcStoneValueAllocationSnapshot.make
            ]
            level = 'make'

        row_agg_cols = [
            func.count(PartyMcStoneValueAllocationSnapshot.id).label('d_cnt'),
            func.sum(PartyMcStoneValueAllocationSnapshot.total_metal_weight).label('m_wt'),
            func.sum(PartyMcStoneValueAllocationSnapshot.total_mc_value).label('mc_val'),
            func.sum(PartyMcStoneValueAllocationSnapshot.stone_weight).label('s_wt'),
            func.sum(PartyMcStoneValueAllocationSnapshot.stone_value).label('s_val')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q).group_by(*group_cols)

        # Dynamic Sorting
        sort_column_map = {
            'party': group_cols[0],
            'make': group_cols[0] if level == 'party' else group_cols[1],
            'design_count': func.count(PartyMcStoneValueAllocationSnapshot.id),
            'metal_weight': func.sum(PartyMcStoneValueAllocationSnapshot.total_metal_weight),
            'mc_value': func.sum(PartyMcStoneValueAllocationSnapshot.total_mc_value),
            'stone_weight': func.sum(PartyMcStoneValueAllocationSnapshot.stone_weight),
            'stone_value': func.sum(PartyMcStoneValueAllocationSnapshot.stone_value)
        }
        order_target = sort_column_map.get(sort_by, group_cols[0])
        if sort_dir == 'desc':
            main_q = main_q.order_by(desc(order_target))
        else:
            main_q = main_q.order_by(asc(order_target))

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            row_dict = {
                'party': r[0] if len(r) > 0 else '',
                'make': r[1] if level == 'make' else '',
                'design_count': int(r.d_cnt or 0),
                'total_metal_weight': float(r.m_wt or 0.0),
                'total_mc_value': float(r.mc_val or 0.0),
                'stone_weight': float(r.s_wt or 0.0),
                'stone_value': float(r.s_val or 0.0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('party_mc_stone_value_allocation.html',
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
        logger.error(f"Error in party_mc_stone_value_allocation: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/party-mc-stone-value-allocation')
@jwt_required()
def get_party_mc_stone_value_allocation_partial():
    try:
        search = request.args.get('search', '').strip()
        party = request.args.get('party', '')
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
                    (PartyMcStoneValueAllocationSnapshot.party.ilike(f"%{search}%")) |
                    (PartyMcStoneValueAllocationSnapshot.make.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, PartyMcStoneValueAllocationSnapshot.party, party)
            query = apply_multi_filter(query, PartyMcStoneValueAllocationSnapshot.make, make)
            query = apply_multi_filter(query, PartyMcStoneValueAllocationSnapshot.order_type, order_type)
            query = apply_multi_filter(query, PartyMcStoneValueAllocationSnapshot.provision_type, provision_type)
            return query

        # Global Aggregate Stats
        agg_cols = [
            func.count(PartyMcStoneValueAllocationSnapshot.id).label('total_design_count'),
            func.sum(PartyMcStoneValueAllocationSnapshot.total_metal_weight).label('total_metal_weight'),
            func.sum(PartyMcStoneValueAllocationSnapshot.total_mc_value).label('total_mc_value'),
            func.sum(PartyMcStoneValueAllocationSnapshot.stone_weight).label('total_stone_weight'),
            func.sum(PartyMcStoneValueAllocationSnapshot.stone_value).label('total_stone_value')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        stats = {
            'design_count': f"{int(aggs.total_design_count or 0):,}",
            'metal_weight': f"{float(aggs.total_metal_weight or 0.0):,.3f}",
            'mc_value': f"₹{float(aggs.total_mc_value or 0.0):,.2f}",
            'stone_weight': f"{float(aggs.total_stone_weight or 0.0):,.3f}",
            'stone_value': f"₹{float(aggs.total_stone_value or 0.0):,.2f}"
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
            group_cols = [PartyMcStoneValueAllocationSnapshot.party]
        else:
            group_cols = [
                PartyMcStoneValueAllocationSnapshot.party,
                PartyMcStoneValueAllocationSnapshot.make
            ]

        row_agg_cols = [
            func.count(PartyMcStoneValueAllocationSnapshot.id).label('d_cnt'),
            func.sum(PartyMcStoneValueAllocationSnapshot.total_metal_weight).label('m_wt'),
            func.sum(PartyMcStoneValueAllocationSnapshot.total_mc_value).label('mc_val'),
            func.sum(PartyMcStoneValueAllocationSnapshot.stone_weight).label('s_wt'),
            func.sum(PartyMcStoneValueAllocationSnapshot.stone_value).label('s_val')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)

        if parent_party:
            main_q = main_q.filter(PartyMcStoneValueAllocationSnapshot.party == parent_party)

        main_q = main_q.group_by(*group_cols)

        # Dynamic Sorting
        sort_column_map = {
            'party': group_cols[0],
            'make': group_cols[0] if level == 'party' else group_cols[1],
            'design_count': func.count(PartyMcStoneValueAllocationSnapshot.id),
            'metal_weight': func.sum(PartyMcStoneValueAllocationSnapshot.total_metal_weight),
            'mc_value': func.sum(PartyMcStoneValueAllocationSnapshot.total_mc_value),
            'stone_weight': func.sum(PartyMcStoneValueAllocationSnapshot.stone_weight),
            'stone_value': func.sum(PartyMcStoneValueAllocationSnapshot.stone_value)
        }
        order_target = sort_column_map.get(sort_by, group_cols[0])
        if sort_dir == 'desc':
            main_q = main_q.order_by(desc(order_target))
        else:
            main_q = main_q.order_by(asc(order_target))

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
                'make': r[1] if level == 'make' else '',
                'design_count': int(r.d_cnt or 0),
                'total_metal_weight': float(r.m_wt or 0.0),
                'total_mc_value': float(r.mc_val or 0.0),
                'stone_weight': float(r.s_wt or 0.0),
                'stone_value': float(r.s_val or 0.0),
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('partials/_view_party_mc_stone_value_allocation.html',
                             rows=processed_rows,
                             pagination=pagination,
                             stats=stats,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             is_child_rows=is_child_rows)
    except Exception as e:
        logger.error(f"Error in get_party_mc_stone_value_allocation_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 500
