from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import ProvisionStockRawSnapshot
from app.extensions import db, redis_client
from app.utils.sync_manager import sync_provision_stock_status_data
from app.utils.cache_utils import generate_cache_key
from sqlalchemy import func, text
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import json

logger = logging.getLogger(__name__)


@dashboard_bp.route('/provision-stock-status')
@jwt_required()
def provision_stock_status():
    try:
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d, %I:%M %p")
        return render_template('provision_stock_status.html', sync_time=sync_time)
    except Exception as e:
        logger.error(f"Error in provision_stock_status: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/provision-stock-status/options')
@jwt_required()
def provision_stock_status_options():
    try:
        # Role-based filtering for Business Head
        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager_2 = 'MANAGER_2' in roles
        is_business_head = 'BUSINESS_HEAD' in roles
        user_id = session.get('user_id')

        # Check cache first
        snapshot_date = db.session.query(func.max(ProvisionStockRawSnapshot.snapshot_date)).scalar()
        date_str = snapshot_date.strftime("%Y%m%d%H%M%S") if snapshot_date else "latest"
        
        # Role-aware cache key
        cache_suffix = "all"
        if not is_admin and not is_manager_2 and is_business_head and user_id:
            cache_suffix = f"bh_{user_id}"
            
        cache_key = f"prov_stock_status_options:{date_str}:{cache_suffix}"
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            redis_client.expire(cache_key, 18000)  # Sliding expiry
            return jsonify(json.loads(cached_data))

        base_q = db.session.query(ProvisionStockRawSnapshot)
        if not is_admin and not is_manager_2:
            if is_business_head and user_id:
                base_q = base_q.filter(ProvisionStockRawSnapshot.business_head_emp_code == user_id)

        # Query distinct values for filters from the local raw snapshot
        locations = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.location.distinct()).order_by(ProvisionStockRawSnapshot.location).all() if r[0]]
        purities = [float(r[0]) for r in base_q.with_entities(ProvisionStockRawSnapshot.purity.distinct()).order_by(ProvisionStockRawSnapshot.purity).all() if r[0]]
        classifications = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.classification.distinct()).order_by(ProvisionStockRawSnapshot.classification).all() if r[0]]
        makes = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.make.distinct()).order_by(ProvisionStockRawSnapshot.make).all() if r[0]]
        collections = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.collection.distinct()).order_by(ProvisionStockRawSnapshot.collection).all() if r[0]]
        sections = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.section.distinct()).order_by(ProvisionStockRawSnapshot.section).all() if r[0]]
        prov_types = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.prov_type.distinct()).order_by(ProvisionStockRawSnapshot.prov_type).all() if r[0]]
        provision_modes = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.provision_mode_filter.distinct()).order_by(ProvisionStockRawSnapshot.provision_mode_filter).all() if r[0]]
        branch_types = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.branch_type.distinct()).order_by(ProvisionStockRawSnapshot.branch_type).all() if r[0]]
        branch_statuses = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.branch_status.distinct()).order_by(ProvisionStockRawSnapshot.branch_status).all() if r[0]]
        business_heads = [r[0] for r in base_q.with_entities(ProvisionStockRawSnapshot.business_head_name.distinct()).order_by(ProvisionStockRawSnapshot.business_head_name).all() if r[0]]

        data = {
            'locations': locations,
            'purities': purities,
            'classifications': classifications,
            'makes': makes,
            'collections': collections,
            'sections': sections,
            'prov_types': prov_types,
            'provision_modes': provision_modes,
            'branch_types': branch_types,
            'branch_statuses': branch_statuses,
            'business_heads': business_heads
        }
        
        # Cache for 5 hours as requested
        redis_client.setex(cache_key, 18000, json.dumps(data))

        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/provision-stock-status')
@jwt_required()
def get_provision_stock_status_partial():
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
        sort_by = request.args.get('sort_by', '')
        sort_order = request.args.get('sort_order', 'asc')

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
            'bh_emp_code': None,
            'sort_by': sort_by if sort_by else None,
            'sort_order': sort_order if sort_order else None
        }

        # Role-based filtering for Business Head
        roles = [r.upper() for r in session.get('roles', [])]
        is_admin = 'ADMIN' in roles
        is_manager_2 = 'MANAGER_2' in roles
        is_business_head = 'BUSINESS_HEAD' in roles
        user_id = session.get('user_id')

        if not is_admin and not is_manager_2:
            if is_business_head and user_id:
                params['bh_emp_code'] = user_id

        # Redis Caching Logic
        snapshot_date = db.session.query(func.max(ProvisionStockRawSnapshot.snapshot_date)).scalar()
        cache_key = generate_cache_key("prov_stock_status_partial", snapshot_date, **params)
        
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
        SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
        SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
            SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
            SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
            SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
            SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
            SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
            SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
        SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
        SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
        SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
        SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(in_shop_wt) + SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) + SUM(in_transit_wt) - SUM(prov_gr_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
    row_sort
        """
        
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
        
        rendered_html = render_template('partials/_view_provision_stock_status.html', 
                                      rows=rows, 
                                      sort_by=sort_by, 
                                      sort_order=sort_order)
        
        # Cache for 5 hours as requested
        redis_client.setex(cache_key, 18000, rendered_html)
        
        return rendered_html

    except Exception as e:
        logger.error(f"Error in get_provision_stock_status_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/sync/provision_stock_status', methods=['POST'])
@jwt_required()
def sync_provision_stock_status():
    user_id = get_jwt_identity()
    return jsonify(sync_provision_stock_status_data(user_id))
