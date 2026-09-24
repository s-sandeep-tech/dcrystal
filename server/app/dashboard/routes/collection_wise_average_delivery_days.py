from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models import Notification, CollectionWiseAverageDeliveryDaysSnapshot
from app.extensions import db
from app.utils.decorators import require_perm, require_report_access, require_role
from sqlalchemy import and_, or_, case, func, distinct, false
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

KMU_MAKES = (
    'KMU - KERALA',
    'KMU 999 COIN',
    'KMU B2B',
    'KMU KARNATAKA',
    'KMU MH',
    'KMU-COIN',
    'KMU-TN',
)

def split_filter_values(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def date_to_iso(value):
    return value.isoformat() if value else None


def build_process_timeline(record):
    stages = [
        ('Order Placed', record.ordered_date),
        ('HM Issued', record.hm_issue_date),
        ('HM Received', record.hm_receipt_date),
        ('QC Issued', record.qc_issue_date),
        ('QC Received', record.qc_receipt_date),
        ('Crystal Invoice', record.crystal_invoice_date),
        ('Office Receipt', record.morr_received_date),
        ('Muziris In-Shop', record.muziris_inshop_received_date),
    ]
    start_date = stages[0][1]

    # Find indices of stages that have actual dates
    completed_indices = [i for i, (label, dt) in enumerate(stages) if dt is not None]

    # Build stage duration breakdown between consecutive completed stages
    stage_durations = []
    for idx in range(len(completed_indices) - 1):
        curr_i = completed_indices[idx]
        next_i = completed_indices[idx + 1]
        from_label, from_date = stages[curr_i]
        to_label, to_date = stages[next_i]
        dur = max((to_date - from_date).days, 0)
        stage_durations.append({
            'from_stage': from_label,
            'to_stage': to_label,
            'start_date': date_to_iso(from_date),
            'end_date': date_to_iso(to_date),
            'duration_days': dur,
        })

    timeline = []
    for index, (label, stage_date) in enumerate(stages):
        # Find the next completed stage after this index (if any)
        next_completed = next((stages[j] for j in range(index + 1, len(stages)) if stages[j][1] is not None), None)
        later_completed_exists = any(stages[j][1] is not None for j in range(index + 1, len(stages)))

        days_to_next = None
        cumulative_days = None
        status = 'pending'

        if stage_date is not None:
            status = 'completed'
            if next_completed and next_completed[1]:
                days_to_next = max((next_completed[1] - stage_date).days, 0)
            if start_date:
                cumulative_days = max((stage_date - start_date).days, 0)
        else:
            if later_completed_exists:
                status = 'skipped'
            else:
                status = 'pending'

        timeline.append({
            'label': label,
            'date': date_to_iso(stage_date),
            'days_to_next': days_to_next,
            'next_stage_label': next_completed[0] if next_completed else None,
            'cumulative_days': cumulative_days,
            'completed': status == 'completed',
            'status': status,
        })

    return timeline, stage_durations


def compute_barcode_bayesian_stage_risk(record, delivery_target_days, tat_days):
    """
    Computes Bayesian predictive risk for a single barcode order in Collection Timeline:
    - If Workshop delivery is pending (morr_received_date IS NULL):
        Calculates posterior probability of exceeding delivery_target_days based on elapsed days and current stage.
    - If Workshop delivery is completed but Muziris In-Shop is pending:
        Calculates office-to-shop transit delay risk.
    - If fully completed:
        Returns completed performance confirmation.
    """
    now_date = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    target_days = float(delivery_target_days) if delivery_target_days is not None else 15.0

    # 1. Fully completed
    if record.morr_received_date is not None and record.muziris_inshop_received_date is not None:
        variance = (record.morr_received_date - record.ordered_date).days - target_days if record.ordered_date else 0
        return {
            'state': 'completed',
            'state_label': 'Fulfilled',
            'predicted_tat_days': tat_days,
            'breach_risk_pct': 0.0,
            'risk_level': 'Delivered On-Time' if variance <= 0 else 'Delivered with Delay',
            'risk_class': 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-800/40' if variance <= 0 else 'text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800/40',
            'risk_note': f"Delivered to Muziris in-shop on {record.muziris_inshop_received_date.strftime('%d-%b-%Y')}. Total Party to Office TAT: {tat_days} days.",
            'active_stage': 'Muziris In-Shop (Completed)',
            'days_in_stage': 0,
            'confidence': 'Actual Audited',
        }

    # 2. Workshop delivery pending (at HM, QC, etc.)
    if record.morr_received_date is None:
        ordered_date = record.ordered_date or now_date
        elapsed_days = max((now_date - ordered_date).days, 0)

        stage_checkpoints = [
            (record.crystal_invoice_date, 'Crystal Invoice', 0.85),
            (record.qc_receipt_date, 'QC Received', 0.75),
            (record.qc_issue_date, 'QC Issued', 0.60),
            (record.hm_receipt_date, 'HM Received', 0.50),
            (record.hm_issue_date, 'HM Issued', 0.30),
            (record.ordered_date, 'Order Placed', 0.10),
        ]

        active_stage = 'Order Placed'
        stage_progress = 0.10
        last_date = ordered_date
        for dt, name, prog in stage_checkpoints:
            if dt is not None:
                active_stage = name
                stage_progress = prog
                last_date = dt
                break

        days_in_stage = max((now_date - last_date).days, 0)
        expected_remaining = max(round(target_days * (1.0 - stage_progress), 1), 2.0)
        predicted_tat = round(elapsed_days + expected_remaining, 1)

        remaining_budget = target_days - elapsed_days
        if remaining_budget <= 0:
            breach_risk_pct = min(round(90.0 + min(abs(remaining_budget) * 2.0, 9.9), 1), 99.9)
            risk_level = 'SLA Overdue'
            risk_class = 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800/40'
            risk_note = f"Overdue by {int(abs(remaining_budget))} days. Current stage: {active_stage} ({days_in_stage}d in stage)"
        else:
            buffer_ratio = (remaining_budget - expected_remaining) / max(target_days * 0.35, 2.5)
            prob = 1.0 / (1.0 + (2.71828 ** (buffer_ratio * 1.8)))
            breach_risk_pct = min(max(round(prob * 100.0, 1), 2.0), 95.0)

            if breach_risk_pct >= 70.0:
                risk_level = 'High Breach Risk'
                risk_class = 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800/40'
                risk_note = f"Only {int(remaining_budget)}d remaining to SLA. Stage progress ({int(stage_progress*100)}%) is behind schedule."
            elif breach_risk_pct >= 35.0:
                risk_level = 'Moderate Risk'
                risk_class = 'text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800/40'
                risk_note = f"{int(remaining_budget)}d remaining buffer. Active in {active_stage} for {days_in_stage}d."
            else:
                risk_level = 'On Track'
                risk_class = 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-800/40'
                risk_note = f"Production on track ({int(remaining_budget)}d buffer remaining vs {int(target_days)}d target)."

        return {
            'state': 'workshop_pending',
            'state_label': 'In Production',
            'predicted_tat_days': predicted_tat,
            'breach_risk_pct': breach_risk_pct,
            'risk_level': risk_level,
            'risk_class': risk_class,
            'risk_note': risk_note,
            'active_stage': active_stage,
            'days_in_stage': days_in_stage,
            'elapsed_days': elapsed_days,
            'confidence': 'Bayesian Survival Forecast',
        }

    # 3. Workshop completed, awaiting Muziris In-Shop receipt
    morr_date = record.morr_received_date
    transit_days = max((now_date - morr_date).days, 0)
    expected_transit_benchmark = 5.0
    if transit_days > expected_transit_benchmark:
        transit_risk_pct = min(round(50.0 + (transit_days - expected_transit_benchmark) * 10.0, 1), 95.0)
        risk_level = 'Transit Overdue' if transit_days > 10 else 'Transit Delayed'
        risk_class = 'text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800/40'
        risk_note = f"Workshop finished on {morr_date.strftime('%d-%b-%Y')} ({tat_days}d TAT). Head Office transit pending {transit_days}d."
    else:
        transit_risk_pct = round(max(transit_days / expected_transit_benchmark * 30.0, 5.0), 1)
        risk_level = 'In Transit'
        risk_class = 'text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800/40'
        risk_note = f"Workshop completed in {tat_days}d. In transit to shop for {transit_days}d."

    return {
        'state': 'inshop_pending',
        'state_label': 'Awaiting Shop Receipt',
        'predicted_tat_days': tat_days,
        'breach_risk_pct': transit_risk_pct,
        'risk_level': risk_level,
        'risk_class': risk_class,
        'risk_note': risk_note,
        'active_stage': 'Office to Muziris In-Shop',
        'days_in_stage': transit_days,
        'confidence': 'Transit Forecast',
    }


def build_delivery_display_rows(records):
    prepared_rows = []
    tat_values = []
    delivery_target_values = []

    for record in records:
        party_to_shop_days = None
        party_to_shop_status = 'not_started'
        if record.ordered_date and record.muziris_inshop_received_date:
            elapsed = (record.muziris_inshop_received_date - record.ordered_date).days
            party_to_shop_status = 'completed' if elapsed >= 0 else 'invalid'
            party_to_shop_days = elapsed if elapsed >= 0 else None
        elif record.ordered_date:
            party_to_shop_status = 'pending'
        tat_days = None
        office_to_shop_days = None
        office_to_shop_pending_days = None
        office_to_shop_status = 'not_started'
        delivery_target_days = int(record.delivery_days) if record.delivery_days is not None else None
        if record.ordered_date and record.morr_received_date:
            tat_days = max((record.morr_received_date - record.ordered_date).days, 0)
            tat_values.append(tat_days)
        if record.morr_received_date and record.muziris_inshop_received_date:
            office_to_shop_days = (
                record.muziris_inshop_received_date - record.morr_received_date
            ).days
            office_to_shop_status = 'completed' if office_to_shop_days >= 0 else 'invalid'
            if office_to_shop_days < 0:
                office_to_shop_days = None
        elif record.morr_received_date:
            office_to_shop_pending_days = max(
                (datetime.now(ZoneInfo("Asia/Kolkata")).date() - record.morr_received_date).days,
                0,
            )
            office_to_shop_status = 'pending'
        if delivery_target_days is not None:
            delivery_target_values.append(delivery_target_days)

        variance_days = (
            tat_days - delivery_target_days
            if tat_days is not None and delivery_target_days is not None
            else None
        )
        if tat_days is None:
            status_key, status_label = 'pending', 'Pending'
        elif delivery_target_days is None:
            status_key, status_label = 'unconfigured', 'SLA Not Set'
        elif variance_days <= 0:
            status_key, status_label = 'on_time', 'On Time'
        elif variance_days <= 5:
            status_key, status_label = 'at_risk', 'At Risk'
        else:
            status_key, status_label = 'critical', 'Critical'

        product_parts = [value for value in (record.section, record.type) if value]
        timeline, stage_durations = build_process_timeline(record)
        bayes_risk = compute_barcode_bayesian_stage_risk(record, delivery_target_days, tat_days)

        prepared_rows.append({
            'record': record,
            'party_to_shop_days': party_to_shop_days,
            'party_to_shop_status': party_to_shop_status,
            'tat_days': tat_days,
            'office_to_shop_days': office_to_shop_days,
            'office_to_shop_pending_days': office_to_shop_pending_days,
            'office_to_shop_status': office_to_shop_status,
            'delivery_target_days': delivery_target_days,
            'variance_days': variance_days,
            'status_key': status_key,
            'status_label': status_label,
            'modal_data': {
                'collection': record.collection or record.master_collection or '-',
                'master_collection': record.master_collection or '-',
                'barcode': record.barcode_no or '-',
                'design_no': record.design_no or '-',
                'branch': record.location or '-',
                'product': ' / '.join(product_parts) or '-',
                'purity': f"{record.purity}K" if record.purity is not None else '-',
                'classification': record.classification or '-',
                'sub_classification': record.sub_classification or '-',
                'make': record.make or '-',
                'size': record.size or '-',
                'screw_type': record.screw_type or '-',
                'weight': float(record.weight) if record.weight is not None else None,
                'tat_days': tat_days,
                'office_receipt_completed': record.morr_received_date is not None,
                'office_pending_age_days': max((datetime.now(ZoneInfo('Asia/Kolkata')).date() - record.ordered_date).days, 0)
                if record.ordered_date and not record.morr_received_date else None,
                'office_to_shop_days': office_to_shop_days,
                'office_to_shop_pending_days': office_to_shop_pending_days,
                'office_to_shop_status': office_to_shop_status,
                'delivery_days': delivery_target_days,
                'variance_days': variance_days,
                'status': status_label,
                'supplier_name': record.supplier_name or '-',
                'by_hand': bool(record.by_hand) if record.by_hand is not None else None,
                'inshop_date': date_to_iso(record.muziris_inshop_received_date),
                'order_type': record.order_request_type_name or (
                    str(record.order_request_type) if record.order_request_type is not None else '-'
                ),
                'branch_type': record.branch_type or '-',
                'received_location': record.received_location or '-',
                'current_location': record.current_location or '-',
                'timeline': timeline,
                'stage_durations': stage_durations,
                'bayes_risk': bayes_risk,
                'is_re_ordered': bool(record.is_re_ordered) if record.is_re_ordered is not None else None,
                'in_transit_days': record.in_transit_days,
            },
        })

    scale_days = max(tat_values + delivery_target_values + [1])
    for item in prepared_rows:
        item['sla_percent'] = (
            min(round(item['delivery_target_days'] * 100 / scale_days), 100)
            if item['delivery_target_days'] is not None
            else 0
        )
        item['tat_percent'] = (
            min(round(item['tat_days'] * 100 / scale_days), 100)
            if item['tat_days'] is not None
            else 0
        )

    return prepared_rows


def apply_owner_visibility_filter(query):
    user_id = str(session.get('user_id') or '').strip()
    if not user_id:
        return query.filter(false())

    roles = [role.upper() for role in session.get('roles', [])]
    if 'ADMIN' in roles or 'MANAGER_2' in roles:
        return query

    snapshot = CollectionWiseAverageDeliveryDaysSnapshot
    if 'MANAGER_KMU' in roles:
        return query.filter(snapshot.make.in_(KMU_MAKES))

    return query.filter(
        (func.trim(snapshot.make_user_code) == user_id)
        | (func.trim(snapshot.collection_user_code) == user_id)
    )


def get_distinct(column):
    try:
        query = db.session.query(distinct(column)).filter(column.isnot(None))
        query = apply_owner_visibility_filter(query)
        results = query.order_by(column).all()
        return [str(r[0]) if isinstance(r[0], (int, float)) or hasattr(r[0], 'as_tuple') else r[0] for r in results if r[0] is not None and str(r[0]).strip() != '']
    except Exception as e:
        logger.error(f"Error fetching distinct values for {column}: {e}")
        return []


def build_snapshot_query(args):
    query = apply_owner_visibility_filter(
        CollectionWiseAverageDeliveryDaysSnapshot.query
    )

    # Search filter
    search = args.get('search', '').strip()
    if search:
        query = query.filter(
            (CollectionWiseAverageDeliveryDaysSnapshot.location.ilike(f"%{search}%")) |
            (CollectionWiseAverageDeliveryDaysSnapshot.collection.ilike(f"%{search}%")) |
            (CollectionWiseAverageDeliveryDaysSnapshot.master_collection.ilike(f"%{search}%")) |
            (CollectionWiseAverageDeliveryDaysSnapshot.classification.ilike(f"%{search}%")) |
            (CollectionWiseAverageDeliveryDaysSnapshot.make.ilike(f"%{search}%")) |
            (CollectionWiseAverageDeliveryDaysSnapshot.section.ilike(f"%{search}%")) |
            (CollectionWiseAverageDeliveryDaysSnapshot.design_no.ilike(f"%{search}%")) |
            (CollectionWiseAverageDeliveryDaysSnapshot.barcode_no.ilike(f"%{search}%"))
        )

    # Multi-select or single location filter
    locations = split_filter_values(args.get('location'))
    if locations:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.location.in_(locations))

    # Group filter
    groups = split_filter_values(args.get('group'))
    if groups:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.group_name.in_(groups))

    # Purity filter
    purity_strs = split_filter_values(args.get('purity'))
    if purity_strs:
        float_purities = []
        for p in purity_strs:
            try:
                float_purities.append(float(p))
            except (ValueError, TypeError):
                pass
        if float_purities:
            query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.purity.in_(float_purities))

    # Classification filter
    classifications = split_filter_values(args.get('classification'))
    if classifications:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.classification.in_(classifications))

    # Make filter
    makes = split_filter_values(args.get('make'))
    if makes:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.make.in_(makes))

    # Collection filter
    collections = split_filter_values(args.get('collection'))
    if collections:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.collection.in_(collections))

    # Master Collection filter
    master_collections = split_filter_values(args.get('master_collection'))
    if master_collections:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.master_collection.in_(master_collections))

    # Section filter
    sections = split_filter_values(args.get('section'))
    if sections:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.section.in_(sections))

    # Branch Type filter
    branch_types = split_filter_values(args.get('branch_type'))
    if branch_types:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.branch_type.in_(branch_types))

    # Order Period filter
    order_periods = split_filter_values(args.get('order_period'))
    if order_periods:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.order_period.in_(order_periods))

    # Re-Ordered filter (defaults to 'false' / Non Re-Ordered if not specified)
    raw_is_re_ordered = args.get('is_re_ordered')
    if raw_is_re_ordered is None:
        is_re_ordered = 'false'
    else:
        is_re_ordered = raw_is_re_ordered.strip().lower()

    if is_re_ordered in ('false', '0', 'no'):
        query = query.filter(
            or_(
                CollectionWiseAverageDeliveryDaysSnapshot.is_re_ordered.is_(False),
                CollectionWiseAverageDeliveryDaysSnapshot.is_re_ordered.is_(None)
            )
        )
    elif is_re_ordered in ('true', '1', 'yes'):
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.is_re_ordered.is_(True))
    # If is_re_ordered in ('all', ''), no filter is applied (All Orders)

    return query


def build_collection_summary_query(args):
    snapshot = CollectionWiseAverageDeliveryDaysSnapshot
    as_on_date = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    party_to_shop_days = case(
        (and_(snapshot.ordered_date.isnot(None),
              snapshot.muziris_inshop_received_date.isnot(None),
              snapshot.muziris_inshop_received_date >= snapshot.ordered_date),
         snapshot.muziris_inshop_received_date - snapshot.ordered_date),
        else_=None,
    )
    tat_days = case(
        (and_(snapshot.ordered_date.isnot(None), snapshot.morr_received_date.isnot(None),
              snapshot.morr_received_date >= snapshot.ordered_date,
              snapshot.morr_received_date <= as_on_date),
         snapshot.morr_received_date - snapshot.ordered_date), else_=None,
    )
    office_age = func.coalesce(snapshot.morr_received_date, as_on_date) - snapshot.ordered_date
    office_pending = and_(snapshot.morr_received_date.is_(None), snapshot.ordered_date.isnot(None),
                          snapshot.ordered_date <= as_on_date)
    valid_target = and_(snapshot.delivery_days.isnot(None), snapshot.delivery_days >= 0)
    assessed_pending = and_(office_pending, valid_target)
    office_to_shop_days = case(
        (
            and_(
                snapshot.morr_received_date.isnot(None),
                snapshot.muziris_inshop_received_date.isnot(None),
                snapshot.muziris_inshop_received_date >= snapshot.morr_received_date,
            ),
            snapshot.muziris_inshop_received_date - snapshot.morr_received_date,
        ),
        else_=None,
    )
    eligible_tat = case((valid_target, tat_days), else_=None)
    sla_variance = case(
        (valid_target, tat_days - snapshot.delivery_days),
        else_=None,
    )
    completed_count = func.count(eligible_tat)
    compliant_count = func.sum(
        case((and_(valid_target, tat_days <= snapshot.delivery_days), 1), else_=0)
    )
    pending_age = case(
        (
            snapshot.muziris_inshop_received_date.is_(None),
            func.current_date() - snapshot.morr_received_date,
        ),
        else_=None,
    )

    metrics = {
        'barcode_count': func.count(snapshot.id),
        'branch_count': func.count(distinct(snapshot.location)),
        'section_count': func.count(distinct(snapshot.section)),
        'type_count': func.count(distinct(snapshot.type)),
        'first_ordered_date': func.min(snapshot.ordered_date),
        'last_ordered_date': func.max(snapshot.ordered_date),
        'avg_tat_days': func.avg(tat_days),
        'valid_tat_count': func.count(tat_days),
        'tat_sum_days': func.sum(tat_days),
        'tat_stddev_days': func.stddev_samp(tat_days),
        'compliance_eligible_count': completed_count,
        'compliant_count': compliant_count,
        'office_assessed_pending_count': func.sum(case((assessed_pending, 1), else_=0)),
        'office_pending_exposure_days': func.sum(case((office_pending, office_age), else_=0)),
        'avg_party_to_shop_days': func.avg(party_to_shop_days),
        'median_tat_days': func.percentile_cont(0.5).within_group(tat_days),
        'p90_tat_days': func.percentile_cont(0.9).within_group(tat_days),
        'max_tat_days': func.max(tat_days),
        'avg_office_to_shop_days': func.avg(office_to_shop_days),
        'median_office_to_shop_days': func.percentile_cont(0.5).within_group(office_to_shop_days),
        'p90_office_to_shop_days': func.percentile_cont(0.9).within_group(office_to_shop_days),
        'max_office_to_shop_days': func.max(office_to_shop_days),
        'office_to_shop_completed_count': func.count(office_to_shop_days),
        'avg_delivery_days': func.avg(snapshot.delivery_days),
        'combined_avg_days': func.avg(office_age),
        'completed_day_contribution': func.sum(case((snapshot.morr_received_date.isnot(None), office_age), else_=0)) * 1.0 / func.nullif(func.count(office_age), 0),
        'pending_day_contribution': func.sum(case((office_pending, office_age), else_=0)) * 1.0 / func.nullif(func.count(office_age), 0),
        'office_pending_count': func.sum(case((office_pending, 1), else_=0)),
        'office_overdue_count': func.sum(case((and_(assessed_pending, office_age > snapshot.delivery_days), 1), else_=0)),
        'avg_sla_variance': func.avg(sla_variance),
        'compliance_pct': compliant_count * 100.0 / func.nullif(completed_count, 0),
        'delayed_count': func.sum(
            case((and_(valid_target, tat_days > snapshot.delivery_days), 1), else_=0)
        ),
        'awaiting_inshop_count': func.sum(
            case((snapshot.muziris_inshop_received_date.is_(None), 1), else_=0)
        ),
        'received_inshop_count': func.sum(
            case((snapshot.muziris_inshop_received_date.isnot(None), 1), else_=0)
        ),
        'avg_pending_age_days': func.avg(pending_age),
        'last_morr_received_date': func.max(snapshot.morr_received_date),
    }

    query = build_snapshot_query(args).with_entities(
        snapshot.collection.label('collection'),
        snapshot.master_collection.label('master_collection'),
        *(expression.label(name) for name, expression in metrics.items()),
    ).group_by(
        snapshot.collection,
        snapshot.master_collection,
    )

    return query, metrics


def compute_bayesian_delivery_metrics(row, global_mu0=None, global_comp0=None, prior_weight_m=5.0):
    """Descriptive estimates; legacy response keys retained for the modal."""
    completed_count = int(row.valid_tat_count or 0)
    office_pending_count = int(row.office_pending_count or 0)
    assessed_pending = int(row.office_assessed_pending_count or 0)
    raw_tat = float(row.avg_tat_days) if completed_count and row.avg_tat_days is not None else None
    adjusted = raw_tat
    if raw_tat is not None and global_mu0 is not None:
        adjusted = (completed_count * raw_tat + prior_weight_m * global_mu0) / (completed_count + prior_weight_m)
    difference = adjusted - raw_tat if raw_tat is not None else None

    # Normal-approximation interval for the observed mean, not a delivery window.
    lower = upper = None
    if completed_count >= 30 and row.tat_stddev_days is not None and raw_tat is not None:
        margin = 1.645 * float(row.tat_stddev_days) / (completed_count ** 0.5)
        lower, upper = round(max(0.0, raw_tat - margin), 1), round(raw_tat + margin, 1)

    eligible = int(row.compliance_eligible_count or 0)
    compliant = int(row.compliant_count or 0)
    smoothed = None
    if eligible:
        smoothed = 100.0 * compliant / eligible
        if global_comp0 is not None:
            smoothed = 100.0 * (compliant + 8.0 * global_comp0 / 100.0) / (eligible + 8.0)

    overdue = int(row.office_overdue_count or 0)
    overdue_pct = round(100.0 * overdue / assessed_pending, 1) if assessed_pending else None
    sample_label = 'Large sample' if completed_count >= 30 else ('Small sample' if completed_count else 'No completed sample')
    return {
        'bayes_adjusted_tat': round(adjusted, 1) if adjusted is not None else None,
        'bayes_raw_tat': round(raw_tat, 1) if raw_tat is not None else None,
        'bayes_shrinkage_diff': round(difference, 1) if difference is not None else None,
        'bayes_credible_min': lower,
        'bayes_credible_max': upper,
        'bayes_smoothed_compliance': round(smoothed, 1) if smoothed is not None else None,
        'bayes_inflight_risk_pct': overdue_pct,
        'bayes_orders_at_risk': overdue,
        'confidence_level': sample_label,
        'confidence_class': 'text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 border border-blue-200',
        'completed_count': completed_count,
        'office_pending_count': office_pending_count,
        'assessed_pending_count': assessed_pending,
        'compliance_eligible_count': eligible,
        'is_low_sample': completed_count < 5,
        'has_high_inflight_risk': overdue_pct is not None and overdue_pct >= 70.0,
    }


def collection_delivery_baselines(query):
    """Weighted baselines across all filtered groups, before sorting/pagination."""
    groups = query.order_by(None).subquery()
    totals = db.session.query(
        func.sum(groups.c.tat_sum_days),
        func.sum(groups.c.valid_tat_count),
        func.sum(groups.c.compliant_count),
        func.sum(groups.c.compliance_eligible_count),
    ).one()
    return (
        float(totals[0]) / int(totals[1]) if totals[1] else None,
        100.0 * int(totals[2] or 0) / int(totals[3]) if totals[3] else None,
    )


def collection_pending_buckets(args, rows):
    """One aggregate query for the visible groups, using the same access filters."""
    if not rows:
        return {}
    snapshot = CollectionWiseAverageDeliveryDaysSnapshot
    as_on_date = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    age = as_on_date - snapshot.ordered_date
    query = build_snapshot_query(args).filter(
        snapshot.morr_received_date.is_(None),
        snapshot.ordered_date.isnot(None), snapshot.ordered_date <= as_on_date,
        or_(*(and_(snapshot.collection == row.collection,
                   snapshot.master_collection == row.master_collection) for row in rows)),
    ).with_entities(snapshot.collection, snapshot.master_collection, age.label('age'),
                    snapshot.delivery_days, func.count(snapshot.id)).group_by(
        snapshot.collection, snapshot.master_collection, snapshot.ordered_date, snapshot.delivery_days)
    buckets = {}
    for collection, master, elapsed, target, count in query.all():
        buckets.setdefault((collection, master), []).append((elapsed, target, count))
    return buckets


def build_collection_summary_display_rows(rows, global_mu0=None, global_comp0=None, pending_buckets=None):
    from app.services.collection_delivery_forecast import delivery_forecast
    pending_buckets = pending_buckets or {}
    display_rows = []
    for row in rows:
        bayes = compute_bayesian_delivery_metrics(
            row,
            global_mu0=global_mu0,
            global_comp0=global_comp0,
            prior_weight_m=5.0
        )
        display_rows.append({
            'record': row,
            'completed_count': bayes['completed_count'],
            'is_low_sample': bayes['is_low_sample'],
            'has_high_inflight_risk': bayes['has_high_inflight_risk'],
            'modal_data': {
                'bayesian_forecast': delivery_forecast(
                    row.valid_tat_count, row.tat_sum_days, row.office_pending_exposure_days,
                    pending_buckets.get((row.collection, row.master_collection), [])),
                'forecast_as_on': datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat(),
                'collection': row.collection or '-',
                'master_collection': row.master_collection or '-',
                'barcode_count': int(row.barcode_count or 0),
                'branch_count': int(row.branch_count or 0),
                'section_count': int(row.section_count or 0),
                'type_count': int(row.type_count or 0),
                'first_ordered_date': date_to_iso(row.first_ordered_date),
                'last_ordered_date': date_to_iso(row.last_ordered_date),
                'avg_tat_days': float(row.avg_tat_days) if row.avg_tat_days is not None else None,
                'median_tat_days': float(row.median_tat_days) if row.median_tat_days is not None else None,
                'p90_tat_days': float(row.p90_tat_days) if row.p90_tat_days is not None else None,
                'max_tat_days': int(row.max_tat_days) if row.max_tat_days is not None else None,
                'avg_office_to_shop_days': (
                    float(row.avg_office_to_shop_days)
                    if row.avg_office_to_shop_days is not None
                    else None
                ),
                'median_office_to_shop_days': (
                    float(row.median_office_to_shop_days)
                    if row.median_office_to_shop_days is not None
                    else None
                ),
                'p90_office_to_shop_days': (
                    float(row.p90_office_to_shop_days)
                    if row.p90_office_to_shop_days is not None
                    else None
                ),
                'max_office_to_shop_days': (
                    int(row.max_office_to_shop_days)
                    if row.max_office_to_shop_days is not None
                    else None
                ),
                'office_to_shop_completed_count': int(row.office_to_shop_completed_count or 0),
                'combined_avg_days': float(row.combined_avg_days) if row.combined_avg_days is not None else None,
                'completed_day_contribution': float(row.completed_day_contribution) if row.completed_day_contribution is not None else None,
                'pending_day_contribution': float(row.pending_day_contribution) if row.pending_day_contribution is not None else None,
                'office_pending_count': int(row.office_pending_count or 0),
                'office_overdue_count': int(row.office_overdue_count or 0),
                'avg_delivery_days': (
                    float(row.avg_delivery_days)
                    if row.avg_delivery_days is not None
                    else None
                ),
                'avg_sla_variance': (
                    float(row.avg_sla_variance)
                    if row.avg_sla_variance is not None
                    else None
                ),
                'compliance_pct': float(row.compliance_pct) if row.compliance_pct is not None else None,
                'delayed_count': int(row.delayed_count or 0),
                'awaiting_inshop_count': int(row.awaiting_inshop_count or 0),
                'received_inshop_count': int(row.received_inshop_count or 0),
                'avg_pending_age_days': (
                    float(row.avg_pending_age_days)
                    if row.avg_pending_age_days is not None
                    else None
                ),
                'last_morr_received_date': date_to_iso(row.last_morr_received_date),
                # Bayesian Reliability & Forecast Metrics
                'bayes_adjusted_tat': bayes['bayes_adjusted_tat'],
                'bayes_raw_tat': bayes['bayes_raw_tat'],
                'bayes_shrinkage_diff': bayes['bayes_shrinkage_diff'],
                'bayes_credible_min': bayes['bayes_credible_min'],
                'bayes_credible_max': bayes['bayes_credible_max'],
                'bayes_smoothed_compliance': bayes['bayes_smoothed_compliance'],
                'bayes_inflight_risk_pct': bayes['bayes_inflight_risk_pct'],
                'bayes_orders_at_risk': bayes['bayes_orders_at_risk'],
                'bayes_confidence_level': bayes['confidence_level'],
                'bayes_confidence_class': bayes['confidence_class'],
                'bayes_completed_count': bayes['completed_count'],
                'bayes_pending_count': bayes['office_pending_count'],
                'bayes_assessed_pending_count': bayes['assessed_pending_count'],
                'bayes_compliance_eligible_count': bayes['compliance_eligible_count'],
                'is_low_sample': bayes['is_low_sample'],
                'has_high_inflight_risk': bayes['has_high_inflight_risk'],
            },
        })
    return display_rows


@dashboard_bp.route('/collection-wise-average-delivery-days')
@require_report_access('/collection-wise-average-delivery-days')
def collection_wise_average_delivery_days_page():
    try:
        unread_count = Notification.query.filter_by(is_read=False).count()
        sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
        permissions = session.get('permissions', [])
        return render_template(
            'collection_wise_average_delivery_days.html',
            unread_count=unread_count,
            sync_time=sync_time,
            permissions=permissions
        )
    except Exception as e:
        logger.error(f"Error rendering collection_wise_average_delivery_days page: {str(e)}")
        return render_template(
            'collection_wise_average_delivery_days.html',
            unread_count=0,
            sync_time=datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p"),
            permissions=session.get('permissions', [])
        )


@dashboard_bp.route('/partial/collection-wise-average-delivery-days')
@jwt_required()
@require_report_access('/collection-wise-average-delivery-days')
def get_collection_wise_average_delivery_days_partial():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        sort_by = request.args.get('sort_by', '').strip()
        sort_order = request.args.get('sort_order', 'none').lower()

        query, metrics = build_collection_summary_query(request.args)
        baseline_tat, baseline_compliance = collection_delivery_baselines(query)

        column_map = {
            'collection': CollectionWiseAverageDeliveryDaysSnapshot.collection,
            'location': metrics['branch_count'],
            'group': metrics['type_count'],
            'ordered_date': metrics['last_ordered_date'],
            'morr_received_date': metrics['last_morr_received_date'],
            'tat_days': metrics['avg_tat_days'],
            'party_to_shop_days': metrics['avg_party_to_shop_days'],
            'office_to_shop_days': metrics['avg_office_to_shop_days'],
            'sla_variance': metrics['avg_tat_days'],
            'muziris_inshop_received_date': metrics['awaiting_inshop_count'],
            'compliance_pct': metrics['compliance_pct'],
        }

        if sort_by in column_map and sort_order in ('asc', 'desc'):
            sort_col = column_map[sort_by]
            if sort_order == 'desc':
                query = query.order_by(sort_col.desc().nullslast())
            else:
                query = query.order_by(sort_col.asc().nullslast())
        else:
            query = query.order_by(CollectionWiseAverageDeliveryDaysSnapshot.collection.asc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return render_template(
            'partials/_view_collection_wise_average_delivery_days.html',
            rows=build_collection_summary_display_rows(
                pagination.items, baseline_tat, baseline_compliance,
                collection_pending_buckets(request.args, pagination.items)),
            total_records=pagination.total,
            page=page,
            per_page=per_page,
            total_pages=pagination.pages or 1,
            sort_by=sort_by,
            sort_order=sort_order
        )
    except Exception as e:
        logger.error(f"Error rendering collection_wise_average_delivery_days partial: {str(e)}")
        return render_template(
            'partials/_view_collection_wise_average_delivery_days.html',
            rows=[],
            total_records=0,
            page=1,
            per_page=50,
            total_pages=1,
            error_message=str(e)
        )


@dashboard_bp.route('/partial/collection-wise-average-delivery-days/collection-rows')
@jwt_required()
@require_report_access('/collection-wise-average-delivery-days')
def get_collection_wise_average_delivery_days_collection_rows():
    try:
        collection = request.args.get('group_collection', '').strip()
        if not collection:
            return render_template(
                'partials/_view_collection_wise_average_delivery_days_rows.html',
                rows=[],
                error_message='Collection is required.'
            ), 400

        page = request.args.get('detail_page', 1, type=int)
        per_page = min(request.args.get('detail_per_page', 25, type=int), 100)
        snapshot = CollectionWiseAverageDeliveryDaysSnapshot
        query = build_snapshot_query(request.args).filter(snapshot.collection == collection)
        pagination = query.order_by(
            snapshot.ordered_date.desc().nullslast(),
            snapshot.id.desc(),
        ).paginate(page=page, per_page=per_page, error_out=False)

        return render_template(
            'partials/_view_collection_wise_average_delivery_days_rows.html',
            rows=build_delivery_display_rows(pagination.items),
            collection=collection,
            page=page,
            per_page=per_page,
            total_pages=pagination.pages or 1,
            total_records=pagination.total,
        )
    except Exception as e:
        logger.error(f"Error rendering collection delivery detail rows: {str(e)}")
        db.session.rollback()
        return render_template(
            'partials/_view_collection_wise_average_delivery_days_rows.html',
            rows=[],
            error_message=str(e)
        ), 500


@dashboard_bp.route('/api/collection-wise-average-delivery-days/supplier-delivery-times')
@require_report_access('/collection-wise-average-delivery-days')
def get_collection_supplier_delivery_times():
    try:
        collection = request.args.get('group_collection', '').strip()
        if not collection:
            return jsonify({
                'suppliers': [],
                'max_delivery_days': 0,
                'message': 'Collection is required.',
            }), 400

        snapshot = CollectionWiseAverageDeliveryDaysSnapshot
        supplier_days = func.max(snapshot.delivery_days)
        tat_days = snapshot.morr_received_date - snapshot.ordered_date
        office_age = func.coalesce(snapshot.morr_received_date, func.current_date()) - snapshot.ordered_date
        office_pending = and_(snapshot.morr_received_date.is_(None), snapshot.ordered_date.isnot(None))
        is_inshop_pending = and_(
            snapshot.morr_received_date.isnot(None),
            snapshot.muziris_inshop_received_date.is_(None),
        )
        inshop_pending_age = case(
            (
                is_inshop_pending,
                func.current_date() - snapshot.morr_received_date,
            ),
            else_=None,
        )
        completed_count = func.count(tat_days)
        compliant_count = func.sum(
            case((tat_days <= snapshot.delivery_days, 1), else_=0)
        )
        rows = (
            build_snapshot_query(request.args)
            .filter(
                snapshot.collection == collection,
                snapshot.supplier_name.isnot(None),
                func.trim(snapshot.supplier_name) != '',
                snapshot.delivery_days.isnot(None),
            )
            .with_entities(
                snapshot.supplier_id.label('supplier_id'),
                snapshot.supplier_name.label('supplier_name'),
                supplier_days.label('delivery_days'),
                func.count(distinct(snapshot.barcode_no)).label('barcode_count'),
                func.avg(tat_days).label('actual_avg_days'),
                func.avg(office_age).label('combined_avg_days'),
                (func.sum(case((snapshot.morr_received_date.isnot(None), office_age), else_=0))
                 * 1.0 / func.nullif(func.count(office_age), 0)).label('completed_day_contribution'),
                (func.sum(case((office_pending, office_age), else_=0))
                 * 1.0 / func.nullif(func.count(office_age), 0)).label('pending_day_contribution'),
                func.sum(case((office_pending, 1), else_=0)).label('office_pending_count'),
                func.sum(case((and_(office_pending, office_age > snapshot.delivery_days), 1), else_=0)).label('office_overdue_count'),
                func.avg(tat_days - snapshot.delivery_days).label('avg_variance_days'),
                (
                    compliant_count * 100.0 / func.nullif(completed_count, 0)
                ).label('compliance_pct'),
                func.sum(
                    case((is_inshop_pending, 1), else_=0)
                ).label('inshop_pending_count'),
                func.max(inshop_pending_age).label('oldest_inshop_pending_days'),
                func.avg(inshop_pending_age).label('avg_inshop_pending_days'),
                func.sum(
                    case(
                        (
                            and_(
                                is_inshop_pending,
                                inshop_pending_age > snapshot.delivery_days,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label('past_target_count'),
            )
            .group_by(snapshot.supplier_id, snapshot.supplier_name)
            .order_by(supplier_days.desc(), snapshot.supplier_name.asc())
            .all()
        )

        max_delivery_days = max((int(row.delivery_days or 0) for row in rows), default=0)
        denominator = max(max_delivery_days, 1)
        suppliers = []
        for row in rows:
            target_days = int(row.delivery_days or 0)
            pending_count = int(row.inshop_pending_count or 0)
            oldest_pending_days = (
                int(row.oldest_inshop_pending_days)
                if row.oldest_inshop_pending_days is not None
                else None
            )
            if not pending_count or oldest_pending_days is None:
                pending_status = 'none'
            elif oldest_pending_days > target_days:
                pending_status = 'past_target'
            elif target_days > 0 and oldest_pending_days >= target_days * 0.75:
                pending_status = 'near_target'
            else:
                pending_status = 'within_target'

            suppliers.append({
                'supplier_id': row.supplier_id,
                'supplier_name': row.supplier_name,
                'delivery_days': target_days,
                'barcode_count': int(row.barcode_count or 0),
                'combined_avg_days': float(row.combined_avg_days) if row.combined_avg_days is not None else None,
                'completed_day_contribution': float(row.completed_day_contribution) if row.completed_day_contribution is not None else None,
                'pending_day_contribution': float(row.pending_day_contribution) if row.pending_day_contribution is not None else None,
                'office_pending_count': int(row.office_pending_count or 0),
                'office_overdue_count': int(row.office_overdue_count or 0),
                'actual_avg_days': (
                    round(float(row.actual_avg_days), 1)
                    if row.actual_avg_days is not None
                    else None
                ),
                'avg_variance_days': (
                    round(float(row.avg_variance_days), 1)
                    if row.avg_variance_days is not None
                    else None
                ),
                'compliance_pct': (
                    round(float(row.compliance_pct), 1)
                    if row.compliance_pct is not None
                    else None
                ),
                'inshop_pending_count': pending_count,
                'oldest_inshop_pending_days': oldest_pending_days,
                'avg_inshop_pending_days': (
                    round(float(row.avg_inshop_pending_days), 1)
                    if row.avg_inshop_pending_days is not None
                    else None
                ),
                'past_target_count': int(row.past_target_count or 0),
                'pending_status': pending_status,
                'progress_percent': round(target_days * 100 / denominator, 1),
                'pending_progress_percent': (
                    min(round(oldest_pending_days * 100 / denominator, 1), 100)
                    if oldest_pending_days is not None
                    else 0
                ),
            })

        return jsonify({
            'suppliers': suppliers,
            'supplier_count': len(suppliers),
            'max_delivery_days': max_delivery_days,
        })
    except Exception as e:
        logger.error(f"Error fetching supplier delivery times: {str(e)}")
        return jsonify({'error': str(e), 'suppliers': [], 'max_delivery_days': 0}), 500


@dashboard_bp.route('/api/collection-wise-average-delivery-days/options')
@require_report_access('/collection-wise-average-delivery-days')
def get_collection_wise_average_delivery_days_options():
    try:
        locations = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.location)
        groups = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.group_name)
        purities = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.purity)
        classifications = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.classification)
        makes = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.make)
        collections = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.collection)
        master_collections = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.master_collection)
        sections = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.section)
        branch_types = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.branch_type)
        order_periods = get_distinct(CollectionWiseAverageDeliveryDaysSnapshot.order_period)

        return jsonify({
            'locations': locations,
            'groups': groups,
            'purities': [str(p) for p in purities],
            'classifications': classifications,
            'makes': makes,
            'collections': collections,
            'master_collections': master_collections,
            'sections': sections,
            'branch_types': branch_types,
            'order_periods': order_periods
        })
    except Exception as e:
        logger.error(f"Error fetching collection_wise_average_delivery_days options: {str(e)}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/sync/collection-wise-average-delivery-days', methods=['POST'])
@require_role(['ADMIN', 'DATA_SYNC_USER'])
def trigger_sync_collection_wise_average_delivery_days():
    from app.utils.sync_manager import sync_collection_wise_average_delivery_days_data
    from app.models.auth import User
    user = db.session.get(User, int(get_jwt_identity()))
    return jsonify(sync_collection_wise_average_delivery_days_data(user.user_id))


@dashboard_bp.route('/api/collection-wise-average-delivery-days/export', methods=['POST'])
@jwt_required()
@require_report_access('/collection-wise-average-delivery-days')
@require_perm('report.export')
def queue_collection_wise_average_delivery_days_export():
    try:
        from app.utils.export_service import create_export_job
        data = request.get_json() or {}
        filters = data.get('filters', {})
        socket_id = data.get('socket_id')
        user_id = get_jwt_identity()

        task_payload = {
            'report_type': 'collection_wise_average_delivery_days',
            'filters': filters,
            'socket_id': socket_id,
            'user_id': user_id
        }

        job_result = create_export_job(task_payload)
        return jsonify(job_result), 200
    except Exception as e:
        logger.error(f"Failed to queue collection_wise_average_delivery_days export: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
