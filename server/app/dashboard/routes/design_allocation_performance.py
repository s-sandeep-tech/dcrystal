from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, DesignAllocationInfoSnapshot
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


@dashboard_bp.route('/design-allocation-performance')
def design_allocation_performance():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Filters & Sorting
        search = request.args.get('search', '').strip()
        make_owner = request.args.get('make_owner', '')
        make = request.args.get('make', '')
        section = request.args.get('section', '')
        wide_range = request.args.get('wide_range', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')

        sort_by = request.args.get('sort_by', 'make').strip().lower()
        sort_dir = request.args.get('sort_dir', 'asc').strip().lower()

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        def apply_filters(query):
            if search:
                query = query.filter(
                    (DesignAllocationInfoSnapshot.make.ilike(f"%{search}%")) |
                    (DesignAllocationInfoSnapshot.make_owner.ilike(f"%{search}%")) |
                    (DesignAllocationInfoSnapshot.section.ilike(f"%{search}%")) |
                    (DesignAllocationInfoSnapshot.wide_range.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.make, make)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.section, section)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.wide_range, wide_range)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.order_type, order_type)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.provision_type, provision_type)
            return query

        def get_options(column):
            return [
                r[0] for r in db.session.query(column)
                .filter(column.isnot(None), column != '')
                .distinct().order_by(column).all()
                if r[0]
            ]

        filter_options = {
            'make_owners': get_options(DesignAllocationInfoSnapshot.make_owner),
            'makes': get_options(DesignAllocationInfoSnapshot.make),
            'sections': get_options(DesignAllocationInfoSnapshot.section),
            'wide_ranges': get_options(DesignAllocationInfoSnapshot.wide_range),
            'order_types': get_options(DesignAllocationInfoSnapshot.order_type),
            'provision_types': get_options(DesignAllocationInfoSnapshot.provision_type),
        }

        # Global Aggregate Stats
        agg_cols = [
            func.sum(DesignAllocationInfoSnapshot.design_count).label('total_design_count')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        tot_design_cnt = int(aggs.total_design_count or 0)

        stats = {
            'total_design_count': f"{tot_design_cnt:,}"
        }

        # Hierarchy level logic: Make (Make Owner) -> section -> wide_range
        if not make:
            group_cols = [
                DesignAllocationInfoSnapshot.make,
                DesignAllocationInfoSnapshot.make_owner
            ]
            level = 'make'
        elif not section:
            group_cols = [
                DesignAllocationInfoSnapshot.make,
                DesignAllocationInfoSnapshot.make_owner,
                DesignAllocationInfoSnapshot.section
            ]
            level = 'section'
        else:
            group_cols = [
                DesignAllocationInfoSnapshot.make,
                DesignAllocationInfoSnapshot.make_owner,
                DesignAllocationInfoSnapshot.section,
                DesignAllocationInfoSnapshot.wide_range
            ]
            level = 'wide_range'

        row_agg_cols = [
            func.sum(DesignAllocationInfoSnapshot.design_count).label('d_cnt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q).group_by(*group_cols)

        # Sorting logic
        sort_col_map = {
            'make': group_cols[0],
            'section': group_cols[2] if level in ('section', 'wide_range') else group_cols[0],
            'wide_range': group_cols[3] if level == 'wide_range' else group_cols[0],
            'design_count': func.sum(DesignAllocationInfoSnapshot.design_count)
        }
        order_col = sort_col_map.get(sort_by, group_cols[0])
        if sort_dir == 'desc':
            main_q = main_q.order_by(desc(order_col))
        else:
            main_q = main_q.order_by(asc(order_col))

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            cnt = int(r.d_cnt or 0)
            pct = (cnt / tot_design_cnt * 100.0) if tot_design_cnt > 0 else 0.0

            row_dict = {
                'make': r[0] if len(r) > 0 else '',
                'make_owner': r[1] if len(r) > 1 else '',
                'section': r[2] if level in ('section', 'wide_range') else '',
                'wide_range': r[3] if level == 'wide_range' else '',
                'design_count': cnt,
                'design_count_pct': pct,
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('design_allocation_performance.html',
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
        logger.error(f"Error in design_allocation_performance: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/design-allocation-performance')
@jwt_required()
def get_design_allocation_performance_partial():
    try:
        search = request.args.get('search', '').strip()
        make_owner = request.args.get('make_owner', '')
        make = request.args.get('make', '')
        section = request.args.get('section', '')
        wide_range = request.args.get('wide_range', '')
        order_type = request.args.get('order_type', '')
        provision_type = request.args.get('provision_type', '')

        parent_make = request.args.get('parent_make', '')
        parent_section = request.args.get('parent_section', '')

        sort_by = request.args.get('sort_by', 'make').strip().lower()
        sort_dir = request.args.get('sort_dir', 'asc').strip().lower()

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        target_level = request.args.get('target_level', '')
        is_child_rows = request.args.get('is_child_rows', 'false') == 'true'

        def apply_filters(query):
            if search:
                query = query.filter(
                    (DesignAllocationInfoSnapshot.make.ilike(f"%{search}%")) |
                    (DesignAllocationInfoSnapshot.make_owner.ilike(f"%{search}%")) |
                    (DesignAllocationInfoSnapshot.section.ilike(f"%{search}%")) |
                    (DesignAllocationInfoSnapshot.wide_range.ilike(f"%{search}%"))
                )
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.make_owner, make_owner)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.make, make)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.section, section)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.wide_range, wide_range)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.order_type, order_type)
            query = apply_multi_filter(query, DesignAllocationInfoSnapshot.provision_type, provision_type)
            return query

        # Global Aggregate Stats
        agg_cols = [
            func.sum(DesignAllocationInfoSnapshot.design_count).label('total_design_count')
        ]
        agg_q = db.session.query(*agg_cols)
        agg_q = apply_filters(agg_q)
        aggs = agg_q.first()

        tot_design_cnt = int(aggs.total_design_count or 0)

        stats = {
            'total_design_count': f"{tot_design_cnt:,}"
        }

        # Hierarchy level logic
        if target_level:
            level = target_level
        elif parent_section:
            level = 'wide_range'
        elif parent_make:
            level = 'section'
        elif not make:
            level = 'make'
        elif not section:
            level = 'section'
        else:
            level = 'wide_range'

        if level == 'make':
            group_cols = [
                DesignAllocationInfoSnapshot.make,
                DesignAllocationInfoSnapshot.make_owner
            ]
        elif level == 'section':
            group_cols = [
                DesignAllocationInfoSnapshot.make,
                DesignAllocationInfoSnapshot.make_owner,
                DesignAllocationInfoSnapshot.section
            ]
        else:
            group_cols = [
                DesignAllocationInfoSnapshot.make,
                DesignAllocationInfoSnapshot.make_owner,
                DesignAllocationInfoSnapshot.section,
                DesignAllocationInfoSnapshot.wide_range
            ]

        row_agg_cols = [
            func.sum(DesignAllocationInfoSnapshot.design_count).label('d_cnt')
        ]

        main_q = db.session.query(*(group_cols + row_agg_cols))
        main_q = apply_filters(main_q)

        if parent_make:
            main_q = main_q.filter(DesignAllocationInfoSnapshot.make == parent_make)
        if parent_section and level == 'wide_range':
            main_q = main_q.filter(DesignAllocationInfoSnapshot.section == parent_section)

        main_q = main_q.group_by(*group_cols)

        # Sorting logic
        sort_col_map = {
            'make': group_cols[0],
            'section': group_cols[2] if level in ('section', 'wide_range') else group_cols[0],
            'wide_range': group_cols[3] if level == 'wide_range' else group_cols[0],
            'design_count': func.sum(DesignAllocationInfoSnapshot.design_count)
        }
        order_col = sort_col_map.get(sort_by, group_cols[0])
        if sort_dir == 'desc':
            main_q = main_q.order_by(desc(order_col))
        else:
            main_q = main_q.order_by(asc(order_col))

        if is_child_rows:
            items = main_q.all()
            pagination = None
        else:
            pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
            items = pagination.items

        processed_rows = []
        for r in items:
            cnt = int(r.d_cnt or 0)
            pct = (cnt / tot_design_cnt * 100.0) if tot_design_cnt > 0 else 0.0

            row_dict = {
                'make': r[0] if len(r) > 0 else '',
                'make_owner': r[1] if len(r) > 1 else '',
                'section': r[2] if level in ('section', 'wide_range') else '',
                'wide_range': r[3] if level == 'wide_range' else '',
                'design_count': cnt,
                'design_count_pct': pct,
                'level': level
            }
            processed_rows.append(row_dict)

        return render_template('partials/_view_design_allocation_performance.html',
                             rows=processed_rows,
                             pagination=pagination,
                             stats=stats,
                             current_level=level,
                             sort_by=sort_by,
                             sort_dir=sort_dir,
                             is_child_rows=is_child_rows)
    except Exception as e:
        logger.error(f"Error in get_design_allocation_performance_partial: {str(e)}")
        return f'<div class="p-4 text-red-500">Error: {str(e)}</div>', 500
