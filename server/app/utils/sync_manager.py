from app.extensions import redis_client
import json
import logging

logger = logging.getLogger(__name__)

SCHEDULED_ALL_SYNC_TASKS = (
    'owner_showroom_combined',
    'process_delay',
    'outstanding_po',
    'stage_delay',
    'order_delay_tracking',
    'pending_acceptance',
    'rejected_weight',
    'provision_stock_status',
    'size_level_nip_barcode',
    'hallmarking_delayed',
    'qc_delayed',
    'order_processing_pending',
    'supplier_hm_issue',
    'hm_return_pending',
    'hm_qc_issue_pending',
    'supplier_qc_issue_receipt_pending',
    'qc_completed_invoice_pending',
    'invoice_completed_pending_deliver',
    'branch_authority',
    'qc_delay_management',
    'hm_delay_management',
    'party_delay_management',
    'order_fulfillment_aging_matrix',
    'collection_wise_average_delivery_days',
    'party_design_average_delivery_days',
)

ALLOWED_SYNC_TASKS = {
    'owner_wise',
    'process_delay',
    'outstanding_po',
    'stage_delay',
    'order_delay_tracking',
    'pending_acceptance',
    'rejected_weight',
    'showroom_wise_order',
    'owner_showroom_combined',
    'provision_stock_status',
    'hallmarking_delayed',
    'qc_delayed',
    'order_processing_pending',
    'supplier_hm_issue',
    'hm_return_pending',
    'hm_qc_issue_pending',
    'supplier_qc_issue_receipt_pending',
    'qc_completed_invoice_pending',
    'qc_completed_invoice_request_pending',
    'invoice_completed_pending_deliver',
    'branch_authority',
    'qc_delay_management',
    'hm_delay_management',
    'qc_receipt_completed_pending',
    'party_delay_management',
    'order_fulfillment_aging_matrix',
    'pending_order_details',
    'active_order_details',
    'size_level_nip_barcode',
    'collection_wise_average_delivery_days',
    'party_design_average_delivery_days',
}


def enqueue_sync_task(task_type, user_id=None):
    """Pushes a sync task to the Redis queue."""
    try:
        if task_type not in ALLOWED_SYNC_TASKS:
            return {"status": "error", "message": f"Unsupported sync task: {task_type}"}
        task_data = json.dumps({"type": task_type, "user_id": user_id})
        redis_client.rpush('sync_queue', task_data)
        logger.info(f"Enqueued sync task: {task_type}")
        return {"status": "success", "message": "Sync task queued. Check notifications for progress."}
    except Exception as e:
        logger.error(f"Failed to enqueue sync task: {str(e)}")
        return {"status": "error", "message": f"Failed to queue task: {str(e)}"}


def _enqueue_scheduled_all_task(batch_id, task_index):
    if task_index >= len(SCHEDULED_ALL_SYNC_TASKS):
        logger.info(f"Scheduled all-sync batch {batch_id} completed")
        return {"status": "success", "message": "Scheduled all-sync batch completed."}

    task_type = SCHEDULED_ALL_SYNC_TASKS[task_index]
    task_data = json.dumps({
        "type": task_type,
        "user_id": "SCHEDULER",
        "scheduled_all_batch": True,
        "batch_id": batch_id,
        "batch_index": task_index,
        "batch_total": len(SCHEDULED_ALL_SYNC_TASKS),
    })
    redis_client.rpush('sync_queue', task_data)
    logger.info(
        "Enqueued scheduled all-sync task %s/%s: %s",
        task_index + 1,
        len(SCHEDULED_ALL_SYNC_TASKS),
        task_type,
    )
    return {"status": "success", "message": f"Queued {task_type}."}


def enqueue_scheduled_all_sync():
    """Starts the daily batch; each completed task queues the next task."""
    from datetime import datetime, timezone

    batch_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    try:
        return _enqueue_scheduled_all_task(batch_id, 0)
    except Exception as e:
        logger.error(f"Failed to start scheduled all-sync batch: {str(e)}")
        return {"status": "error", "message": f"Failed to start scheduled batch: {str(e)}"}


def enqueue_next_scheduled_all_task(task_data):
    """Queues the next task after the current scheduled batch task finishes."""
    return _enqueue_scheduled_all_task(
        task_data['batch_id'],
        int(task_data['batch_index']) + 1,
    )

def sync_owner_wise_data(user_id=None):
    return enqueue_sync_task('owner_wise', user_id)

def sync_process_level_delay_data(user_id=None):
    return enqueue_sync_task('process_delay', user_id)

def sync_outstanding_purchase_order_data(user_id=None):
    return enqueue_sync_task('outstanding_po', user_id)

def sync_stage_level_delay_data(user_id=None):
    return enqueue_sync_task('stage_delay', user_id)

def sync_order_delay_tracking_data(user_id=None):
    return enqueue_sync_task('order_delay_tracking', user_id)

def sync_pending_acceptance_data(user_id=None):
    return enqueue_sync_task('pending_acceptance', user_id)

def sync_rejected_weight_data(user_id=None):
    return enqueue_sync_task('rejected_weight', user_id)


def sync_showroom_wise_order_summary_data(user_id=None):
    return enqueue_sync_task('showroom_wise_order', user_id)

def sync_owner_and_showroom_wise_data(user_id=None):
    """Enqueues the combined Owner Wise + Showroom Wise sync task."""
    return enqueue_sync_task('owner_showroom_combined', user_id)

def sync_provision_stock_status_data(user_id=None):
    return enqueue_sync_task('provision_stock_status', user_id)

def sync_hallmarking_delayed_data(user_id=None):
    return enqueue_sync_task('hallmarking_delayed', user_id)

def sync_qc_delayed_data(user_id=None):
    return enqueue_sync_task('qc_delayed', user_id)

def sync_order_processing_pending_data(user_id=None):
    return enqueue_sync_task('order_processing_pending', user_id)

def sync_supplier_hm_issue_data(user_id=None):
    return enqueue_sync_task('supplier_hm_issue', user_id)

def sync_hm_return_pending_data(user_id=None):
    return enqueue_sync_task('hm_return_pending', user_id)

def sync_hm_qc_issue_pending_data(user_id=None):
    return enqueue_sync_task('hm_qc_issue_pending', user_id)

def sync_supplier_qc_issue_receipt_pending_data(user_id=None):
    return enqueue_sync_task('supplier_qc_issue_receipt_pending', user_id)

def sync_qc_completed_invoice_pending_data(user_id=None):
    return enqueue_sync_task('qc_completed_invoice_pending', user_id)

def sync_qc_completed_invoice_request_pending_data(user_id=None):
    return enqueue_sync_task('qc_completed_invoice_request_pending', user_id)

def sync_invoice_completed_pending_deliver_data(user_id=None):
    return enqueue_sync_task('invoice_completed_pending_deliver', user_id)

def sync_branch_authority_data(user_id=None):
    return enqueue_sync_task('branch_authority', user_id)

def sync_qc_delay_management_data(user_id=None):
    return enqueue_sync_task('qc_delay_management', user_id)

def sync_hm_delay_management_data(user_id=None):
    return enqueue_sync_task('hm_delay_management', user_id)

def sync_qc_receipt_completed_pending_data(user_id=None):
    return enqueue_sync_task('qc_receipt_completed_pending', user_id)

def sync_party_delay_management_data(user_id=None):
    return enqueue_sync_task('party_delay_management', user_id)


def sync_order_fulfillment_aging_matrix_data(user_id=None):
    return enqueue_sync_task('order_fulfillment_aging_matrix', user_id)

def sync_pending_order_details_data(user_id=None):
    return enqueue_sync_task('pending_order_details', user_id)

def sync_active_order_details_data(user_id=None):
    return enqueue_sync_task('active_order_details', user_id)


def sync_size_level_nip_barcode_data(user_id=None):
    return enqueue_sync_task('size_level_nip_barcode', user_id)

def sync_collection_wise_average_delivery_days_data(user_id=None):
    return enqueue_sync_task('collection_wise_average_delivery_days', user_id)


def sync_party_design_average_delivery_days_data(user_id=None):
    return enqueue_sync_task('party_design_average_delivery_days', user_id)
