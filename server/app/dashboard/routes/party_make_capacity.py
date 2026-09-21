import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import render_template, request, jsonify, session, send_file, abort, current_app
from sqlalchemy import func, case, and_, or_

from app.dashboard import dashboard_bp
from app.utils.decorators import require_report_access
from app.extensions import db
from app.models import Notification, ExportDownloadLog
from app.models.snapshots import PartyMakeCapacityDetailsSnapshot

logger = logging.getLogger(__name__)

# Exports directory configuration
if os.path.isdir('/app/uploads'):
    EXPORTS_DIR = '/app/uploads/exports'
else:
    EXPORTS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'uploads',
        'exports'
    )

def ensure_exports_dir():
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def split_filter_values(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(',') if v.strip()]


def determine_primary_bottleneck(process_wt, barcode_wt, hallmark_wt, qc_issue_wt, qc_complete_wt, invoice_wt):
    stages = [
        ('PROCESS', float(process_wt or 0)),
        ('BARCODE', float(barcode_wt or 0)),
        ('HALLMARK', float(hallmark_wt or 0)),
        ('QC ISSUE', float(qc_issue_wt or 0)),
        ('QC COMPLETE', float(qc_complete_wt or 0)),
        ('INVOICE', float(invoice_wt or 0))
    ]
    max_stage, max_wt = max(stages, key=lambda s: s[1])
    if max_wt <= 0:
        return 'NONE'
    return max_stage


def apply_capacity_filters(query):
    vendor_type = request.args.get('vendor_type', '').strip().lower()
    if vendor_type == 'discount':
        query = query.filter(PartyMakeCapacityDetailsSnapshot.party_capacity_kg != 0)
    elif vendor_type == 'non_discount':
        query = query.filter(PartyMakeCapacityDetailsSnapshot.party_capacity_kg == 0)
    search = request.args.get('search', '').strip()
    order_ro = request.args.get('order_ro', '')
    location = request.args.get('location', '')
    provision_type = request.args.get('provision_type', '')
    branch_type = request.args.get('branch_type', '')
    is_msme = request.args.get('is_msme', '')
    division = request.args.get('division', '')
    group_name = request.args.get('group', '')
    purity = request.args.get('purity', '')
    classification = request.args.get('classification', '')
    make = request.args.get('make', '')
    collection = request.args.get('collection', '')
    order_type = request.args.get('order_type', '')
    order_request_type = request.args.get('order_request_type', '')
    party = request.args.get('party', '') or request.args.get('supplier', '')

    if search:
        query = query.filter(
            or_(
                PartyMakeCapacityDetailsSnapshot.supplier.ilike(f"%{search}%"),
                PartyMakeCapacityDetailsSnapshot.make.ilike(f"%{search}%")
            )
        )

    parties = split_filter_values(party)
    if parties:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.supplier.in_(parties))

    makes = split_filter_values(make)
    if makes:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.make.in_(makes))

    order_ros = split_filter_values(order_ro)
    if order_ros:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.order_ro.in_(order_ros))

    locations = split_filter_values(location)
    if locations:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.location.in_(locations))

    provision_types = split_filter_values(provision_type)
    if provision_types:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.provision_type.in_(provision_types))

    branch_types = split_filter_values(branch_type)
    if branch_types:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.branch_type.in_(branch_types))

    if is_msme and is_msme.lower() in ['true', '1', 'yes']:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.is_msme == True)
    elif is_msme and is_msme.lower() in ['false', '0', 'no']:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.is_msme == False)

    divisions = split_filter_values(division)
    if divisions:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.division.in_(divisions))

    groups = split_filter_values(group_name)
    if groups:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.group_name.in_(groups))

    purities = split_filter_values(purity)
    if purities:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.purity.in_(purities))

    classifications = split_filter_values(classification)
    if classifications:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.classification.in_(classifications))

    collections = split_filter_values(collection)
    if collections:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.collection.in_(collections))

    order_types = split_filter_values(order_type)
    if order_types:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.order_type.in_(order_types))

    order_request_types = split_filter_values(order_request_type)
    if order_request_types:
        query = query.filter(PartyMakeCapacityDetailsSnapshot.order_request_type.in_(order_request_types))

    return query


def fetch_all_filter_options():
    try:
        def get_distinct(column):
            rows = db.session.query(column).distinct().order_by(column).all()
            return [str(r[0]).strip() for r in rows if r[0] is not None and str(r[0]).strip()]

        return {
            'parties': get_distinct(PartyMakeCapacityDetailsSnapshot.supplier),
            'makes': get_distinct(PartyMakeCapacityDetailsSnapshot.make),
            'order_ros': get_distinct(PartyMakeCapacityDetailsSnapshot.order_ro),
            'locations': get_distinct(PartyMakeCapacityDetailsSnapshot.location),
            'provision_types': get_distinct(PartyMakeCapacityDetailsSnapshot.provision_type),
            'branch_types': get_distinct(PartyMakeCapacityDetailsSnapshot.branch_type),
            'divisions': get_distinct(PartyMakeCapacityDetailsSnapshot.division),
            'groups': get_distinct(PartyMakeCapacityDetailsSnapshot.group_name),
            'purities': get_distinct(PartyMakeCapacityDetailsSnapshot.purity),
            'classifications': get_distinct(PartyMakeCapacityDetailsSnapshot.classification),
            'collections': get_distinct(PartyMakeCapacityDetailsSnapshot.collection),
            'order_types': get_distinct(PartyMakeCapacityDetailsSnapshot.order_type),
            'order_request_types': get_distinct(PartyMakeCapacityDetailsSnapshot.order_request_type),
        }
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        return {
            'parties': [], 'makes': [], 'order_ros': [], 'locations': [],
            'provision_types': [], 'branch_types': [], 'divisions': [],
            'groups': [], 'purities': [], 'classifications': [],
            'collections': [], 'order_types': [], 'order_request_types': []
        }


@dashboard_bp.route('/party-make-capacity-report')
@require_report_access('/party-make-capacity-report')
def party_make_capacity_report():
    try:
        unread_count = 0
        try:
            unread_count = Notification.query.filter_by(is_read=False).count()
        except Exception:
            pass
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        filter_options = fetch_all_filter_options()

        return render_template(
            'party_make_capacity.html',
            unread_count=unread_count,
            sync_time=sync_time,
            filter_options=filter_options
        )
    except Exception as e:
        logger.error(f"Error loading party_make_capacity_report: {e}")
        return f"Error loading report: {str(e)}", 500


@dashboard_bp.route('/api/party-make-capacity/filter-options')
@require_report_access('/party-make-capacity-report')
def api_party_make_capacity_filter_options():
    return jsonify(fetch_all_filter_options())


def get_aggregated_capacity_data():
    """
    Core calculation function:
    1. Aggregates data by (supplier, make)
    2. Computes make-level metrics (WIP total, diff, utilization, bottleneck, etc.)
    3. Rolls up into supplier-level parent rows
    4. Applies status filter and pagination
    """
    urgent_expr = case(
        (func.lower(PartyMakeCapacityDetailsSnapshot.order_request_type).like('%urgent%'), PartyMakeCapacityDetailsSnapshot.total_wt),
        else_=0
    )

    agg_query = db.session.query(
        PartyMakeCapacityDetailsSnapshot.supplier.label('supplier'),
        PartyMakeCapacityDetailsSnapshot.make.label('make'),
        func.max(PartyMakeCapacityDetailsSnapshot.party_capacity_kg).label('party_capacity_kg'),
        func.max(PartyMakeCapacityDetailsSnapshot.actual_capacity_kg).label('actual_capacity_kg'),
        func.sum(PartyMakeCapacityDetailsSnapshot.process_pending_pcs).label('process_pending_pcs'),
        func.sum(PartyMakeCapacityDetailsSnapshot.process_pending_wt).label('process_pending_wt'),
        func.sum(PartyMakeCapacityDetailsSnapshot.barcode_pending_pcs).label('barcode_pending_pcs'),
        func.sum(PartyMakeCapacityDetailsSnapshot.barcode_pending_wt).label('barcode_pending_wt'),
        func.sum(PartyMakeCapacityDetailsSnapshot.hallmark_pending_pcs).label('hallmark_pending_pcs'),
        func.sum(PartyMakeCapacityDetailsSnapshot.hallmark_pending_wt).label('hallmark_pending_wt'),
        func.sum(PartyMakeCapacityDetailsSnapshot.qc_issue_pending_pcs).label('qc_issue_pending_pcs'),
        func.sum(PartyMakeCapacityDetailsSnapshot.qc_issue_pending_wt).label('qc_issue_pending_wt'),
        func.sum(PartyMakeCapacityDetailsSnapshot.correction_wt).label('correction_wt'),
        func.sum(PartyMakeCapacityDetailsSnapshot.qc_complete_pending_pcs).label('qc_complete_pending_pcs'),
        func.sum(PartyMakeCapacityDetailsSnapshot.qc_complete_pending_wt).label('qc_complete_pending_wt'),
        func.sum(PartyMakeCapacityDetailsSnapshot.invoice_pending_pcs).label('invoice_pending_pcs'),
        func.sum(PartyMakeCapacityDetailsSnapshot.invoice_pending_wt).label('invoice_pending_wt'),
        func.sum(PartyMakeCapacityDetailsSnapshot.receipt_pending_pcs).label('receipt_pending_pcs'),
        func.sum(PartyMakeCapacityDetailsSnapshot.receipt_pending_wt).label('receipt_pending_wt'),
        func.sum(PartyMakeCapacityDetailsSnapshot.total_pcs).label('total_pcs'),
        func.sum(PartyMakeCapacityDetailsSnapshot.total_wt).label('total_wt'),
        func.count(func.distinct(PartyMakeCapacityDetailsSnapshot.order_ro)).label('ro_count'),
        func.sum(urgent_expr).label('urgent_wt'),
        func.bool_or(PartyMakeCapacityDetailsSnapshot.is_msme).label('is_msme'),
        func.min(case(
            (PartyMakeCapacityDetailsSnapshot.is_orders.is_(False), 1), else_=0
        )).label('all_no_orders')
    )

    agg_query = apply_capacity_filters(agg_query)
    agg_query = agg_query.group_by(
        PartyMakeCapacityDetailsSnapshot.supplier,
        PartyMakeCapacityDetailsSnapshot.make
    ).order_by(
        PartyMakeCapacityDetailsSnapshot.supplier,
        PartyMakeCapacityDetailsSnapshot.make
    )

    rows = agg_query.all()

    # Process make-level rows and group under supplier
    suppliers_dict = {}

    for r in rows:
        sup_name = r.supplier or 'Unknown Supplier'
        make_name = r.make or 'Unknown Make'

        make_cap = float(r.party_capacity_kg or 0.0)
        proc_wt = float(r.process_pending_wt or 0.0)
        barc_wt = float(r.barcode_pending_wt or 0.0)
        hm_wt = float(r.hallmark_pending_wt or 0.0)
        qc_iss_wt = float(r.qc_issue_pending_wt or 0.0)
        correction_wt = float(r.correction_wt or 0.0)
        qc_comp_wt = float(r.qc_complete_pending_wt or 0.0)
        inv_wt = float(r.invoice_pending_wt or 0.0)
        rcpt_wt = float(r.receipt_pending_wt or 0.0)
        tot_pcs = int(r.total_pcs or 0)
        urg_wt = float(r.urgent_wt or 0.0)
        stage_sum = proc_wt + barc_wt + hm_wt + qc_iss_wt + qc_comp_wt + inv_wt
        tot_wt = float(r.total_wt) if (r.total_wt is not None and float(r.total_wt) > 0) else stage_sum
        tot_wt_kg = round(tot_wt / 1000.0, 4)

        diff = round(make_cap - tot_wt_kg, 4)
        util_pct = round((tot_wt_kg / make_cap * 100), 1) if make_cap > 0 else 0.0
        bottleneck = determine_primary_bottleneck(proc_wt, barc_wt, hm_wt, qc_iss_wt, qc_comp_wt, inv_wt)
        qc_rework_pct = round((correction_wt / tot_wt * 100), 1) if tot_wt > 0 else 0.0
        avg_piece_wt = round((tot_wt / tot_pcs), 2) if tot_pcs > 0 else 0.0
        urg_pct = round((urg_wt / tot_wt * 100), 1) if tot_wt > 0 else 0.0

        make_data = {
            'is_orders': not bool(r.all_no_orders),
            'make': make_name,
            'supplier': sup_name,
            'actual_capacity': float(r.actual_capacity_kg) if r.actual_capacity_kg is not None else None,
            'capacity_wt_kg_per_month': make_cap,
            'process_pending_pcs': int(r.process_pending_pcs or 0),
            'process_pending_wt': round(proc_wt, 3),
            'barcode_pending_pcs': int(r.barcode_pending_pcs or 0),
            'barcode_pending_wt': round(barc_wt, 3),
            'hallmark_pending_pcs': int(r.hallmark_pending_pcs or 0),
            'hallmark_pending_wt': round(hm_wt, 3),
            'qc_issue_pending_pcs': int(r.qc_issue_pending_pcs or 0),
            'qc_issue_pending_wt': round(qc_iss_wt, 3),
            'qc_complete_pending_pcs': int(r.qc_complete_pending_pcs or 0),
            'qc_complete_pending_wt': round(qc_comp_wt, 3),
            'invoice_pending_pcs': int(r.invoice_pending_pcs or 0),
            'invoice_pending_wt': round(inv_wt, 3),
            'receipt_pending_pcs': int(r.receipt_pending_pcs or 0),
            'receipt_pending_wt': round(rcpt_wt, 3),
            'receipt_pending_wt_kg': round(rcpt_wt / 1000.0, 4),
            'total_pcs': tot_pcs,
            'total_wt': round(tot_wt, 3),
            'total_wt_in_kg': tot_wt_kg,
            'diff': diff,
            'utilization_pct': util_pct,
            'primary_bottleneck': bottleneck,
            'qc_rework_pct': qc_rework_pct,
            'correction_wt': correction_wt,
            'avg_piece_wt': avg_piece_wt,
            'urgent_order_pct': urg_pct,
            'ro_count': int(r.ro_count or 0),
            'is_msme': bool(r.is_msme)
        }

        if sup_name not in suppliers_dict:
            suppliers_dict[sup_name] = {
                'is_orders': False,
                'supplier': sup_name,
                'actual_capacity': None,
                'capacity_wt_kg_per_month': 0.0,
                'process_pending_pcs': 0,
                'process_pending_wt': 0.0,
                'barcode_pending_pcs': 0,
                'barcode_pending_wt': 0.0,
                'hallmark_pending_pcs': 0,
                'hallmark_pending_wt': 0.0,
                'qc_issue_pending_pcs': 0,
                'qc_issue_pending_wt': 0.0,
                'qc_complete_pending_pcs': 0,
                'qc_complete_pending_wt': 0.0,
                'invoice_pending_pcs': 0,
                'invoice_pending_wt': 0.0,
                'receipt_pending_pcs': 0,
                'receipt_pending_wt': 0.0,
                'receipt_pending_wt_kg': 0.0,
                'total_pcs': 0,
                'total_wt': 0.0,
                'total_wt_in_kg': 0.0,
                'diff': 0.0,
                'utilization_pct': 0.0,
                'primary_bottleneck': 'NONE',
                'qc_rework_pct': 0.0,
                'correction_wt': 0.0,
                'avg_piece_wt': 0.0,
                'urgent_order_pct': 0.0,
                'ro_count': 0,
                'is_msme': False,
                'makes': []
            }

        sup = suppliers_dict[sup_name]
        # Capacity repeats across detail records: max per make, then sum makes.
        if make_data['actual_capacity'] is not None:
            sup['actual_capacity'] = (sup['actual_capacity'] or 0.0) + make_data['actual_capacity']
        sup['is_orders'] = sup['is_orders'] or make_data['is_orders']
        sup['capacity_wt_kg_per_month'] += make_cap
        sup['process_pending_pcs'] += make_data['process_pending_pcs']
        sup['process_pending_wt'] += make_data['process_pending_wt']
        sup['barcode_pending_pcs'] += make_data['barcode_pending_pcs']
        sup['barcode_pending_wt'] += make_data['barcode_pending_wt']
        sup['hallmark_pending_pcs'] += make_data['hallmark_pending_pcs']
        sup['hallmark_pending_wt'] += make_data['hallmark_pending_wt']
        sup['qc_issue_pending_pcs'] += make_data['qc_issue_pending_pcs']
        sup['qc_issue_pending_wt'] += make_data['qc_issue_pending_wt']
        sup['correction_wt'] += make_data['correction_wt']
        sup['qc_complete_pending_pcs'] += make_data['qc_complete_pending_pcs']
        sup['qc_complete_pending_wt'] += make_data['qc_complete_pending_wt']
        sup['invoice_pending_pcs'] += make_data['invoice_pending_pcs']
        sup['invoice_pending_wt'] += make_data['invoice_pending_wt']
        sup['receipt_pending_pcs'] += make_data['receipt_pending_pcs']
        sup['receipt_pending_wt'] += make_data['receipt_pending_wt']
        sup['total_pcs'] += make_data['total_pcs']
        sup['total_wt'] += make_data['total_wt']
        sup['ro_count'] = max(sup['ro_count'], make_data['ro_count'])
        if make_data['is_msme']:
            sup['is_msme'] = True
        sup['makes'].append(make_data)

    # Rollup calculations for supplier parent rows
    suppliers_list = []
    global_kpis = {
        'total_capacity_kg': 0.0,
        'total_wip_wt': 0.0,
        'total_wip_kg': 0.0,
        'net_diff_kg': 0.0,
        'overall_utilization_pct': 0.0,
        'over_capacity_count': 0,
        'under_capacity_count': 0,
        'severe_overload_count': 0,
        'total_transit_kg': 0.0,
        'total_qc_rework_kg': 0.0,
        'total_suppliers_count': len(suppliers_dict)
    }

    for sup_name, sup in suppliers_dict.items():
        sup['capacity_wt_kg_per_month'] = round(sup['capacity_wt_kg_per_month'], 4)
        sup['total_wt'] = round(sup['total_wt'], 3)
        sup['total_wt_in_kg'] = round(sup['total_wt'] / 1000.0, 4)
        sup['diff'] = round(sup['capacity_wt_kg_per_month'] - sup['total_wt_in_kg'], 4)
        sup['utilization_pct'] = round((sup['total_wt_in_kg'] / sup['capacity_wt_kg_per_month'] * 100), 1) if sup['capacity_wt_kg_per_month'] > 0 else 0.0
        sup['receipt_pending_wt_kg'] = round(sup['receipt_pending_wt'] / 1000.0, 4)
        sup['primary_bottleneck'] = determine_primary_bottleneck(
            sup['process_pending_wt'], sup['barcode_pending_wt'], sup['hallmark_pending_wt'],
            sup['qc_issue_pending_wt'], sup['qc_complete_pending_wt'], sup['invoice_pending_wt']
        )
        sup['qc_rework_pct'] = round((sup['correction_wt'] / sup['total_wt'] * 100), 1) if sup['total_wt'] > 0 else 0.0
        sup['avg_piece_wt'] = round((sup['total_wt'] / sup['total_pcs']), 2) if sup['total_pcs'] > 0 else 0.0

        # Global stats accumulation
        global_kpis['total_capacity_kg'] += sup['capacity_wt_kg_per_month']
        global_kpis['total_wip_wt'] += sup['total_wt']
        global_kpis['total_wip_kg'] += sup['total_wt_in_kg']
        global_kpis['total_transit_kg'] += sup['receipt_pending_wt_kg']
        global_kpis['total_qc_rework_kg'] += (sup['correction_wt'] / 1000.0)

        if sup['diff'] < 0:
            global_kpis['over_capacity_count'] += 1
        else:
            global_kpis['under_capacity_count'] += 1

        if sup['utilization_pct'] > 120:
            global_kpis['severe_overload_count'] += 1

        suppliers_list.append(sup)

    global_kpis['total_capacity_kg'] = round(global_kpis['total_capacity_kg'], 3)
    global_kpis['total_wip_kg'] = round(global_kpis['total_wip_kg'], 3)
    global_kpis['net_diff_kg'] = round(global_kpis['total_capacity_kg'] - global_kpis['total_wip_kg'], 3)
    global_kpis['overall_utilization_pct'] = round((global_kpis['total_wip_kg'] / global_kpis['total_capacity_kg'] * 100), 1) if global_kpis['total_capacity_kg'] > 0 else 0.0
    global_kpis['total_transit_kg'] = round(global_kpis['total_transit_kg'], 3)
    global_kpis['total_qc_rework_kg'] = round(global_kpis['total_qc_rework_kg'], 3)

    # Apply status filter
    status = request.args.get('status', 'all').strip().lower()
    if status == 'over_capacity':
        suppliers_list = [s for s in suppliers_list if s['diff'] < 0]
    elif status == 'under_capacity':
        suppliers_list = [s for s in suppliers_list if s['diff'] >= 0]
    elif status == 'severe_overload':
        suppliers_list = [s for s in suppliers_list if s['utilization_pct'] > 120]

    # Sorting
    sort_by = request.args.get('sort_by', 'supplier').strip().lower()
    sort_order = request.args.get('sort_order', 'asc').strip().lower()
    reverse = (sort_order == 'desc')

    if sort_by in ['actual_capacity', 'capacity_wt_kg_per_month', 'total_wt', 'total_wt_in_kg', 'diff', 'utilization_pct', 'qc_rework_pct', 'receipt_pending_wt_kg']:
        suppliers_list.sort(key=lambda s: s.get(sort_by, 0.0) or 0.0, reverse=reverse)
    else:
        suppliers_list.sort(key=lambda s: str(s.get('supplier', '')).upper(), reverse=reverse)

    # Stable partition keeps the selected sort within each order-status group.
    suppliers_list.sort(key=lambda s: s['is_orders'] is False)
    for sup in suppliers_list:
        sup['makes'].sort(key=lambda m: m['is_orders'] is False)

    return suppliers_list, global_kpis


@dashboard_bp.route('/api/party-make-capacity/data')
@require_report_access('/party-make-capacity-report')
def api_party_make_capacity_data():
    try:
        suppliers_list, global_kpis = get_aggregated_capacity_data()

        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        total_records = len(suppliers_list)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_suppliers = suppliers_list[start_idx:end_idx]

        total_pages = (total_records + per_page - 1) // per_page if per_page > 0 else 1

        return jsonify({
            'status': 'success',
            'data': paginated_suppliers,
            'kpis': global_kpis,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_records': total_records,
                'total_pages': total_pages
            }
        })
    except Exception as e:
        logger.error(f"Error in api_party_make_capacity_data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@dashboard_bp.route('/api/party-make-capacity/drilldown')
@require_report_access('/party-make-capacity-report')
def api_party_make_capacity_drilldown():
    try:
        supplier = request.args.get('supplier', '').strip()
        make = request.args.get('make', '').strip()

        if not supplier:
            return jsonify({'status': 'error', 'message': 'Supplier is required'}), 400

        query = db.session.query(PartyMakeCapacityDetailsSnapshot).filter(
            PartyMakeCapacityDetailsSnapshot.supplier == supplier
        )
        if make:
            query = query.filter(PartyMakeCapacityDetailsSnapshot.make == make)

        query = apply_capacity_filters(query)
        page = max(1, request.args.get('page', 1, type=int))
        per_page = 50
        total = query.count()
        orders = query.order_by(
            case((PartyMakeCapacityDetailsSnapshot.is_orders.is_(False), 1), else_=0),
            PartyMakeCapacityDetailsSnapshot.location,
            PartyMakeCapacityDetailsSnapshot.id
        ).offset((page - 1) * per_page).limit(per_page).all()

        results = []
        for o in orders:
            stage_sum = (float(o.process_pending_wt or 0) + float(o.barcode_pending_wt or 0) +
                         float(o.hallmark_pending_wt or 0) + float(o.qc_issue_pending_wt or 0) +
                         float(o.qc_complete_pending_wt or 0) + float(o.invoice_pending_wt or 0))
            tot_wt = float(o.total_wt) if (o.total_wt is not None and float(o.total_wt) > 0) else stage_sum
            results.append({
                'is_orders': o.is_orders,
                'order_ro': o.order_ro or '',
                'location': o.location or '',
                'division': o.division or '',
                'group': o.group_name or '',
                'purity': o.purity or '',
                'classification': o.classification or '',
                'collection': o.collection or '',
                'order_type': o.order_type or '',
                'order_request_type': o.order_request_type or '',
                'process_pending_wt': float(o.process_pending_wt or 0),
                'barcode_pending_wt': float(o.barcode_pending_wt or 0),
                'hallmark_pending_wt': float(o.hallmark_pending_wt or 0),
                'qc_issue_pending_wt': float(o.qc_issue_pending_wt or 0),
                'qc_complete_pending_wt': float(o.qc_complete_pending_wt or 0),
                'invoice_pending_wt': float(o.invoice_pending_wt or 0),
                'receipt_pending_wt': float(o.receipt_pending_wt or 0),
                'total_pcs': int(o.total_pcs or 0),
                'total_wt': round(tot_wt, 3)
            })

        return jsonify({'status': 'success', 'data': results, 'count': len(results), 'total': total,
                        'page': page, 'pages': max(1, (total + per_page - 1) // per_page)})
    except Exception as e:
        logger.error(f"Error in api_party_make_capacity_drilldown: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@dashboard_bp.route('/api/party-make-capacity/export')
@require_report_access('/party-make-capacity-report')
def api_party_make_capacity_export():
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        ensure_exports_dir()
        suppliers_list, global_kpis = get_aggregated_capacity_data()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Supplier Capacity & Backlog"

        # Styling definitions matching reference sheet
        peach_fill = PatternFill(start_color="FCE5CD", end_color="FCE5CD", fill_type="solid")
        blue_header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        parent_fill = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")
        border_thin = Side(border_style="thin", color="D9D9D9")
        cell_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

        header_font = Font(name="Calibri", size=10, bold=True, color="000000")
        parent_font = Font(name="Calibri", size=10, bold=True, color="1F2937")
        child_font = Font(name="Calibri", size=9, color="374151")
        green_font = Font(name="Calibri", size=9, bold=True, color="047857")
        red_font = Font(name="Calibri", size=9, bold=True, color="DC2626")

        headers = [
            "supplier", "make", "Act. Capacity (kg)", "Capacity (kg)", "Total Pending (kg)", "Balance (kg)",
            "utilization_pct", "primary_bottleneck", "qc_rework_pct",
            "process_pending_wt", "barcode_pending_wt", "hallmark_pending_wt",
            "qc_issue_pending_wt", "qc_complete_pending_wt", "invoice_pending_wt",
            "total_wt", "receipt_pending_wt", "ro_count"
        ]

        ws.append(headers)
        header_row = ws[1]
        for col_num, cell in enumerate(header_row, 1):
            cell.font = header_font
            cell.border = cell_border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if col_num in (3, 4): # Capacity columns
                cell.fill = peach_fill
            else:
                cell.fill = blue_header_fill

        row_num = 2
        for sup in suppliers_list:
            # Supplier Parent Row
            sup_row = [
                sup['supplier'],
                f"ALL MAKES ({len(sup['makes'])})",
                sup['actual_capacity'],
                sup['capacity_wt_kg_per_month'],
                sup['total_wt_in_kg'],
                sup['diff'],
                f"{sup['utilization_pct']}%",
                sup['primary_bottleneck'],
                f"{sup['qc_rework_pct']}%",
                sup['process_pending_wt'],
                sup['barcode_pending_wt'],
                sup['hallmark_pending_wt'],
                sup['qc_issue_pending_wt'],
                sup['qc_complete_pending_wt'],
                sup['invoice_pending_wt'],
                sup['total_wt'],
                sup['receipt_pending_wt'],
                sup['ro_count']
            ]
            ws.append(sup_row)
            for cell in ws[row_num]:
                cell.fill = parent_fill
                cell.font = parent_font
                cell.border = cell_border
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "#,##0.000" if isinstance(cell.value, float) else "#,##0"
            row_num += 1

            # Make Child Rows
            for m in sup['makes']:
                make_row = [
                    f"  ↳ {sup['supplier']}",
                    m['make'],
                    m['actual_capacity'],
                    m['capacity_wt_kg_per_month'],
                    m['total_wt_in_kg'],
                    m['diff'],
                    f"{m['utilization_pct']}%",
                    m['primary_bottleneck'],
                    f"{m['qc_rework_pct']}%",
                    m['process_pending_wt'],
                    m['barcode_pending_wt'],
                    m['hallmark_pending_wt'],
                    m['qc_issue_pending_wt'],
                    m['qc_complete_pending_wt'],
                    m['invoice_pending_wt'],
                    m['total_wt'],
                    m['receipt_pending_wt'],
                    m['ro_count']
                ]
                ws.append(make_row)
                for col_idx, cell in enumerate(ws[row_num], 1):
                    cell.font = child_font
                    cell.border = cell_border
                    if col_idx == 6: # Balance column
                        cell.font = red_font if m['diff'] < 0 else green_font
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = "#,##0.000" if isinstance(cell.value, float) else "#,##0"
                row_num += 1

        # Adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"supplier_capacity_backlog_analysis_{timestamp}.xlsx"
        filepath = os.path.join(EXPORTS_DIR, filename)
        wb.save(filepath)

        # Log export
        try:
            log_entry = ExportDownloadLog(
                filename=filename,
                username=session.get('username'),
                user_id=session.get('user_id'),
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
                downloaded_at=datetime.utcnow()
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to log export: {e}")

        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error in export: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@dashboard_bp.route('/api/sync/party-make-capacity-report', methods=['POST'])
@dashboard_bp.route('/api/sync/party-make-capacity', methods=['POST'])
@dashboard_bp.route('/sync/party-make-capacity-report', methods=['POST'])
@dashboard_bp.route('/party-make-capacity-report/sync', methods=['POST'])
@require_report_access('/party-make-capacity-report')
def sync_party_make_capacity_report():
    """
    Sync endpoint for Party Make Capacity Report (/party-make-capacity-report).
    Actual sync logic is commented out; returns a  message after sleep.
    """
    # Actual sync logic:
    # from app.utils.sync_manager import sync_party_make_capacity_details_data
    # user_id = session.get('user_id')
    # return jsonify(sync_party_make_capacity_details_data(user_id))

    time.sleep(3)
    return jsonify({
        'status': 'success',
        'message': 'Party Make Capacity Report sync completed successfully',
        'count': 0
    }), 200
