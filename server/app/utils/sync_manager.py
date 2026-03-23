from app.extensions import redis_client
import json
import logging

logger = logging.getLogger(__name__)

def enqueue_sync_task(task_type):
    """Pushes a sync task to the Redis queue."""
    try:
        task_data = json.dumps({"type": task_type})
        redis_client.rpush('sync_queue', task_data)
        logger.info(f"Enqueued sync task: {task_type}")
        return {"status": "success", "message": "Sync task queued. Check notifications for progress."}
    except Exception as e:
        logger.error(f"Failed to enqueue sync task: {str(e)}")
        return {"status": "error", "message": f"Failed to queue task: {str(e)}"}

def sync_owner_wise_data():
    return enqueue_sync_task('owner_wise')

def sync_process_level_delay_data():
    return enqueue_sync_task('process_delay')

def sync_outstanding_purchase_order_data():
    return enqueue_sync_task('outstanding_po')

def sync_stage_level_delay_data():
    return enqueue_sync_task('stage_delay')

def sync_order_delay_tracking_data():
    return enqueue_sync_task('order_delay_tracking')

def sync_pending_acceptance_data():
    return enqueue_sync_task('pending_acceptance')

def sync_rejected_weight_data():
    return enqueue_sync_task('rejected_weight')

def sync_provision_allocation_data():
    return enqueue_sync_task('provision_allocation')

def sync_showroom_wise_order_summary_data():
    return enqueue_sync_task('showroom_wise_order')

def sync_owner_and_showroom_wise_data():
    """Enqueues the combined Owner Wise + Showroom Wise sync task."""
    return enqueue_sync_task('owner_showroom_combined')
