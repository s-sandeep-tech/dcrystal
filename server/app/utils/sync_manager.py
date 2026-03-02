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
