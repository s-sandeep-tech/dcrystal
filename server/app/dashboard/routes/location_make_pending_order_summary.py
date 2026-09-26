from flask import g, render_template, request, session, jsonify
from flask_jwt_extended import jwt_required
from app.dashboard import dashboard_bp
from app.models import Notification, PendingOrderDetailsSnapshot, OwnerWiseOrderSummarySnapshot
from app.extensions import db
from sqlalchemy import String, false, func
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def mask_supplier_data():
    return 'BUSINESS_HEAD' in {str(role).strip().upper() for role in session.get('roles', [])}


def clean_group_value(column):
    return func.coalesce(func.nullif(func.trim(column), ''), 'Unknown')


def split_filter_values(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def apply_make_filter(query, make):
    makes = split_filter_values(make)
    if not makes:
        return query
    if len(makes) == 1:
        return query.filter(PendingOrderDetailsSnapshot.make == makes[0])
    return query.filter(PendingOrderDetailsSnapshot.make.in_(makes))


def get_owner_names_by_emp_code(emp_code):
    if not emp_code:
        return (), ()

    cache_key = f'pending_order_owner_names:{emp_code}'
    cached_names = getattr(g, cache_key, None)
    if cached_names is not None:
        return cached_names

    make_owner_names = []
    collection_owner_names = []
    try:
        rows = db.session.query(OwnerWiseOrderSummarySnapshot.make_owner).filter(
            func.trim(OwnerWiseOrderSummarySnapshot.make_owner_emp_code) == emp_code
        ).distinct().all()
        make_owner_names.extend([r[0] for r in rows if r[0]])

        rows2 = db.session.query(OwnerWiseOrderSummarySnapshot.collection_owner).filter(
            func.trim(OwnerWiseOrderSummarySnapshot.collection_owner_emp_code) == emp_code
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
        conditions.append(PendingOrderDetailsSnapshot.make_owner.in_(make_owner_names))
    if collection_owner_names:
        conditions.append(PendingOrderDetailsSnapshot.collection_owner.in_(collection_owner_names))

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
        return query.filter(func.trim(PendingOrderDetailsSnapshot.bh_emp_code) == emp_code)
    if 'MANAGER_KMU' in roles:
        return query.filter(PendingOrderDetailsSnapshot.make.in_([
            'KMU - KERALA', 'KMU 999 COIN', 'KMU B2B', 'KMU KARNATAKA',
            'KMU MH', 'KMU-COIN', 'KMU-TN'
        ]))
    if not session.get('user_id'):
        return query.filter(false())
    return apply_owner_visibility_filter(query)


def build_filter_query(base_query):
    business_head = request.args.get('business_head', '')
    search = request.args.get('search', '').strip()
    division = request.args.get('division', '')
    group_name = request.args.get('group', '')
    purity = request.args.get('purity', '')
    supplier = request.args.get('supplier', '')
    classification_owner = request.args.get('classification_owner', '')
    collection_owner = request.args.get('collection_owner', '')
    make_owner = request.args.get('make_owner', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    order_type = request.args.get('order_type', '')
    customer_order_type = request.args.get('customer_order_type', '')
    is_msme = request.args.get('is_msme', '') or request.args.get('is_discount_party', '')
    order_ro = request.args.get('order_ro', '')
    order_request_type = request.args.get('order_request_type', '')
    provision_type = request.args.get('provision_type', '')
    branch_provision_type = request.args.get('branch_provision_type', '')
    branch_type = request.args.get('branch_type', '')
    qc_ro = request.args.get('qc_ro', '')
    location = request.args.get('location', '')

    query = base_query
    if business_head:
        query = query.filter(PendingOrderDetailsSnapshot.business_head_name == business_head)

    if search:
        supplier_search = false() if mask_supplier_data() else PendingOrderDetailsSnapshot.supplier.ilike(f"%{search}%")
        query = query.filter(
            (PendingOrderDetailsSnapshot.location.ilike(f"%{search}%")) |
            (PendingOrderDetailsSnapshot.make.ilike(f"%{search}%")) |
            supplier_search |
            (PendingOrderDetailsSnapshot.classification.ilike(f"%{search}%")) |
            (PendingOrderDetailsSnapshot.collection.ilike(f"%{search}%")) |
            (PendingOrderDetailsSnapshot.order_ro.ilike(f"%{search}%"))
        )

    locations = split_filter_values(location)
    if locations:
        query = query.filter(PendingOrderDetailsSnapshot.location.in_(locations))
    if division:
        query = query.filter(PendingOrderDetailsSnapshot.division == division)
    if group_name:
        query = query.filter(PendingOrderDetailsSnapshot.group_name == group_name)
    if purity:
        query = query.filter(PendingOrderDetailsSnapshot.purity == purity)
    if supplier and not mask_supplier_data():
        query = query.filter(PendingOrderDetailsSnapshot.supplier == supplier)
    if classification_owner:
        query = query.filter(PendingOrderDetailsSnapshot.classification_owner == classification_owner)
    if collection_owner:
        query = query.filter(PendingOrderDetailsSnapshot.collection_owner == collection_owner)
    if make_owner:
        query = query.filter(PendingOrderDetailsSnapshot.make_owner == make_owner)
    if classification:
        query = query.filter(PendingOrderDetailsSnapshot.classification == classification)
    query = apply_make_filter(query, make)
    if collection:
        query = query.filter(PendingOrderDetailsSnapshot.collection == collection)
    order_types = split_filter_values(order_type)
    if order_types:
        query = query.filter(PendingOrderDetailsSnapshot.order_type.in_(order_types))
    if customer_order_type:
        query = query.filter(PendingOrderDetailsSnapshot.customer_order_type == customer_order_type)
    if is_msme:
        query = query.filter(PendingOrderDetailsSnapshot.is_discount_party == is_msme)
    if order_ro:
        query = query.filter(PendingOrderDetailsSnapshot.order_ro == order_ro)
    if order_request_type:
        query = query.filter(PendingOrderDetailsSnapshot.order_request_type == order_request_type)
    if provision_type:
        query = query.filter(PendingOrderDetailsSnapshot.provision_type == provision_type)
    if branch_provision_type:
        query = query.filter(PendingOrderDetailsSnapshot.branch_provision_type == branch_provision_type)
    branch_types = split_filter_values(branch_type)
    if branch_types:
        query = query.filter(PendingOrderDetailsSnapshot.branch_type.in_(branch_types))
    if qc_ro:
        query = query.filter(PendingOrderDetailsSnapshot.qc_ro == qc_ro)

    return apply_visibility_filter(query)


def get_stage_aggregate_columns():
    return [
        func.sum(PendingOrderDetailsSnapshot.accept_pending_pcs).label('accept_pcs'),
        func.sum(PendingOrderDetailsSnapshot.accept_pending_wt).label('accept_wt'),
        func.sum(PendingOrderDetailsSnapshot.process_pending_pcs).label('process_pcs'),
        func.sum(PendingOrderDetailsSnapshot.process_pending_wt).label('process_wt'),
        func.sum(PendingOrderDetailsSnapshot.barcode_pending_pcs).label('barcode_pcs'),
        func.sum(PendingOrderDetailsSnapshot.barcode_pending_wt).label('barcode_wt'),
        func.sum(PendingOrderDetailsSnapshot.hallmark_pending_pcs).label('hallmark_pcs'),
        func.sum(PendingOrderDetailsSnapshot.hallmark_pending_wt).label('hallmark_wt'),
        func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_pcs).label('qc_issue_pcs'),
        func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_wt).label('qc_issue_wt'),
        func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_pcs).label('qc_complete_pcs'),
        func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_wt).label('qc_complete_wt'),
        func.sum(PendingOrderDetailsSnapshot.invoice_pending_pcs).label('invoice_pcs'),
        func.sum(PendingOrderDetailsSnapshot.invoice_pending_wt).label('invoice_wt'),
        func.sum(PendingOrderDetailsSnapshot.total_pcs).label('tot_pcs'),
        func.sum(PendingOrderDetailsSnapshot.total_weight).label('tot_wt')
    ]


@dashboard_bp.route('/location-make-pending-order-summary')
def location_make_pending_order_summary():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        # Base query for filter options
        opts_base = apply_visibility_filter(db.session.query(PendingOrderDetailsSnapshot))

        def get_distinct_list(column):
            query = opts_base.with_entities(column).filter(column.isnot(None))
            if isinstance(column.type, String):
                query = query.filter(column != '')
            return [r[0] for r in query.distinct().order_by(column).all()]

        filter_options = {
            'business_heads': get_distinct_list(PendingOrderDetailsSnapshot.business_head_name),
            'locations': get_distinct_list(PendingOrderDetailsSnapshot.location),
            'divisions': get_distinct_list(PendingOrderDetailsSnapshot.division),
            'groups': get_distinct_list(PendingOrderDetailsSnapshot.group_name),
            'purities': [str(x) for x in get_distinct_list(PendingOrderDetailsSnapshot.purity)],
            'suppliers': [] if mask_supplier_data() else get_distinct_list(PendingOrderDetailsSnapshot.supplier),
            'classifications': get_distinct_list(PendingOrderDetailsSnapshot.classification),
            'makes': get_distinct_list(PendingOrderDetailsSnapshot.make),
            'collections': get_distinct_list(PendingOrderDetailsSnapshot.collection),
            'order_types': get_distinct_list(PendingOrderDetailsSnapshot.order_type),
            'customer_order_types': get_distinct_list(PendingOrderDetailsSnapshot.customer_order_type),
            'is_msme_options': get_distinct_list(PendingOrderDetailsSnapshot.is_discount_party),
            'order_ros': get_distinct_list(PendingOrderDetailsSnapshot.order_ro),
            'qc_ros': get_distinct_list(PendingOrderDetailsSnapshot.qc_ro),
            'order_request_types': get_distinct_list(PendingOrderDetailsSnapshot.order_request_type),
            'provision_types': get_distinct_list(PendingOrderDetailsSnapshot.provision_type),
            'branch_provision_types': get_distinct_list(PendingOrderDetailsSnapshot.branch_provision_type),
            'branch_types': get_distinct_list(PendingOrderDetailsSnapshot.branch_type),
            'classification_owners': get_distinct_list(PendingOrderDetailsSnapshot.classification_owner),
            'collection_owners': get_distinct_list(PendingOrderDetailsSnapshot.collection_owner),
            'make_owners': get_distinct_list(PendingOrderDetailsSnapshot.make_owner)
        }

        return render_template('location_make_pending_order_summary.html', unread_count=unread_count,
                               sync_time=sync_time, stats=None, rows=[], pagination=None,
                               current_level='location', filter_options=filter_options,
                               mask_suppliers=mask_supplier_data())
    except Exception as e:
        db.session.rollback()
        logger.exception('Error loading location-make report page')
        return 'Unable to load report page', 500


@dashboard_bp.route('/api/location-make-pending-order-summary/data')
@jwt_required()
def location_make_pending_order_summary_data():
    try:
        page = max(1, request.args.get('page', 1, type=int))
        per_page = min(100, max(1, request.args.get('per_page', 50, type=int)))
        # Global Top Stats Aggregation
        agg_cols = [
            func.sum(PendingOrderDetailsSnapshot.accept_pending_pcs).label('total_accept_pcs'),
            func.sum(PendingOrderDetailsSnapshot.accept_pending_wt).label('total_accept_wt'),
            func.sum(PendingOrderDetailsSnapshot.process_pending_pcs).label('total_process_pcs'),
            func.sum(PendingOrderDetailsSnapshot.process_pending_wt).label('total_process_wt'),
            func.sum(PendingOrderDetailsSnapshot.barcode_pending_pcs).label('total_barcode_pcs'),
            func.sum(PendingOrderDetailsSnapshot.barcode_pending_wt).label('total_barcode_wt'),
            func.sum(PendingOrderDetailsSnapshot.hallmark_pending_pcs).label('total_hallmark_pcs'),
            func.sum(PendingOrderDetailsSnapshot.hallmark_pending_wt).label('total_hallmark_wt'),
            func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_pcs).label('total_qc_issue_pcs'),
            func.sum(PendingOrderDetailsSnapshot.qc_issue_pending_wt).label('total_qc_issue_wt'),
            func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_pcs).label('total_qc_complete_pcs'),
            func.sum(PendingOrderDetailsSnapshot.qc_complete_pending_wt).label('total_qc_complete_wt'),
            func.sum(PendingOrderDetailsSnapshot.invoice_pending_pcs).label('total_invoice_pcs'),
            func.sum(PendingOrderDetailsSnapshot.invoice_pending_wt).label('total_invoice_wt'),
            func.sum(PendingOrderDetailsSnapshot.total_pcs).label('total_total_pcs'),
            func.sum(PendingOrderDetailsSnapshot.total_weight).label('total_total_wt')
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
            'invoice_perc': get_perc(aggs.total_invoice_wt) if aggs else 0
        }

        # Level 1 Table: Group by Location
        loc_col = clean_group_value(PendingOrderDetailsSnapshot.location).label('location')
        row_agg_cols = get_stage_aggregate_columns()

        main_q = db.session.query(loc_col, *row_agg_cols)
        main_q = build_filter_query(main_q)
        main_q = main_q.group_by(loc_col).order_by(loc_col)

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)

        processed_rows = []
        for r in pagination.items:
            processed_rows.append({
                'location': r[0] or 'Unknown',
                'make': '',
                'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                'level': 'location'
            })

        html = render_template('partials/_view_location_make_pending_order_summary.html',
                               rows=processed_rows, pagination=pagination, current_level='location', is_child=False)
        return jsonify(html=html, stats=stats, total=pagination.total, count=len(processed_rows))
    except Exception as e:
        logger.error(f"Error in location_make_pending_order_summary: {str(e)}")
        db.session.rollback()
        return jsonify(error='Unable to load report data'), 500


@dashboard_bp.route('/partial/location-make-pending-order-summary')
@jwt_required()
def get_location_make_pending_order_summary_partial():
    try:
        parent_level = request.args.get('parent_level')
        parent_value = request.args.get('parent_value')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        is_child_rows = bool(parent_level)

        loc_col = clean_group_value(PendingOrderDetailsSnapshot.location).label('location')
        make_col = clean_group_value(PendingOrderDetailsSnapshot.make).label('make')
        row_agg_cols = get_stage_aggregate_columns()

        if is_child_rows and parent_level == 'location':
            # Children: group by make under the parent location
            main_q = db.session.query(loc_col, make_col, *row_agg_cols)
            main_q = build_filter_query(main_q)
            main_q = main_q.filter(loc_col == parent_value)
            main_q = main_q.group_by(loc_col, make_col).order_by(make_col)

            items = main_q.all()
            processed_rows = []
            for r in items:
                processed_rows.append({
                    'location': r[0],
                    'make': r[1],
                    'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                    'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                    'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                    'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                    'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                    'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                    'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                    'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                    'level': 'make'
                })
            return render_template(
                'partials/_view_location_make_pending_order_summary.html',
                rows=processed_rows,
                is_child=True,
                parent_level=parent_level
            )

        # Full Level 1 pagination
        main_q = db.session.query(loc_col, *row_agg_cols)
        main_q = build_filter_query(main_q)
        main_q = main_q.group_by(loc_col).order_by(loc_col)

        pagination = main_q.paginate(page=page, per_page=per_page, error_out=False)
        processed_rows = []
        for r in pagination.items:
            processed_rows.append({
                'location': r[0] or 'Unknown',
                'make': '',
                'accept_pcs': int(r.accept_pcs or 0), 'accept_wt': float(r.accept_wt or 0),
                'process_pcs': int(r.process_pcs or 0), 'process_wt': float(r.process_wt or 0),
                'barcode_pcs': int(r.barcode_pcs or 0), 'barcode_wt': float(r.barcode_wt or 0),
                'hallmark_pcs': int(r.hallmark_pcs or 0), 'hallmark_wt': float(r.hallmark_wt or 0),
                'qc_issue_pcs': int(r.qc_issue_pcs or 0), 'qc_issue_wt': float(r.qc_issue_wt or 0),
                'qc_complete_pcs': int(r.qc_complete_pcs or 0), 'qc_complete_wt': float(r.qc_complete_wt or 0),
                'invoice_pcs': int(r.invoice_pcs or 0), 'invoice_wt': float(r.invoice_wt or 0),
                'total_pcs': int(r.tot_pcs or 0), 'total_weight': float(r.tot_wt or 0),
                'level': 'location'
            })

        return render_template(
            'partials/_view_location_make_pending_order_summary.html',
            rows=processed_rows,
            pagination=pagination,
            is_child=False
        )
    except Exception as e:
        logger.error(f"Error in get_location_make_pending_order_summary_partial: {str(e)}")
        return f"Error: {str(e)}", 500


@dashboard_bp.route('/partial/location-make-pending-order-summary/leaf_detail')
@jwt_required()
def get_location_make_pending_order_summary_leaf_detail():
    try:
        parent_location = request.args.get('parent_location', '').strip()
        parent_make = request.args.get('parent_make', '').strip()

        query = PendingOrderDetailsSnapshot.query
        loc_col = clean_group_value(PendingOrderDetailsSnapshot.location)
        make_col = clean_group_value(PendingOrderDetailsSnapshot.make)

        if parent_location:
            query = query.filter(loc_col == parent_location)
        if parent_make:
            query = query.filter(make_col == parent_make)

        query = build_filter_query(query)
        records = query.all()

        # Group by supplier
        grouped_records = defaultdict(list)
        for rec in records:
            supplier_key = rec.supplier or 'Unknown Supplier'
            grouped_records[supplier_key].append(rec)

        supplier_summaries = []
        for idx, (sup_name, items) in enumerate(grouped_records.items()):
            summary = {
                'id': f"sup_{idx}",
                'supplier': 'XXX' if mask_supplier_data() else sup_name,
                'accept_pending_pcs': sum(float(x.accept_pending_pcs or 0) for x in items),
                'accept_pending_wt': sum(float(x.accept_pending_wt or 0) for x in items),
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
                'total_pcs': sum(float(x.total_pcs or 0) for x in items),
                'total_weight': sum(float(x.total_weight or 0) for x in items),
                'details': items
            }
            supplier_summaries.append(summary)

        return render_template(
            'partials/_view_location_make_pending_order_summary_leaf.html',
            parent_location=parent_location,
            parent_make=parent_make,
            supplier_summaries=supplier_summaries
        )
    except Exception as e:
        logger.error(f"Error in get_location_make_pending_order_summary_leaf_detail: {str(e)}")
        return f"Error: {str(e)}", 500
