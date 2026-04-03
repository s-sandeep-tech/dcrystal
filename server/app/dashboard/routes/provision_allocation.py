from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models.snapshots import ProvisionStockRawSnapshot
from app.extensions import db, redis_client
from app.utils.cache_utils import generate_cache_key
from sqlalchemy import func, case, text
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import json

logger = logging.getLogger(__name__)

class CachedPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.has_prev = page > 1
        self.has_next = (page * per_page) < total
        self.prev_num = page - 1
        self.next_num = page + 1
        self.pages = (total + per_page - 1) // per_page if per_page else 0


@dashboard_bp.route('/provision-allocation-summary')
@jwt_required()
def provision_allocation_summary():
    try:
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        return render_template('provision_allocation_summary.html', sync_time=sync_time)
    except Exception as e:
        logger.error(f"Error in provision_allocation_summary: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/provision-allocation/options')
@jwt_required()
def provision_allocation_options():
    try:
        # Check cache first
        snapshot_date = db.session.query(func.max(ProvisionStockRawSnapshot.snapshot_date)).scalar()
        date_str = snapshot_date.strftime("%Y%m%d%H%M%S") if snapshot_date else "latest"
        cache_key = f"prov_alloc_options:{date_str}"
        
        cached_data = redis_client.get(cache_key)
        if cached_data:
            redis_client.expire(cache_key, 18000)  # Sliding expiry
            return jsonify(json.loads(cached_data))

        locations = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.location.distinct()).order_by(ProvisionStockRawSnapshot.location).all() if r[0]]
        purities = [float(r[0]) for r in db.session.query(ProvisionStockRawSnapshot.purity.distinct()).order_by(ProvisionStockRawSnapshot.purity).all() if r[0]]
        classifications = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.classification.distinct()).order_by(ProvisionStockRawSnapshot.classification).all() if r[0]]
        makes = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.make.distinct()).order_by(ProvisionStockRawSnapshot.make).all() if r[0]]
        collections = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.collection.distinct()).order_by(ProvisionStockRawSnapshot.collection).all() if r[0]]
        sections = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.section.distinct()).order_by(ProvisionStockRawSnapshot.section).all() if r[0]]
        prov_types = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.prov_type.distinct()).order_by(ProvisionStockRawSnapshot.prov_type).all() if r[0]]
        provision_modes = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.provision_mode_filter.distinct()).order_by(ProvisionStockRawSnapshot.provision_mode_filter).all() if r[0]]
        branch_types = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.branch_type.distinct()).order_by(ProvisionStockRawSnapshot.branch_type).all() if r[0]]
        business_heads = [r[0] for r in db.session.query(ProvisionStockRawSnapshot.business_head_name.distinct()).order_by(ProvisionStockRawSnapshot.business_head_name).all() if r[0]]

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
            'business_heads': business_heads
        }
        
        # Cache for 5 hours
        redis_client.setex(cache_key, 18000, json.dumps(data))

        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/provision-allocation')
@jwt_required()
def get_provision_allocation_partial():
    try:
        # Read filters from request
        search = request.args.get('search', '').strip()
        location = request.args.get('location', '')
        purity = request.args.get('purity', '')
        classification = request.args.get('classification', '')
        make = request.args.get('make', '')
        collection = request.args.get('collection', '')
        section = request.args.get('section', '')
        prov_type = request.args.get('prov_type', '')
        provision_mode = request.args.get('provision_mode', '')
        branch_type = request.args.get('branch_type', '')
        business_head = request.args.get('business_head', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 2000, type=int)

        params = {
            'location': location if location else None,
            'purity': float(purity) if purity else None,
            'classification': classification if classification else None,
            'make': make if make else None,
            'collection': collection if collection else None,
            'section': section if section else None,
            'prov_type': prov_type if prov_type else None,
            'provision_mode': provision_mode if provision_mode else None,
            'branch_type': branch_type if branch_type else None,
            'business_head': business_head if business_head else None
        }

        # Redis Caching Logic
        snapshot_date = db.session.query(func.max(ProvisionStockRawSnapshot.snapshot_date)).scalar()
        cache_key = generate_cache_key("prov_alloc_partial", snapshot_date, **params, search=search, page=page)
        
        cached_html = redis_client.get(cache_key)
        if cached_html:
            redis_client.expire(cache_key, 18000)  # Sliding expiry
            return cached_html

        query = """
WITH base AS (
    SELECT *
    FROM provision_stock_raw_snapshot
    WHERE 
        (:location IS NULL OR location = :location)
        AND (:purity IS NULL OR purity = :purity)
        AND (:classification IS NULL OR classification = :classification)
        AND (:make IS NULL OR make = :make)
        AND (:collection IS NULL OR collection = :collection)
        AND (:section IS NULL OR section = :section)
        AND (:prov_type IS NULL OR prov_type = :prov_type)
        AND (:provision_mode IS NULL OR provision_mode_filter = :provision_mode)
        AND (:branch_type IS NULL OR branch_type = :branch_type)
        AND (:business_head IS NULL OR business_head_name = :business_head)
),
global_total AS (
    SELECT
        COALESCE(SUM(prov_gr_wt), 0) AS total_prov_wt
    FROM base
),

location_summary AS (
    SELECT
        CASE 
            WHEN COUNT(DISTINCT location) > 4 THEN COUNT(DISTINCT location)::text || '+ Location'
            ELSE (SELECT STRING_AGG(loc, ', ') FROM (SELECT DISTINCT location AS loc FROM base ORDER BY loc) s)
        END::text AS location,
        'Location Summary'::text AS report_section,
        CASE 
            WHEN COUNT(DISTINCT location) > 4 THEN COUNT(DISTINCT location)::text || '+ Location'
            ELSE (SELECT STRING_AGG(loc, ', ') FROM (SELECT DISTINCT location AS loc FROM base ORDER BY loc) s)
        END::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        SUM(prov_pieces) AS pcs,
        SUM(prov_gr_wt) AS gr_wt,
        100.00::numeric AS percent,
        1 AS section_sort,
        1 AS row_sort
    FROM base
),

purity_wise AS (
    SELECT
        'ALL'::text AS location,
        'Purity Wise'::text AS report_section,
        COALESCE(b.purity::text, 'Unknown') AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        NULL::numeric AS pcs,
        SUM(b.prov_gr_wt) AS gr_wt,
        ROUND(
            CASE
                WHEN gt.total_prov_wt = 0 THEN 0
                ELSE SUM(b.prov_gr_wt) * 100.0 / gt.total_prov_wt
            END,
            2
        ) AS percent,
        2 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY b.purity) AS row_sort
    FROM base b
    CROSS JOIN global_total gt
    GROUP BY b.purity, gt.total_prov_wt
),

classification_wise AS (
    SELECT
        'ALL'::text AS location,
        x.report_section,
        x.report_label,
        x.classification,
        x.sub_classification,
        x.is_parent,
        x.pcs,
        x.gr_wt,
        x.percent,
        3 AS section_sort,
        ROW_NUMBER() OVER (
            ORDER BY
                x.classification,
                x.level_order,
                x.sub_classification NULLS FIRST
        ) AS row_sort
    FROM (
        SELECT
            'Classification Wise'::text AS report_section,
            COALESCE(b.classification::text, 'Unknown') AS report_label,
            b.classification::text AS classification,
            NULL::text AS sub_classification,
            1 AS is_parent,
            NULL::numeric AS pcs,
            SUM(b.prov_gr_wt) AS gr_wt,
            ROUND(
                CASE
                    WHEN gt.total_prov_wt = 0 THEN 0
                    ELSE SUM(b.prov_gr_wt) * 100.0 / gt.total_prov_wt
                END,
                2
            ) AS percent,
            0 AS level_order
        FROM base b
        CROSS JOIN global_total gt
        GROUP BY b.classification, gt.total_prov_wt

        UNION ALL

        SELECT
            'Classification Wise'::text AS report_section,
            '   ' || COALESCE(b.sub_classification::text, 'Unknown') AS report_label,
            b.classification::text AS classification,
            COALESCE(b.sub_classification::text, 'Unknown') AS sub_classification,
            0 AS is_parent,
            NULL::numeric AS pcs,
            SUM(b.prov_gr_wt) AS gr_wt,
            ROUND(
                CASE
                    WHEN gt.total_prov_wt = 0 THEN 0
                    ELSE SUM(b.prov_gr_wt) * 100.0 / gt.total_prov_wt
                END,
                2
            ) AS percent,
            1 AS level_order
        FROM base b
        CROSS JOIN global_total gt
        GROUP BY b.classification, b.sub_classification, gt.total_prov_wt
    ) x
),

make_wise AS (
    SELECT
        'ALL'::text AS location,
        'Make Wise'::text AS report_section,
        COALESCE(b.make::text, 'Unknown') AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        NULL::numeric AS pcs,
        SUM(b.prov_gr_wt) AS gr_wt,
        ROUND(
            CASE
                WHEN gt.total_prov_wt = 0 THEN 0
                ELSE SUM(b.prov_gr_wt) * 100.0 / gt.total_prov_wt
            END,
            2
        ) AS percent,
        4 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY b.make) AS row_sort
    FROM base b
    CROSS JOIN global_total gt
    GROUP BY b.make, gt.total_prov_wt
),

prov_type_wise AS (
    SELECT
        'ALL'::text AS location,
        'Provision Type Wise'::text AS report_section,
        COALESCE(b.prov_type::text, 'Unknown') AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        NULL::numeric AS pcs,
        SUM(b.prov_gr_wt) AS gr_wt,
        ROUND(
            CASE
                WHEN gt.total_prov_wt = 0 THEN 0
                ELSE SUM(b.prov_gr_wt) * 100.0 / gt.total_prov_wt
            END,
            2
        ) AS percent,
        5 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY b.prov_type) AS row_sort
    FROM base b
    CROSS JOIN global_total gt
    GROUP BY b.prov_type, gt.total_prov_wt
),

section_wise AS (
    SELECT
        'ALL'::text AS location,
        'Section Wise'::text AS report_section,
        COALESCE(b.section::text, 'Unknown') AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        SUM(b.prov_pieces) AS pcs,
        SUM(b.prov_gr_wt) AS gr_wt,
        ROUND(
            CASE
                WHEN gt.total_prov_wt = 0 THEN 0
                ELSE SUM(b.prov_gr_wt) * 100.0 / gt.total_prov_wt
            END,
            2
        ) AS percent,
        6 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY b.section) AS row_sort
    FROM base b
    CROSS JOIN global_total gt
    GROUP BY b.section, gt.total_prov_wt
),

provision_mode_wise AS (
    SELECT
        'ALL'::text AS location,
        'Provision Mode Wise'::text AS report_section,
        COALESCE(b.provision_mode_filter::text, 'Unknown') AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        NULL::numeric AS pcs,
        SUM(b.prov_gr_wt) AS gr_wt,
        ROUND(
            CASE
                WHEN gt.total_prov_wt = 0 THEN 0
                ELSE SUM(b.prov_gr_wt) * 100.0 / gt.total_prov_wt
            END,
            2
        ) AS percent,
        7 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY b.provision_mode_filter) AS row_sort
    FROM base b
    CROSS JOIN global_total gt
    GROUP BY b.provision_mode_filter, gt.total_prov_wt
),

provision_mode_count AS (
    SELECT
        'ALL'::text AS location,
        'Provision Mode Count'::text AS report_section,
        COALESCE(b.provision_mode_filter::text, 'Unknown') AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        SUM(b.prov_pieces) AS pcs,
        NULL::numeric AS gr_wt,
        NULL::numeric AS percent,
        8 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY b.provision_mode_filter) AS row_sort
    FROM base b
    GROUP BY b.provision_mode_filter
),

combined_report AS (
    SELECT * FROM location_summary
    UNION ALL
    SELECT * FROM purity_wise
    UNION ALL
    SELECT * FROM classification_wise
    UNION ALL
    SELECT * FROM make_wise
    UNION ALL
    SELECT * FROM prov_type_wise
    UNION ALL
    SELECT * FROM section_wise
    UNION ALL
    SELECT * FROM provision_mode_wise
    UNION ALL
    SELECT * FROM provision_mode_count
)

SELECT
    location,
    report_section,
    report_label,
    classification,
    sub_classification,
    is_parent,
    pcs,
    gr_wt AS grossweight,
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
        all_rows = [dict(r._mapping) for r in result]

        if search:
            s_lower = search.lower()
            all_rows = [r for r in all_rows if (s_lower in (r.get('report_label') or '').lower() or s_lower in (r.get('report_section') or '').lower())]

        pagination = CachedPagination(all_rows, 1, per_page, len(all_rows))
        
        rendered_html = render_template('partials/_view_provision_allocation_summary.html', 
                             rows=all_rows, pagination=pagination)
        
        # Cache the result for 5 hours
        redis_client.setex(cache_key, 18000, rendered_html)
        
        return rendered_html
    except Exception as e:
        logger.error(f"Error in get_provision_allocation_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

