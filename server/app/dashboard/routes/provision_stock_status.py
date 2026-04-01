from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models.snapshots import ProvisionStockRawSnapshot
from app.extensions import db, redis_client
from app.utils.sync_manager import sync_provision_stock_status_data
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
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        return render_template('provision_stock_status.html', sync_time=sync_time)
    except Exception as e:
        logger.error(f"Error in provision_stock_status: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/api/provision-stock-status/options')
@jwt_required()
def provision_stock_status_options():
    try:
        # Query distinct values for filters from the local raw snapshot
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

        return jsonify({
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
        })
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
        business_head = request.args.get('business_head', '')

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

        # Dynamic Pivot Query
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
location_summary AS (
    SELECT
        location,
        'Location Summary'::text AS report_section,
        location::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        SUM(prov_pieces) AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt) AS short_excess_wt,
        ROUND(
            CASE
                WHEN SUM(prov_gr_wt) = 0 THEN 0
                ELSE (SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt)) * 100.0 / SUM(prov_gr_wt)
            END,
            2
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
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt) AS short_excess_wt,
        ROUND(
            CASE
                WHEN SUM(prov_gr_wt) = 0 THEN 0
                ELSE (SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt)) * 100.0 / SUM(prov_gr_wt)
            END,
            2
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
            SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
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
            SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt) AS short_excess_wt,
            ROUND(
                CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
            ) AS percent,
            1 AS level_order
        FROM base
        GROUP BY classification, sub_classification
    ) x
),
make_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Make Wise'::text AS report_section,
        make::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        4 AS section_sort,
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
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        5 AS section_sort,
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
        1 AS is_parent,
        SUM(prov_pieces) AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        6 AS section_sort,
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
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt) AS short_excess_wt,
        ROUND(
            CASE WHEN SUM(prov_gr_wt) = 0 THEN 0 ELSE (SUM(prov_gr_wt) - SUM(in_shop_wt) - SUM(COALESCE(order_only, 0) + COALESCE(req_only, 0)) - SUM(in_transit_wt)) * 100.0 / SUM(prov_gr_wt) END, 2
        ) AS percent,
        7 AS section_sort,
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
    SELECT * FROM make_wise
    UNION ALL
    SELECT * FROM prov_type_wise
    UNION ALL
    SELECT * FROM section_wise
    UNION ALL
    SELECT * FROM provision_mode_wise
)

SELECT
    location,
    report_section,
    report_label,
    classification,
    sub_classification,
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
        
        return render_template('partials/_view_provision_stock_status.html', rows=rows)

    except Exception as e:
        logger.error(f"Error in get_provision_stock_status_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

@dashboard_bp.route('/api/sync/provision_stock_status', methods=['POST'])
@jwt_required()
def sync_provision_stock_status():
    user_id = get_jwt_identity()
    return jsonify(sync_provision_stock_status_data(user_id))
