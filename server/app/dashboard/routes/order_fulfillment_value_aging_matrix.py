from flask import render_template, request, jsonify, session
from flask_jwt_extended import get_jwt_identity, jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, OrderFulfillmentValueAgingMatrixSnapshot, User
from app.extensions import db, redis_client
from app.utils.cache_utils import generate_cache_key
from sqlalchemy import func, text
from datetime import date, datetime
from zoneinfo import ZoneInfo
import logging
import re

logger = logging.getLogger(__name__)


def escape_val(v):
    if v is None:
        return ""
    return str(v).replace("'", "''")


def build_order_to_delivery_query(table_expression):
    return f"""
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
                    SUM(ordervalue) AS order_amount
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


def build_delivery_to_order_query(table_expression):
    return f"""
DROP VIEW IF EXISTS delivery_report_last_6_months;

DO $$
DECLARE
    column_sql        text;
    select_column_sql text;
    final_sql         text;
BEGIN
    SELECT
        string_agg(
            format(
                'ROUND(
                    SUM(
                        CASE
                            WHEN ob.order_date_range = %L
                            THEN ob.order_amount
                            ELSE 0
                        END
                    ) / 100000.0,
                    2
                ) AS %I',
                order_date_range,
                'Ord ' || display_label
            ),
            ', ' ORDER BY bucket_start
        ),
        string_agg(
            format('%I', 'Ord ' || display_label),
            ', ' ORDER BY bucket_start
        )
    INTO column_sql, select_column_sql
    FROM (
        SELECT
            order_date_range,
            replace(order_date_range, ' - ', ' to ') AS display_label,
            CASE
                WHEN EXTRACT(MONTH FROM TO_DATE(split_part(order_date_range, ' ', 1), 'Mon'))
                     > EXTRACT(MONTH FROM CURRENT_DATE)
                THEN TO_DATE(
                    split_part(order_date_range, ' ', 1) || ' ' ||
                    split_part(order_date_range, ' ', 2) || ' ' ||
                    (EXTRACT(YEAR FROM CURRENT_DATE)::int - 1),
                    'Mon DD YYYY'
                )
                ELSE TO_DATE(
                    split_part(order_date_range, ' ', 1) || ' ' ||
                    split_part(order_date_range, ' ', 2) || ' ' ||
                    EXTRACT(YEAR FROM CURRENT_DATE)::int,
                    'Mon DD YYYY'
                )
            END AS bucket_start
        FROM (
            SELECT DISTINCT order_date_range
            FROM {table_expression}
            WHERE invoicedate >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
              AND invoicedate <  DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
              AND order_date_range IS NOT NULL
              AND order_date_range <> ''
        ) distinct_ranges
    ) order_buckets;

    final_sql := format($sql$
        CREATE TEMP VIEW delivery_report_last_6_months AS

        WITH base AS (
            SELECT *
            FROM {table_expression}
            WHERE invoicedate >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
              AND invoicedate <  DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
        ),

        order_bucket_base AS (
            SELECT
                orderno,
                inv_date_range,
                order_date_range,
                SUM(ordervalue) AS order_amount
            FROM base
            WHERE inv_date_range IS NOT NULL
              AND inv_date_range <> ''
              AND order_date_range IS NOT NULL
              AND order_date_range <> ''
            GROUP BY
                orderno,
                inv_date_range,
                order_date_range
        ),

        delivery_summary AS (
            SELECT
                inv_date_range,
                SUM(delivery_amount) AS delivery_amount
            FROM (
                SELECT
                    orderno,
                    inv_date_range,
                    SUM(inv_netvalue) AS delivery_amount
                FROM base
                WHERE inv_date_range IS NOT NULL
                  AND inv_date_range <> ''
                GROUP BY
                    orderno,
                    inv_date_range
            ) AS x
            GROUP BY inv_date_range
        ),

        total_order_summary AS (
            SELECT
                inv_date_range,
                SUM(order_amount) AS total_order_amount
            FROM order_bucket_base
            GROUP BY inv_date_range
        ),

        report AS (
            SELECT
                ob.inv_date_range AS "Deliver Date",

                CASE
                    WHEN EXTRACT(MONTH FROM TO_DATE(split_part(ob.inv_date_range, ' ', 1), 'Mon'))
                         > EXTRACT(MONTH FROM CURRENT_DATE)
                    THEN TO_DATE(
                        split_part(ob.inv_date_range, ' ', 1) || ' ' ||
                        split_part(ob.inv_date_range, ' ', 2) || ' ' ||
                        (EXTRACT(YEAR FROM CURRENT_DATE)::int - 1),
                        'Mon DD YYYY'
                    )
                    ELSE TO_DATE(
                        split_part(ob.inv_date_range, ' ', 1) || ' ' ||
                        split_part(ob.inv_date_range, ' ', 2) || ' ' ||
                        EXTRACT(YEAR FROM CURRENT_DATE)::int,
                        'Mon DD YYYY'
                    )
                END AS sort_date,

                ROUND(COALESCE(d.delivery_amount, 0) / 100000.0, 2) AS "Delivery Amount",

                %s,

                ROUND(COALESCE(t.total_order_amount, 0) / 100000.0, 2) AS "Total Order Amount"

            FROM order_bucket_base ob
            LEFT JOIN delivery_summary d
                ON d.inv_date_range = ob.inv_date_range
            LEFT JOIN total_order_summary t
                ON t.inv_date_range = ob.inv_date_range
            GROUP BY
                ob.inv_date_range,
                d.delivery_amount,
                t.total_order_amount
        )

        SELECT
            "Deliver Date",
            "Delivery Amount",
            %s,
            "Total Order Amount"
        FROM report
        ORDER BY sort_date;
    $sql$, column_sql, select_column_sql);

    EXECUTE final_sql;
END $$;

SELECT *
FROM delivery_report_last_6_months;
    """


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
    user_id = session.get('user_id')
    if not user_id:
        jwt_identity = get_jwt_identity()
        user = db.session.get(User, int(jwt_identity)) if jwt_identity else None
        user_id = user.user_id if user else None
    return jsonify(sync_order_fulfillment_aging_matrix_data(user_id))


@dashboard_bp.route('/api/order_fulfillment_value_aging_matrix/options')
@jwt_required()
def order_fulfillment_aging_options():
    try:
        def get_distinct(col):
            return [r[0] for r in db.session.query(col.distinct()).order_by(col).all() if r[0]]

        location_rows = (
            db.session.query(
                OrderFulfillmentValueAgingMatrixSnapshot.locationid,
                OrderFulfillmentValueAgingMatrixSnapshot.locationname
            )
            .filter(
                OrderFulfillmentValueAgingMatrixSnapshot.locationid.isnot(None),
                OrderFulfillmentValueAgingMatrixSnapshot.locationid != ''
            )
            .distinct()
            .order_by(OrderFulfillmentValueAgingMatrixSnapshot.locationname)
            .all()
        )
        options = {
            'purchase_offices': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.purchaseoffice),
            'supplier_names': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.suppliername),
            'groups': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.groupname),
            'sections': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.sectionname),
            'purities': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.purity),
            'location_types': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.locationtype),
            'location_statuses': get_distinct(OrderFulfillmentValueAgingMatrixSnapshot.locationstatus),
            'locations': [{'id': r.locationid, 'name': r.locationname or r.locationid} for r in location_rows]
        }
        return jsonify(options)
    except Exception as e:
        logger.error(f"Error loading order fulfillment filter options: {str(e)}")
        return jsonify({'error': str(e)}), 500


def apply_matrix_detail_filters(query):
    filter_columns = {
        'purchase_office': OrderFulfillmentValueAgingMatrixSnapshot.purchaseoffice,
        'supplier_name': OrderFulfillmentValueAgingMatrixSnapshot.suppliername,
        'group_name': OrderFulfillmentValueAgingMatrixSnapshot.groupname,
        'section_name': OrderFulfillmentValueAgingMatrixSnapshot.sectionname,
        'purity': OrderFulfillmentValueAgingMatrixSnapshot.purity,
        'location_type': OrderFulfillmentValueAgingMatrixSnapshot.locationtype,
        'location': OrderFulfillmentValueAgingMatrixSnapshot.locationid,
        'locationstatus': OrderFulfillmentValueAgingMatrixSnapshot.locationstatus,
    }

    for parameter, column in filter_columns.items():
        values = [value.strip() for value in request.args.get(parameter, '').split(',') if value.strip()]
        if values:
            query = query.filter(column.in_(values))

    return query


def get_invoice_bucket_dates(bucket_label):
    match = re.fullmatch(r'([A-Za-z]{3})\s+(\d{1,2})\s*-\s*(\d{1,2})', bucket_label.strip())
    if not match:
        return None, None

    try:
        month = datetime.strptime(match.group(1).title(), '%b').month
        start_day = int(match.group(2))
        today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        year = today.year - 1 if month > today.month else today.year
        bucket_start = date(year, month, start_day)

        if start_day <= 15:
            bucket_end = date(year, month, 16)
        elif month == 12:
            bucket_end = date(year + 1, 1, 1)
        else:
            bucket_end = date(year, month + 1, 1)

        return bucket_start, bucket_end
    except ValueError:
        return None, None


@dashboard_bp.route('/partial/order_fulfillment_value_aging_matrix/cell_details')
@jwt_required()
def get_order_fulfillment_cell_details():
    order_date_range = request.args.get('order_date_range', '').strip()
    inv_date_range = request.args.get('inv_date_range', '').strip()

    if not order_date_range or not inv_date_range:
        return '<div class="p-6 text-center text-sm text-red-600">Order and invoice date buckets are required.</div>', 400

    bucket_start, bucket_end = get_invoice_bucket_dates(inv_date_range)
    if not bucket_start or not bucket_end:
        return '<div class="p-6 text-center text-sm text-red-600">Invalid invoice date bucket.</div>', 400

    try:
        query = OrderFulfillmentValueAgingMatrixSnapshot.query.filter(
            OrderFulfillmentValueAgingMatrixSnapshot.order_date_range == order_date_range,
            OrderFulfillmentValueAgingMatrixSnapshot.invoicedate >= bucket_start,
            OrderFulfillmentValueAgingMatrixSnapshot.invoicedate < bucket_end,
        )
        query = apply_matrix_detail_filters(query)
        details = query.order_by(
            OrderFulfillmentValueAgingMatrixSnapshot.invoicedate,
            OrderFulfillmentValueAgingMatrixSnapshot.invoiceno,
            OrderFulfillmentValueAgingMatrixSnapshot.orderno,
        ).all()

        invoice_total = sum(float(detail.inv_netvalue or 0) for detail in details) / 100000.0
        return render_template(
            'partials/_view_order_fulfillment_matrix_cell_details.html',
            details=details,
            order_date_range=order_date_range,
            inv_date_range=inv_date_range,
            invoice_total=invoice_total,
        )
    except Exception as e:
        logger.error(f"Error loading order fulfillment cell details: {str(e)}")
        return '<div class="p-6 text-center text-sm text-red-600">Unable to load invoice details.</div>', 500


@dashboard_bp.route('/partial/order_fulfillment_value_aging_matrix')
@jwt_required()
def get_order_fulfillment_partial():
    try:
        purchase_office = request.args.get('purchase_office', '')
        supplier_name = request.args.get('supplier_name', '')
        group_name = request.args.get('group_name', '')
        section_name = request.args.get('section_name', '')
        purity = request.args.get('purity', '')
        location_type = request.args.get('location_type', '')
        location = request.args.get('location', '')
        locationstatus = request.args.get('locationstatus', '')
        matrix_mode = request.args.get('matrix_mode', 'order_to_delivery')

        params = {
            'matrix_mode': matrix_mode,
            'matrix_version': '2026_07_13_01',
            'purchase_office': purchase_office if purchase_office else None,
            'supplier_name': supplier_name if supplier_name else None,
            'group_name': group_name if group_name else None,
            'section_name': section_name if section_name else None,
            'purity': purity if purity else None,
            'location_type': location_type if location_type else None,
            'location': location if location else None,
            'locationstatus': locationstatus if locationstatus else None
        }
        snapshot_date = db.session.query(func.max(OrderFulfillmentValueAgingMatrixSnapshot.snapshot_date)).scalar()
        cache_key = generate_cache_key("order_fulfillment_aging_matrix_partial", snapshot_date, **params)

        cached_html = redis_client.get(cache_key)
        if cached_html:
            redis_client.expire(cache_key, 14400)
            return cached_html

        filter_sql = ""
        if purchase_office:
            if ',' in purchase_office:
                offs = [f"'{escape_val(o.strip())}'" for o in purchase_office.split(',') if o.strip()]
                filter_sql += f" AND purchaseoffice IN ({','.join(offs)})"
            else:
                filter_sql += f" AND purchaseoffice = '{escape_val(purchase_office)}'"

        if supplier_name:
            if ',' in supplier_name:
                sups = [f"'{escape_val(s.strip())}'" for s in supplier_name.split(',') if s.strip()]
                filter_sql += f" AND suppliername IN ({','.join(sups)})"
            else:
                filter_sql += f" AND suppliername = '{escape_val(supplier_name)}'"

        if group_name:
            filter_sql += f" AND groupname = '{escape_val(group_name)}'"

        if section_name:
            if ',' in section_name:
                secs = [f"'{escape_val(s.strip())}'" for s in section_name.split(',') if s.strip()]
                filter_sql += f" AND sectionname IN ({','.join(secs)})"
            else:
                filter_sql += f" AND sectionname = '{escape_val(section_name)}'"

        if purity:
            if ',' in purity:
                purs = [f"'{escape_val(p.strip())}'" for p in purity.split(',') if p.strip()]
                filter_sql += f" AND purity IN ({','.join(purs)})"
            else:
                filter_sql += f" AND purity = '{escape_val(purity)}'"

        if location_type:
            filter_sql += f" AND locationtype = '{escape_val(location_type)}'"

        if location:
            if ',' in location:
                locs = [f"'{escape_val(l.strip())}'" for l in location.split(',') if l.strip()]
                filter_sql += f" AND locationid IN ({','.join(locs)})"
            else:
                filter_sql += f" AND locationid = '{escape_val(location)}'"

        if locationstatus:
            filter_sql += f" AND locationstatus = '{escape_val(locationstatus)}'"

        table_expression = f"(SELECT * FROM order_fulfillment_value_aging_matrix_snapshot WHERE 1=1{filter_sql}) AS tbl"
        if matrix_mode == 'delivery_to_order':
            query = build_delivery_to_order_query(table_expression)
        else:
            query = build_order_to_delivery_query(table_expression)

        db.session.execute(text(query))
        res = db.session.execute(text("SELECT * FROM delivery_report_last_6_months"))

        headers = list(res.keys())
        rows = [dict(zip(headers, row)) for row in res.fetchall()]

        amount_headers = {'Order Amount', 'Delivery Amount', 'Grand Total', 'Total Order Amount'}
        delivery_headers = [h for h in headers[1:] if h not in amount_headers]

        if 'Total Order Amount' in headers:
            total_order_amount = sum(float(row.get('Total Order Amount') or 0.0) for row in rows)
        elif 'Order Amount' in headers:
            total_order_amount = sum(float(row.get('Order Amount') or 0.0) for row in rows)
        else:
            total_order_amount_res = db.session.execute(text(f"""
                SELECT COALESCE(SUM(order_amount), 0) / 100000.0 AS total_order_amount
                FROM (
                    SELECT
                        orderno,
                        order_date_range,
                        SUM(ordervalue) AS order_amount
                    FROM {table_expression}
                    WHERE invoicedate >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
                      AND invoicedate <  DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
                    GROUP BY orderno, order_date_range
                ) x
            """)).scalar()
            total_order_amount = float(total_order_amount_res or 0.0)

        if 'Delivery Amount' in headers:
            total_delivered_amount = sum(float(row.get('Delivery Amount') or 0.0) for row in rows)
        else:
            total_delivered_amount = sum(float(row.get('Grand Total') or 0.0) for row in rows)

        num_order_buckets = len(rows)
        delivery_totals = {h: sum(float(row.get(h) or 0.0) for row in rows) for h in delivery_headers}

        highest_delivery_bucket = "N/A"
        if delivery_totals:
            max_bucket = max(delivery_totals, key=delivery_totals.get)
            if delivery_totals[max_bucket] > 0:
                highest_delivery_bucket = f"{max_bucket} ({delivery_totals[max_bucket]:,.2f} L)"

        stats_query = db.session.query(
            func.sum(OrderFulfillmentValueAgingMatrixSnapshot.netweight).label('total_net_weight'),
            func.sum(OrderFulfillmentValueAgingMatrixSnapshot.invoicegrwt).label('total_gross_weight'),
            func.sum(OrderFulfillmentValueAgingMatrixSnapshot.diamondcarat).label('total_diamond_carat'),
            func.sum(OrderFulfillmentValueAgingMatrixSnapshot.colourstonecarat).label('total_colour_stone_carat')
        )

        if purchase_office:
            offs = [o.strip() for o in purchase_office.split(',') if o.strip()]
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.purchaseoffice.in_(offs)) if len(offs) > 1 else stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.purchaseoffice == purchase_office)

        if supplier_name:
            sups = [s.strip() for s in supplier_name.split(',') if s.strip()]
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.suppliername.in_(sups)) if len(sups) > 1 else stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.suppliername == supplier_name)

        if group_name:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.groupname == group_name)

        if section_name:
            secs = [s.strip() for s in section_name.split(',') if s.strip()]
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.sectionname.in_(secs)) if len(secs) > 1 else stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.sectionname == section_name)

        if purity:
            purs = [p.strip() for p in purity.split(',') if p.strip()]
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.purity.in_(purs)) if len(purs) > 1 else stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.purity == purity)

        if location_type:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.locationtype == location_type)

        if location:
            locs = [l.strip() for l in location.split(',') if l.strip()]
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.locationid.in_(locs)) if len(locs) > 1 else stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.locationid == location)

        if locationstatus:
            stats_query = stats_query.filter(OrderFulfillmentValueAgingMatrixSnapshot.locationstatus == locationstatus)

        stats_query = stats_query.filter(
            OrderFulfillmentValueAgingMatrixSnapshot.invoicedate >= func.date_trunc('month', func.current_date()) - text("INTERVAL '5 months'"),
            OrderFulfillmentValueAgingMatrixSnapshot.invoicedate < func.date_trunc('month', func.current_date()) + text("INTERVAL '1 month'")
        )

        extra_stats = stats_query.first()
        total_net_weight = float(extra_stats.total_net_weight or 0.0)
        total_gross_weight = float(extra_stats.total_gross_weight or 0.0)
        total_diamond_carat = float(extra_stats.total_diamond_carat or 0.0)
        total_colour_stone_carat = float(extra_stats.total_colour_stone_carat or 0.0)

        first_header = headers[0] if headers else 'Order Date'
        footer_totals = {
            first_header: 'Grand Total',
            'Order Amount': total_order_amount,
            'Delivery Amount': total_delivered_amount,
            'Grand Total': total_delivered_amount,
            'Total Order Amount': total_order_amount
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

        partial_template = (
            'partials/_view_order_fulfillment_delivery_to_order_matrix.html'
            if matrix_mode == 'delivery_to_order'
            else 'partials/_view_order_fulfillment_value_aging_matrix.html'
        )
        rendered_html = render_template(partial_template,
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
