from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models import Notification, CollectionWiseAverageDeliveryDaysSnapshot
from app.extensions import db
from app.utils.decorators import require_perm
from sqlalchemy import case, func, distinct
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

WORKSHOP_SLA_DAYS = 10


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
        ('MORR Received', record.morr_received_date),
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


def build_delivery_display_rows(records):
    prepared_rows = []
    tat_values = []

    for record in records:
        tat_days = None
        if record.ordered_date and record.morr_received_date:
            tat_days = max((record.morr_received_date - record.ordered_date).days, 0)
            tat_values.append(tat_days)

        variance_days = tat_days - WORKSHOP_SLA_DAYS if tat_days is not None else None
        if variance_days is None:
            status_key, status_label = 'pending', 'Pending'
        elif variance_days <= 0:
            status_key, status_label = 'on_time', 'On Time'
        elif variance_days <= 5:
            status_key, status_label = 'at_risk', 'At Risk'
        else:
            status_key, status_label = 'critical', 'Critical'

        product_parts = [value for value in (record.section, record.type) if value]
        timeline, stage_durations = build_process_timeline(record)

        prepared_rows.append({
            'record': record,
            'tat_days': tat_days,
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
                'variance_days': variance_days,
                'status': status_label,
                'inshop_date': date_to_iso(record.muziris_inshop_received_date),
                'order_type': record.order_request_type_name or (
                    str(record.order_request_type) if record.order_request_type is not None else '-'
                ),
                'branch_type': record.branch_type or '-',
                'received_location': record.received_location or '-',
                'current_location': record.current_location or '-',
                'timeline': timeline,
                'stage_durations': stage_durations,
            },
        })

    scale_days = max(tat_values + [WORKSHOP_SLA_DAYS])
    for item in prepared_rows:
        item['sla_percent'] = min(round(WORKSHOP_SLA_DAYS * 100 / scale_days), 100)
        item['tat_percent'] = (
            min(round(item['tat_days'] * 100 / scale_days), 100)
            if item['tat_days'] is not None
            else 0
        )

    return prepared_rows


def get_distinct(column):
    try:
        query = db.session.query(distinct(column)).filter(column.isnot(None))
        results = query.order_by(column).all()
        return [str(r[0]) if isinstance(r[0], (int, float)) or hasattr(r[0], 'as_tuple') else r[0] for r in results if r[0] is not None and str(r[0]).strip() != '']
    except Exception as e:
        logger.error(f"Error fetching distinct values for {column}: {e}")
        return []


def build_snapshot_query(args):
    query = CollectionWiseAverageDeliveryDaysSnapshot.query

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

    return query


def build_collection_summary_query(args):
    snapshot = CollectionWiseAverageDeliveryDaysSnapshot
    tat_days = snapshot.morr_received_date - snapshot.ordered_date
    completed_count = func.count(tat_days)
    compliant_count = func.sum(case((tat_days <= WORKSHOP_SLA_DAYS, 1), else_=0))
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
        'median_tat_days': func.percentile_cont(0.5).within_group(tat_days),
        'p90_tat_days': func.percentile_cont(0.9).within_group(tat_days),
        'max_tat_days': func.max(tat_days),
        'compliance_pct': compliant_count * 100.0 / func.nullif(completed_count, 0),
        'delayed_count': func.sum(case((tat_days > WORKSHOP_SLA_DAYS, 1), else_=0)),
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


def build_collection_summary_display_rows(rows):
    display_rows = []
    for row in rows:
        display_rows.append({
            'record': row,
            'modal_data': {
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
            },
        })
    return display_rows


@dashboard_bp.route('/collection-wise-average-delivery-days')
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
def get_collection_wise_average_delivery_days_partial():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        sort_by = request.args.get('sort_by', '').strip()
        sort_order = request.args.get('sort_order', 'none').lower()

        query, metrics = build_collection_summary_query(request.args)

        column_map = {
            'collection': CollectionWiseAverageDeliveryDaysSnapshot.collection,
            'location': metrics['branch_count'],
            'group': metrics['type_count'],
            'ordered_date': metrics['last_ordered_date'],
            'morr_received_date': metrics['last_morr_received_date'],
            'tat_days': metrics['avg_tat_days'],
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
            rows=build_collection_summary_display_rows(pagination.items),
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
        return render_template(
            'partials/_view_collection_wise_average_delivery_days_rows.html',
            rows=[],
            error_message=str(e)
        ), 500


@dashboard_bp.route('/api/collection-wise-average-delivery-days/supplier-delivery-times')
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
                func.count(snapshot.id).label('record_count'),
            )
            .group_by(snapshot.supplier_id, snapshot.supplier_name)
            .order_by(supplier_days.desc(), snapshot.supplier_name.asc())
            .all()
        )

        max_delivery_days = max((int(row.delivery_days or 0) for row in rows), default=0)
        denominator = max(max_delivery_days, 1)
        suppliers = [
            {
                'supplier_id': row.supplier_id,
                'supplier_name': row.supplier_name,
                'delivery_days': int(row.delivery_days or 0),
                'record_count': int(row.record_count or 0),
                'progress_percent': round(int(row.delivery_days or 0) * 100 / denominator, 1),
            }
            for row in rows
        ]

        return jsonify({
            'suppliers': suppliers,
            'max_delivery_days': max_delivery_days,
        })
    except Exception as e:
        logger.error(f"Error fetching supplier delivery times: {str(e)}")
        return jsonify({'error': str(e), 'suppliers': [], 'max_delivery_days': 0}), 500


@dashboard_bp.route('/api/collection-wise-average-delivery-days/options')
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

        return jsonify({
            'locations': locations,
            'groups': groups,
            'purities': [str(p) for p in purities],
            'classifications': classifications,
            'makes': makes,
            'collections': collections,
            'master_collections': master_collections,
            'sections': sections,
            'branch_types': branch_types
        })
    except Exception as e:
        logger.error(f"Error fetching collection_wise_average_delivery_days options: {str(e)}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/sync/collection-wise-average-delivery-days', methods=['POST'])
@jwt_required(optional=True)
def trigger_sync_collection_wise_average_delivery_days():
    from app.utils.sync_manager import sync_collection_wise_average_delivery_days_data
    from app.models.auth import User
    user_id = session.get('user_id') or get_jwt_identity()
    if user_id and str(user_id).isdigit():
        user = User.query.get(int(user_id))
        if user:
            user_id = user.user_id
    return jsonify(sync_collection_wise_average_delivery_days_data(user_id))


@dashboard_bp.route('/api/collection-wise-average-delivery-days/export', methods=['POST'])
@jwt_required()
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
