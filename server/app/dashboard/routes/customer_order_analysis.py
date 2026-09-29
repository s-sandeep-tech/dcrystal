from flask import g, render_template, request, session, jsonify, redirect, url_for
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import (
    Notification,
    CustomerOrderAnalysis,
    CustomerOrderAnalysisSnapshot,
    OwnerWiseOrderSummarySnapshot,
)
from app.models.snapshots import BranchAuthoritySnapshot
from app.extensions import db
from sqlalchemy import String, false, func
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def mask_supplier_data():
    roles = {str(role).strip().upper() for role in session.get('roles', [])}
    return bool(roles.intersection({'BUSINESS_HEAD', 'SHOWROOM_MANAGER'}))


def clean_group_value(column):
    return func.coalesce(func.nullif(func.trim(column), ''), 'Unknown')


def get_order_age_expression():
    return (
        func.coalesce(CustomerOrderAnalysis.snapshot_date, func.current_date())
        - CustomerOrderAnalysis.request_date
    )


def split_filter_values(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(',') if v.strip()]


def get_owner_names_by_emp_code(emp_code):
    if not emp_code:
        return (), ()

    cache_key = f'customer_order_owner_names:{emp_code}'
    cached_names = getattr(g, cache_key, None)
    if cached_names is not None:
        return cached_names

    make_owner_names = []
    collection_owner_names = []
    try:
        rows = db.session.query(CustomerOrderAnalysisSnapshot.make_owner).filter(
            func.trim(CustomerOrderAnalysisSnapshot.make_owner_emp_code) == emp_code
        ).distinct().all()
        make_owner_names.extend([r[0] for r in rows if r[0]])

        rows2 = db.session.query(CustomerOrderAnalysisSnapshot.collection_wner).filter(
            func.trim(CustomerOrderAnalysisSnapshot.collection_owner_emp_code) == emp_code
        ).distinct().all()
        collection_owner_names.extend([r[0] for r in rows2 if r[0]])
    except Exception as e:
        logger.error(f"Error fetching owner names for user {emp_code}: {e}")
        db.session.rollback()

    owner_names = (
        tuple(set(make_owner_names)),
        tuple(set(collection_owner_names)),
    )
    setattr(g, cache_key, owner_names)
    return owner_names


def apply_owner_visibility_filter(query):
    user_id = str(session.get('user_id') or '').strip()
    if not user_id:
        return query

    make_owner_names, collection_owner_names = get_owner_names_by_emp_code(user_id)
    conditions = []
    if make_owner_names:
        conditions.append(CustomerOrderAnalysis.make_owner.in_(make_owner_names))
    if collection_owner_names:
        conditions.append(CustomerOrderAnalysis.collection_wner.in_(collection_owner_names))

    if not conditions:
        return query.filter(false())

    owner_filter = conditions[0]
    for condition in conditions[1:]:
        owner_filter = owner_filter | condition
    return query.filter(owner_filter)


def apply_visibility_filter(query):
    roles = {str(role).strip().upper() for role in session.get('roles', [])}
    if roles.intersection({'ADMIN', 'MANAGER_2', 'MANAGER-BIC', 'TSK_DIRECTOR'}):
        return query
    if 'BUSINESS_HEAD' in roles:
        emp_code = str(session.get('user_id') or '').strip()
        if not emp_code:
            return query.filter(false())
        return query.filter(func.trim(CustomerOrderAnalysis.bh_emp_code) == emp_code)
    if 'SHOWROOM_MANAGER' in roles:
        try:
            emp_code = int(session.get('user_id'))
        except (TypeError, ValueError):
            return query.filter(false())
        authorized_branches = db.session.query(BranchAuthoritySnapshot.branch_id).filter(
            BranchAuthoritySnapshot.emp_code == emp_code
        )
        return query.filter(CustomerOrderAnalysis.branch_id.in_(authorized_branches))
    if 'MANAGER_KMU' in roles:
        return query.filter(CustomerOrderAnalysis.make.in_([
            'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA',
            'KMU MH', 'KMU-COIN', 'KMU-TN'
        ]))
    if not session.get('user_id'):
        return query.filter(false())
    return apply_owner_visibility_filter(query)


def apply_multi_value_filter(query, column, values):
    vals = split_filter_values(values)
    if not vals:
        return query
    if len(vals) == 1:
        return query.filter(column == vals[0])
    return query.filter(column.in_(vals))


def build_filter_query(base_query):
    """
    Applies all 28 filters plus general text search and visibility constraints.
    """
    query = base_query

    # 0. Order Status
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.order_status, request.args.get('order_status'))
    # 1. State
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.state, request.args.get('state'))
    # 2. Location
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.location, request.args.get('location'))
    # 3. Business Head
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.business_head_name, request.args.get('business_head') or request.args.get('business_head_name'))
    # 4. Regional Office (order_ro)
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.order_ro, request.args.get('order_ro'))
    # 5. Branch Type
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.branch_type, request.args.get('branch_type'))
    # 6. Division
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.division, request.args.get('division'))
    # 7. Group Category
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.group_category, request.args.get('group_category'))
    # 8. Group
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.group, request.args.get('group'))
    # 9. Classification
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.classification, request.args.get('classification'))
    # 10. Sub Classification
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.sub_classification, request.args.get('sub_classification'))
    # 11. Make
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.make, request.args.get('make'))
    # 12. Section
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.section, request.args.get('section'))
    # 13. Collection
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.collection, request.args.get('collection'))
    # 14. Purity
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.purity, request.args.get('purity'))
    # 15. Supplier (party_name)
    if not mask_supplier_data():
        query = apply_multi_value_filter(query, CustomerOrderAnalysis.party_name, request.args.get('supplier') or request.args.get('party_name'))
    # 16. Supplier Type (party_type)
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.party_type, request.args.get('party_type'))
    # 17. Order Type (customer_order_type)
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.customer_order_type, request.args.get('order_type') or request.args.get('customer_order_type'))

    # 19. Request Date Range
    req_date_from = request.args.get('request_date_from') or request.args.get('request_date_start')
    req_date_to = request.args.get('request_date_to') or request.args.get('request_date_end')
    if req_date_from:
        try:
            d_from = datetime.strptime(req_date_from.strip(), "%Y-%m-%d").date()
            query = query.filter(CustomerOrderAnalysis.request_date >= d_from)
        except ValueError:
            pass
    if req_date_to:
        try:
            d_to = datetime.strptime(req_date_to.strip(), "%Y-%m-%d").date()
            query = query.filter(CustomerOrderAnalysis.request_date <= d_to)
        except ValueError:
            pass

    # 20. Expected Delivery Date Range
    exp_date_from = request.args.get('expected_delivery_date_from') or request.args.get('expected_delivery_start')
    exp_date_to = request.args.get('expected_delivery_date_to') or request.args.get('expected_delivery_end')
    if exp_date_from:
        try:
            ed_from = datetime.strptime(exp_date_from.strip(), "%Y-%m-%d")
            query = query.filter(CustomerOrderAnalysis.expected_delivery_date >= ed_from)
        except ValueError:
            pass
    if exp_date_to:
        try:
            ed_to = datetime.strptime(exp_date_to.strip() + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(CustomerOrderAnalysis.expected_delivery_date <= ed_to)
        except ValueError:
            pass

    # 21. Classification Owner
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.classification_owner, request.args.get('classification_owner'))
    # 22. Make Owner
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.make_owner, request.args.get('make_owner'))
    # 23. Collection Owner
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.collection_wner, request.args.get('collection_owner') or request.args.get('collection_wner'))
    # 24. Shop Manager
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.shop_manger, request.args.get('shop_manager') or request.args.get('shop_manger'))
    # 25. Gender
    query = apply_multi_value_filter(query, CustomerOrderAnalysis.gender, request.args.get('gender'))

    # 26. MSME (is_msme: True / False / All)
    is_msme_val = request.args.get('is_msme', '').strip().lower()
    if is_msme_val in ('true', 'yes', '1'):
        query = query.filter(CustomerOrderAnalysis.is_msme.is_(True))
    elif is_msme_val in ('false', 'no', '0'):
        query = query.filter(CustomerOrderAnalysis.is_msme.is_(False))

    # 27. Reorder (re_order: True / False / All)
    re_order_val = request.args.get('re_order', '').strip().lower()
    if re_order_val in ('true', 'yes', '1'):
        query = query.filter(CustomerOrderAnalysis.re_order.is_(True))
    elif re_order_val in ('false', 'no', '0'):
        query = query.filter(CustomerOrderAnalysis.re_order.is_(False))

    # 28. Advance Linked (advance_linked: with / without / all)
    advance_linked = request.args.get('advance_linked', '').strip().lower()
    if advance_linked in ('with', 'yes', 'true', 'linked', 'with_advance'):
        query = query.filter(
            CustomerOrderAnalysis.advance_no.isnot(None),
            func.trim(CustomerOrderAnalysis.advance_no) != ''
        )
    elif advance_linked in ('without', 'no', 'false', 'unlinked', 'without_advance'):
        query = query.filter(
            (CustomerOrderAnalysis.advance_no.is_(None)) |
            (func.trim(CustomerOrderAnalysis.advance_no) == '')
        )

    # 29. Order Age Filter (Reporting Date - Request Date)
    order_age = (request.args.get('order_age') or '').strip().lower()
    order_age_min = request.args.get('order_age_min')
    order_age_max = request.args.get('order_age_max')
    age_min = None
    age_max = None
    if order_age_min and str(order_age_min).strip().isdigit():
        age_min = int(str(order_age_min).strip())
    if order_age_max and str(order_age_max).strip().isdigit():
        age_max = int(str(order_age_max).strip())

    if order_age:
        if order_age == '0-15':
            age_min, age_max = 0, 15
        elif order_age == '16-30':
            age_min, age_max = 16, 30
        elif order_age == '31-60':
            age_min, age_max = 31, 60
        elif order_age == '61-90':
            age_min, age_max = 61, 90
        elif order_age == '91-120':
            age_min, age_max = 91, 120
        elif order_age in ('120+', '>120', '121+', '>120 days'):
            age_min = 121
        elif order_age.isdigit():
            age_min = int(order_age)

    if age_min is not None or age_max is not None:
        age_expr = get_order_age_expression()
        query = query.filter(CustomerOrderAnalysis.request_date.isnot(None))
        if age_min is not None:
            query = query.filter(age_expr >= age_min)
        if age_max is not None:
            query = query.filter(age_expr <= age_max)

    # 30. Expected Delivery Period (today, this_week, this_month, next_month, overdue)
    delivery_period = (request.args.get('delivery_period') or request.args.get('expected_delivery_period') or '').strip().lower()
    if delivery_period and delivery_period != 'all':
        try:
            today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        except Exception:
            today = date.today()

        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        query = query.filter(CustomerOrderAnalysis.expected_delivery_date.isnot(None))

        if delivery_period == 'today':
            query = query.filter(
                CustomerOrderAnalysis.expected_delivery_date >= today_start,
                CustomerOrderAnalysis.expected_delivery_date <= today_end
            )
        elif delivery_period in ('this_week', 'week'):
            week_start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
            week_end = datetime.combine(week_start.date() + timedelta(days=6), datetime.max.time())
            query = query.filter(
                CustomerOrderAnalysis.expected_delivery_date >= week_start,
                CustomerOrderAnalysis.expected_delivery_date <= week_end
            )
        elif delivery_period in ('this_month', 'month'):
            month_start = datetime.combine(date(today.year, today.month, 1), datetime.min.time())
            if today.month == 12:
                next_month_start_date = date(today.year + 1, 1, 1)
            else:
                next_month_start_date = date(today.year, today.month + 1, 1)
            month_end = datetime.combine(next_month_start_date - timedelta(days=1), datetime.max.time())
            query = query.filter(
                CustomerOrderAnalysis.expected_delivery_date >= month_start,
                CustomerOrderAnalysis.expected_delivery_date <= month_end
            )
        elif delivery_period == 'next_month':
            if today.month == 12:
                next_month_start_date = date(today.year + 1, 1, 1)
                month_after_next_date = date(today.year + 1, 2, 1)
            else:
                next_month_start_date = date(today.year, today.month + 1, 1)
                if next_month_start_date.month == 12:
                    month_after_next_date = date(next_month_start_date.year + 1, 1, 1)
                else:
                    month_after_next_date = date(next_month_start_date.year, next_month_start_date.month + 1, 1)
            next_month_start = datetime.combine(next_month_start_date, datetime.min.time())
            next_month_end = datetime.combine(month_after_next_date - timedelta(days=1), datetime.max.time())
            query = query.filter(
                CustomerOrderAnalysis.expected_delivery_date >= next_month_start,
                CustomerOrderAnalysis.expected_delivery_date <= next_month_end
            )
        elif delivery_period == 'overdue':
            query = query.filter(CustomerOrderAnalysis.expected_delivery_date < today_start)

    # Search query
    search = request.args.get('search', '').strip()
    if search:
        supplier_search = false() if mask_supplier_data() else CustomerOrderAnalysis.party_name.ilike(f"%{search}%")
        query = query.filter(
            (CustomerOrderAnalysis.location.ilike(f"%{search}%")) |
            (CustomerOrderAnalysis.make.ilike(f"%{search}%")) |
            supplier_search |
            (CustomerOrderAnalysis.classification.ilike(f"%{search}%")) |
            (CustomerOrderAnalysis.collection.ilike(f"%{search}%")) |
            (CustomerOrderAnalysis.section.ilike(f"%{search}%")) |
            (CustomerOrderAnalysis.customer_name.ilike(f"%{search}%")) |
            (CustomerOrderAnalysis.request_no.ilike(f"%{search}%")) |
            (CustomerOrderAnalysis.order_ro.ilike(f"%{search}%"))
        )

    return apply_visibility_filter(query)


def get_stage_aggregate_columns():
    return [
        func.coalesce(func.sum(CustomerOrderAnalysis.pending_to_accepted_pcs), 0).label('accept_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.pending_to_accepted_wt), 0).label('accept_wt'),
        func.coalesce(func.sum(CustomerOrderAnalysis.process_pending_pcs), 0).label('process_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.process_pending_wt), 0).label('process_wt'),
        func.coalesce(func.sum(CustomerOrderAnalysis.barcode_pending_pcs), 0).label('barcode_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.barcode_pending_wt), 0).label('barcode_wt'),
        func.coalesce(func.sum(CustomerOrderAnalysis.hallmark_pending_pcs), 0).label('hallmark_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.hallmark_pending_wt), 0).label('hallmark_wt'),
        func.coalesce(func.sum(CustomerOrderAnalysis.qc_issue_pending_pcs), 0).label('qc_issue_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.qc_issue_pending_wt), 0).label('qc_issue_wt'),
        func.coalesce(func.sum(CustomerOrderAnalysis.qc_complete_pending_pcs), 0).label('qc_complete_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.qc_complete_pending_wt), 0).label('qc_complete_wt'),
        func.coalesce(func.sum(CustomerOrderAnalysis.invoice_pending_pcs), 0).label('invoice_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.invoice_pending_wt), 0).label('invoice_wt'),
        func.coalesce(func.sum(CustomerOrderAnalysis.receipt_pending_pcs), 0).label('receipt_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.receipt_pending_wt), 0).label('receipt_wt'),
        func.coalesce(func.sum(CustomerOrderAnalysis.total_pending_pcs), 0).label('tot_pcs'),
        func.coalesce(func.sum(CustomerOrderAnalysis.total_pending_wt), 0).label('tot_wt')
    ]


@dashboard_bp.route('/customer-order-analysis')
def customer_order_analysis():
    try:
        CustomerOrderAnalysisSnapshot.__table__.create(db.engine, checkfirst=True)
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        # Base query for filter options
        opts_base = apply_visibility_filter(db.session.query(CustomerOrderAnalysisSnapshot))

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
            'order_statuses': get_distinct_list(CustomerOrderAnalysis.order_status),
            'states': get_distinct_list(CustomerOrderAnalysis.state),
            'locations': get_distinct_list(CustomerOrderAnalysis.location),
            'business_heads': get_distinct_list(CustomerOrderAnalysis.business_head_name),
            'order_ros': get_distinct_list(CustomerOrderAnalysis.order_ro),
            'branch_types': get_distinct_list(CustomerOrderAnalysis.branch_type),
            'divisions': get_distinct_list(CustomerOrderAnalysis.division),
            'group_categories': get_distinct_list(CustomerOrderAnalysis.group_category),
            'groups': get_distinct_list(CustomerOrderAnalysis.group),
            'classifications': get_distinct_list(CustomerOrderAnalysis.classification),
            'sub_classifications': get_distinct_list(CustomerOrderAnalysis.sub_classification),
            'makes': get_distinct_list(CustomerOrderAnalysis.make),
            'sections': get_distinct_list(CustomerOrderAnalysis.section),
            'collections': get_distinct_list(CustomerOrderAnalysis.collection),
            'purities': [str(x) for x in get_distinct_list(CustomerOrderAnalysis.purity)],
            'suppliers': [] if mask_supplier_data() else get_distinct_list(CustomerOrderAnalysis.party_name),
            'party_types': get_distinct_list(CustomerOrderAnalysis.party_type),
            'customer_order_types': get_distinct_list(CustomerOrderAnalysis.customer_order_type),
            'classification_owners': get_distinct_list(CustomerOrderAnalysis.classification_owner),
            'make_owners': get_distinct_list(CustomerOrderAnalysis.make_owner),
            'collection_owners': get_distinct_list(CustomerOrderAnalysis.collection_wner),
            'shop_managers': get_distinct_list(CustomerOrderAnalysis.shop_manger),
            'genders': get_distinct_list(CustomerOrderAnalysis.gender),
            'is_msme_options': ['Yes', 'No'],
            're_order_options': ['Yes', 'No']
        }

        return render_template(
            'customer_order_analysis.html',
            unread_count=unread_count,
            sync_time=sync_time,
            stats=None,
            rows=[],
            pagination=None,
            current_level='location',
            filter_options=filter_options,
            mask_suppliers=mask_supplier_data(),
            sort_by=request.args.get('sort_by', 'primary'),
            sort_order=request.args.get('sort_order', 'asc')
        )
    except Exception as e:
        db.session.rollback()
        logger.exception('Error loading customer-order-analysis report page: %s', str(e))
        return 'Unable to load Customer Order Pending Analysis Report page', 500


@dashboard_bp.route('/customer-order-analysis-report')
def customer_order_analysis_report_alias():
    """Friendly route alias redirecting to /customer-order-analysis with full query params"""
    return redirect(url_for('dashboard.customer_order_analysis', **request.args))


@dashboard_bp.route('/api/customer-order-analysis/data')
@jwt_required()
def customer_order_analysis_data():
    try:
        CustomerOrderAnalysisSnapshot.__table__.create(db.engine, checkfirst=True)
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(100, max(1, request.args.get('per_page', 50, type=int)))
        hierarchy_mode = request.args.get('hierarchy_mode', 'location')  # 'location' or 'section'

        # Global Top Stats Aggregation
        agg_cols = [
            func.coalesce(func.sum(CustomerOrderAnalysis.pending_to_accepted_pcs), 0).label('total_accept_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.pending_to_accepted_wt), 0).label('total_accept_wt'),
            func.coalesce(func.sum(CustomerOrderAnalysis.process_pending_pcs), 0).label('total_process_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.process_pending_wt), 0).label('total_process_wt'),
            func.coalesce(func.sum(CustomerOrderAnalysis.barcode_pending_pcs), 0).label('total_barcode_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.barcode_pending_wt), 0).label('total_barcode_wt'),
            func.coalesce(func.sum(CustomerOrderAnalysis.hallmark_pending_pcs), 0).label('total_hallmark_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.hallmark_pending_wt), 0).label('total_hallmark_wt'),
            func.coalesce(func.sum(CustomerOrderAnalysis.qc_issue_pending_pcs), 0).label('total_qc_issue_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.qc_issue_pending_wt), 0).label('total_qc_issue_wt'),
            func.coalesce(func.sum(CustomerOrderAnalysis.qc_complete_pending_pcs), 0).label('total_qc_complete_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.qc_complete_pending_wt), 0).label('total_qc_complete_wt'),
            func.coalesce(func.sum(CustomerOrderAnalysis.invoice_pending_pcs), 0).label('total_invoice_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.invoice_pending_wt), 0).label('total_invoice_wt'),
            func.coalesce(func.sum(CustomerOrderAnalysis.receipt_pending_pcs), 0).label('total_receipt_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.receipt_pending_wt), 0).label('total_receipt_wt'),
            func.coalesce(func.sum(CustomerOrderAnalysis.total_pending_pcs), 0).label('total_total_pcs'),
            func.coalesce(func.sum(CustomerOrderAnalysis.total_pending_wt), 0).label('total_total_wt')
        ]

        agg_q = db.session.query(*agg_cols)
        agg_q = build_filter_query(agg_q)
        aggs = agg_q.first()

        total_wt = float(aggs.total_total_wt or 0) if aggs else 0.0

        def get_perc(val):
            if total_wt <= 0:
                return 0
            return min(100, round((float(val or 0) / total_wt) * 100, 1))

        stats = {
            'total_pcs': f"{int(aggs.total_total_pcs or 0):,}" if aggs else "0",
            'total_wt': f"{float(aggs.total_total_wt or 0):,.3f}" if aggs else "0.000",
            'accept_pcs': f"{int(aggs.total_accept_pcs or 0):,}" if aggs else "0",
            'accept_wt': f"{float(aggs.total_accept_wt or 0):,.3f}" if aggs else "0.000",
            'accept_perc': get_perc(aggs.total_accept_wt) if aggs else 0,
            'process_pcs': f"{int(aggs.total_process_pcs or 0):,}" if aggs else "0",
            'process_wt': f"{float(aggs.total_process_wt or 0):,.3f}" if aggs else "0.000",
            'process_perc': get_perc(aggs.total_process_wt) if aggs else 0,
            'barcode_pcs': f"{int(aggs.total_barcode_pcs or 0):,}" if aggs else "0",
            'barcode_wt': f"{float(aggs.total_barcode_wt or 0):,.3f}" if aggs else "0.000",
            'barcode_perc': get_perc(aggs.total_barcode_wt) if aggs else 0,
            'hallmark_pcs': f"{int(aggs.total_hallmark_pcs or 0):,}" if aggs else "0",
            'hallmark_wt': f"{float(aggs.total_hallmark_wt or 0):,.3f}" if aggs else "0.000",
            'hallmark_perc': get_perc(aggs.total_hallmark_wt) if aggs else 0,
            'qc_issue_pcs': f"{int(aggs.total_qc_issue_pcs or 0):,}" if aggs else "0",
            'qc_issue_wt': f"{float(aggs.total_qc_issue_wt or 0):,.3f}" if aggs else "0.000",
            'qc_issue_perc': get_perc(aggs.total_qc_issue_wt) if aggs else 0,
            'qc_complete_pcs': f"{int(aggs.total_qc_complete_pcs or 0):,}" if aggs else "0",
            'qc_complete_wt': f"{float(aggs.total_qc_complete_wt or 0):,.3f}" if aggs else "0.000",
            'qc_complete_perc': get_perc(aggs.total_qc_complete_wt) if aggs else 0,
            'invoice_pcs': f"{int(aggs.total_invoice_pcs or 0):,}" if aggs else "0",
            'invoice_wt': f"{float(aggs.total_invoice_wt or 0):,.3f}" if aggs else "0.000",
            'invoice_perc': get_perc(aggs.total_invoice_wt) if aggs else 0,
            'receipt_pcs': f"{int(aggs.total_receipt_pcs or 0):,}" if aggs else "0",
            'receipt_wt': f"{float(aggs.total_receipt_wt or 0):,.3f}" if aggs else "0.000",
            'receipt_perc': get_perc(aggs.total_receipt_wt) if aggs else 0,
        }

        # Level 1 Table grouping
        if hierarchy_mode == 'section':
            primary_col = clean_group_value(CustomerOrderAnalysis.section).label('primary_group')
            current_level = 'section'
        else:
            primary_col = clean_group_value(CustomerOrderAnalysis.location).label('primary_group')
            current_level = 'location'

        row_agg_cols = get_stage_aggregate_columns()
        main_q = db.session.query(primary_col, *row_agg_cols)
        main_q = build_filter_query(main_q)

        # Sorting support
        sort_by = request.args.get('sort_by', 'primary').strip().lower()
        sort_order = request.args.get('sort_order', 'asc' if sort_by in ('primary', 'location', 'section') else 'desc').strip().lower()
        if sort_order not in ('asc', 'desc'):
            sort_order = 'desc'

        sort_col_map = {
            'primary': primary_col,
            'location': primary_col,
            'section': primary_col,
            'accept_pcs': row_agg_cols[0],
            'accept_wt': row_agg_cols[1],
            'process_pcs': row_agg_cols[2],
            'process_wt': row_agg_cols[3],
            'barcode_pcs': row_agg_cols[4],
            'barcode_wt': row_agg_cols[5],
            'hallmark_pcs': row_agg_cols[6],
            'hallmark_wt': row_agg_cols[7],
            'qc_issue_pcs': row_agg_cols[8],
            'qc_issue_wt': row_agg_cols[9],
            'qc_complete_pcs': row_agg_cols[10],
            'qc_complete_wt': row_agg_cols[11],
            'invoice_pcs': row_agg_cols[12],
            'invoice_wt': row_agg_cols[13],
            'receipt_pcs': row_agg_cols[14],
            'receipt_wt': row_agg_cols[15],
            'tot_pcs': row_agg_cols[16],
            'tot_wt': row_agg_cols[17],
            'total_pcs': row_agg_cols[16],
            'total_weight': row_agg_cols[17],
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
                'location': r[0] if current_level == 'location' else '',
                'section': r[0] if current_level == 'section' else '',
                'make': '',
                'classification': '',
                'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                'receipt_pcs': int(r.receipt_pcs or 0), 'receipt_wt': float(r.receipt_wt or 0),
                'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                'level': current_level,
                'hierarchy_mode': hierarchy_mode
            })

        html = render_template(
            'partials/_view_customer_order_analysis.html',
            rows=processed_rows,
            pagination=pagination,
            current_level=current_level,
            hierarchy_mode=hierarchy_mode,
            is_child=False,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return jsonify(html=html, stats=stats, total=pagination.total, count=len(processed_rows))
    except Exception as e:
        logger.error(f"Error in customer_order_analysis_data: {str(e)}")
        db.session.rollback()
        return jsonify(error='Unable to load Customer Order Analysis data'), 500


@dashboard_bp.route('/partial/customer-order-analysis')
@jwt_required()
def get_customer_order_analysis_partial():
    try:
        CustomerOrderAnalysisSnapshot.__table__.create(db.engine, checkfirst=True)
        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        hierarchy_mode = request.args.get('hierarchy_mode', 'location')

        is_child_rows = bool(parent_level)
        row_agg_cols = get_stage_aggregate_columns()

        sort_by = request.args.get('sort_by', 'primary').strip().lower()
        sort_order = request.args.get('sort_order', 'asc' if sort_by in ('primary', 'location', 'section') else 'desc').strip().lower()
        if sort_order not in ('asc', 'desc'):
            sort_order = 'desc'

        sort_col_map = {
            'accept_pcs': row_agg_cols[0],
            'accept_wt': row_agg_cols[1],
            'process_pcs': row_agg_cols[2],
            'process_wt': row_agg_cols[3],
            'barcode_pcs': row_agg_cols[4],
            'barcode_wt': row_agg_cols[5],
            'hallmark_pcs': row_agg_cols[6],
            'hallmark_wt': row_agg_cols[7],
            'qc_issue_pcs': row_agg_cols[8],
            'qc_issue_wt': row_agg_cols[9],
            'qc_complete_pcs': row_agg_cols[10],
            'qc_complete_wt': row_agg_cols[11],
            'invoice_pcs': row_agg_cols[12],
            'invoice_wt': row_agg_cols[13],
            'receipt_pcs': row_agg_cols[14],
            'receipt_wt': row_agg_cols[15],
            'tot_pcs': row_agg_cols[16],
            'tot_wt': row_agg_cols[17],
            'total_pcs': row_agg_cols[16],
            'total_weight': row_agg_cols[17],
        }

        if is_child_rows:
            if parent_level == 'location':
                loc_col = clean_group_value(CustomerOrderAnalysis.location).label('location')
                make_col = clean_group_value(CustomerOrderAnalysis.make).label('make')

                main_q = db.session.query(loc_col, make_col, *row_agg_cols)
                main_q = build_filter_query(main_q)
                main_q = main_q.filter(loc_col == parent_value)

                child_order_expr = sort_col_map.get(sort_by, make_col)
                if sort_order == 'desc':
                    main_q = main_q.group_by(loc_col, make_col).order_by(child_order_expr.desc().nullslast(), make_col.asc())
                else:
                    main_q = main_q.group_by(loc_col, make_col).order_by(child_order_expr.asc().nullslast(), make_col.asc())

                items = main_q.all()
                processed_rows = []
                for r in items:
                    processed_rows.append({
                        'primary_value': r[0],
                        'location': r[0],
                        'make': r[1],
                        'secondary_value': r[1],
                        'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                        'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                        'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                        'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                        'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                        'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                        'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                        'receipt_pcs': int(r.receipt_pcs or 0), 'receipt_wt': float(r.receipt_wt or 0),
                        'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                        'level': 'make',
                        'hierarchy_mode': hierarchy_mode
                    })
                return render_template(
                    'partials/_view_customer_order_analysis.html',
                    rows=processed_rows,
                    is_child=True,
                    parent_level=parent_level,
                    hierarchy_mode=hierarchy_mode,
                    sort_by=sort_by,
                    sort_order=sort_order
                )

            elif parent_level == 'section':
                sec_col = clean_group_value(CustomerOrderAnalysis.section).label('section')
                cls_col = clean_group_value(CustomerOrderAnalysis.classification).label('classification')

                main_q = db.session.query(sec_col, cls_col, *row_agg_cols)
                main_q = build_filter_query(main_q)
                main_q = main_q.filter(sec_col == parent_value)

                child_order_expr = sort_col_map.get(sort_by, cls_col)
                if sort_order == 'desc':
                    main_q = main_q.group_by(sec_col, cls_col).order_by(child_order_expr.desc().nullslast(), cls_col.asc())
                else:
                    main_q = main_q.group_by(sec_col, cls_col).order_by(child_order_expr.asc().nullslast(), cls_col.asc())

                items = main_q.all()
                processed_rows = []
                for r in items:
                    processed_rows.append({
                        'primary_value': r[0],
                        'section': r[0],
                        'classification': r[1],
                        'secondary_value': r[1],
                        'make': '',
                        'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                        'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                        'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                        'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                        'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                        'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                        'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                        'receipt_pcs': int(r.receipt_pcs or 0), 'receipt_wt': float(r.receipt_wt or 0),
                        'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                        'level': 'classification',
                        'hierarchy_mode': hierarchy_mode
                    })
                return render_template(
                    'partials/_view_customer_order_analysis.html',
                    rows=processed_rows,
                    is_child=True,
                    parent_level=parent_level,
                    hierarchy_mode=hierarchy_mode,
                    sort_by=sort_by,
                    sort_order=sort_order
                )

        # Full Level 1 pagination
        primary_col = clean_group_value(
            CustomerOrderAnalysis.section if hierarchy_mode == 'section' else CustomerOrderAnalysis.location
        ).label('primary_group')
        cur_level = 'section' if hierarchy_mode == 'section' else 'location'

        main_q = db.session.query(primary_col, *row_agg_cols)
        main_q = build_filter_query(main_q)

        level1_sort_col_map = dict(sort_col_map)
        level1_sort_col_map['primary'] = primary_col
        level1_sort_col_map['location'] = primary_col
        level1_sort_col_map['section'] = primary_col

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
                'location': r[0] if cur_level == 'location' else '',
                'section': r[0] if cur_level == 'section' else '',
                'make': '',
                'classification': '',
                'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                'receipt_pcs': int(r.receipt_pcs or 0), 'receipt_wt': float(r.receipt_wt or 0),
                'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                'level': cur_level,
                'hierarchy_mode': hierarchy_mode
            })

        return render_template(
            'partials/_view_customer_order_analysis.html',
            rows=processed_rows,
            pagination=pagination,
            current_level=cur_level,
            hierarchy_mode=hierarchy_mode,
            is_child=False,
            sort_by=sort_by,
            sort_order=sort_order
        )
    except Exception as e:
        logger.error(f"Error in get_customer_order_analysis_partial: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/customer-order-analysis/leaf_detail')
@jwt_required()
def get_customer_order_analysis_leaf_detail():
    try:
        parent_location = request.args.get('parent_location', '').strip()
        parent_make = request.args.get('parent_make', '').strip()
        parent_section = request.args.get('parent_section', '').strip()
        parent_classification = request.args.get('parent_classification', '').strip()

        query = CustomerOrderAnalysis.query
        loc_col = clean_group_value(CustomerOrderAnalysis.location)
        make_col = clean_group_value(CustomerOrderAnalysis.make)
        sec_col = clean_group_value(CustomerOrderAnalysis.section)
        cls_col = clean_group_value(CustomerOrderAnalysis.classification)

        if parent_location:
            query = query.filter(loc_col == parent_location)
        if parent_make:
            query = query.filter(make_col == parent_make)
        if parent_section:
            query = query.filter(sec_col == parent_section)
        if parent_classification:
            query = query.filter(cls_col == parent_classification)

        query = build_filter_query(query)
        records = query.all()

        # Group by supplier (party_name)
        grouped_records = defaultdict(list)
        for rec in records:
            supplier_key = rec.party_name or 'Unknown Supplier'
            grouped_records[supplier_key].append(rec)

        supplier_summaries = []
        for idx, (sup_name, items) in enumerate(grouped_records.items()):
            summary = {
                'id': f"sup_{idx}",
                'supplier': 'XXX' if mask_supplier_data() else sup_name,
                'party_code': items[0].party_code if items else '',
                'party_type': items[0].party_type if items else '',
                'accept_pending_pcs': sum(float(x.pending_to_accepted_pcs or 0) for x in items),
                'accept_pending_wt': sum(float(x.pending_to_accepted_wt or 0) for x in items),
                'process_pending_pcs': sum(float(x.process_pending_pcs or 0) for x in items),
                'process_pending_wt': sum(float(x.process_pending_wt or 0) for x in items),
                'barcode_pending_pcs': sum(float(x.barcode_pending_pcs or 0) for x in items),
                'barcode_pending_wt': sum(float(x.barcode_pending_wt or 0) for x in items),
                'hallmark_pending_pcs': sum(float(x.hallmark_pending_pcs or 0) for x in items),
                'hallmark_pending_wt': sum(float(x.hallmark_pending_wt or 0) for x in items),
                'qc_issue_pending_pcs': sum(float(x.qc_issue_pending_pcs or 0) for x in items),
                'qc_issue_pending_wt': sum(float(x.qc_issue_pending_wt or 0) for x in items),
                'qc_complete_pending_pcs': sum(float(x.qc_complete_pending_pcs or 0) for x in items),
                'qc_complete_pending_wt': sum(float(x.qc_complete_pending_wt or 0) for x in items),
                'invoice_pending_pcs': sum(float(x.invoice_pending_pcs or 0) for x in items),
                'invoice_pending_wt': sum(float(x.invoice_pending_wt or 0) for x in items),
                'receipt_pending_pcs': sum(float(x.receipt_pending_pcs or 0) for x in items),
                'receipt_pending_wt': sum(float(x.receipt_pending_wt or 0) for x in items),
                'total_pcs': sum(float(x.total_pending_pcs or 0) for x in items),
                'total_weight': sum(float(x.total_pending_wt or 0) for x in items),
                'details': items
            }
            supplier_summaries.append(summary)

        return render_template(
            'partials/_view_customer_order_analysis_leaf.html',
            parent_location=parent_location,
            parent_make=parent_make,
            parent_section=parent_section,
            parent_classification=parent_classification,
            supplier_summaries=supplier_summaries,
            mask_suppliers=mask_supplier_data()
        )
    except Exception as e:
        logger.error(f"Error in get_customer_order_analysis_leaf_detail: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/api/sync/customer-order-analysis', methods=['POST'])
@jwt_required(optional=True)
def trigger_sync_customer_order_analysis():
    """Trigger background sync task for Customer Order Pending Analysis report"""
    try:
        from flask_jwt_extended import current_user
        from app.utils.sync_manager import sync_customer_order_analysis_data
        user_id = getattr(current_user, 'user_id', None) if current_user else session.get('user_id')
        res = sync_customer_order_analysis_data(user_id)
        return jsonify(res)
    except Exception as e:
        logger.exception("Failed to trigger Customer Order Pending Analysis sync: %s", str(e))
        return jsonify(status="error", message=str(e)), 500
