from flask import g, render_template, request, session, jsonify, redirect, url_for
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification
from app.models.customer_order_approval_pending import (
    CustomerOrderApprovalPending,
    CustomerOrderApprovalPendingSnapshot,
)
from app.extensions import db
from sqlalchemy import String, false, func
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def clean_group_value(column):
    return func.coalesce(func.nullif(func.trim(column), ''), 'Unknown')


def split_filter_values(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(',') if v.strip()]


def apply_visibility_filter(query):
    roles = {str(role).strip().upper() for role in session.get('roles', [])}
    if roles.intersection({'ADMIN', 'MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR', 'CUSTOMER OREDR CHECKER'}):
        return query
    if 'BUSINESS_HEAD' in roles:
        emp_code = str(session.get('user_id') or '').strip()
        if not emp_code:
            return query.filter(false())
        # Check against business_head or bh employee code
        return query
    if not session.get('user_id'):
        return query.filter(false())
    return query


def apply_multi_value_filter(query, column, values):
    vals = split_filter_values(values)
    if not vals:
        return query
    if len(vals) == 1:
        return query.filter(column == vals[0])
    return query.filter(column.in_(vals))


def build_filter_query(base_query):
    query = base_query

    # 1. BH (Business Head)
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.business_head_name, request.args.get('business_head') or request.args.get('business_head_name') or request.args.get('bh'))
    # 2. Location
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.location, request.args.get('location'))
    # 3. State
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.state, request.args.get('state'))
    # 4. Classification Owner
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.classification_owner, request.args.get('classification_owner'))
    # 5. Make Owner
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.make_owner, request.args.get('make_owner'))
    # 6. Collection Owner
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.collection_owner, request.args.get('collection_owner'))
    # 7. Request Type
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.request_type, request.args.get('request_type'))
    # 8. Order Item Type
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.order_item_type, request.args.get('order_item_type'))
    # 9. Order RO
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.order_ro, request.args.get('order_ro'))
    # 10. Division
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.division, request.args.get('division'))
    # 11. Group Category
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.group_category, request.args.get('group_category'))
    # 12. Group
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.group, request.args.get('group'))
    # 13. Make
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.make, request.args.get('make'))
    # 14. Classification
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.classification, request.args.get('classification'))
    # 15. Collection
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.collection, request.args.get('collection'))
    # 16. Purity
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.purity, request.args.get('purity'))
    # 17. Party Name (Supplier)
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.party_name, request.args.get('party_name') or request.args.get('supplier'))
    # 18. Combine Order Status
    query = apply_multi_value_filter(query, CustomerOrderApprovalPending.combine_order_status, request.args.get('combine_order_status') or request.args.get('order_status'))

    # Reorder Y/N
    reorder_val = (request.args.get('reorder') or request.args.get('re_order') or '').strip().lower()
    if reorder_val in ('yes', 'y', 'true', '1'):
        query = query.filter(func.lower(CustomerOrderApprovalPending.reorder).in_(['yes', 'y', 'true', '1']))
    elif reorder_val in ('no', 'n', 'false', '0'):
        query = query.filter(func.lower(CustomerOrderApprovalPending.reorder).in_(['no', 'n', 'false', '0']))

    # Request Date range filters
    req_date_from = request.args.get('request_date_from') or request.args.get('request_date_start')
    req_date_to = request.args.get('request_date_to') or request.args.get('request_date_end')
    if req_date_from:
        try:
            d_from = datetime.strptime(req_date_from.strip(), "%Y-%m-%d").date()
            query = query.filter(CustomerOrderApprovalPending.request_date >= d_from)
        except ValueError:
            pass
    if req_date_to:
        try:
            d_to = datetime.strptime(req_date_to.strip(), "%Y-%m-%d").date()
            query = query.filter(CustomerOrderApprovalPending.request_date <= d_to)
        except ValueError:
            pass

    # Customer Delivery Date Range filters
    deliv_date_from = request.args.get('customer_delivery_date_from') or request.args.get('customer_delivery_date_start')
    deliv_date_to = request.args.get('customer_delivery_date_to') or request.args.get('customer_delivery_date_end')
    if deliv_date_from:
        try:
            cd_from = datetime.strptime(deliv_date_from.strip(), "%Y-%m-%d").date()
            query = query.filter(CustomerOrderApprovalPending.customer_expected_delivery_date >= cd_from)
        except ValueError:
            pass
    if deliv_date_to:
        try:
            cd_to = datetime.strptime(deliv_date_to.strip(), "%Y-%m-%d").date()
            query = query.filter(CustomerOrderApprovalPending.customer_expected_delivery_date <= cd_to)
        except ValueError:
            pass

    # Customer Delivery Period (overdue, today, this_week, this_month, next_month, 1_3, 4_7, 7_plus)
    deliv_period = (request.args.get('customer_delivery_period') or request.args.get('delivery_period') or '').strip().lower()
    if deliv_period and deliv_period != 'all':
        try:
            today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        except Exception:
            today = date.today()

        query = query.filter(CustomerOrderApprovalPending.customer_expected_delivery_date.isnot(None))

        if deliv_period == 'overdue':
            query = query.filter(CustomerOrderApprovalPending.customer_expected_delivery_date < today)
        elif deliv_period in ('today', 'due_today'):
            query = query.filter(CustomerOrderApprovalPending.customer_expected_delivery_date == today)
        elif deliv_period in ('this_week', 'week'):
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            query = query.filter(
                CustomerOrderApprovalPending.customer_expected_delivery_date >= week_start,
                CustomerOrderApprovalPending.customer_expected_delivery_date <= week_end
            )
        elif deliv_period in ('this_month', 'month'):
            month_start = date(today.year, today.month, 1)
            next_month_start_date = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
            month_end = next_month_start_date - timedelta(days=1)
            query = query.filter(
                CustomerOrderApprovalPending.customer_expected_delivery_date >= month_start,
                CustomerOrderApprovalPending.customer_expected_delivery_date <= month_end
            )
        elif deliv_period == 'next_month':
            next_month_start_date = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
            month_after_next_date = date(next_month_start_date.year + 1, 1, 1) if next_month_start_date.month == 12 else date(next_month_start_date.year, next_month_start_date.month + 1, 1)
            next_month_end = month_after_next_date - timedelta(days=1)
            query = query.filter(
                CustomerOrderApprovalPending.customer_expected_delivery_date >= next_month_start_date,
                CustomerOrderApprovalPending.customer_expected_delivery_date <= next_month_end
            )
        elif deliv_period == '1_3':
            query = query.filter(
                CustomerOrderApprovalPending.customer_expected_delivery_date >= today + timedelta(days=1),
                CustomerOrderApprovalPending.customer_expected_delivery_date <= today + timedelta(days=3)
            )
        elif deliv_period == '4_7':
            query = query.filter(
                CustomerOrderApprovalPending.customer_expected_delivery_date >= today + timedelta(days=4),
                CustomerOrderApprovalPending.customer_expected_delivery_date <= today + timedelta(days=7)
            )
        elif deliv_period == '7_plus':
            query = query.filter(
                CustomerOrderApprovalPending.customer_expected_delivery_date > today + timedelta(days=7)
            )

    # Search filter
    search = (request.args.get('search') or '').strip()
    if search:
        query = query.filter(
            (CustomerOrderApprovalPending.business_head_name.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.classification_owner.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.make_owner.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.collection_owner.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.request_no.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.sooc.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.barcode.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.po_number.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.customer_name.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.party_name.ilike(f"%{search}%")) |
            (CustomerOrderApprovalPending.location.ilike(f"%{search}%"))
        )

    return apply_visibility_filter(query)


def get_approval_aggregate_columns():
    return [
        func.coalesce(func.sum(CustomerOrderApprovalPending.manager_approval_pending_pcs), 0).label('mgr_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.manager_approval_pending_wt), 0).label('mgr_wt'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.estimation_and_advance_pending_pcs), 0).label('est_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.estimation_and_advance_pending_wt), 0).label('est_wt'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.collection_owner_approval_pending_pcs), 0).label('coll_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.collection_owner_approval_pending_wt), 0).label('coll_wt'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.customer_approval_pending_pcs), 0).label('cust_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.customer_approval_pending_wt), 0).label('cust_wt'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.verifying_team_approval_pending_pcs), 0).label('vt_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.verifying_team_approval_pending_wt), 0).label('vt_wt'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.advance_verification_pending_pcs), 0).label('adv_v_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.advance_verification_pending_wt), 0).label('adv_v_wt'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.party_order_creation_pending_pcs), 0).label('pty_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.party_order_creation_pending_wt), 0).label('pty_wt'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.composition_pending_pcs), 0).label('comp_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.composition_pending_wt), 0).label('comp_wt'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.total_pending_pcs), 0).label('tot_pcs'),
        func.coalesce(func.sum(CustomerOrderApprovalPending.total_pending_wt), 0).label('tot_wt'),
    ]


@dashboard_bp.route('/pending-customer-order-approvals')
def pending_customer_order_approvals():
    try:
        CustomerOrderApprovalPendingSnapshot.__table__.create(db.engine, checkfirst=True)
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        opts_base = apply_visibility_filter(db.session.query(CustomerOrderApprovalPendingSnapshot))

        def get_distinct_list(column):
            try:
                query = opts_base.with_entities(column).filter(column.isnot(None))
                if isinstance(column.type, String):
                    query = query.filter(column != '')
                return [r[0] for r in query.distinct().order_by(column).all() if r[0] is not None]
            except Exception as e:
                db.session.rollback()
                logger.warning(f"Error fetching distinct list for {column}: {e}")
                return []

        filter_options = {
            'business_heads': get_distinct_list(CustomerOrderApprovalPending.business_head_name),
            'locations': get_distinct_list(CustomerOrderApprovalPending.location),
            'states': get_distinct_list(CustomerOrderApprovalPending.state),
            'classification_owners': get_distinct_list(CustomerOrderApprovalPending.classification_owner),
            'make_owners': get_distinct_list(CustomerOrderApprovalPending.make_owner),
            'collection_owners': get_distinct_list(CustomerOrderApprovalPending.collection_owner),
            'request_types': get_distinct_list(CustomerOrderApprovalPending.request_type),
            'order_item_types': get_distinct_list(CustomerOrderApprovalPending.order_item_type),
            'order_ros': get_distinct_list(CustomerOrderApprovalPending.order_ro),
            'divisions': get_distinct_list(CustomerOrderApprovalPending.division),
            'group_categories': get_distinct_list(CustomerOrderApprovalPending.group_category),
            'groups': get_distinct_list(CustomerOrderApprovalPending.group),
            'makes': get_distinct_list(CustomerOrderApprovalPending.make),
            'classifications': get_distinct_list(CustomerOrderApprovalPending.classification),
            'collections': get_distinct_list(CustomerOrderApprovalPending.collection),
            'purities': [str(x) for x in get_distinct_list(CustomerOrderApprovalPending.purity)],
            'party_names': get_distinct_list(CustomerOrderApprovalPending.party_name),
            'combine_order_statuses': get_distinct_list(CustomerOrderApprovalPending.combine_order_status),
            'reorder_options': ['Yes', 'No']
        }

        return render_template(
            'pending_customer_order_approvals.html',
            unread_count=unread_count,
            sync_time=sync_time,
            stats=None,
            rows=[],
            pagination=None,
            current_level='bh',
            filter_options=filter_options,
            sort_by=request.args.get('sort_by', 'primary'),
            sort_order=request.args.get('sort_order', 'asc')
        )
    except Exception as e:
        db.session.rollback()
        logger.exception('Error loading pending-customer-order-approvals report page: %s', str(e))
        return 'Unable to load Pending Customer Order Approvals Report page', 500


@dashboard_bp.route('/customer-order-approvals')
def customer_order_approvals_alias():
    """Friendly route alias redirecting to /pending-customer-order-approvals with full query params"""
    return redirect(url_for('dashboard.pending_customer_order_approvals', **request.args))


@dashboard_bp.route('/api/pending-customer-order-approvals/data')
@jwt_required(optional=True)
def pending_customer_order_approvals_data():
    try:
        CustomerOrderApprovalPendingSnapshot.__table__.create(db.engine, checkfirst=True)
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(100, max(1, request.args.get('per_page', 50, type=int)))

        # Global Top Stats Aggregation
        agg_cols = [
            func.coalesce(func.sum(CustomerOrderApprovalPending.manager_approval_pending_pcs), 0).label('total_mgr_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.manager_approval_pending_wt), 0).label('total_mgr_wt'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.estimation_and_advance_pending_pcs), 0).label('total_est_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.estimation_and_advance_pending_wt), 0).label('total_est_wt'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.collection_owner_approval_pending_pcs), 0).label('total_coll_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.collection_owner_approval_pending_wt), 0).label('total_coll_wt'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.customer_approval_pending_pcs), 0).label('total_cust_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.customer_approval_pending_wt), 0).label('total_cust_wt'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.verifying_team_approval_pending_pcs), 0).label('total_vt_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.verifying_team_approval_pending_wt), 0).label('total_vt_wt'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.advance_verification_pending_pcs), 0).label('total_adv_v_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.advance_verification_pending_wt), 0).label('total_adv_v_wt'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.party_order_creation_pending_pcs), 0).label('total_pty_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.party_order_creation_pending_wt), 0).label('total_pty_wt'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.composition_pending_pcs), 0).label('total_comp_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.composition_pending_wt), 0).label('total_comp_wt'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.total_pending_pcs), 0).label('total_tot_pcs'),
            func.coalesce(func.sum(CustomerOrderApprovalPending.total_pending_wt), 0).label('total_tot_wt'),
        ]

        agg_q = db.session.query(*agg_cols)
        agg_q = build_filter_query(agg_q)
        aggs = agg_q.first()

        total_wt = float(aggs.total_tot_wt or 0) if aggs else 0.0

        def get_perc(val):
            if total_wt <= 0:
                return 0
            return min(100, round((float(val or 0) / total_wt) * 100, 1))

        stats = {
            'total_pcs': f"{int(aggs.total_tot_pcs or 0):,}" if aggs else "0",
            'total_wt': f"{float(aggs.total_tot_wt or 0):,.3f}" if aggs else "0.000",
            'manager_approval_pcs': f"{int(aggs.total_mgr_pcs or 0):,}" if aggs else "0",
            'manager_approval_wt': f"{float(aggs.total_mgr_wt or 0):,.3f}" if aggs else "0.000",
            'manager_approval_perc': get_perc(aggs.total_mgr_wt) if aggs else 0,
            'order_confirmation_pcs': f"{int(aggs.total_est_pcs or 0):,}" if aggs else "0",
            'order_confirmation_wt': f"{float(aggs.total_est_wt or 0):,.3f}" if aggs else "0.000",
            'order_confirmation_perc': get_perc(aggs.total_est_wt) if aggs else 0,
            'collection_owner_pcs': f"{int(aggs.total_coll_pcs or 0):,}" if aggs else "0",
            'collection_owner_wt': f"{float(aggs.total_coll_wt or 0):,.3f}" if aggs else "0.000",
            'collection_owner_perc': get_perc(aggs.total_coll_wt) if aggs else 0,
            'customer_approval_pcs': f"{int(aggs.total_cust_pcs or 0):,}" if aggs else "0",
            'customer_approval_wt': f"{float(aggs.total_cust_wt or 0):,.3f}" if aggs else "0.000",
            'customer_approval_perc': get_perc(aggs.total_cust_wt) if aggs else 0,
            'verifying_team_pcs': f"{int(aggs.total_vt_pcs or 0):,}" if aggs else "0",
            'verifying_team_wt': f"{float(aggs.total_vt_wt or 0):,.3f}" if aggs else "0.000",
            'verifying_team_perc': get_perc(aggs.total_vt_wt) if aggs else 0,
            'advance_verification_pcs': f"{int(aggs.total_adv_v_pcs or 0):,}" if aggs else "0",
            'advance_verification_wt': f"{float(aggs.total_adv_v_wt or 0):,.3f}" if aggs else "0.000",
            'advance_verification_perc': get_perc(aggs.total_adv_v_wt) if aggs else 0,
            'party_order_creation_pcs': f"{int(aggs.total_pty_pcs or 0):,}" if aggs else "0",
            'party_order_creation_wt': f"{float(aggs.total_pty_wt or 0):,.3f}" if aggs else "0.000",
            'party_order_creation_perc': get_perc(aggs.total_pty_wt) if aggs else 0,
            'composition_pcs': f"{int(aggs.total_comp_pcs or 0):,}" if aggs else "0",
            'composition_wt': f"{float(aggs.total_comp_wt or 0):,.3f}" if aggs else "0.000",
            'composition_perc': get_perc(aggs.total_comp_wt) if aggs else 0,
        }

        # Level 1: BH (Business Head)
        primary_col = clean_group_value(CustomerOrderApprovalPending.business_head_name).label('primary_group')
        row_agg_cols = get_approval_aggregate_columns()
        main_q = db.session.query(primary_col, *row_agg_cols)
        main_q = build_filter_query(main_q)

        # Sorting support
        sort_by = request.args.get('sort_by', 'primary').strip().lower()
        sort_order = request.args.get('sort_order', 'asc' if sort_by in ('primary', 'bh', 'business_head') else 'desc').strip().lower()
        if sort_order not in ('asc', 'desc'):
            sort_order = 'desc'

        sort_col_map = {
            'primary': primary_col,
            'bh': primary_col,
            'business_head': primary_col,
            'manager_approval_wt': row_agg_cols[1], 'manager_approval_pcs': row_agg_cols[0],
            'order_confirmation_wt': row_agg_cols[3], 'order_confirmation_pcs': row_agg_cols[2],
            'collection_owner_wt': row_agg_cols[5], 'collection_owner_pcs': row_agg_cols[4],
            'customer_approval_wt': row_agg_cols[7], 'customer_approval_pcs': row_agg_cols[6],
            'verifying_team_wt': row_agg_cols[9], 'verifying_team_pcs': row_agg_cols[8],
            'advance_verification_wt': row_agg_cols[11], 'advance_verification_pcs': row_agg_cols[10],
            'party_order_creation_wt': row_agg_cols[13], 'party_order_creation_pcs': row_agg_cols[12],
            'composition_wt': row_agg_cols[15], 'composition_pcs': row_agg_cols[14],
            'tot_wt': row_agg_cols[17], 'total_weight': row_agg_cols[17],
            'tot_pcs': row_agg_cols[16], 'total_pcs': row_agg_cols[16],
        }

        order_expr = sort_col_map.get(sort_by, primary_col)
        if sort_order == 'desc':
            main_q = main_q.group_by(primary_col).order_by(order_expr.desc().nullslast(), primary_col.asc())
        else:
            main_q = main_q.group_by(primary_col).order_by(order_expr.asc().nullslast(), primary_col.asc())

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            processed_rows.append({
                'primary_value': r[0] or 'Unknown',
                'bh': r[0] or 'Unknown',
                'classification_owner': '',
                'make_owner': '',
                'collection_owner': '',
                'manager_approval_pcs': int(r.mgr_pcs or 0), 'manager_approval_wt': float(r.mgr_wt or 0),
                'order_confirmation_pcs': int(r.est_pcs or 0), 'order_confirmation_wt': float(r.est_wt or 0),
                'collection_owner_pcs': int(r.coll_pcs or 0), 'collection_owner_wt': float(r.coll_wt or 0),
                'customer_approval_pcs': int(r.cust_pcs or 0), 'customer_approval_wt': float(r.cust_wt or 0),
                'verifying_team_pcs': int(r.vt_pcs or 0), 'verifying_team_wt': float(r.vt_wt or 0),
                'advance_verification_pcs': int(r.adv_v_pcs or 0), 'advance_verification_wt': float(r.adv_v_wt or 0),
                'party_order_creation_pcs': int(r.pty_pcs or 0), 'party_order_creation_wt': float(r.pty_wt or 0),
                'composition_pcs': int(r.comp_pcs or 0), 'composition_wt': float(r.comp_wt or 0),
                'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                'level': 'bh',
            })

        html = render_template(
            'partials/_view_pending_customer_order_approvals.html',
            rows=processed_rows,
            pagination=pagination,
            current_level='bh',
            is_child=False,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return jsonify(html=html, stats=stats, total=pagination.total, count=len(processed_rows))
    except Exception as e:
        logger.error(f"Error in pending_customer_order_approvals_data: {str(e)}")
        db.session.rollback()
        return jsonify(error='Unable to load Pending Customer Order Approvals data'), 500


@dashboard_bp.route('/partial/pending-customer-order-approvals')
@jwt_required(optional=True)
def get_pending_customer_order_approvals_partial():
    try:
        CustomerOrderApprovalPendingSnapshot.__table__.create(db.engine, checkfirst=True)
        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        bh_value = request.args.get('bh_value') or request.args.get('parent_bh')
        classification_owner_value = request.args.get('classification_owner_value') or request.args.get('parent_classification_owner')
        make_owner_value = request.args.get('make_owner_value') or request.args.get('parent_make_owner')

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        is_child_rows = bool(parent_level)
        row_agg_cols = get_approval_aggregate_columns()

        sort_by = request.args.get('sort_by', 'primary').strip().lower()
        sort_order = request.args.get('sort_order', 'asc' if sort_by in ('primary', 'bh', 'business_head') else 'desc').strip().lower()
        if sort_order not in ('asc', 'desc'):
            sort_order = 'desc'

        sort_col_map = {
            'manager_approval_wt': row_agg_cols[1], 'manager_approval_pcs': row_agg_cols[0],
            'order_confirmation_wt': row_agg_cols[3], 'order_confirmation_pcs': row_agg_cols[2],
            'collection_owner_wt': row_agg_cols[5], 'collection_owner_pcs': row_agg_cols[4],
            'customer_approval_wt': row_agg_cols[7], 'customer_approval_pcs': row_agg_cols[6],
            'verifying_team_wt': row_agg_cols[9], 'verifying_team_pcs': row_agg_cols[8],
            'advance_verification_wt': row_agg_cols[11], 'advance_verification_pcs': row_agg_cols[10],
            'party_order_creation_wt': row_agg_cols[13], 'party_order_creation_pcs': row_agg_cols[12],
            'composition_wt': row_agg_cols[15], 'composition_pcs': row_agg_cols[14],
            'tot_wt': row_agg_cols[17], 'total_weight': row_agg_cols[17],
            'tot_pcs': row_agg_cols[16], 'total_pcs': row_agg_cols[16],
        }

        if is_child_rows:
            # 1. BH -> Classification Owner
            if parent_level == 'bh':
                bh_col = clean_group_value(CustomerOrderApprovalPending.business_head_name).label('bh')
                co_col = clean_group_value(CustomerOrderApprovalPending.classification_owner).label('classification_owner')

                main_q = db.session.query(bh_col, co_col, *row_agg_cols)
                main_q = build_filter_query(main_q)
                main_q = main_q.filter(bh_col == parent_value)

                child_order_expr = sort_col_map.get(sort_by, co_col)
                if sort_order == 'desc':
                    main_q = main_q.group_by(bh_col, co_col).order_by(child_order_expr.desc().nullslast(), co_col.asc())
                else:
                    main_q = main_q.group_by(bh_col, co_col).order_by(child_order_expr.asc().nullslast(), co_col.asc())

                items = main_q.all()
                processed_rows = []
                for r in items:
                    processed_rows.append({
                        'primary_value': r[1],
                        'bh': r[0],
                        'classification_owner': r[1],
                        'make_owner': '',
                        'collection_owner': '',
                        'manager_approval_pcs': int(r.mgr_pcs or 0), 'manager_approval_wt': float(r.mgr_wt or 0),
                        'order_confirmation_pcs': int(r.est_pcs or 0), 'order_confirmation_wt': float(r.est_wt or 0),
                        'collection_owner_pcs': int(r.coll_pcs or 0), 'collection_owner_wt': float(r.coll_wt or 0),
                        'customer_approval_pcs': int(r.cust_pcs or 0), 'customer_approval_wt': float(r.cust_wt or 0),
                        'verifying_team_pcs': int(r.vt_pcs or 0), 'verifying_team_wt': float(r.vt_wt or 0),
                        'advance_verification_pcs': int(r.adv_v_pcs or 0), 'advance_verification_wt': float(r.adv_v_wt or 0),
                        'party_order_creation_pcs': int(r.pty_pcs or 0), 'party_order_creation_wt': float(r.pty_wt or 0),
                        'composition_pcs': int(r.comp_pcs or 0), 'composition_wt': float(r.comp_wt or 0),
                        'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                        'level': 'classification_owner',
                    })
                return render_template(
                    'partials/_view_pending_customer_order_approvals.html',
                    rows=processed_rows,
                    is_child=True,
                    parent_level=parent_level,
                    sort_by=sort_by,
                    sort_order=sort_order
                )

            # 2. Classification Owner -> Make Owner
            elif parent_level == 'classification_owner':
                bh_col = clean_group_value(CustomerOrderApprovalPending.business_head_name).label('bh')
                co_col = clean_group_value(CustomerOrderApprovalPending.classification_owner).label('classification_owner')
                mo_col = clean_group_value(CustomerOrderApprovalPending.make_owner).label('make_owner')

                main_q = db.session.query(bh_col, co_col, mo_col, *row_agg_cols)
                main_q = build_filter_query(main_q)
                main_q = main_q.filter(co_col == parent_value)
                if bh_value:
                    main_q = main_q.filter(bh_col == bh_value)

                child_order_expr = sort_col_map.get(sort_by, mo_col)
                if sort_order == 'desc':
                    main_q = main_q.group_by(bh_col, co_col, mo_col).order_by(child_order_expr.desc().nullslast(), mo_col.asc())
                else:
                    main_q = main_q.group_by(bh_col, co_col, mo_col).order_by(child_order_expr.asc().nullslast(), mo_col.asc())

                items = main_q.all()
                processed_rows = []
                for r in items:
                    processed_rows.append({
                        'primary_value': r[2],
                        'bh': r[0],
                        'classification_owner': r[1],
                        'make_owner': r[2],
                        'collection_owner': '',
                        'manager_approval_pcs': int(r.mgr_pcs or 0), 'manager_approval_wt': float(r.mgr_wt or 0),
                        'order_confirmation_pcs': int(r.est_pcs or 0), 'order_confirmation_wt': float(r.est_wt or 0),
                        'collection_owner_pcs': int(r.coll_pcs or 0), 'collection_owner_wt': float(r.coll_wt or 0),
                        'customer_approval_pcs': int(r.cust_pcs or 0), 'customer_approval_wt': float(r.cust_wt or 0),
                        'verifying_team_pcs': int(r.vt_pcs or 0), 'verifying_team_wt': float(r.vt_wt or 0),
                        'advance_verification_pcs': int(r.adv_v_pcs or 0), 'advance_verification_wt': float(r.adv_v_wt or 0),
                        'party_order_creation_pcs': int(r.pty_pcs or 0), 'party_order_creation_wt': float(r.pty_wt or 0),
                        'composition_pcs': int(r.comp_pcs or 0), 'composition_wt': float(r.comp_wt or 0),
                        'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                        'level': 'make_owner',
                    })
                return render_template(
                    'partials/_view_pending_customer_order_approvals.html',
                    rows=processed_rows,
                    is_child=True,
                    parent_level=parent_level,
                    sort_by=sort_by,
                    sort_order=sort_order
                )

            # 3. Make Owner -> Collection Owner
            elif parent_level == 'make_owner':
                bh_col = clean_group_value(CustomerOrderApprovalPending.business_head_name).label('bh')
                co_col = clean_group_value(CustomerOrderApprovalPending.classification_owner).label('classification_owner')
                mo_col = clean_group_value(CustomerOrderApprovalPending.make_owner).label('make_owner')
                coll_col = clean_group_value(CustomerOrderApprovalPending.collection_owner).label('collection_owner')

                main_q = db.session.query(bh_col, co_col, mo_col, coll_col, *row_agg_cols)
                main_q = build_filter_query(main_q)
                main_q = main_q.filter(mo_col == parent_value)
                if classification_owner_value:
                    main_q = main_q.filter(co_col == classification_owner_value)
                if bh_value:
                    main_q = main_q.filter(bh_col == bh_value)

                child_order_expr = sort_col_map.get(sort_by, coll_col)
                if sort_order == 'desc':
                    main_q = main_q.group_by(bh_col, co_col, mo_col, coll_col).order_by(child_order_expr.desc().nullslast(), coll_col.asc())
                else:
                    main_q = main_q.group_by(bh_col, co_col, mo_col, coll_col).order_by(child_order_expr.asc().nullslast(), coll_col.asc())

                items = main_q.all()
                processed_rows = []
                for r in items:
                    processed_rows.append({
                        'primary_value': r[3],
                        'bh': r[0],
                        'classification_owner': r[1],
                        'make_owner': r[2],
                        'collection_owner': r[3],
                        'manager_approval_pcs': int(r.mgr_pcs or 0), 'manager_approval_wt': float(r.mgr_wt or 0),
                        'order_confirmation_pcs': int(r.est_pcs or 0), 'order_confirmation_wt': float(r.est_wt or 0),
                        'collection_owner_pcs': int(r.coll_pcs or 0), 'collection_owner_wt': float(r.coll_wt or 0),
                        'customer_approval_pcs': int(r.cust_pcs or 0), 'customer_approval_wt': float(r.cust_wt or 0),
                        'verifying_team_pcs': int(r.vt_pcs or 0), 'verifying_team_wt': float(r.vt_wt or 0),
                        'advance_verification_pcs': int(r.adv_v_pcs or 0), 'advance_verification_wt': float(r.adv_v_wt or 0),
                        'party_order_creation_pcs': int(r.pty_pcs or 0), 'party_order_creation_wt': float(r.pty_wt or 0),
                        'composition_pcs': int(r.comp_pcs or 0), 'composition_wt': float(r.comp_wt or 0),
                        'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                        'level': 'collection_owner',
                    })
                return render_template(
                    'partials/_view_pending_customer_order_approvals.html',
                    rows=processed_rows,
                    is_child=True,
                    parent_level=parent_level,
                    sort_by=sort_by,
                    sort_order=sort_order
                )

        # Full Level 1 pagination
        primary_col = clean_group_value(CustomerOrderApprovalPending.business_head_name).label('primary_group')
        main_q = db.session.query(primary_col, *row_agg_cols)
        main_q = build_filter_query(main_q)

        level1_sort_col_map = dict(sort_col_map)
        level1_sort_col_map['primary'] = primary_col
        level1_sort_col_map['bh'] = primary_col
        level1_sort_col_map['business_head'] = primary_col

        order_expr = level1_sort_col_map.get(sort_by, primary_col)
        if sort_order == 'desc':
            main_q = main_q.group_by(primary_col).order_by(order_expr.desc().nullslast(), primary_col.asc())
        else:
            main_q = main_q.group_by(primary_col).order_by(order_expr.asc().nullslast(), primary_col.asc())

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        processed_rows = []
        for r in pagination.items:
            processed_rows.append({
                'primary_value': r[0] or 'Unknown',
                'bh': r[0] or 'Unknown',
                'classification_owner': '',
                'make_owner': '',
                'collection_owner': '',
                'manager_approval_pcs': int(r.mgr_pcs or 0), 'manager_approval_wt': float(r.mgr_wt or 0),
                'order_confirmation_pcs': int(r.est_pcs or 0), 'order_confirmation_wt': float(r.est_wt or 0),
                'collection_owner_pcs': int(r.coll_pcs or 0), 'collection_owner_wt': float(r.coll_wt or 0),
                'customer_approval_pcs': int(r.cust_pcs or 0), 'customer_approval_wt': float(r.cust_wt or 0),
                'verifying_team_pcs': int(r.vt_pcs or 0), 'verifying_team_wt': float(r.vt_wt or 0),
                'advance_verification_pcs': int(r.adv_v_pcs or 0), 'advance_verification_wt': float(r.adv_v_wt or 0),
                'party_order_creation_pcs': int(r.pty_pcs or 0), 'party_order_creation_wt': float(r.pty_wt or 0),
                'composition_pcs': int(r.comp_pcs or 0), 'composition_wt': float(r.comp_wt or 0),
                'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                'level': 'bh',
            })

        return render_template(
            'partials/_view_pending_customer_order_approvals.html',
            rows=processed_rows,
            pagination=pagination,
            current_level='bh',
            is_child=False,
            sort_by=sort_by,
            sort_order=sort_order
        )
    except Exception as e:
        logger.error(f"Error in get_pending_customer_order_approvals_partial: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/pending-customer-order-approvals/leaf_detail')
@jwt_required(optional=True)
def get_pending_customer_order_approvals_leaf_detail():
    try:
        parent_bh = request.args.get('parent_bh', '').strip()
        parent_classification_owner = request.args.get('parent_classification_owner', '').strip()
        parent_make_owner = request.args.get('parent_make_owner', '').strip()
        parent_collection_owner = request.args.get('parent_collection_owner', '').strip()

        M = CustomerOrderApprovalPending
        query = M.query

        if parent_bh:
            if parent_bh == 'Unknown':
                query = query.filter((M.business_head_name == None) | (func.trim(M.business_head_name) == '') | (M.business_head_name == 'Unknown'))
            else:
                query = query.filter(M.business_head_name == parent_bh)

        if parent_classification_owner:
            if parent_classification_owner == 'Unknown':
                query = query.filter((M.classification_owner == None) | (func.trim(M.classification_owner) == '') | (M.classification_owner == 'Unknown'))
            else:
                query = query.filter(M.classification_owner == parent_classification_owner)

        if parent_make_owner:
            if parent_make_owner == 'Unknown':
                query = query.filter((M.make_owner == None) | (func.trim(M.make_owner) == '') | (M.make_owner == 'Unknown'))
            else:
                query = query.filter(M.make_owner == parent_make_owner)

        if parent_collection_owner:
            if parent_collection_owner == 'Unknown':
                query = query.filter((M.collection_owner == None) | (func.trim(M.collection_owner) == '') | (M.collection_owner == 'Unknown'))
            else:
                query = query.filter(M.collection_owner == parent_collection_owner)

        query = build_filter_query(query)

        # Single fast SQL aggregation for stage sums across all matching records
        leaf_summary = query.with_entities(
            func.count(M.id).label('record_count'),
            func.coalesce(func.sum(M.manager_approval_pending_pcs), 0).label('mgr_pcs'),
            func.coalesce(func.sum(M.manager_approval_pending_wt), 0).label('mgr_wt'),
            func.coalesce(func.sum(M.estimation_and_advance_pending_pcs), 0).label('est_pcs'),
            func.coalesce(func.sum(M.estimation_and_advance_pending_wt), 0).label('est_wt'),
            func.coalesce(func.sum(M.collection_owner_approval_pending_pcs), 0).label('coll_pcs'),
            func.coalesce(func.sum(M.collection_owner_approval_pending_wt), 0).label('coll_wt'),
            func.coalesce(func.sum(M.customer_approval_pending_pcs), 0).label('cust_pcs'),
            func.coalesce(func.sum(M.customer_approval_pending_wt), 0).label('cust_wt'),
            func.coalesce(func.sum(M.verifying_team_approval_pending_pcs), 0).label('vt_pcs'),
            func.coalesce(func.sum(M.verifying_team_approval_pending_wt), 0).label('vt_wt'),
            func.coalesce(func.sum(M.advance_verification_pending_pcs), 0).label('adv_v_pcs'),
            func.coalesce(func.sum(M.advance_verification_pending_wt), 0).label('adv_v_wt'),
            func.coalesce(func.sum(M.party_order_creation_pending_pcs), 0).label('pty_pcs'),
            func.coalesce(func.sum(M.party_order_creation_pending_wt), 0).label('pty_wt'),
            func.coalesce(func.sum(M.composition_pending_pcs), 0).label('comp_pcs'),
            func.coalesce(func.sum(M.composition_pending_wt), 0).label('comp_wt'),
            func.coalesce(func.sum(M.total_pending_pcs), 0).label('tot_pcs'),
            func.coalesce(func.sum(M.total_pending_wt), 0).label('tot_wt'),
        ).first()

        total_records = leaf_summary.record_count if leaf_summary else 0

        stage_totals = [
            {'label': 'Total', 'pcs': int(leaf_summary.tot_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.tot_wt or 0) if leaf_summary else 0.0, 'color': 'green', 'prefix': 'total_pending'},
            {'label': 'Estimation & Advance', 'pcs': int(leaf_summary.est_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.est_wt or 0) if leaf_summary else 0.0, 'color': 'amber', 'prefix': 'estimation_and_advance_pending'},
            {'label': 'Manager Approval', 'pcs': int(leaf_summary.mgr_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.mgr_wt or 0) if leaf_summary else 0.0, 'color': 'purple', 'prefix': 'manager_approval_pending'},
            {'label': 'Advance Verification', 'pcs': int(leaf_summary.adv_v_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.adv_v_wt or 0) if leaf_summary else 0.0, 'color': 'red', 'prefix': 'advance_verification_pending'},
            {'label': 'Customer Approval', 'pcs': int(leaf_summary.cust_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.cust_wt or 0) if leaf_summary else 0.0, 'color': 'indigo', 'prefix': 'customer_approval_pending'},
            {'label': 'Verifying Team', 'pcs': int(leaf_summary.vt_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.vt_wt or 0) if leaf_summary else 0.0, 'color': 'yellow', 'prefix': 'verifying_team_approval_pending'},
            {'label': 'Composition', 'pcs': int(leaf_summary.comp_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.comp_wt or 0) if leaf_summary else 0.0, 'color': 'teal', 'prefix': 'composition_pending'},
            {'label': 'Collection Owner', 'pcs': int(leaf_summary.coll_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.coll_wt or 0) if leaf_summary else 0.0, 'color': 'blue', 'prefix': 'collection_owner_approval_pending'},
            {'label': 'Party Order Creation', 'pcs': int(leaf_summary.pty_pcs or 0) if leaf_summary else 0, 'wt': float(leaf_summary.pty_wt or 0) if leaf_summary else 0.0, 'color': 'cyan', 'prefix': 'party_order_creation_pending'},
        ]

        # Fast record fetching capped to 300 to ensure fast DOM rendering
        records = query.order_by(M.request_date.desc().nullslast(), M.id.desc()).limit(300).all()

        grouped_records = defaultdict(list)
        for rec in records:
            supplier_key = rec.party_name or 'Unknown Supplier'
            grouped_records[supplier_key].append(rec)

        supplier_summaries = [
            {'id': f"sup_{idx}", 'supplier': k, 'party_code': items[0].party_code if items else '', 'details': items}
            for idx, (k, items) in enumerate(grouped_records.items())
        ]

        breadcrumbs = [
            {'label': label, 'value': value, 'icon': icon}
            for label, value, icon in [
                ('BH', parent_bh, 'person'),
                ('Classification Owner', parent_classification_owner, 'category'),
                ('Make Owner', parent_make_owner, 'precision_manufacturing'),
                ('Collection Owner', parent_collection_owner, 'view_quilt'),
            ] if value
        ]

        return render_template(
            'partials/_view_pending_customer_order_approvals_leaf.html',
            parent_bh=parent_bh,
            parent_classification_owner=parent_classification_owner,
            parent_make_owner=parent_make_owner,
            parent_collection_owner=parent_collection_owner,
            records=records,
            supplier_summaries=supplier_summaries,
            stage_totals=stage_totals,
            total_records=total_records,
            breadcrumbs=breadcrumbs,
        )
    except Exception as e:
        logger.error(f"Error in get_pending_customer_order_approvals_leaf_detail: {str(e)}")
        return f'<div class="p-8 text-center text-red-500 font-bold">Error loading details: {str(e)}</div>', 200


@dashboard_bp.route('/api/sync/pending-customer-order-approvals', methods=['POST'])
@jwt_required(optional=True)
def trigger_sync_pending_customer_order_approvals():
    """Trigger background sync task for Pending Customer Order Approvals report"""
    try:
        from flask_jwt_extended import current_user
        from app.utils.sync_manager import sync_customer_order_approval_pending_data
        user_id = getattr(current_user, 'user_id', None) if current_user else session.get('user_id')
        res = sync_customer_order_approval_pending_data(user_id)
        return jsonify(res)
    except Exception as e:
        logger.exception("Failed to trigger Pending Customer Order Approvals sync: %s", str(e))
        return jsonify(status="error", message=str(e)), 500
