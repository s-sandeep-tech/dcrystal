from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, CustomerOrderFulfilmentSummarySnapshot
from app.extensions import db
from sqlalchemy import func, case
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import json

logger = logging.getLogger(__name__)

ORDER_STATUS_FILTERS = {'all_rejected', 'active_orders', 'delivery_in_progress', 'received_orders'}

HIERARCHIES = {
    1: {
        'id': 1,
        'name': 'Month → Date → Location',
        'levels': [
            {'field': 'report_month', 'label': 'Month', 'icon': 'calendar_month'},
            {'field': 'report_date', 'label': 'Date', 'icon': 'event'},
            {'field': 'location', 'label': 'Location', 'icon': 'location_on'}
        ]
    },
    2: {
        'id': 2,
        'name': 'Month → Business Head → Location → Date',
        'levels': [
            {'field': 'report_month', 'label': 'Month', 'icon': 'calendar_month'},
            {'field': 'business_head_name', 'label': 'Business Head', 'icon': 'person_celebrate'},
            {'field': 'location', 'label': 'Location', 'icon': 'location_on'},
            {'field': 'report_date', 'label': 'Date', 'icon': 'event'}
        ]
    },
    3: {
        'id': 3,
        'name': 'Month → Make → Collection → Location',
        'levels': [
            {'field': 'report_month', 'label': 'Month', 'icon': 'calendar_month'},
            {'field': 'make', 'label': 'Make', 'icon': 'precision_manufacturing'},
            {'field': 'collection', 'label': 'Collection', 'icon': 'category'},
            {'field': 'location', 'label': 'Location', 'icon': 'location_on'}
        ]
    },
    4: {
        'id': 4,
        'name': 'Month → Section → Wide Range',
        'levels': [
            {'field': 'report_month', 'label': 'Month', 'icon': 'calendar_month'},
            {'field': 'section', 'label': 'Section', 'icon': 'view_quilt'},
            {'field': 'wide_range', 'label': 'Wide Range', 'icon': 'tune'}
        ]
    },
    5: {
        'id': 5,
        'name': 'Month → RO → Location',
        'levels': [
            {'field': 'report_month', 'label': 'Month', 'icon': 'calendar_month'},
            {'field': 'order_ro', 'label': 'Order RO', 'icon': 'account_tree'},
            {'field': 'location', 'label': 'Location', 'icon': 'location_on'}
        ]
    },
    6: {
        'id': 6,
        'name': 'Month → Party → Location',
        'levels': [
            {'field': 'report_month', 'label': 'Month', 'icon': 'calendar_month'},
            {'field': 'party_name', 'label': 'Party', 'icon': 'factory'},
            {'field': 'location', 'label': 'Location', 'icon': 'location_on'}
        ]
    }
}


def get_order_status_filter():
    if request.args.get('all_rejected', 'false') == 'true':
        return 'all_rejected'
    status_filter = request.args.get('order_status_filter', '').strip()
    return status_filter if status_filter in ORDER_STATUS_FILTERS else ''


def apply_order_status_filter(query, status_filter):
    M = CustomerOrderFulfilmentSummarySnapshot
    if status_filter == 'all_rejected':
        return query.filter(M.total_order > 0, M.total_order == M.rejected_pcs)
    if status_filter == 'active_orders':
        return query.filter(func.coalesce(M.pending_to_be_delivered_pcs, M.pending_to_delivered_pcs, 0) > 0)
    if status_filter == 'delivery_in_progress':
        return query.filter(
            func.coalesce(M.delivered_pcs, M.delivered_to_customer_pcs, 0) > 0,
            func.coalesce(M.pending_to_be_delivered_pcs, M.pending_to_delivered_pcs, 0) > 0
        )
    if status_filter == 'received_orders':
        effective_ordered_pcs = (
            func.coalesce(M.total_order, 0)
            - func.coalesce(M.cancelled_pcs, 0)
            - func.coalesce(M.rejected_pcs, 0)
        )
        return query.filter(
            M.total_order > 0,
            func.coalesce(M.delivered_pcs, M.delivered_to_customer_pcs, 0) >= effective_ordered_pcs
        )
    return query


def split_filter_values(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def format_display_label(field_name, val):
    if val is None:
        return 'Unknown'
    val_str = str(val).strip()
    if field_name == 'report_month' or (len(val_str) == 7 and val_str[:4].isdigit() and val_str[4] == '-' and val_str[5:7].isdigit()):
        try:
            parts = val_str.split('-')
            if len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) in (1, 2):
                dt = datetime.strptime(f"{parts[0]}-{int(parts[1]):02d}-01", "%Y-%m-%d")
                return f"{dt.strftime('%b')} -{dt.strftime('%y')}"
        except Exception:
            pass
    return val_str


def parse_month_value(val_str):
    if not val_str:
        return val_str
    val_str = str(val_str).strip()
    if len(val_str) == 7 and val_str[:4].isdigit() and val_str[4] == '-' and val_str[5:7].isdigit():
        return val_str
    try:
        cleaned = val_str.replace(' ', '').replace('-', '')
        dt = datetime.strptime(cleaned, '%b%y')
        return dt.strftime('%Y-%m')
    except Exception:
        pass
    return val_str


def build_filter_query(query, search_fields=None):
    M = CustomerOrderFulfilmentSummarySnapshot

    # Order Status quick toggles
    order_status_filter = get_order_status_filter()
    query = apply_order_status_filter(query, order_status_filter)

    # Search hierarchy text
    search = request.args.get('search', '').strip()
    if search:
        search_terms = f"%{search}%"
        if search_fields:
            conditions = [getattr(M, f).ilike(search_terms) for f in search_fields if hasattr(M, f)]
            if conditions:
                cond = conditions[0]
                for c in conditions[1:]:
                    cond = cond | c
                query = query.filter(cond)
        else:
            query = query.filter(
                (M.location.ilike(search_terms)) |
                (M.business_head_name.ilike(search_terms)) |
                (M.make.ilike(search_terms)) |
                (M.collection.ilike(search_terms)) |
                (M.section.ilike(search_terms)) |
                (M.wide_range.ilike(search_terms)) |
                (M.order_ro.ilike(search_terms)) |
                (M.party_name.ilike(search_terms))
            )

    # Filter 1: report_month
    report_month = request.args.get('report_month', '').strip()
    if report_month:
        parsed_month = parse_month_value(report_month)
        query = query.filter((M.report_month == report_month) | (M.report_month == parsed_month))

    # Filter 2: report_date
    report_date = request.args.get('report_date', '').strip()
    if report_date:
        try:
            d_val = datetime.strptime(report_date, '%Y-%m-%d').date()
            query = query.filter(M.report_date == d_val)
        except ValueError:
            query = query.filter(func.cast(M.report_date, db.String).ilike(f"%{report_date}%"))

    # Filter 3: current_stage (Multi-select)
    current_stages = split_filter_values(request.args.get('current_stage', ''))
    if current_stages:
        query = query.filter(M.current_stage.in_(current_stages))

    # Filter 4: order_ageing_days (Select)
    ageing = request.args.get('order_ageing_days', '').strip()
    if ageing:
        if ageing == '0-7':
            query = query.filter(M.order_ageing_days.between(0, 7))
        elif ageing == '8-15':
            query = query.filter(M.order_ageing_days.between(8, 15))
        elif ageing == '16-30':
            query = query.filter(M.order_ageing_days.between(16, 30))
        elif ageing == '31-60':
            query = query.filter(M.order_ageing_days.between(31, 60))
        elif ageing == '60+':
            query = query.filter(M.order_ageing_days > 60)
        elif ageing.isdigit():
            query = query.filter(M.order_ageing_days >= int(ageing))

    # Filter 5: delivery_delay_days (Select)
    delay_days = request.args.get('delivery_delay_days', '').strip()
    if delay_days:
        if delay_days == '0':
            query = query.filter(M.delivery_delay_days <= 0)
        elif delay_days == '1-5':
            query = query.filter(M.delivery_delay_days.between(1, 5))
        elif delay_days == '6-10':
            query = query.filter(M.delivery_delay_days.between(6, 10))
        elif delay_days == '11-15':
            query = query.filter(M.delivery_delay_days.between(11, 15))
        elif delay_days == '15+':
            query = query.filter(M.delivery_delay_days > 15)
        elif delay_days.isdigit():
            query = query.filter(M.delivery_delay_days >= int(delay_days))

    # Filter 6: delay_status (Multi-select)
    delay_statuses = split_filter_values(request.args.get('delay_status', ''))
    if delay_statuses:
        query = query.filter(M.delay_status.in_(delay_statuses))

    # Filter 7: delay_bucket (Multi-select)
    delay_buckets = split_filter_values(request.args.get('delay_bucket', ''))
    if delay_buckets:
        query = query.filter(M.delay_bucket.in_(delay_buckets))

    # Filter 8: manager_approval_tat (Select)
    mgr_tat = request.args.get('manager_approval_tat', '').strip()
    if mgr_tat and mgr_tat.isdigit():
        query = query.filter(M.manager_approval_tat >= int(mgr_tat))

    # Filter 9: collection_owner_approval_tat (Select)
    coll_tat = request.args.get('collection_owner_approval_tat', '').strip()
    if coll_tat and coll_tat.isdigit():
        query = query.filter(M.collection_owner_approval_tat >= int(coll_tat))

    # Filter 10: customer_approval_tat (Select)
    cust_tat = request.args.get('customer_approval_tat', '').strip()
    if cust_tat and cust_tat.isdigit():
        query = query.filter(M.customer_approval_tat >= int(cust_tat))

    # Filter 11: party_acceptance_tat (Select)
    party_tat = request.args.get('party_acceptance_tat', '').strip()
    if party_tat and party_tat.isdigit():
        query = query.filter(M.party_acceptance_tat >= int(party_tat))

    # Filter 12: office_delivery_tat (Select)
    off_tat = request.args.get('office_delivery_tat', '').strip()
    if off_tat and off_tat.isdigit():
        query = query.filter(M.office_delivery_tat >= int(off_tat))

    # Filter 13: shop_delivery_tat (Select)
    shop_tat = request.args.get('shop_delivery_tat', '').strip()
    if shop_tat and shop_tat.isdigit():
        query = query.filter(M.shop_delivery_tat >= int(shop_tat))

    # Filter 14: overall_order_tat (Select)
    overall_tat = request.args.get('overall_order_tat', '').strip()
    if overall_tat and overall_tat.isdigit():
        query = query.filter(M.overall_order_tat >= int(overall_tat))

    # Filter 15: expected_vs_actual_delivery_days (Select)
    exp_act = request.args.get('expected_vs_actual_delivery_days', '').strip()
    if exp_act:
        if exp_act == 'ahead':
            query = query.filter(M.expected_vs_actual_delivery_days < 0)
        elif exp_act == 'on_time':
            query = query.filter(M.expected_vs_actual_delivery_days == 0)
        elif exp_act == 'delayed':
            query = query.filter(M.expected_vs_actual_delivery_days > 0)
        elif exp_act.replace('-', '').isdigit():
            query = query.filter(M.expected_vs_actual_delivery_days == int(exp_act))

    # Filter 16: days_to_expected_delivery (Select)
    days_to_exp = request.args.get('days_to_expected_delivery', '').strip()
    if days_to_exp:
        if days_to_exp == 'overdue':
            query = query.filter(M.days_to_expected_delivery < 0)
        elif days_to_exp == 'today':
            query = query.filter(M.days_to_expected_delivery == 0)
        elif days_to_exp == '1_3':
            query = query.filter(M.days_to_expected_delivery.between(1, 3))
        elif days_to_exp == '4_7':
            query = query.filter(M.days_to_expected_delivery.between(4, 7))
        elif days_to_exp == '7_plus':
            query = query.filter(M.days_to_expected_delivery > 7)
        elif days_to_exp.replace('-', '').isdigit():
            query = query.filter(M.days_to_expected_delivery == int(days_to_exp))

    # Filter 17: delivery_status (Multi-select)
    delv_statuses = split_filter_values(request.args.get('delivery_status', ''))
    if delv_statuses:
        query = query.filter(M.delivery_status.in_(delv_statuses))

    # Filter 18: with_reference_status (Select)
    ref_stat = request.args.get('with_reference_status', '').strip()
    if ref_stat:
        query = query.filter(M.with_reference_status == ref_stat)

    # Location filter if specified
    location = request.args.get('location', '').strip()
    if location:
        query = query.filter(M.location == location)

    return query


def get_metric_aggregates():
    M = CustomerOrderFulfilmentSummarySnapshot
    return [
        func.sum(func.coalesce(M.order_generated_wt, 0)).label('ord_wt'),
        func.sum(func.coalesce(M.total_order, 0)).label('ord_pcs'),
        func.sum(func.coalesce(M.rejected_wt, 0)).label('rej_wt'),
        func.sum(func.coalesce(M.rejected_pcs, 0)).label('rej_pcs'),
        func.sum(func.coalesce(M.cancelled_wt, 0)).label('can_wt'),
        func.sum(func.coalesce(M.cancelled_pcs, 0)).label('can_pcs'),
        func.sum(func.coalesce(M.approved_wt, 0)).label('appr_wt'),
        func.sum(func.coalesce(M.approved_pcs, 0)).label('appr_pcs'),
        func.sum(func.coalesce(M.accepted_wt, 0)).label('acc_wt'),
        func.sum(func.coalesce(M.accepted_pcs, 0)).label('acc_pcs'),
        func.sum(func.coalesce(M.barcoded_wt, 0)).label('bar_wt'),
        func.sum(func.coalesce(M.barcoded_pcs, 0)).label('bar_pcs'),
        func.sum(func.coalesce(M.hallmarked_wt, 0)).label('hm_wt'),
        func.sum(func.coalesce(M.hallmarked_pcs, 0)).label('hm_pcs'),
        func.sum(func.coalesce(M.qc_passed_wt, 0)).label('qc_wt'),
        func.sum(func.coalesce(M.qc_passed_pcs, 0)).label('qc_pcs'),
        func.sum(func.coalesce(M.invoiced_wt, 0)).label('inv_wt'),
        func.sum(func.coalesce(M.invoiced_pcs, 0)).label('inv_pcs'),
        func.sum(func.coalesce(M.delivered_wt, M.delivered_to_customer_wt, 0)).label('del_wt'),
        func.sum(func.coalesce(M.delivered_pcs, M.delivered_to_customer_pcs, 0)).label('del_pcs'),
        func.sum(func.coalesce(M.pending_to_be_delivered_wt, M.pending_to_delivered_wt, 0)).label('pend_del_wt'),
        func.sum(func.coalesce(M.pending_to_be_delivered_pcs, M.pending_to_delivered_pcs, 0)).label('pend_del_pcs')
    ]


def compute_global_stats(filtered_query):
    agg_cols = get_metric_aggregates()
    agg_res = filtered_query.with_entities(*agg_cols).first()

    ord_wt = float(agg_res.ord_wt or 0) if agg_res else 0.0

    def perc(val):
        if ord_wt <= 0:
            return 0
        return min(100, round((float(val or 0) / ord_wt) * 100, 1))

    if agg_res:
        return {
            'ordered_wt': f"{float(agg_res.ord_wt or 0):,.3f}",
            'ordered_pcs': f"{int(agg_res.ord_pcs or 0):,}",
            'rejected_wt': f"{float(agg_res.rej_wt or 0):,.3f}",
            'rejected_pcs': f"{int(agg_res.rej_pcs or 0):,}",
            'rejected_perc': perc(agg_res.rej_wt),
            'cancelled_wt': f"{float(agg_res.can_wt or 0):,.3f}",
            'cancelled_pcs': f"{int(agg_res.can_pcs or 0):,}",
            'cancelled_perc': perc(agg_res.can_wt),
            'approved_wt': f"{float(agg_res.appr_wt or 0):,.3f}",
            'approved_pcs': f"{int(agg_res.appr_pcs or 0):,}",
            'approved_perc': perc(agg_res.appr_wt),
            'accepted_wt': f"{float(agg_res.acc_wt or 0):,.3f}",
            'accepted_pcs': f"{int(agg_res.acc_pcs or 0):,}",
            'accepted_perc': perc(agg_res.acc_wt),
            'barcoded_wt': f"{float(agg_res.bar_wt or 0):,.3f}",
            'barcoded_pcs': f"{int(agg_res.bar_pcs or 0):,}",
            'barcoded_perc': perc(agg_res.bar_wt),
            'hallmarked_wt': f"{float(agg_res.hm_wt or 0):,.3f}",
            'hallmarked_pcs': f"{int(agg_res.hm_pcs or 0):,}",
            'hallmarked_perc': perc(agg_res.hm_wt),
            'qc_passed_wt': f"{float(agg_res.qc_wt or 0):,.3f}",
            'qc_passed_pcs': f"{int(agg_res.qc_pcs or 0):,}",
            'qc_passed_perc': perc(agg_res.qc_wt),
            'invoiced_wt': f"{float(agg_res.inv_wt or 0):,.3f}",
            'invoiced_pcs': f"{int(agg_res.inv_pcs or 0):,}",
            'invoiced_perc': perc(agg_res.inv_wt),
            'delivered_wt': f"{float(agg_res.del_wt or 0):,.3f}",
            'delivered_pcs': f"{int(agg_res.del_pcs or 0):,}",
            'delivered_perc': perc(agg_res.del_wt),
            'pending_to_be_delv_wt': f"{float(agg_res.pend_del_wt or 0):,.3f}",
            'pending_to_be_delv_pcs': f"{int(agg_res.pend_del_pcs or 0):,}",
            'pending_to_be_delv_perc': perc(agg_res.pend_del_wt)
        }
    return {
        'ordered_wt': '0.000', 'ordered_pcs': '0',
        'rejected_wt': '0.000', 'rejected_pcs': '0', 'rejected_perc': 0,
        'cancelled_wt': '0.000', 'cancelled_pcs': '0', 'cancelled_perc': 0,
        'approved_wt': '0.000', 'approved_pcs': '0', 'approved_perc': 0,
        'accepted_wt': '0.000', 'accepted_pcs': '0', 'accepted_perc': 0,
        'barcoded_wt': '0.000', 'barcoded_pcs': '0', 'barcoded_perc': 0,
        'hallmarked_wt': '0.000', 'hallmarked_pcs': '0', 'hallmarked_perc': 0,
        'qc_passed_wt': '0.000', 'qc_passed_pcs': '0', 'qc_passed_perc': 0,
        'invoiced_wt': '0.000', 'invoiced_pcs': '0', 'invoiced_perc': 0,
        'delivered_wt': '0.000', 'delivered_pcs': '0', 'delivered_perc': 0,
        'pending_to_be_delv_wt': '0.000', 'pending_to_be_delv_pcs': '0', 'pending_to_be_delv_perc': 0
    }


def get_filter_options():
    M = CustomerOrderFulfilmentSummarySnapshot
    try:
        months = [
            {'value': r[0], 'label': format_display_label('report_month', r[0])}
            for r in db.session.query(M.report_month).filter(M.report_month.isnot(None)).distinct().order_by(M.report_month.desc()).all()
            if r[0]
        ]
        dates = [str(r[0]) for r in db.session.query(M.report_date).filter(M.report_date.isnot(None)).distinct().order_by(M.report_date.desc()).all() if r[0]]
        stages = [r[0] for r in db.session.query(M.current_stage).filter(M.current_stage.isnot(None)).distinct().order_by(M.current_stage).all() if r[0]]
        delay_stats = [r[0] for r in db.session.query(M.delay_status).filter(M.delay_status.isnot(None)).distinct().order_by(M.delay_status).all() if r[0]]
        delay_bcks = [r[0] for r in db.session.query(M.delay_bucket).filter(M.delay_bucket.isnot(None)).distinct().order_by(M.delay_bucket).all() if r[0]]
        delv_stats = [r[0] for r in db.session.query(M.delivery_status).filter(M.delivery_status.isnot(None)).distinct().order_by(M.delivery_status).all() if r[0]]
        locations = [r[0] for r in db.session.query(M.location).filter(M.location.isnot(None)).distinct().order_by(M.location).all() if r[0]]
        business_heads = [r[0] for r in db.session.query(M.business_head_name).filter(M.business_head_name.isnot(None)).distinct().order_by(M.business_head_name).all() if r[0]]
        makes = [r[0] for r in db.session.query(M.make).filter(M.make.isnot(None)).distinct().order_by(M.make).all() if r[0]]
        parties = [r[0] for r in db.session.query(M.party_name).filter(M.party_name.isnot(None)).distinct().order_by(M.party_name).all() if r[0]]
        ros = [r[0] for r in db.session.query(M.order_ro).filter(M.order_ro.isnot(None)).distinct().order_by(M.order_ro).all() if r[0]]
    except Exception as e:
        logger.warning(f"Unable to fetch filter options from snapshot table: {e}")
        months, dates, stages, delay_stats, delay_bcks, delv_stats, locations = [], [], [], [], [], [], []
        business_heads, makes, parties, ros = [], [], [], []

    return {
        'report_months': months,
        'report_dates': dates,
        'current_stages': stages or ['Order Generated', 'Approved', 'Party Accepted', 'Barcoded', 'Hallmarked', 'QC Passed', 'Invoiced', 'Received in Office', 'Delivered to Shop', 'Delivered to Customer'],
        'delay_statuses': delay_stats or ['On Time', 'Delayed', 'Critical Delay'],
        'delay_buckets': delay_bcks or ['0 Days (On Time)', '1-3 Days', '4-7 Days', '8-14 Days', '15-30 Days', '> 30 Days'],
        'delivery_statuses': delv_stats or ['Delivered to Customer', 'Delivered to Shop', 'Received in Office', 'Pending Delivery'],
        'with_reference_statuses': ['With Reference', 'Without Reference'],
        'locations': locations,
        'business_heads': business_heads,
        'makes': makes,
        'parties': parties,
        'ros': ros
    }


@dashboard_bp.route('/customerorderfulfilmentsummary')
@dashboard_bp.route('/customer-order-fulfilment-summary')
def customer_order_fulfilment_summary():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        hierarchy_id = request.args.get('hierarchy', 1, type=int)
        if hierarchy_id not in HIERARCHIES:
            hierarchy_id = 1
        current_hierarchy = HIERARCHIES[hierarchy_id]
        levels = current_hierarchy['levels']

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        search_field_names = [lvl['field'] for lvl in levels]
        base_query = db.session.query(CustomerOrderFulfilmentSummarySnapshot)
        filtered_query = build_filter_query(base_query, search_fields=search_field_names)

        # Global stats across entire filtered dataset
        stats = compute_global_stats(filtered_query)

        # Level 0 Grouping
        level_0_field = getattr(CustomerOrderFulfilmentSummarySnapshot, levels[0]['field'])
        row_aggs = get_metric_aggregates()

        group_query = filtered_query.with_entities(level_0_field, *row_aggs)
        group_query = group_query.group_by(level_0_field).order_by(level_0_field.desc() if levels[0]['field'] in ('report_month', 'report_date') else level_0_field.asc())

        pagination = group_query.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        is_leaf = len(levels) == 1
        for r in pagination.items:
            val = r[0]
            raw_val = str(val) if val is not None else 'Unknown'
            display_label = format_display_label(levels[0]['field'], val)
            processed_rows.append({
                'label': display_label,
                'level_idx': 0,
                'level_name': levels[0]['label'],
                'level_icon': levels[0]['icon'],
                'path': [raw_val],
                'is_leaf': is_leaf,
                'ord_wt': float(r.ord_wt or 0), 'ord_pcs': int(r.ord_pcs or 0),
                'rej_wt': float(r.rej_wt or 0), 'rej_pcs': int(r.rej_pcs or 0),
                'can_wt': float(r.can_wt or 0), 'can_pcs': int(r.can_pcs or 0),
                'appr_wt': float(r.appr_wt or 0), 'appr_pcs': int(r.appr_pcs or 0),
                'acc_wt': float(r.acc_wt or 0), 'acc_pcs': int(r.acc_pcs or 0),
                'bar_wt': float(r.bar_wt or 0), 'bar_pcs': int(r.bar_pcs or 0),
                'hm_wt': float(r.hm_wt or 0), 'hm_pcs': int(r.hm_pcs or 0),
                'qc_wt': float(r.qc_wt or 0), 'qc_pcs': int(r.qc_pcs or 0),
                'inv_wt': float(r.inv_wt or 0), 'inv_pcs': int(r.inv_pcs or 0),
                'del_wt': float(r.del_wt or 0), 'del_pcs': int(r.del_pcs or 0),
                'pend_del_wt': float(r.pend_del_wt or 0), 'pend_del_pcs': int(r.pend_del_pcs or 0),
            })

        filter_options = get_filter_options()

        return render_template('customer_order_fulfilment_summary.html',
                               unread_count=unread_count,
                               sync_time=sync_time,
                               stats=stats,
                               rows=processed_rows,
                               pagination=pagination,
                               hierarchies=HIERARCHIES,
                               current_hierarchy=current_hierarchy,
                               current_level_idx=0,
                               filter_options=filter_options)
    except Exception as e:
        logger.exception(f"Error in customer_order_fulfilment_summary: {e}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/customerorderfulfilmentsummary')
@dashboard_bp.route('/partial/customer-order-fulfilment-summary')
def customer_order_fulfilment_summary_partial():
    try:
        hierarchy_id = request.args.get('hierarchy', 1, type=int)
        if hierarchy_id not in HIERARCHIES:
            hierarchy_id = 1
        current_hierarchy = HIERARCHIES[hierarchy_id]
        levels = current_hierarchy['levels']

        parent_level_str = request.args.get('parent_level')
        parent_path_json = request.args.get('parent_path')

        is_child_request = parent_level_str is not None and parent_path_json is not None

        search_field_names = [lvl['field'] for lvl in levels]
        base_query = db.session.query(CustomerOrderFulfilmentSummarySnapshot)
        filtered_query = build_filter_query(base_query, search_fields=search_field_names)

        M = CustomerOrderFulfilmentSummarySnapshot
        row_aggs = get_metric_aggregates()

        if is_child_request:
            parent_level_idx = int(parent_level_str)
            target_level_idx = parent_level_idx + 1

            if target_level_idx >= len(levels):
                return '', 200

            try:
                ancestor_values = json.loads(parent_path_json)
            except Exception:
                ancestor_values = [v.strip() for v in parent_path_json.split('|')]

            child_query = filtered_query
            for i, val in enumerate(ancestor_values[:target_level_idx]):
                f_name = levels[i]['field']
                col = getattr(M, f_name)
                if val == 'Unknown' or val is None:
                    child_query = child_query.filter((col == None) | (col == '') | (col == 'Unknown'))
                elif f_name == 'report_date':
                    try:
                        d_val = datetime.strptime(str(val), '%Y-%m-%d').date()
                        child_query = child_query.filter(col == d_val)
                    except ValueError:
                        child_query = child_query.filter(func.cast(col, db.String) == str(val))
                else:
                    child_query = child_query.filter(col == val)

            target_field = getattr(M, levels[target_level_idx]['field'])
            child_query = child_query.with_entities(target_field, *row_aggs)
            child_query = child_query.group_by(target_field).order_by(
                target_field.desc() if levels[target_level_idx]['field'] in ('report_month', 'report_date') else target_field.asc()
            )

            results = child_query.all()
            is_leaf = target_level_idx == (len(levels) - 1)

            processed_rows = []
            for r in results:
                val = r[0]
                raw_val = str(val) if val is not None else 'Unknown'
                display_label = format_display_label(levels[target_level_idx]['field'], val)
                row_path = ancestor_values[:target_level_idx] + [raw_val]
                processed_rows.append({
                    'label': display_label,
                    'level_idx': target_level_idx,
                    'level_name': levels[target_level_idx]['label'],
                    'level_icon': levels[target_level_idx]['icon'],
                    'path': row_path,
                    'is_leaf': is_leaf,
                    'ord_wt': float(r.ord_wt or 0), 'ord_pcs': int(r.ord_pcs or 0),
                    'rej_wt': float(r.rej_wt or 0), 'rej_pcs': int(r.rej_pcs or 0),
                    'can_wt': float(r.can_wt or 0), 'can_pcs': int(r.can_pcs or 0),
                    'appr_wt': float(r.appr_wt or 0), 'appr_pcs': int(r.appr_pcs or 0),
                    'acc_wt': float(r.acc_wt or 0), 'acc_pcs': int(r.acc_pcs or 0),
                    'bar_wt': float(r.bar_wt or 0), 'bar_pcs': int(r.bar_pcs or 0),
                    'hm_wt': float(r.hm_wt or 0), 'hm_pcs': int(r.hm_pcs or 0),
                    'qc_wt': float(r.qc_wt or 0), 'qc_pcs': int(r.qc_pcs or 0),
                    'inv_wt': float(r.inv_wt or 0), 'inv_pcs': int(r.inv_pcs or 0),
                    'del_wt': float(r.del_wt or 0), 'del_pcs': int(r.del_pcs or 0),
                    'pend_del_wt': float(r.pend_del_wt or 0), 'pend_del_pcs': int(r.pend_del_pcs or 0),
                })

            return render_template('partials/_view_customer_order_fulfilment_summary.html',
                                 rows=processed_rows,
                                 is_child_rows=True,
                                 current_hierarchy=current_hierarchy,
                                 current_level_idx=target_level_idx,
                                 stats=None,
                                 pagination=None)

        # Full table view reload (Level 0)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        stats = compute_global_stats(filtered_query)

        level_0_field = getattr(M, levels[0]['field'])
        group_query = filtered_query.with_entities(level_0_field, *row_aggs)
        group_query = group_query.group_by(level_0_field).order_by(
            level_0_field.desc() if levels[0]['field'] in ('report_month', 'report_date') else level_0_field.asc()
        )

        pagination = group_query.paginate(page=page, per_page=per_page, error_out=False)

        is_leaf = len(levels) == 1
        processed_rows = []
        for r in pagination.items:
            val = r[0]
            raw_val = str(val) if val is not None else 'Unknown'
            display_label = format_display_label(levels[0]['field'], val)
            processed_rows.append({
                'label': display_label,
                'level_idx': 0,
                'level_name': levels[0]['label'],
                'level_icon': levels[0]['icon'],
                'path': [raw_val],
                'is_leaf': is_leaf,
                'ord_wt': float(r.ord_wt or 0), 'ord_pcs': int(r.ord_pcs or 0),
                'rej_wt': float(r.rej_wt or 0), 'rej_pcs': int(r.rej_pcs or 0),
                'can_wt': float(r.can_wt or 0), 'can_pcs': int(r.can_pcs or 0),
                'appr_wt': float(r.appr_wt or 0), 'appr_pcs': int(r.appr_pcs or 0),
                'acc_wt': float(r.acc_wt or 0), 'acc_pcs': int(r.acc_pcs or 0),
                'bar_wt': float(r.bar_wt or 0), 'bar_pcs': int(r.bar_pcs or 0),
                'hm_wt': float(r.hm_wt or 0), 'hm_pcs': int(r.hm_pcs or 0),
                'qc_wt': float(r.qc_wt or 0), 'qc_pcs': int(r.qc_pcs or 0),
                'inv_wt': float(r.inv_wt or 0), 'inv_pcs': int(r.inv_pcs or 0),
                'del_wt': float(r.del_wt or 0), 'del_pcs': int(r.del_pcs or 0),
                'pend_del_wt': float(r.pend_del_wt or 0), 'pend_del_pcs': int(r.pend_del_pcs or 0),
            })

        return render_template('partials/_view_customer_order_fulfilment_summary.html',
                             rows=processed_rows,
                             is_child_rows=False,
                             current_hierarchy=current_hierarchy,
                             stats=stats,
                             pagination=pagination)
    except Exception as e:
        logger.exception(f"Error in customer_order_fulfilment_summary_partial: {e}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Backend Error: {str(e)}</div>', 200


@dashboard_bp.route('/settings/sync-customer-order-fulfilment-summary', methods=['POST'])
def sync_customer_order_fulfilment_summary_endpoint():
    roles = {str(role).upper() for role in session.get('roles', [])}
    if not session.get('user_id') or not ({'ADMIN', 'DATA_SYNC_USER'} & roles):
        return {'status': 'error', 'message': 'Unauthorized: Admin or Data Sync role required'}, 401

    from app.utils.sync_manager import sync_customer_order_fulfilment_summary_data
    result = sync_customer_order_fulfilment_summary_data(session.get('user_id'))
    return jsonify(result), 200 if result.get('status') == 'success' else 500
