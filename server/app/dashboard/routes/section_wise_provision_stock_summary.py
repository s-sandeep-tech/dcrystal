from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.extensions import db, redis_client
from app.models.snapshots import ProvisionStockRawSnapshot
from app.utils.cache_utils import generate_cache_key
from app.services.section_wise_provision_stock_summary_data import (
    SectionWiseProvisionStockSummaryData,
)
from datetime import datetime
from zoneinfo import ZoneInfo
from app.utils.decorators import require_perm
import logging
import json

logger = logging.getLogger(__name__)

FRANCHISE_INDIA_HEAD_ROLE = 'FRANCHISE_INDIA_HEAD'
FRANCHISE_INDIA_BRANCH_TYPE = 'FRANCHISE_SHOP'


def is_franchise_india_head(roles):
    return FRANCHISE_INDIA_HEAD_ROLE in roles and 'SUPER_ADMIN' not in roles


def apply_franchise_india_branch_param(params, roles):
    if is_franchise_india_head(roles):
        params['branch_type'] = FRANCHISE_INDIA_BRANCH_TYPE


@dashboard_bp.route('/section-wise-provision-stock-summary')
@dashboard_bp.route('/section-provision-stock-summary')
@jwt_required()
def section_wise_provision_stock_summary():
    try:
        snapshot_date = SectionWiseProvisionStockSummaryData.latest_snapshot_date()
        is_today = True
        if snapshot_date:
            sync_time = snapshot_date.strftime("%d, %I:%M %p")
            today_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
            if snapshot_date.date() == today_date:
                is_today = True
            else:
                is_today = False
        else:
            sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d, %I:%M %p")

        roles = [r.upper() for r in session.get('roles', [])]
        base_q = db.session.query(ProvisionStockRawSnapshot)
        if is_franchise_india_head(roles):
            base_q = base_q.filter(ProvisionStockRawSnapshot.branch_type == FRANCHISE_INDIA_BRANCH_TYPE)
        divisions = [
            r[0] for r in base_q.with_entities(
                ProvisionStockRawSnapshot.division.distinct()
            ).order_by(ProvisionStockRawSnapshot.division).all() if r[0]
        ]

        return render_template(
            'section_wise_provision_stock_summary.html',
            sync_time=sync_time,
            is_today=is_today,
            divisions=divisions,
        )
    except Exception as e:
        logger.error(f"Error in section_wise_provision_stock_summary: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/api/section-wise-provision-stock-summary/options')
@jwt_required()
def section_wise_provision_stock_summary_options():
    try:
        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        authorized_branch_ids = []
        if not is_admin and not is_manager and is_showroom_manager and user_id:
            authorized_branch_ids = (
                SectionWiseProvisionStockSummaryData.authorized_branch_ids(user_id)
            )

        snapshot_date = SectionWiseProvisionStockSummaryData.latest_snapshot_date()
        date_str = snapshot_date.strftime("%Y%m%d%H%M%S") if snapshot_date else "latest"

        cache_suffix = "all"
        if is_franchise_india_head(roles):
            cache_suffix = "franchise_india_head"
        elif not is_admin and not is_manager:
            if is_business_head and user_id:
                cache_suffix = f"bh_{user_id}"
            elif is_showroom_manager and user_id:
                cache_suffix = f"sm_{user_id}"

        cache_key = (
            f"section_wise_provision_stock_summary_options_v1:"
            f"{date_str}:{cache_suffix}"
        )

        cached_data = redis_client.get(cache_key)
        if cached_data:
            parsed = json.loads(cached_data)
            if 'divisions' in parsed:
                redis_client.expire(cache_key, 18000)
                return jsonify(parsed)

        data = SectionWiseProvisionStockSummaryData.fetch_filter_options(
            branch_type=(
                FRANCHISE_INDIA_BRANCH_TYPE
                if is_franchise_india_head(roles) else None
            ),
            business_head_emp_code=(
                user_id
                if not is_admin and not is_manager and is_business_head else None
            ),
            authorized_branch_ids=(
                authorized_branch_ids
                if not is_admin and not is_manager and is_showroom_manager else None
            ),
            deny_all=(
                not is_admin and not is_manager
                and is_showroom_manager and not authorized_branch_ids
            ),
        )

        redis_client.setex(cache_key, 18000, json.dumps(data))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/section-wise-provision-stock-summary/collections/search')
@jwt_required()
def section_wise_provision_stock_summary_collections_search():
    try:
        q = request.args.get('q', '').strip()
        division = request.args.get('division', '').strip()

        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        authorized_branch_ids = (
            SectionWiseProvisionStockSummaryData.authorized_branch_ids(user_id)
            if not is_admin and not is_manager and is_showroom_manager else None
        )
        collections = SectionWiseProvisionStockSummaryData.search_collections(
            search=q,
            division=division if division else None,
            branch_type=(
                FRANCHISE_INDIA_BRANCH_TYPE
                if is_franchise_india_head(roles) else None
            ),
            business_head_emp_code=(
                user_id
                if not is_admin and not is_manager and is_business_head else None
            ),
            authorized_branch_ids=authorized_branch_ids,
            deny_all=(
                not is_admin and not is_manager
                and is_showroom_manager and not authorized_branch_ids
            ),
        )
        return jsonify(collections)
    except Exception as e:
        logger.error(f"Error in collections search: {str(e)}")
        return jsonify([]), 500


@dashboard_bp.route('/api/section-wise-provision-stock-summary/makes/search')
@jwt_required()
def section_wise_provision_stock_summary_makes_search():
    try:
        q = request.args.get('q', '').strip()
        division = request.args.get('division', '').strip()

        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        authorized_branch_ids = (
            SectionWiseProvisionStockSummaryData.authorized_branch_ids(user_id)
            if not is_admin and not is_manager and is_showroom_manager else None
        )
        makes = SectionWiseProvisionStockSummaryData.search_makes(
            search=q,
            division=division if division else None,
            branch_type=(
                FRANCHISE_INDIA_BRANCH_TYPE
                if is_franchise_india_head(roles) else None
            ),
            business_head_emp_code=(
                user_id
                if not is_admin and not is_manager and is_business_head else None
            ),
            authorized_branch_ids=authorized_branch_ids,
            deny_all=(
                not is_admin and not is_manager
                and is_showroom_manager and not authorized_branch_ids
            ),
        )
        return jsonify(makes)
    except Exception as e:
        logger.error(f"Error in makes search: {str(e)}")
        return jsonify([]), 500


@dashboard_bp.route('/partial/section-wise-provision-stock-summary')
@jwt_required()
def get_section_wise_provision_stock_summary_partial():
    try:
        location = request.args.get('location', '')
        division = request.args.get('division', 'Gold' if 'division' not in request.args else '')
        purity = request.args.get('purity', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')
        section = request.args.get('section', '')
        prov_type = request.args.get('prov_type', '')
        provision_mode = request.args.get('provision_mode', '')
        branch_type = request.args.get('branch_type', '')
        branch_status = request.args.get('branch_status', '')
        business_head = request.args.get('business_head', '')
        state = request.args.get('state', '')
        sort_by = request.args.get('sort_by', '')
        sort_order = request.args.get('sort_order', 'asc')

        params = {
            'location': location if location else None,
            'division': division if division else None,
            'state': state if state else None,
            'purity': purity if purity else None,
            'classification': classification if classification else None,
            'make': make if make else None,
            'collection': collection if collection else None,
            'section': section if section else None,
            'prov_type': prov_type if prov_type else None,
            'provision_mode': provision_mode if provision_mode else None,
            'branch_type': branch_type if branch_type else None,
            'branch_status': branch_status if branch_status else None,
            'business_head': business_head if business_head else None,
            'bh_emp_code': None,
            'authorized_branch_ids': None,
        }

        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        apply_franchise_india_branch_param(params, roles)

        if not is_admin and not is_manager:
            if is_business_head and user_id:
                params['bh_emp_code'] = user_id
            elif is_showroom_manager and user_id:
                branch_ids = SectionWiseProvisionStockSummaryData.authorized_branch_ids(
                    user_id
                )
                params['authorized_branch_ids'] = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        snapshot_date = SectionWiseProvisionStockSummaryData.latest_snapshot_date()
        cache_key = generate_cache_key(
            "section_wise_provision_stock_summary_partial_v1",
            snapshot_date,
            **params,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        cached_html = redis_client.get(cache_key)
        if cached_html:
            redis_client.expire(cache_key, 18000)
            return cached_html

        raw_rows = SectionWiseProvisionStockSummaryData.fetch_summary_rows(params)

        grand_totals = None
        tree_rows = []
        for r in raw_rows:
            if r['level_id'] == 0:
                grand_totals = r
            else:
                tree_rows.append(r)

        hierarchy_columns = ('section', 'make', 'collection', 'wide_range', 'type')
        hierarchy_labels = ('Section', 'Make', 'Collection', 'Wide Range', 'Type')
        node_ids = {}
        hierarchy_paths = []

        for index, row in enumerate(tree_rows, start=1):
            level = row['level_id']
            path = tuple(row[column] for column in hierarchy_columns[:level])
            hierarchy_paths.append(path)
            parent_path = path[:-1]
            node_id = f'sec-node-{index}'
            row['node_id'] = node_id
            row['parent_id'] = node_ids.get(parent_path, '')
            row['hierarchy_label'] = path[-1] if path else 'Unknown'
            row['hierarchy_level_name'] = hierarchy_labels[level - 1]
            row['is_leaf'] = (level == len(hierarchy_columns))
            node_ids[path] = node_id

        sibling_paths = {}
        for path in hierarchy_paths:
            sibling_paths.setdefault(path[:-1], []).append(path)

        for row, path in zip(tree_rows, hierarchy_paths):
            siblings = sibling_paths[path[:-1]]
            row['is_last_sibling'] = (path == siblings[-1])
            row['tree_ancestor_continuations'] = [
                ancestor_path != sibling_paths[ancestor_path[:-1]][-1]
                for depth in range(2, len(path))
                for ancestor_path in [path[:depth]]
            ]

        if not grand_totals and tree_rows:
            sec_rows = [r for r in tree_rows if r['level_id'] == 1]
            grand_totals = {
                'prov_pcs': sum((r['prov_pcs'] or 0) for r in sec_rows),
                'prov_gr_wt': sum((r['prov_gr_wt'] or 0) for r in sec_rows),
                'in_shop_wt': sum((r['in_shop_wt'] or 0) for r in sec_rows),
                'in_transit_wt': sum((r['in_transit_wt'] or 0) for r in sec_rows),
                'short_pcs': sum((r['short_pcs'] or 0) for r in sec_rows),
                'excess_pcs': sum((r['excess_pcs'] or 0) for r in sec_rows),
                'short_wt': sum((r['short_wt'] or 0) for r in sec_rows),
                'excess_wt': sum((r['excess_wt'] or 0) for r in sec_rows),
                'net_short_excess': sum((r['net_short_excess'] or 0) for r in sec_rows),
                'ordered_wt': sum((r['ordered_wt'] or 0) for r in sec_rows),
            }
            tot_wt = grand_totals['prov_gr_wt']
            short_pct_wt = sum(((r['short_percent'] or 0) * (r['prov_gr_wt'] or 0)) for r in sec_rows)
            grand_totals['short_percent'] = round(short_pct_wt / tot_wt, 2) if tot_wt else 0

        rendered_html = render_template(
            'partials/_view_section_wise_provision_stock_summary.html',
            rows=tree_rows,
            grand_totals=grand_totals,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        redis_client.setex(cache_key, 18000, rendered_html)
        return rendered_html

    except Exception as e:
        logger.error(f"Error in get_section_wise_provision_stock_summary_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200


@dashboard_bp.route('/api/section-wise-provision-stock-summary/export', methods=['POST'])
@jwt_required()
@require_perm('report.export')
def queue_section_wise_provision_stock_summary_export():
    try:
        data = request.get_json() or {}
        filters = data.get('filters', {})
        socket_id = data.get('socket_id')
        user_id = get_jwt_identity()

        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        session_user_id = session.get('user_id')

        bh_emp_code = None
        authorized_branch_ids = None
        if is_franchise_india_head(roles):
            filters['branch_type'] = FRANCHISE_INDIA_BRANCH_TYPE

        if not is_admin and not is_manager:
            if is_business_head and session_user_id:
                bh_emp_code = session_user_id
            elif is_showroom_manager and session_user_id:
                branch_ids = SectionWiseProvisionStockSummaryData.authorized_branch_ids(
                    session_user_id
                )
                authorized_branch_ids = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        filters['bh_emp_code'] = bh_emp_code
        filters['authorized_branch_ids'] = authorized_branch_ids

        task_payload = {
            'type': 'export_section_wise_provision_stock_summary',
            'filters': filters,
            'socket_id': socket_id,
            'user_id': user_id,
        }

        redis_client.rpush('export_queue', json.dumps(task_payload))
        logger.info(f"Queued section_wise_provision_stock_summary export for user {user_id}")

        return jsonify({'status': 'success', 'message': 'Export job enqueued.'}), 200
    except Exception as e:
        logger.error(f"Failed to queue section_wise_provision_stock_summary export: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

