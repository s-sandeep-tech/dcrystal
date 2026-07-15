from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import (
    ProvisionStockRawSnapshot,
    BranchAuthoritySnapshot,
)
from app.extensions import db, redis_client
from app.utils.sync_manager import sync_provision_stock_status_data
from app.utils.cache_utils import generate_cache_key
from sqlalchemy import func, text, cast, Integer
from datetime import datetime
from zoneinfo import ZoneInfo
from app.utils.decorators import require_perm
import logging
import json

logger = logging.getLogger(__name__)

FRANCHISE_INDIA_HEAD_ROLE = 'FRANCHISE_INDIA_HEAD'
FRANCHISE_INDIA_BRANCH_TYPE = 'FRANCHISE_SHOP'


def is_franchise_india_head(roles):
    return FRANCHISE_INDIA_HEAD_ROLE in roles


def apply_franchise_india_branch_filter(query, roles):
    if is_franchise_india_head(roles):
        return query.filter(ProvisionStockRawSnapshot.branch_type == FRANCHISE_INDIA_BRANCH_TYPE)
    return query


def apply_franchise_india_branch_param(params, roles):
    if is_franchise_india_head(roles):
        params['branch_type'] = FRANCHISE_INDIA_BRANCH_TYPE


@dashboard_bp.route('/location-physical-stock-status')
@jwt_required()
def location_physical_stock_status():
    try:
        snapshot_date = db.session.query(func.max(ProvisionStockRawSnapshot.snapshot_date)).scalar()
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
            
        return render_template('location_physical_stock_status.html', sync_time=sync_time, is_today=is_today)
    except Exception as e:
        logger.error(f"Error in location_physical_stock_status: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/location-physical-stock-status/options')
@jwt_required()
def location_physical_stock_status_options():
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
            try:
                emp_code_int = int(user_id)
                auth_records = BranchAuthoritySnapshot.query.filter_by(emp_code=emp_code_int).all()
                authorized_branch_ids = [r.branch_id for r in auth_records]
            except (ValueError, TypeError):
                pass

        # Check cache first
        snapshot_date = db.session.query(func.max(ProvisionStockRawSnapshot.snapshot_date)).scalar()
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
            
        cache_key = f"loc_phys_stock_status_options:{date_str}:{cache_suffix}"
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            redis_client.expire(cache_key, 18000)  # Sliding expiry
            return jsonify(json.loads(cached_data))

        base_q = db.session.query(ProvisionStockRawSnapshot)
        base_q = apply_franchise_india_branch_filter(base_q, roles)
        if not is_admin and not is_manager:
            if is_business_head and user_id:
                base_q = base_q.filter(ProvisionStockRawSnapshot.business_head_emp_code == user_id)
            elif is_showroom_manager and authorized_branch_ids:
                base_q = base_q.filter(ProvisionStockRawSnapshot.branch_id.in_(authorized_branch_ids))
            elif is_showroom_manager and not authorized_branch_ids:
                # If showroom manager but no branch authority records found, return empty results
                base_q = base_q.filter(False)

        # Query distinct values for filters from the local raw snapshot
        locations = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.location.distinct()).order_by(ProvisionStockRawSnapshot.location).all() if r[0]]
        purities = [float(r[0]) for r in base_q.with_entities(ProvisionStockRawSnapshot.purity.distinct()).order_by(ProvisionStockRawSnapshot.purity).all() if r[0]]
        classifications = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.classification.distinct()).order_by(ProvisionStockRawSnapshot.classification).all() if r[0]]
        # makes and collections removed for dynamic loading
        sections = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.section.distinct()).order_by(ProvisionStockRawSnapshot.section).all() if r[0]]
        prov_types = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.prov_type.distinct()).order_by(ProvisionStockRawSnapshot.prov_type).all() if r[0]]
        provision_modes = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.provision_mode_filter.distinct()).order_by(ProvisionStockRawSnapshot.provision_mode_filter).all() if r[0]]
        branch_types = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.branch_type.distinct()).order_by(ProvisionStockRawSnapshot.branch_type).all() if r[0]]
        branch_statuses = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.branch_status.distinct()).order_by(ProvisionStockRawSnapshot.branch_status).all() if r[0]]
        business_heads = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.business_head_name.distinct()).order_by(ProvisionStockRawSnapshot.business_head_name).all() if r[0]]
        states = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.state.distinct()).order_by(ProvisionStockRawSnapshot.state).all() if r[0]]

        data = {
            'locations': locations,
            'purities': purities,
            'classifications': classifications,
            'sections': sections,
            'prov_types': prov_types,
            'provision_modes': provision_modes,
            'branch_types': branch_types,
            'branch_statuses': branch_statuses,
            'business_heads': business_heads,
            'states': states
        }
        
        # Cache for 5 hours as requested
        redis_client.setex(cache_key, 18000, json.dumps(data))

        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/location-physical-stock-status/collections/search')
@jwt_required()
def location_physical_stock_status_collections_search():
    try:
        q = request.args.get('q', '').strip()
        
        # Role-based filtering (identical logic to options API)
        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        base_q = db.session.query(ProvisionStockRawSnapshot.collection.distinct())
        base_q = apply_franchise_india_branch_filter(base_q, roles)
        
        if not is_admin and not is_manager:
            if is_business_head and user_id:
                base_q = base_q.filter(ProvisionStockRawSnapshot.business_head_emp_code == user_id)
            elif is_showroom_manager:
                emp_code_int = int(user_id)
                auth_records = BranchAuthoritySnapshot.query.filter_by(emp_code=emp_code_int).all()
                authorized_branch_ids = [r.branch_id for r in auth_records]
                if authorized_branch_ids:
                    base_q = base_q.filter(ProvisionStockRawSnapshot.branch_id.in_(authorized_branch_ids))
                else:
                    return jsonify([])

        if q:
            base_q = base_q.filter(ProvisionStockRawSnapshot.collection.ilike(f'%{q}%'))
        
        # Limit results for performance
        collections = [r[0] for r in base_q.order_by(ProvisionStockRawSnapshot.collection).limit(50).all() if r[0]]
        
        return jsonify(collections)
    except Exception as e:
        logger.error(f"Error in collections search: {str(e)}")
        return jsonify([]), 500

@dashboard_bp.route('/api/location-physical-stock-status/makes/search')
@jwt_required()
def location_physical_stock_status_makes_search():
    try:
        q = request.args.get('q', '').strip()
        
        # Role-based filtering
        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(r in roles for r in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        is_business_head = 'BUSINESS_HEAD' in roles
        is_showroom_manager = 'SHOWROOM_MANAGER' in roles
        user_id = session.get('user_id')

        base_q = db.session.query(ProvisionStockRawSnapshot.make.distinct())
        base_q = apply_franchise_india_branch_filter(base_q, roles)
        
        if not is_admin and not is_manager:
            if is_business_head and user_id:
                base_q = base_q.filter(ProvisionStockRawSnapshot.business_head_emp_code == user_id)
            elif is_showroom_manager:
                emp_code_int = int(user_id)
                auth_records = BranchAuthoritySnapshot.query.filter_by(emp_code=emp_code_int).all()
                authorized_branch_ids = [r.branch_id for r in auth_records]
                if authorized_branch_ids:
                    base_q = base_q.filter(ProvisionStockRawSnapshot.branch_id.in_(authorized_branch_ids))
                else:
                    return jsonify([])

        if q:
            base_q = base_q.filter(ProvisionStockRawSnapshot.make.ilike(f'%{q}%'))
        
        # Limit results for performance
        makes = [r[0] for r in base_q.order_by(ProvisionStockRawSnapshot.make).limit(50).all() if r[0]]
        
        return jsonify(makes)
    except Exception as e:
        logger.error(f"Error in makes search: {str(e)}")
        return jsonify([]), 500

@dashboard_bp.route('/partial/location-physical-stock-status')
@jwt_required()
def get_location_physical_stock_status_partial():
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
                try:
                    emp_code_int = int(user_id)
                    auth_records = BranchAuthoritySnapshot.query.filter_by(emp_code=emp_code_int).all()
                    branch_ids = [r.branch_id for r in auth_records]
                    if branch_ids:
                        params['authorized_branch_ids'] = ','.join(map(str, branch_ids))
                    else:
                        params['authorized_branch_ids'] = '-1' # Force empty
                except (ValueError, TypeError):
                    params['authorized_branch_ids'] = '-1'

        # Redis Caching Logic
        snapshot_date = db.session.query(func.max(ProvisionStockRawSnapshot.snapshot_date)).scalar()
        cache_key = generate_cache_key("loc_phys_stock_status_partial", snapshot_date, **params)
        
        cached_html = redis_client.get(cache_key)
        if cached_html:
            redis_client.expire(cache_key, 18000)  # Sliding expiry
            return cached_html

        # Dynamic Pivot Query
        query = """
WITH base AS (
    SELECT *
    FROM provision_stock_raw_snapshot
    WHERE 
        (:location IS NULL OR location = ANY(string_to_array(CAST(:location AS text), ',')))
        AND (:state IS NULL OR state = ANY(string_to_array(CAST(:state AS text), ',')))
        AND (:purity IS NULL OR purity = ANY(string_to_array(CAST(:purity AS text), ',')::numeric[]))
        AND (:classification IS NULL OR classification = ANY(string_to_array(CAST(:classification AS text), ',')))
        AND (:make IS NULL OR make = ANY(string_to_array(CAST(:make AS text), ',')))
        AND (:collection IS NULL OR collection = ANY(string_to_array(CAST(:collection AS text), ',')))
        AND (:section IS NULL OR section = ANY(string_to_array(CAST(:section AS text), ',')))
        AND (:prov_type IS NULL OR prov_type = ANY(string_to_array(CAST(:prov_type AS text), ',')))
        AND (:provision_mode IS NULL OR provision_mode_filter = ANY(string_to_array(CAST(:provision_mode AS text), ',')))
        AND (:branch_type IS NULL OR branch_type = ANY(string_to_array(CAST(:branch_type AS text), ',')))
        AND (:branch_status IS NULL OR branch_status = ANY(string_to_array(CAST(:branch_status AS text), ',')))
        AND (:business_head IS NULL OR business_head_name = ANY(string_to_array(CAST(:business_head AS text), ',')))
        AND (:bh_emp_code IS NULL OR business_head_emp_code = :bh_emp_code)
        AND (:authorized_branch_ids IS NULL OR branch_id = ANY(string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]))
),
location_summary AS (
    SELECT
        location::text AS location,
        'Location Summary'::text AS report_section,
        location::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        SUM(prov_pieces) AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        1 AS section_sort,
        1 AS row_sort
    FROM base
    GROUP BY location
),
purity_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Purity Wise'::text AS report_section,
        purity::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        2 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY purity) AS row_sort
    FROM base
    GROUP BY purity
),
classification_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        x.report_section,
        x.report_label,
        x.classification,
        x.sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        x.is_parent,
        x.prov_pcs,
        x.prov_gr_wt,
        x.in_shop_wt,
        x.ordered_wt,
        x.in_transit_wt,
        x.short_excess_wt,
        x.percent,
        3 AS section_sort,
        ROW_NUMBER() OVER (
            ORDER BY x.classification, x.level_order, x.sub_classification NULLS FIRST
        ) AS row_sort
    FROM (
        SELECT
            'Classification Wise'::text AS report_section,
            classification::text AS report_label,
            classification::text AS classification,
            NULL::text AS sub_classification,
            1 AS is_parent,
            NULL::numeric AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
            ) AS percent,
            0 AS level_order
        FROM base
        GROUP BY classification

        UNION ALL

        SELECT
            'Classification Wise'::text AS report_section,
            '   ' || COALESCE(sub_classification::text, 'Unknown') AS report_label,
            classification::text AS classification,
            COALESCE(sub_classification::text, 'Unknown') AS sub_classification,
            0 AS is_parent,
            NULL::numeric AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
            ) AS percent,
            1 AS level_order
        FROM base
        GROUP BY classification, sub_classification
    ) x
),
collection_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        x.report_section,
        x.report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        x.collection,
        x.sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        x.is_parent,
        x.prov_pcs,
        x.prov_gr_wt,
        x.in_shop_wt,
        x.ordered_wt,
        x.in_transit_wt,
        x.short_excess_wt,
        x.percent,
        10 AS section_sort,
        ROW_NUMBER() OVER (
            ORDER BY x.collection, x.level_order, x.sub_section NULLS FIRST
        ) AS row_sort
    FROM (
        SELECT
            'Collection Wise'::text AS report_section,
            collection::text AS report_label,
            collection::text AS collection,
            NULL::text AS sub_section,
            1 AS is_parent,
            NULL::numeric AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
            ) AS percent,
            0 AS level_order
        FROM base
        GROUP BY collection

        UNION ALL

        SELECT
            'Collection Wise'::text AS report_section,
            '   ' || COALESCE(sub_section::text, 'Unknown') AS report_label,
            collection::text AS collection,
            COALESCE(sub_section::text, 'Unknown') AS sub_section,
            0 AS is_parent,
            NULL::numeric AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
            ) AS percent,
            1 AS level_order
        FROM base
        GROUP BY collection, sub_section
    ) x
),
section_details_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        x.report_section,
        x.report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        x.sec_name,
        x.typ_name,
        x.is_parent,
        x.prov_pcs,
        x.prov_gr_wt,
        x.in_shop_wt,
        x.ordered_wt,
        x.in_transit_wt,
        x.short_excess_wt,
        x.percent,
        9 AS section_sort,
        ROW_NUMBER() OVER (
            ORDER BY x.sec_name, x.level_order, x.typ_name NULLS FIRST
        ) AS row_sort
    FROM (
        SELECT
            'Section Details'::text AS report_section,
            section::text AS report_label,
            section::text AS sec_name,
            NULL::text AS typ_name,
            1 AS is_parent,
            SUM(prov_pieces) AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
            ) AS percent,
            0 AS level_order
        FROM base
        GROUP BY section

        UNION ALL

        SELECT
            'Section Details'::text AS report_section,
            '   ' || COALESCE(type::text, 'Unknown') AS report_label,
            section::text AS sec_name,
            COALESCE(type::text, 'Unknown') AS typ_name,
            0 AS is_parent,
            SUM(prov_pieces) AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
            ) AS percent,
            1 AS level_order
        FROM base
        GROUP BY section, type
    ) x
),
make_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Make Wise'::text AS report_section,
        make::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        5 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY make) AS row_sort
    FROM base
    GROUP BY make
),
prov_type_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Provision Type Wise'::text AS report_section,
        prov_type::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        6 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY prov_type) AS row_sort
    FROM base
    GROUP BY prov_type
),
section_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Section Wise'::text AS report_section,
        section::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        SUM(prov_pieces) AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        7 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY section) AS row_sort
    FROM base
    GROUP BY section
),
provision_mode_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Provision Mode Wise'::text AS report_section,
        provision_mode_filter::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        8 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY provision_mode_filter) AS row_sort
    FROM base
    GROUP BY provision_mode_filter
),
combined_report AS (
    SELECT * FROM location_summary
    UNION ALL
    SELECT * FROM purity_wise
    UNION ALL
    SELECT * FROM classification_wise
    UNION ALL
    SELECT * FROM collection_wise
    UNION ALL
    SELECT * FROM make_wise
    UNION ALL
    SELECT * FROM prov_type_wise
    UNION ALL
    SELECT * FROM section_wise
    UNION ALL
    SELECT * FROM provision_mode_wise
    UNION ALL
    SELECT * FROM section_details_wise
)

SELECT
    location,
    report_section,
    report_label,
    classification,
    sub_classification,
    collection,
    sub_section,
    sec_name,
    typ_name,
    is_parent,
    prov_pcs,
    prov_gr_wt,
    in_shop_wt,
    ordered_wt,
    in_transit_wt,
    short_excess_wt,
    percent,
    section_sort,
    row_sort
FROM combined_report
ORDER BY
    location,
    section_sort,
    row_sort        """
        
        result = db.session.execute(text(query), params)
        rows = [dict(r._mapping) for r in result]

        # General In-memory sorting for all report sections
        numeric_cols = ['prov_pcs', 'prov_gr_wt', 'in_shop_wt', 'ordered_wt', 'in_transit_wt', 'short_excess_wt', 'percent']
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
        
        rendered_html = render_template('partials/_view_location_physical_stock_status.html', 
                                      rows=rows, 
                                      sort_by=sort_by, 
                                      sort_order=sort_order)
        
        # Cache for 5 hours as requested
        redis_client.setex(cache_key, 18000, rendered_html)
        
        return rendered_html

    except Exception as e:
        logger.error(f"Error in get_location_physical_stock_status_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/location-physical-stock-status/drilldown')
@jwt_required()
def get_location_physical_stock_status_drilldown():
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
                try:
                    emp_code_int = int(user_id)
                    auth_records = BranchAuthoritySnapshot.query.filter_by(emp_code=emp_code_int).all()
                    branch_ids = [r.branch_id for r in auth_records]
                    if branch_ids:
                        params['authorized_branch_ids'] = ','.join(map(str, branch_ids))
                    else:
                        params['authorized_branch_ids'] = '-1' # Force empty
                except (ValueError, TypeError):
                    params['authorized_branch_ids'] = '-1'

        # Hierarchical Query for Modal (Location Physical logic minus ordered_wt in short_excess)
        query = '''
WITH base AS (
    SELECT *
    FROM provision_stock_raw_snapshot
    WHERE 
        (:location IS NULL OR location = ANY(string_to_array(CAST(:location AS text), ',')))
        AND (:state IS NULL OR state = ANY(string_to_array(CAST(:state AS text), ',')))
        AND (:purity IS NULL OR purity = ANY(string_to_array(CAST(:purity AS text), ',')::numeric[]))
        AND (:classification IS NULL OR classification = ANY(string_to_array(CAST(:classification AS text), ',')))
        AND (:make IS NULL OR make = ANY(string_to_array(CAST(:make AS text), ',')))
        AND (:collection IS NULL OR collection = ANY(string_to_array(CAST(:collection AS text), ',')))
        AND (:section IS NULL OR section = ANY(string_to_array(CAST(:section AS text), ',')))
        AND (:prov_type IS NULL OR prov_type = ANY(string_to_array(CAST(:prov_type AS text), ',')))
        AND (:provision_mode IS NULL OR provision_mode_filter = ANY(string_to_array(CAST(:provision_mode AS text), ',')))
        AND (:branch_type IS NULL OR branch_type = ANY(string_to_array(CAST(:branch_type AS text), ',')))
        AND (:branch_status IS NULL OR branch_status = ANY(string_to_array(CAST(:branch_status AS text), ',')))
        AND (:business_head IS NULL OR business_head_name = ANY(string_to_array(CAST(:business_head AS text), ',')))
        AND (:bh_emp_code IS NULL OR business_head_emp_code = :bh_emp_code)
        AND (:authorized_branch_ids IS NULL OR branch_id = ANY(string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]))
        AND (:drill_section IS NULL OR section = :drill_section)
),
levels AS (
    -- Level 1: Section
    SELECT 1 as level_id, section as l1, NULL::text as l2, NULL::text as l3, NULL::numeric as l4,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section
    
    UNION ALL
    -- Level 2: Section + Type
    SELECT 2 as level_id, section as l1, type as l2, NULL::text as l3, NULL::numeric as l4,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section, type

    UNION ALL
    -- Level 3: Section + Type + Wide Range
    SELECT 3 as level_id, section as l1, type as l2, wide_range as l3, NULL::numeric as l4,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section, type, wide_range

    UNION ALL
    -- Level 4: Section + Type + Wide Range + Range Weight
    SELECT 4 as level_id, section as l1, type as l2, wide_range as l3, range_weight as l4,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section, type, wide_range, range_weight
)
SELECT 
    level_id, l1 as section, l2 as type, l3 as wide_range, l4 as range_weight,
    prov_pcs, prov_gr_wt, in_shop_wt, ordered_wt, in_transit_wt,
    (in_shop_wt + in_transit_wt - prov_gr_wt) as short_excess_wt,
    CASE WHEN prov_gr_wt = 0 THEN 0 ELSE (in_shop_wt + in_transit_wt - prov_gr_wt) * 100.0 / prov_gr_wt END as percent
FROM levels
ORDER BY section, type NULLS FIRST, wide_range NULLS FIRST, range_weight NULLS FIRST, level_id
        '''
        
        result = db.session.execute(text(query), params)
        rows = [dict(r._mapping) for r in result]
        
        # Calculate Grand Total for the modal
        total_pcs = sum(r['prov_pcs'] or 0 for r in rows if r['level_id'] == 1)
        total_gr_wt = sum(r['prov_gr_wt'] or 0 for r in rows if r['level_id'] == 1)
        total_in_shop = sum(r['in_shop_wt'] or 0 for r in rows if r['level_id'] == 1)
        total_transit = sum(r['in_transit_wt'] or 0 for r in rows if r['level_id'] == 1)
        total_ordered = sum(r['ordered_wt'] or 0 for r in rows if r['level_id'] == 1)
        
        total_short_excess = total_in_shop + total_transit - total_gr_wt
        total_percent = (total_short_excess * 100 / total_gr_wt) if total_gr_wt != 0 else 0
        
        modal_totals = {
            'prov_pcs': total_pcs,
            'prov_gr_wt': total_gr_wt,
            'in_shop_wt': total_in_shop,
            'ordered_wt': total_ordered,
            'in_transit_wt': total_transit,
            'short_excess_wt': total_short_excess,
            'percent': total_percent
        }

        # We will reuse the provision partial view since it only loops rows
        return render_template('partials/_view_provision_stock_drilldown.html', 
                               rows=rows, 
                               modal_totals=modal_totals,
                               drill_section=drill_section,
                               enable_in_shop_details=True)

    except Exception as e:
        logger.error(f"Error in get_location_physical_stock_status_drilldown: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200


@dashboard_bp.route('/api/location-physical-stock-status/in-shop-details')
@jwt_required()
def get_location_physical_stock_in_shop_details():
    try:
        page = max(request.args.get('page', 1, type=int), 1)
        per_page = 100
        drill_level = min(max(request.args.get('drill_level', 1, type=int), 1), 4)

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
            'drill_section': request.args.get('drill_section') or None,
            'drill_type': request.args.get('drill_type') or None,
            'drill_wide_range': request.args.get('drill_wide_range') or None,
            'drill_range_weight': request.args.get('drill_range_weight') or None,
            'limit': per_page,
            'offset': (page - 1) * per_page,
        }

        if not params['drill_section']:
            return '<div class="p-8 text-center text-red-500">A section is required.</div>', 400

        roles = [role.upper() for role in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager = any(role in roles for role in ['MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'])
        user_id = session.get('user_id')

        apply_franchise_india_branch_param(params, roles)

        if not is_admin and not is_manager:
            if 'BUSINESS_HEAD' in roles and user_id:
                params['bh_emp_code'] = user_id
            elif 'SHOWROOM_MANAGER' in roles and user_id:
                try:
                    branch_ids = [
                        row.branch_id
                        for row in BranchAuthoritySnapshot.query.filter_by(emp_code=int(user_id)).all()
                    ]
                    params['authorized_branch_ids'] = ','.join(map(str, branch_ids)) if branch_ids else '-1'
                except (ValueError, TypeError):
                    params['authorized_branch_ids'] = '-1'

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

        query = text(f'''
WITH matching_stock AS MATERIALIZED (
    SELECT DISTINCT
        {stock_identity_columns}
    FROM provision_stock_raw_snapshot AS p
    WHERE (:location IS NULL OR p.location = ANY(string_to_array(CAST(:location AS text), ',')))
          AND (:state IS NULL OR p.state = ANY(string_to_array(CAST(:state AS text), ',')))
          AND (:purity IS NULL OR p.purity = ANY(string_to_array(CAST(:purity AS text), ',')::numeric[]))
          AND (:classification IS NULL OR p.classification = ANY(string_to_array(CAST(:classification AS text), ',')))
          AND (:make IS NULL OR p.make = ANY(string_to_array(CAST(:make AS text), ',')))
          AND (:collection IS NULL OR p.collection = ANY(string_to_array(CAST(:collection AS text), ',')))
          AND (:section IS NULL OR p.section = ANY(string_to_array(CAST(:section AS text), ',')))
          AND (:prov_type IS NULL OR p.prov_type = ANY(string_to_array(CAST(:prov_type AS text), ',')))
          AND (:provision_mode IS NULL OR p.provision_mode_filter = ANY(string_to_array(CAST(:provision_mode AS text), ',')))
          AND (:branch_type IS NULL OR p.branch_type = ANY(string_to_array(CAST(:branch_type AS text), ',')))
          AND (:branch_status IS NULL OR p.branch_status = ANY(string_to_array(CAST(:branch_status AS text), ',')))
          AND (:business_head IS NULL OR p.business_head_name = ANY(string_to_array(CAST(:business_head AS text), ',')))
          AND (:bh_emp_code IS NULL OR p.business_head_emp_code = :bh_emp_code)
          AND (:authorized_branch_ids IS NULL OR p.branch_id = ANY(string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]))
          AND p.section = CAST(:drill_section AS text)
          AND (:drill_level < 2 OR p.type = CAST(:drill_type AS text))
          AND (:drill_level < 3 OR p.wide_range = CAST(:drill_wide_range AS text))
          AND (:drill_level < 4 OR p.range_weight = CAST(:drill_range_weight AS numeric))
),
matched_barcodes AS (
    SELECT b.*
    FROM matching_stock AS p
    JOIN size_level_nip_barcode_snapshot AS b
      ON TRUE
      {identity_join}
    WHERE (:drill_level < 4 OR b.weight = CAST(:drill_range_weight AS numeric))
)
SELECT
    b.*,
    COUNT(*) OVER () AS total_records,
    COALESCE(SUM(b.pieces) OVER (), 0) AS total_pieces,
    COALESCE(SUM(b.gross_wt) OVER (), 0) AS total_gross_wt
FROM matched_barcodes AS b
ORDER BY b.barcode_no NULLS LAST, b.design_no NULLS LAST, b.id
LIMIT :limit OFFSET :offset
        ''')

        result = db.session.execute(query, params)
        rows = [dict(row._mapping) for row in result]
        total_records = int(rows[0]['total_records']) if rows else 0
        total_pages = max((total_records + per_page - 1) // per_page, 1)

        return render_template(
            'partials/_view_location_physical_stock_in_shop_details.html',
            rows=rows,
            page=page,
            total_pages=total_pages,
            total_records=total_records,
            total_pieces=rows[0]['total_pieces'] if rows else 0,
            total_gross_wt=rows[0]['total_gross_wt'] if rows else 0,
        )
    except Exception as e:
        logger.exception('Error loading location physical in-shop details')
        return render_template(
            'partials/_view_location_physical_stock_in_shop_details.html',
            rows=[],
            page=1,
            total_pages=1,
            total_records=0,
            total_pieces=0,
            total_gross_wt=0,
            error_message=str(e),
        ), 500

@dashboard_bp.route('/api/sync/location-physical-stock-status', methods=['POST'])
@jwt_required()
def sync_location_physical_stock_status():
    user_id = get_jwt_identity()
    return jsonify(sync_provision_stock_status_data(user_id))


@dashboard_bp.route('/api/location-physical-stock-status/export', methods=['POST'])
@jwt_required()
@require_perm('report.export')
def queue_location_physical_stock_status_export():
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
                try:
                    emp_code_int = int(session_user_id)
                    auth_records = BranchAuthoritySnapshot.query.filter_by(emp_code=emp_code_int).all()
                    branch_ids = [r.branch_id for r in auth_records]
                    if branch_ids:
                        authorized_branch_ids = ','.join(map(str, branch_ids))
                    else:
                        authorized_branch_ids = '-1' # Force empty
                except (ValueError, TypeError):
                    authorized_branch_ids = '-1'

        filters['bh_emp_code'] = bh_emp_code
        filters['authorized_branch_ids'] = authorized_branch_ids

        task_payload = {
            'type': 'export_location_physical_stock_status',
            'filters': filters,
            'socket_id': socket_id,
            'user_id': user_id
        }

        redis_client.rpush('export_queue', json.dumps(task_payload))
        logger.info(f"Queued location_physical_stock_status export for user {user_id}")

        return jsonify({'status': 'success', 'message': 'Export job enqueued.'}), 200
    except Exception as e:
        logger.error(f"Failed to queue location_physical_stock_status export: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
