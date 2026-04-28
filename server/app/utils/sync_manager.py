from app.extensions import redis_client
import json
import logging

logger = logging.getLogger(__name__)

def enqueue_sync_task(task_type, user_id=None):
    """Pushes a sync task to the Redis queue."""
    try:
        task_data = json.dumps({"type": task_type, "user_id": user_id})
        redis_client.rpush('sync_queue', task_data)
        logger.info(f"Enqueued sync task: {task_type}")
        return {"status": "success", "message": "Sync task queued. Check notifications for progress."}
    except Exception as e:
        logger.error(f"Failed to enqueue sync task: {str(e)}")
        return {"status": "error", "message": f"Failed to queue task: {str(e)}"}

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

def sync_invoice_completed_pending_deliver_data(user_id=None):
    return enqueue_sync_task('invoice_completed_pending_deliver', user_id)

def sync_branch_authority_data(user_id=None):
    return enqueue_sync_task('branch_authority', user_id)
