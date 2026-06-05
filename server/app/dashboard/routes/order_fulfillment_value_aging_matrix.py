from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, OrderFulfillmentValueAgingMatrixSnapshot
from app.extensions import db, redis_client
from app.utils.cache_utils import generate_cache_key
from sqlalchemy import func, text
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

def escape_val(v):
    if v is None:
        return ""
    return str(v).replace("'", "''")

@dashboard_bp.route('/order_fulfillment_value_aging_matrix')
def order_fulfillment_value_aging_matrix():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        return render_template('order_fulfillment_value_aging_matrix.html', 
                             unread_count=unread_count, 
                             sync_time=sync_time)
    except Exception as e:
        logger.error(f"Error in order_fulfillment_value_aging_matrix: {str(e)}")
        return f"Error: {str(e)}", 500

@dashboard_bp.route('/sync/order_fulfillment_value_aging_matrix', methods=['POST'])
@jwt_required()
def sync_order_fulfillment_value_aging_matrix():
    from app.utils.sync_manager import sync_order_fulfillment_aging_matrix_data
    return jsonify(sync_order_fulfillment_aging_matrix_data())

@dashboard_bp.route('/api/order_fulfillment_value_aging_matrix/options')
@jwt_required()
def order_fulfillment_aging_options():
    try:
        def get_distinct(col):
            return [r[0] for r in db.session.query(col.distinct()).order_by(col).all() if r[0]]

        options = {
            'purchase_offices': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.purchaseoffice),
            'supplier_names': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.suppliername),
            'groups': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.groupname),
            'sections': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.sectionname),
            'purities': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.purity),
            'location_types': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.locationtype),
            'locations': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.locationid)
        }
        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/partial/order_fulfillment_value_aging_matrix')
@jwt_required()
def get_order_fulfillment_partial():
    try:
        # Retrieve filters
        purchase_office = request.args.get('purchase_office', '')
        supplier_name = request.args.get('supplier_name', '')
        group_name = request.args.get('group_name', '')
        section_name = request.args.get('section_name', '')
        purity = request.args.get('purity', '')
        location_type = request.args.get('location_type', '')
        location = request.args.get('location', '')

        # Redis Caching Logic
        params = {
            'purchase_office': purchase_office if purchase_office else None,
            'supplier_name': supplier_name if supplier_name else None,
            'group_name': group_name if group_name else None,
            'section_name': section_name if section_name else None,
            'purity': purity if purity else None,
            'location_type': location_type if location_type else None,
            'location': location if location else None
        }
        snapshot_date = db.session.query(func.max(OrderFulfillmentValueAgingMatrixSnapshot.snapshot_date)).scalar()
        cache_key = generate_cache_key("order_fulfillment_aging_matrix_partial", snapshot_date, **params)
        
        cached_html = redis_client.get(cache_key)
        if cached_html:
            redis_client.expire(cache_key, 14400)  # Sliding expiry (4 hours)
            return cached_html

        # Build filter SQL clause
        filter_sql = ""
        if purchase_office:
            filter_sql += f" AND purchaseoffice = '{escape_val(purchase_office)}'"
        if supplier_name:
            filter_sql += f" AND suppliername = '{escape_val(supplier_name)}'"
        if group_name:
            filter_sql += f" AND groupname = '{escape_val(group_name)}'"
        if section_name:
            filter_sql += f" AND sectionname = '{escape_val(section_name)}'"
        if purity:
            filter_sql += f" AND purity = '{escape_val(purity)}'"
        if location_type:
            filter_sql += f" AND locationtype = '{escape_val(location_type)}'"
        if location:
            if ',' in location:
                locs = [f"'{escape_val(l.strip())}'" for l in location.split(',') if l.strip()]
                filter_sql += f" AND locationid IN ({','.join(locs)})"
            else:
                filter_sql += f" AND locationid = '{escape_val(location)}'"

        table_expression = f"(SELECT * FROM order_fulfillment_value_aging_matrix_snapshot WHERE 1=1{filter_sql}) AS tbl"

        # SQL template as requested
        query = f"""
DROP VIEW IF EXISTS delivery_report_last_6_months;

DO $$
DECLARE
    column_sql text;
    select_column_sql text;
    final_sql text;
BEGIN
    SELECT
        string_agg(
            format(
                'ROUND(SUM(CASE WHEN b.invoicedate >= %L::date AND b.invoicedate < %L::date THEN b.inv_netvalue ELSE 0 END) / 100000.0, 2) AS %I',
                bucket_start,
                bucket_end,
                bucket_label
            ),
            ', ' ORDER BY bucket_start
        ),
        string_agg(
            format('%I', bucket_label),
            ', ' ORDER BY bucket_start
        )
    INTO column_sql, select_column_sql
    FROM (
        SELECT
            month_start::date AS bucket_start,
            (month_start + INTERVAL '15 days')::date AS bucket_end,
            TO_CHAR(month_start, 'Mon') || ' 1 to 15' AS bucket_label
        FROM generate_series(
            DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months',
            DATE_TRUNC('month', CURRENT_DATE),
            INTERVAL '1 month'
        ) month_start

        UNION ALL

        SELECT
            (month_start + INTERVAL '15 days')::date AS bucket_start,
            (month_start + INTERVAL '1 month')::date AS bucket_end,
            TO_CHAR(month_start, 'Mon') || ' 16 to ' ||
            EXTRACT(DAY FROM month_start + INTERVAL '1 month - 1 day')::int AS bucket_label
        FROM generate_series(
            DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months',
            DATE_TRUNC('month', CURRENT_DATE),
            INTERVAL '1 month'
        ) month_start
    ) buckets;

    final_sql := format($sql$
        CREATE TEMP VIEW delivery_report_last_6_months AS
        WITH base AS (
            SELECT *
            FROM {table_expression}
            WHERE invoicedate >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
              AND invoicedate <  DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
        ),

        order_summary AS (
            SELECT
                order_date_range,
                SUM(order_amount) AS order_amount
            FROM (
                SELECT
                    orderno,
                    order_date_range,
                    MAX(ordervalue) AS order_amount
                FROM base
                GROUP BY orderno, order_date_range
            ) x
            GROUP BY order_date_range
        ),

        report AS (
            SELECT
                b.order_date_range AS "Order Date",

                CASE
                    WHEN EXTRACT(MONTH FROM TO_DATE(split_part(b.order_date_range, ' ', 1), 'Mon'))
                         > EXTRACT(MONTH FROM CURRENT_DATE)
                    THEN TO_DATE(
                        split_part(b.order_date_range, ' ', 1) || ' ' ||
                        split_part(b.order_date_range, ' ', 2) || ' ' ||
                        (EXTRACT(YEAR FROM CURRENT_DATE)::int - 1),
                        'Mon DD YYYY'
                    )
                    ELSE TO_DATE(
                        split_part(b.order_date_range, ' ', 1) || ' ' ||
                        split_part(b.order_date_range, ' ', 2) || ' ' ||
                        EXTRACT(YEAR FROM CURRENT_DATE)::int,
                        'Mon DD YYYY'
                    )
                END AS sort_date,

                ROUND(COALESCE(o.order_amount, 0) / 100000.0, 2) AS "Order Amount",
                %s,
                ROUND(SUM(b.inv_netvalue) / 100000.0, 2) AS "Grand Total"

            FROM base b
            LEFT JOIN order_summary o
                ON o.order_date_range = b.order_date_range
            GROUP BY
                b.order_date_range,
                o.order_amount
        )

        SELECT
            "Order Date",
            "Order Amount",
            %s,
            "Grand Total"
        FROM report
        ORDER BY sort_date;
    $sql$, column_sql, select_column_sql);

    EXECUTE final_sql;
END $$;

SELECT *
FROM delivery_report_last_6_months;
        """

        # Execute PL/pgSQL DO block to generate temp view and select results
        db.session.execute(text(query))
        res = db.session.execute(text("SELECT * FROM delivery_report_last_6_months"))
        
        headers = list(res.keys())
        rows = [dict(zip(headers, row)) for row in res.fetchall()]
        
        # Calculate summary statistics:
        # 1. Total Order Amount = SUM of "Order Amount" across rows
        # 2. Total Delivered Amount = SUM of "Grand Total" across rows
        # 3. Number of Order Buckets = count of rows
        # 4. Highest Delivery Bucket = bucket with the highest value sum
        total_order_amount = sum(float(row.get('Order Amount') or 0.0) for row in rows)
        total_delivered_amount = sum(float(row.get('Grand Total') or 0.0) for row in rows)
        num_order_buckets = len(rows)
        
        # Find highest delivery bucket
        delivery_totals = {}
        delivery_headers = headers[2:-1] # columns between Order Amount and Grand Total
        for h in delivery_headers:
            delivery_totals[h] = sum(float(row.get(h) or 0.0) for row in rows)
        
        highest_delivery_bucket = "N/A"
        if delivery_totals:
            max_bucket = max(delivery_totals, key=delivery_totals.get)
            if delivery_totals[max_bucket] > 0:
                highest_delivery_bucket = f"{max_bucket} ({delivery_totals[max_bucket]:,.2f} L)"

        # Calculate extra stats using SQLAlchemy
        stats_query = db.session.query(
            func.sum(OrderFulfillmentValueAgingMatrixSnapshot.netweight).label('total_net_weight'),
            func.sum(OrderFulfillmentValueAgingMatrixSnapshot.invoicegrwt).label('total_gross_weight'),
            func.sum(OrderFulfillmentValueAgingMatrixSnapshot.diamondcarat).label('total_diamond_carat'),
            func.sum(OrderFulfillmentValueAgingMatrixSnapshot.colourstonecarat).label('total_colour_stone_carat')
        )
        
        if purchase_office:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.purchaseoffice == purchase_office)
        if supplier_name:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.suppliername == supplier_name)
        if group_name:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.groupname == group_name)
        if section_name:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.sectionname == section_name)
        if purity:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.purity == purity)
        if location_type:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.locationtype == location_type)
        if location:
            if ',' in location:
                locs = [l.strip() for l in location.split(',') if l.strip()]
                stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.locationid.in_(locs))
            else:
                stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.locationid == location)
                
        stats_query = stats_query.filter(
            OrderFulfillmentValueAgingMatrixSnapshot.invoicedate >= func.date_trunc('month', func.current_date()) - text("INTERVAL '5 months'"),
            OrderFulfillmentValueAgingMatrixSnapshot.invoicedate < func.date_trunc('month', func.current_date()) + text("INTERVAL '1 month'")
        )
        
        extra_stats = stats_query.first()
        total_net_weight = float(extra_stats.total_net_weight or 0.0)
        total_gross_weight = float(extra_stats.total_gross_weight or 0.0)
        total_diamond_carat = float(extra_stats.total_diamond_carat or 0.0)
        total_colour_stone_carat = float(extra_stats.total_colour_stone_carat or 0.0)

        # Calculate column totals for footer row
        footer_totals = {
            'Order Date': 'Grand Total',
            'Order Amount': total_order_amount,
            'Grand Total': total_delivered_amount
        }
        for h in delivery_headers:
            footer_totals[h] = delivery_totals[h]

        stats = {
            'total_order_amount': total_order_amount,
            'total_delivered_amount': total_delivered_amount,
            'num_order_buckets': num_order_buckets,
            'highest_delivery_bucket': highest_delivery_bucket,
            'total_net_weight': total_net_weight,
            'total_gross_weight': total_gross_weight,
            'total_diamond_carat': total_diamond_carat,
            'total_colour_stone_carat': total_colour_stone_carat
        }

        rendered_html = render_template('partials/_view_order_fulfillment_value_aging_matrix.html', 
                             headers=headers, 
                             rows=rows, 
                             stats=stats,
                             footer_totals=footer_totals,
                             delivery_headers=delivery_headers)
        redis_client.setex(cache_key, 14400, rendered_html)
        return rendered_html
    except Exception as e:
        logger.error(f"Error in get_order_fulfillment_partial: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200

