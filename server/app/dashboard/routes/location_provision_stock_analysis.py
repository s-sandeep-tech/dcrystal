from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.extensions import redis_client
from app.utils.cache_utils import generate_cache_key
from app.services.location_provision_stock_analysis_data import (
    LocationProvisionStockAnalysisData,
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


@dashboard_bp.route('/location-provision-stock-analysis')
@jwt_required()
def location_provision_stock_analysis():
    try:
        snapshot_date = LocationProvisionStockAnalysisData.latest_snapshot_date()
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
            
        return render_template('location_provision_stock_analysis.html', sync_time=sync_time, is_today=is_today)
    except Exception as e:
        logger.error(f"Error in location_provision_stock_analysis: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/location-provision-stock-analysis/options')
@jwt_required()
def location_provision_stock_analysis_options():
    try:
        # Role-based filtering for Business Head
        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        # Get authorized branch IDs if showroom manager
        authorized_branch_ids = []
        if not is_admin and not is_manager and is_showroom_manager and user_id:
            authorized_branch_ids = (
                LocationProvisionStockAnalysisData.authorized_branch_ids(user_id)
            )

        # Check cache first
        snapshot_date = LocationProvisionStockAnalysisData.latest_snapshot_date()
        date_str = snapshot_date.strftime("%Y%m%d%H%M%S") if snapshot_date else "latest"
        
        # Role-aware cache key
        cache_suffix = "all"
        if is_franchise_india_head(roles):
            cache_suffix = "franchise_india_head"
        elif not is_admin and not is_manager:
            if is_business_head and user_id:
                cache_suffix = f"bh_{user_id}"
            elif is_showroom_manager and user_id:
                cache_suffix = f"sm_{user_id}"
            
        cache_key = (
            f"location_provision_stock_analysis_options_v2:"
            f"{date_str}:{cache_suffix}"
        )
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            redis_client.expire(cache_key, 18000)  # Sliding expiry
            return jsonify(json.loads(cached_data))

        data = LocationProvisionStockAnalysisData.fetch_filter_options(
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
        
        # Cache for 5 hours as requested
        redis_client.setex(cache_key, 18000, json.dumps(data))

        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/location-provision-stock-analysis/collections/search')
@jwt_required()
def location_provision_stock_analysis_collections_search():
    try:
        q = request.args.get('q', '').strip()
        
        # Role-based filtering (identical logic to options API)
        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        authorized_branch_ids = (
            LocationProvisionStockAnalysisData.authorized_branch_ids(user_id)
            if not is_admin and not is_manager and is_showroom_manager else None
        )
        collections = LocationProvisionStockAnalysisData.search_collections(
            search=q,
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

@dashboard_bp.route('/api/location-provision-stock-analysis/makes/search')
@jwt_required()
def location_provision_stock_analysis_makes_search():
    try:
        q = request.args.get('q', '').strip()
        
        # Role-based filtering
        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        authorized_branch_ids = (
            LocationProvisionStockAnalysisData.authorized_branch_ids(user_id)
            if not is_admin and not is_manager and is_showroom_manager else None
        )
        makes = LocationProvisionStockAnalysisData.search_makes(
            search=q,
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

@dashboard_bp.route('/partial/location-provision-stock-analysis')
@jwt_required()
def get_location_provision_stock_analysis_partial():
    try:
        # Read filters from request
        location = request.args.get('location', '')
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
            'sort_by': sort_by if sort_by else None,
            'sort_order': sort_order if sort_order else None
        }

        # Role-based filtering for Business Head
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
                branch_ids = LocationProvisionStockAnalysisData.authorized_branch_ids(
                    user_id
                )
                params['authorized_branch_ids'] = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        # Redis Caching Logic
        snapshot_date = LocationProvisionStockAnalysisData.latest_snapshot_date()
        cache_key = generate_cache_key(
            "location_provision_stock_analysis_partial_v9",
            snapshot_date,
            **params,
        )
        
        cached_html = redis_client.get(cache_key)
        if cached_html:
            redis_client.expire(cache_key, 18000)  # Sliding expiry
            return cached_html

        rows = LocationProvisionStockAnalysisData.fetch_summary_rows(params)

        # General In-memory sorting for all report sections
        numeric_cols = [
            'prov_pcs', 'prov_gr_wt', 'in_shop_wt', 'ordered_wt',
            'in_transit_wt', 'short_pcs', 'excess_pcs', 'short_wt',
            'excess_wt', 'short_percent',
        ]
        if sort_by in numeric_cols:
            sections = {}
            for row in rows:
                section_name = row['report_section']
                if section_name not in sections:
                    sections[section_name] = []
                sections[section_name].append(row)
            
            all_sorted_rows = []
            sorted_section_names = sorted(sections.keys(), key=lambda s: sections[s][0]['section_sort'])
            
            for s in sorted_section_names:
                sec_rows = sections[s]
                if s in ['Classification Wise', 'Collection Wise', 'Section Details']:
                    # Hierarchical sorting
                    key = 'classification' if s == 'Classification Wise' else ('collection' if s == 'Collection Wise' else 'sec_name')
                    
                    parents = [r for r in sec_rows if r['is_parent'] == 1]
                    parents.sort(key=lambda r: float(r.get(sort_by) or 0), reverse=(sort_order == 'desc'))
                    
                    for p in parents:
                        all_sorted_rows.append(p)
                        children = [r for r in sec_rows if r['is_parent'] == 0 and r.get(key) == p.get(key)]
                        children.sort(key=lambda r: float(r.get(sort_by) or 0), reverse=(sort_order == 'desc'))
                        all_sorted_rows.extend(children)
                else:
                    # Flat sorting
                    sec_rows.sort(key=lambda r: float(r.get(sort_by) or 0), reverse=(sort_order == 'desc'))
                    all_sorted_rows.extend(sec_rows)
            
            rows = all_sorted_rows
        
        rendered_html = render_template('partials/_view_location_provision_stock_analysis.html', 
                                      rows=rows, 
                                      sort_by=sort_by, 
                                      sort_order=sort_order)
        
        # Cache for 5 hours as requested
        redis_client.setex(cache_key, 18000, rendered_html)
        
        return rendered_html

    except Exception as e:
        logger.error(f"Error in get_location_provision_stock_analysis_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/location-provision-stock-analysis/drilldown')
@jwt_required()
def get_location_provision_stock_analysis_drilldown():
    try:
        # Read filters from request
        location = request.args.get('location', '')
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
        
        # Specific filter for the clicked section
        drill_section = request.args.get('drill_section', '')

        params = {
            'location': location if location else None,
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
            'state': state if state else None,
            'bh_emp_code': None,
            'authorized_branch_ids': None,
            'drill_section': drill_section if drill_section else None
        }

        # Role-based filtering for Business Head
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
                branch_ids = LocationProvisionStockAnalysisData.authorized_branch_ids(
                    user_id
                )
                params['authorized_branch_ids'] = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        # Hierarchical query for the analysis modal.
        rows = LocationProvisionStockAnalysisData.fetch_drilldown_rows(params)
        
        # Calculate Grand Total for the modal
        total_pcs = sum(r['prov_pcs'] or 0 for r in rows if r['level_id'] == 1)
        total_gr_wt = sum(r['prov_gr_wt'] or 0 for r in rows if r['level_id'] == 1)
        total_in_shop = sum(r['in_shop_wt'] or 0 for r in rows if r['level_id'] == 1)
        total_transit = sum(r['in_transit_wt'] or 0 for r in rows if r['level_id'] == 1)
        total_ordered = sum(r['ordered_wt'] or 0 for r in rows if r['level_id'] == 1)
        total_short_excess_pcs = sum(r['short_excess_pcs'] or 0 for r in rows if r['level_id'] == 1)
        
        total_short_excess = total_in_shop + total_transit - total_gr_wt
        total_percent = (total_short_excess * 100 / total_gr_wt) if total_gr_wt != 0 else 0
        
        modal_totals = {
            'prov_pcs': total_pcs,
            'prov_gr_wt': total_gr_wt,
            'in_shop_wt': total_in_shop,
            'ordered_wt': total_ordered,
            'in_transit_wt': total_transit,
            'short_excess_pcs': total_short_excess_pcs,
            'short_excess_wt': total_short_excess,
            'percent': total_percent
        }

        # We will reuse the provision partial view since it only loops rows
        return render_template('partials/_view_location_provision_stock_analysis_drilldown.html', 
                               rows=rows, 
                               modal_totals=modal_totals,
                               drill_section=drill_section,
                               include_purity_hierarchy=True,
                               include_piece_variance=True,
                               enable_in_shop_details=True)

    except Exception as e:
        logger.error(f"Error in get_location_provision_stock_analysis_drilldown: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200


@dashboard_bp.route('/api/location-provision-stock-analysis/location-details')
@jwt_required()
def get_location_provision_stock_analysis_location_details():
    try:
        detail_location = request.args.get('detail_location', '').strip()
        if not detail_location:
            return '<div class="p-8 text-center text-gray-500">Location is required.</div>', 400

        params = {
            'detail_location': detail_location,
            'state': request.args.get('state') or None,
            'purity': request.args.get('purity') or None,
            'classification': request.args.get('classification') or None,
            'make': request.args.get('make') or None,
            'collection': request.args.get('collection') or None,
            'section': request.args.get('section') or None,
            'prov_type': request.args.get('prov_type') or None,
            'provision_mode': request.args.get('provision_mode') or None,
            'branch_type': request.args.get('branch_type') or None,
            'branch_status': request.args.get('branch_status') or None,
            'business_head': request.args.get('business_head') or None,
            'bh_emp_code': None,
            'authorized_branch_ids': None,
        }

        roles = [role.upper() for role in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(
            role in roles for role in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR']
        )
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        apply_franchise_india_branch_param(params, roles)

        if not is_admin and not is_manager:
            if is_business_head and user_id:
                params['bh_emp_code'] = user_id
            elif is_showroom_manager and user_id:
                branch_ids = (
                    LocationProvisionStockAnalysisData.authorized_branch_ids(user_id)
                )
                params['authorized_branch_ids'] = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        rows = LocationProvisionStockAnalysisData.fetch_location_detail_rows(params)
        hierarchy_columns = (
            'group_name', 'purity', 'classification', 'sub_classification',
            'section', 'type', 'make', 'master_collection', 'collection',
            'sub_section', 'gender', 'wide_range', 'range_weight',
        )
        hierarchy_labels = (
            'Group', 'Purity', 'Classification', 'Sub Classification',
            'Section', 'Type', 'Make', 'Master Collection', 'Collection',
            'Sub Section', 'Gender', 'Wide Range', 'Range Weight',
        )
        node_ids = {}
        hierarchy_paths = []
        for index, row in enumerate(rows, start=1):
            level = row['level_id']
            path = tuple(row[column] for column in hierarchy_columns[:level])
            hierarchy_paths.append(path)
            parent_path = path[:-1]
            node_id = f'location-node-{index}'
            row['node_id'] = node_id
            row['parent_id'] = node_ids.get(parent_path, '')
            row['hierarchy_label'] = path[-1] if path else 'Unknown'
            row['hierarchy_level_name'] = hierarchy_labels[level - 1]
            row['is_leaf'] = level == len(hierarchy_columns)
            node_ids[path] = node_id

        sibling_paths = {}
        for path in hierarchy_paths:
            sibling_paths.setdefault(path[:-1], []).append(path)

        for row, path in zip(rows, hierarchy_paths):
            siblings = sibling_paths[path[:-1]]
            row['is_last_sibling'] = path == siblings[-1]
            row['tree_ancestor_continuations'] = [
                ancestor_path != sibling_paths[ancestor_path[:-1]][-1]
                for depth in range(2, len(path))
                for ancestor_path in [path[:depth]]
            ]

        total_rows = [row for row in rows if row['level_id'] == 1]
        totals = {
            'prov_gr_wt': sum((row['prov_gr_wt'] or 0) for row in total_rows),
            'in_shop_wt': sum((row['in_shop_wt'] or 0) for row in total_rows),
            'in_transit_wt': sum(
                (row['in_transit_wt'] or 0) for row in total_rows
            ),
            'ordered_wt': sum((row['ordered_wt'] or 0) for row in total_rows),
            'short_wt': sum((row['short_wt'] or 0) for row in total_rows),
            'excess_wt': sum((row['excess_wt'] or 0) for row in total_rows),
            'net_short_excess': sum(
                (row['net_short_excess'] or 0) for row in total_rows
            ),
        }
        short_percent_weight = sum(
            (row['short_percent_weight'] or 0) for row in total_rows
        )
        totals['short_percent'] = (
            short_percent_weight / totals['prov_gr_wt']
            if totals['prov_gr_wt'] else 0
        )

        return render_template(
            'partials/_view_location_provision_stock_analysis_location_details.html',
            rows=rows,
            totals=totals,
            detail_location=detail_location,
        )
    except Exception as e:
        logger.error(
            'Error in location provision stock location details: %s',
            str(e),
        )
        return (
            f'<div class="p-8 text-center text-red-500 font-bold">'
            f'Backend Error: {str(e)}</div>',
            200,
        )


@dashboard_bp.route('/api/location-provision-stock-analysis/in-shop-details')
@jwt_required()
def get_location_provision_stock_analysis_in_shop_details():
    try:
        page = max(request.args.get('page', 1, type=int), 1)
        per_page = 100
        drill_level = min(max(request.args.get('drill_level', 1, type=int), 1), 5)

        params = {
            'location': request.args.get('location') or None,
            'purity': request.args.get('purity') or None,
            'classification': request.args.get('classification') or None,
            'make': request.args.get('make') or None,
            'collection': request.args.get('collection') or None,
            'section': request.args.get('section') or None,
            'prov_type': request.args.get('prov_type') or None,
            'provision_mode': request.args.get('provision_mode') or None,
            'branch_type': request.args.get('branch_type') or None,
            'branch_status': request.args.get('branch_status') or None,
            'business_head': request.args.get('business_head') or None,
            'state': request.args.get('state') or None,
            'bh_emp_code': None,
            'authorized_branch_ids': None,
            'drill_level': drill_level,
            'drill_range_weight': request.args.get('drill_range_weight') or None,
            'drill_section_ids': request.args.get('drill_section_ids') or None,
            'drill_purity_ids': request.args.get('drill_purity_ids') or None,
            'drill_type_ids': request.args.get('drill_type_ids') or None,
            'drill_wide_range_ids': request.args.get('drill_wide_range_ids') or None,
            'limit': per_page,
            'offset': (page - 1) * per_page,
        }

        required_id_params = ['drill_section_ids']
        if drill_level >= 2:
            required_id_params.append('drill_purity_ids')
        if drill_level >= 3:
            required_id_params.append('drill_type_ids')
        if drill_level >= 4:
            required_id_params.append('drill_wide_range_ids')

        if any(not params[param] for param in required_id_params):
            return '<div class="p-8 text-center text-red-500">Required hierarchy IDs are missing.</div>', 400
        if drill_level >= 5 and params['drill_range_weight'] is None:
            return '<div class="p-8 text-center text-red-500">A range weight is required.</div>', 400

        roles = [role.upper() for role in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(role in roles for role in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        user_id = session.get('user_id')

        apply_franchise_india_branch_param(params, roles)

        if not is_admin and not is_manager:
            if 'BUSINESS_HEAD' in roles and user_id:
                params['bh_emp_code'] = user_id
            elif 'SHOWROOM_MANAGER' in roles and user_id:
                branch_ids = LocationProvisionStockAnalysisData.authorized_branch_ids(
                    user_id
                )
                params['authorized_branch_ids'] = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        hierarchy_id_columns = (
            'division_id', 'group_id', 'purity_id', 'classification_id',
            'sub_classification_id', 'section_id', 'type_id', 'make_id',
            'collection_id', 'master_collection_id', 'sub_section_id',
            'wide_range_id', 'gender_id', 'size_id', 'screw_type_id',
        )
        stock_identity_columns = ',\n        '.join(
            ('branch_id', *hierarchy_id_columns)
        )
        identity_join = '\n'.join(
            f'AND p.{column} = b.{column}'
            for column in ('branch_id', *hierarchy_id_columns)
        )

        rows = LocationProvisionStockAnalysisData.fetch_in_shop_detail_rows(
            params, stock_identity_columns, identity_join,
        )
        total_records = int(rows[0]['total_records']) if rows else 0
        total_pages = max((total_records + per_page - 1) // per_page, 1)

        return render_template(
            'partials/_view_location_provision_stock_analysis_in_shop_details.html',
            rows=rows,
            page=page,
            total_pages=total_pages,
            total_records=total_records,
            total_pieces=rows[0]['total_pieces'] if rows else 0,
            total_gross_wt=rows[0]['total_gross_wt'] if rows else 0,
        )
    except Exception as e:
        logger.exception('Error loading provision stock analysis in-shop details')
        return render_template(
            'partials/_view_location_provision_stock_analysis_in_shop_details.html',
            rows=[],
            page=1,
            total_pages=1,
            total_records=0,
            total_pieces=0,
            total_gross_wt=0,
            error_message=str(e),
        ), 500


@dashboard_bp.route('/api/location-provision-stock-analysis/provision-details')
@jwt_required()
def get_location_provision_stock_analysis_provision_details():
    try:
        page = max(request.args.get('page', 1, type=int), 1)
        per_page = 100
        drill_level = min(max(request.args.get('drill_level', 1, type=int), 1), 5)

        params = {
            'location': request.args.get('location') or None,
            'purity': request.args.get('purity') or None,
            'classification': request.args.get('classification') or None,
            'make': request.args.get('make') or None,
            'collection': request.args.get('collection') or None,
            'section': request.args.get('section') or None,
            'prov_type': request.args.get('prov_type') or None,
            'provision_mode': request.args.get('provision_mode') or None,
            'branch_type': request.args.get('branch_type') or None,
            'branch_status': request.args.get('branch_status') or None,
            'business_head': request.args.get('business_head') or None,
            'state': request.args.get('state') or None,
            'bh_emp_code': None,
            'authorized_branch_ids': None,
            'drill_level': drill_level,
            'drill_range_weight': request.args.get('drill_range_weight') or None,
            'drill_section_ids': request.args.get('drill_section_ids') or None,
            'drill_purity_ids': request.args.get('drill_purity_ids') or None,
            'drill_type_ids': request.args.get('drill_type_ids') or None,
            'drill_wide_range_ids': request.args.get('drill_wide_range_ids') or None,
            'limit': per_page,
            'offset': (page - 1) * per_page,
        }

        required_id_params = ['drill_section_ids']
        if drill_level >= 2:
            required_id_params.append('drill_purity_ids')
        if drill_level >= 3:
            required_id_params.append('drill_type_ids')
        if drill_level >= 4:
            required_id_params.append('drill_wide_range_ids')

        if any(not params[param] for param in required_id_params):
            return '<div class="p-8 text-center text-red-500">Required hierarchy IDs are missing.</div>', 400
        if drill_level >= 5 and params['drill_range_weight'] is None:
            return '<div class="p-8 text-center text-red-500">A range weight is required.</div>', 400

        roles = [role.upper() for role in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(role in roles for role in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        user_id = session.get('user_id')

        apply_franchise_india_branch_param(params, roles)

        if not is_admin and not is_manager:
            if 'BUSINESS_HEAD' in roles and user_id:
                params['bh_emp_code'] = user_id
            elif 'SHOWROOM_MANAGER' in roles and user_id:
                branch_ids = LocationProvisionStockAnalysisData.authorized_branch_ids(
                    user_id
                )
                params['authorized_branch_ids'] = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        rows = LocationProvisionStockAnalysisData.fetch_provision_detail_rows(params)
        total_records = int(rows[0]['total_records']) if rows else 0
        total_pages = max((total_records + per_page - 1) // per_page, 1)

        return render_template(
            'partials/_view_location_provision_stock_analysis_provision_details.html',
            rows=rows,
            page=page,
            total_pages=total_pages,
            total_records=total_records,
            total_pieces=rows[0]['total_pieces'] if rows else 0,
            total_gross_wt=rows[0]['total_gross_wt'] if rows else 0,
        )
    except Exception as e:
        logger.exception('Error loading provision stock analysis provision details')
        return render_template(
            'partials/_view_location_provision_stock_analysis_provision_details.html',
            rows=[],
            page=1,
            total_pages=1,
            total_records=0,
            total_pieces=0,
            total_gross_wt=0,
            error_message=str(e),
        ), 500


@dashboard_bp.route('/api/location-provision-stock-analysis/stock-comparison')
@jwt_required()
def get_location_provision_stock_analysis_comparison():
    try:
        page = max(request.args.get('page', 1, type=int), 1)
        per_page = 50
        drill_level = min(max(request.args.get('drill_level', 1, type=int), 1), 5)

        params = {
            'location': request.args.get('location') or None,
            'purity': request.args.get('purity') or None,
            'classification': request.args.get('classification') or None,
            'make': request.args.get('make') or None,
            'collection': request.args.get('collection') or None,
            'section': request.args.get('section') or None,
            'prov_type': request.args.get('prov_type') or None,
            'provision_mode': request.args.get('provision_mode') or None,
            'branch_type': request.args.get('branch_type') or None,
            'branch_status': request.args.get('branch_status') or None,
            'business_head': request.args.get('business_head') or None,
            'state': request.args.get('state') or None,
            'bh_emp_code': None,
            'authorized_branch_ids': None,
            'drill_level': drill_level,
            'drill_range_weight': request.args.get('drill_range_weight') or None,
            'drill_section_ids': request.args.get('drill_section_ids') or None,
            'drill_purity_ids': request.args.get('drill_purity_ids') or None,
            'drill_type_ids': request.args.get('drill_type_ids') or None,
            'drill_wide_range_ids': request.args.get('drill_wide_range_ids') or None,
            'limit': per_page,
            'offset': (page - 1) * per_page,
        }

        required_id_params = ['drill_section_ids']
        if drill_level >= 2:
            required_id_params.append('drill_purity_ids')
        if drill_level >= 3:
            required_id_params.append('drill_type_ids')
        if drill_level >= 4:
            required_id_params.append('drill_wide_range_ids')

        if any(not params[param] for param in required_id_params):
            return '<div class="p-8 text-center text-red-500">Required hierarchy IDs are missing.</div>', 400
        if drill_level >= 5 and params['drill_range_weight'] is None:
            return '<div class="p-8 text-center text-red-500">A range weight is required.</div>', 400

        roles = [role.upper() for role in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(role in roles for role in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        user_id = session.get('user_id')

        apply_franchise_india_branch_param(params, roles)

        if not is_admin and not is_manager:
            if 'BUSINESS_HEAD' in roles and user_id:
                params['bh_emp_code'] = user_id
            elif 'SHOWROOM_MANAGER' in roles and user_id:
                branch_ids = LocationProvisionStockAnalysisData.authorized_branch_ids(
                    user_id
                )
                params['authorized_branch_ids'] = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        identity_columns = (
            'branch_id', 'division_id', 'group_id', 'purity_id',
            'classification_id', 'sub_classification_id', 'section_id',
            'type_id', 'make_id', 'collection_id', 'master_collection_id',
            'sub_section_id', 'wide_range_id', 'gender_id', 'size_id',
            'screw_type_id',
        )
        provision_identity = ',\n        '.join(f'p.{column}' for column in identity_columns)
        nip_identity = ',\n        '.join(f'b.{column}' for column in identity_columns)
        provision_group_by = ', '.join(f'p.{column}' for column in identity_columns)
        nip_group_by = ', '.join(f'b.{column}' for column in identity_columns)
        provision_nip_join = '\n'.join(
            f'      AND p.{column} = b.{column}' for column in identity_columns
        )
        comparison_join = '\n'.join(
            f'      AND p.{column} = n.{column}' for column in identity_columns
        )

        rows = LocationProvisionStockAnalysisData.fetch_stock_comparison_rows(
            params, provision_identity, nip_identity, provision_group_by,
            nip_group_by, provision_nip_join, comparison_join,
        )
        total_pairs = int(rows[0]['total_pairs']) if rows else 0
        total_pages = max((total_pairs + per_page - 1) // per_page, 1)

        summary = {
            'total_pairs': total_pairs,
            'mismatch_pairs': int(rows[0]['mismatch_pairs']) if rows else 0,
            'provision_pieces': rows[0]['total_provision_pieces'] if rows else 0,
            'nip_pieces': rows[0]['total_nip_pieces'] if rows else 0,
            'provision_weight': rows[0]['total_provision_weight'] if rows else 0,
            'nip_weight': rows[0]['total_nip_weight'] if rows else 0,
        }

        return render_template(
            'partials/_view_location_provision_stock_analysis_comparison.html',
            rows=rows,
            summary=summary,
            page=page,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.exception('Error loading provision stock analysis comparison')
        return render_template(
            'partials/_view_location_provision_stock_analysis_comparison.html',
            rows=[],
            summary={},
            page=1,
            total_pages=1,
            error_message=str(e),
        ), 500


@dashboard_bp.route('/api/location-provision-stock-analysis/stock-comparison-barcodes')
@jwt_required()
def get_location_provision_stock_analysis_comparison_barcodes():
    try:
        page = max(request.args.get('page', 1, type=int), 1)
        per_page = 100
        identity_columns = (
            'branch_id', 'division_id', 'group_id', 'purity_id',
            'classification_id', 'sub_classification_id', 'section_id',
            'type_id', 'make_id', 'collection_id', 'master_collection_id',
            'sub_section_id', 'wide_range_id', 'gender_id', 'size_id',
            'screw_type_id',
        )
        params = {
            column: request.args.get(column) or None
            for column in identity_columns
        }
        params.update({
            'range_weight': request.args.get('range_weight') or None,
            'bh_emp_code': None,
            'authorized_branch_ids': None,
            'required_branch_type': None,
            'limit': per_page,
            'offset': (page - 1) * per_page,
        })

        if any(params[column] is None for column in identity_columns) or params['range_weight'] is None:
            return render_template(
                'partials/_view_location_provision_stock_analysis_comparison_barcodes.html',
                rows=[],
                page=1,
                total_pages=1,
                total_records=0,
                error_message='Required comparison identity values are missing.',
            ), 400

        roles = [role.upper() for role in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(role in roles for role in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        user_id = session.get('user_id')

        if is_franchise_india_head(roles):
            params['required_branch_type'] = FRANCHISE_INDIA_BRANCH_TYPE

        if not is_admin and not is_manager:
            if 'BUSINESS_HEAD' in roles and user_id:
                params['bh_emp_code'] = user_id
            elif 'SHOWROOM_MANAGER' in roles and user_id:
                branch_ids = LocationProvisionStockAnalysisData.authorized_branch_ids(
                    user_id
                )
                params['authorized_branch_ids'] = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        provision_identity_filters = '\n'.join(
            f'      AND p.{column} = CAST(:{column} AS bigint)'
            for column in identity_columns
        )
        barcode_identity_join = '\n'.join(
            f'      AND p.{column} = b.{column}'
            for column in identity_columns
        )

        rows = LocationProvisionStockAnalysisData.fetch_comparison_barcode_rows(
            params, identity_columns, provision_identity_filters,
            barcode_identity_join,
        )
        total_records = int(rows[0]['total_records']) if rows else 0
        total_pages = max((total_records + per_page - 1) // per_page, 1)

        return render_template(
            'partials/_view_location_provision_stock_analysis_comparison_barcodes.html',
            rows=rows,
            page=page,
            total_pages=total_pages,
            total_records=total_records,
            total_pieces=rows[0]['total_pieces'] if rows else 0,
            total_gross_wt=rows[0]['total_gross_wt'] if rows else 0,
        )
    except Exception as e:
        logger.exception('Error loading comparison barcode details')
        return render_template(
            'partials/_view_location_provision_stock_analysis_comparison_barcodes.html',
            rows=[],
            page=1,
            total_pages=1,
            total_records=0,
            error_message=str(e),
        ), 500


@dashboard_bp.route('/api/location-provision-stock-analysis/export', methods=['POST'])
@jwt_required()
@require_perm('report.export')
def queue_location_provision_stock_analysis_export():
    try:
        data = request.get_json() or {}
        filters = data.get('filters', {})
        socket_id = data.get('socket_id')
        user_id = get_jwt_identity()

        # Role-based filtering resolution
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
                branch_ids = LocationProvisionStockAnalysisData.authorized_branch_ids(
                    session_user_id
                )
                authorized_branch_ids = (
                    ','.join(map(str, branch_ids)) if branch_ids else '-1'
                )

        filters['bh_emp_code'] = bh_emp_code
        filters['authorized_branch_ids'] = authorized_branch_ids

        task_payload = {
            'type': 'export_location_provision_stock_analysis',
            'filters': filters,
            'socket_id': socket_id,
            'user_id': user_id
        }

        redis_client.rpush('export_queue', json.dumps(task_payload))
        logger.info(f"Queued location_provision_stock_analysis export for user {user_id}")

        return jsonify({'status': 'success', 'message': 'Export job enqueued.'}), 200
    except Exception as e:
        logger.error(f"Failed to queue location_provision_stock_analysis export: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
