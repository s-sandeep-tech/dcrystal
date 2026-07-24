from flask import render_template, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.dashboard import dashboard_bp
from app.models import Notification, CollectionWiseAverageDeliveryDaysSnapshot
from app.extensions import db
from app.utils.decorators import require_perm
from sqlalchemy import func, distinct
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

    timeline = []
    stage_durations = []

    for index, (label, stage_date) in enumerate(stages):
        next_label, next_date = stages[index + 1] if index + 1 < len(stages) else (None, None)
        days_to_next = None
        cumulative_days = None
        if stage_date and next_date:
            days_to_next = max((next_date - stage_date).days, 0)
            stage_durations.append({
                'from_stage': label,
                'to_stage': next_label,
                'start_date': date_to_iso(stage_date),
                'end_date': date_to_iso(next_date),
                'duration_days': days_to_next,
            })
        if start_date and stage_date:
            cumulative_days = max((stage_date - start_date).days, 0)

        timeline.append({
            'label': label,
            'date': date_to_iso(stage_date),
            'days_to_next': days_to_next,
            'cumulative_days': cumulative_days,
            'completed': stage_date is not None,
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
        results = db.session.query(distinct(column)).filter(column.isnot(None), column != '').order_by(column).all()
        return [r[0] for r in results if r[0] is not None]
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

    # Multi-select location filter
    locations = split_filter_values(args.get('location'))
    if locations:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.location.in_(locations))

    # Single or Multi-select filters
    group_name = args.get('group', '').strip()
    if group_name:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.group_name == group_name)

    purity = args.get('purity', '').strip()
    if purity:
        try:
            query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.purity == float(purity))
        except (ValueError, TypeError):
            pass

    classification = args.get('classification', '').strip()
    if classification:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.classification == classification)

    make = args.get('make', '').strip()
    if make:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.make == make)

    collection = args.get('collection', '').strip()
    if collection:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.collection == collection)

    master_collection = args.get('master_collection', '').strip()
    if master_collection:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.master_collection == master_collection)

    section = args.get('section', '').strip()
    if section:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.section == section)

    branch_type = args.get('branch_type', '').strip()
    if branch_type:
        query = query.filter(CollectionWiseAverageDeliveryDaysSnapshot.branch_type == branch_type)

    return query


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

        query = build_snapshot_query(request.args)
        pagination = query.order_by(CollectionWiseAverageDeliveryDaysSnapshot.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        display_rows = build_delivery_display_rows(pagination.items)

        return render_template(
            'partials/_view_collection_wise_average_delivery_days.html',
            rows=display_rows,
            total_records=pagination.total,
            page=page,
            per_page=per_page,
            total_pages=pagination.pages or 1
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
@jwt_required()
def trigger_sync_collection_wise_average_delivery_days():
    from app.utils.sync_manager import sync_collection_wise_average_delivery_days_data
    user_id = get_jwt_identity()
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
