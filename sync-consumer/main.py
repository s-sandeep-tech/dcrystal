import time
import json
import logging
import threading
from app import create_app
from app.extensions import redis_client
from app.utils.sync_tasks import (
    sync_owner_wise_data_task,
    sync_process_level_delay_data_task,
    sync_outstanding_purchase_order_data_task,
    sync_stage_level_delay_data_task,
    sync_order_delay_tracking_data_task,
    sync_pending_acceptance_data_task,
    sync_rejected_weight_data_task,
    sync_provision_allocation_summary_task,
    sync_showroom_wise_order_summary_task,
    emit_sync_update
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncConsumer")

app = create_app()

# ─────────────────────────────────────────────────────────────────────────────
# Sync Queue Worker (original behaviour — unchanged)
# ─────────────────────────────────────────────────────────────────────────────
def process_sync_queue():
    logger.info("Sync Consumer started. Waiting for sync tasks...")

    while True:
        try:
            _, task_data_json = redis_client.blpop('sync_queue')

            task_data = json.loads(task_data_json)
            task_type = task_data.get('type')

            logger.info(f"[sync_queue] Processing task: {task_type}")

            with app.app_context():
                if task_type == 'owner_wise':
                    sync_owner_wise_data_task()
                elif task_type == 'process_delay':
                    sync_process_level_delay_data_task()
                elif task_type == 'outstanding_po':
                    sync_outstanding_purchase_order_data_task()
                elif task_type == 'stage_delay':
                    sync_stage_level_delay_data_task()
                elif task_type == 'order_delay_tracking':
                    sync_order_delay_tracking_data_task()
                elif task_type == 'pending_acceptance':
                    sync_pending_acceptance_data_task()
                elif task_type == 'rejected_weight':
                    sync_rejected_weight_data_task()
                elif task_type == 'provision_allocation':
                    sync_provision_allocation_summary_task()
                elif task_type == 'showroom_wise_order':
                    sync_showroom_wise_order_summary_task()
                else:
                    logger.error(f"Unknown sync task type: {task_type}")
                    emit_sync_update('error', f'Unknown task type: {task_type}')

            logger.info(f"[sync_queue] Task {task_type} completed.")

        except Exception as e:
            logger.error(f"Error in sync consumer loop: {str(e)}")
            time.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# Export Queue Worker (handles background Excel export jobs)
# ─────────────────────────────────────────────────────────────────────────────
def process_export_queue():
    logger.info("Export Consumer started. Waiting for export tasks...")

    while True:
        try:
            _, task_data_json = redis_client.blpop('export_queue')

            task_data = json.loads(task_data_json)
            task_type = task_data.get('type')

            logger.info(f"[export_queue] Processing task: {task_type}")

            with app.app_context():
                if task_type == 'export_opo':
                    _handle_export_opo(task_data)
                else:
                    logger.error(f"Unknown export task type: {task_type}")

            logger.info(f"[export_queue] Task {task_type} completed.")

        except Exception as e:
            logger.error(f"Error in export consumer loop: {str(e)}")
            time.sleep(5)


def _handle_export_opo(task_data: dict):
    """Generate Outstanding PO Excel export and push a download notification."""
    from datetime import datetime, timezone, timedelta
    from app.models import Notification
    from app.extensions import db, socketio
    from app.utils.export_service import generate_outstanding_po_export

    filters = task_data.get('filters', {})

    try:
        filename = generate_outstanding_po_export(filters)
        download_url = f'/exports/download/{filename}'

        notification = Notification(
            title='Export Ready — Outstanding PO',
            message='Success! Your Outstanding Purchase Order Excel file is ready. Open the notification window and click Download to download your file.',
            notification_type='success',
            icon='download',
            priority='high',
            user_id=task_data.get('user_id'), # Targeted to the user who started the export
            created_at=datetime.utcnow(),
            is_read=False,
            action_url=download_url
        )
        db.session.add(notification)
        db.session.commit()

        IST = timezone(timedelta(hours=5, minutes=30))
        time_ago = notification.get_time_ago()

        socket_id = task_data.get('socket_id')
        socketio_payload = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'icon': notification.icon,
            'priority': notification.priority,
            'time': time_ago,
            'related_order_id': None,
            'action_url': download_url,
            'socket_id': socket_id,
            'user_id': task_data.get('user_id')
        }
        
        # 1. Internal SocketIO emit
        socketio.emit('new_notification', socketio_payload)

        # 2. Bridge to Node.js socket server via Redis
        redis_client.publish('global_notifications', json.dumps(socketio_payload))

        logger.info(f"Export notification sent for file: {filename}")

    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        # Push error notification to users
        try:
            with app.app_context():
                notification = Notification(
                    title='Export Failed',
                    message=f'Outstanding PO export could not be generated. Please try again.',
                    notification_type='error',
                    icon='error',
                    priority='high',
                    related_order_id=None,
                    user_id=task_data.get('user_id'),
                    created_at=datetime.utcnow(),
                    is_read=False
                )
                db.session.add(notification)
                db.session.commit()
                
                err_payload = {
                    'id': notification.id,
                    'title': notification.title,
                    'message': notification.message,
                    'type': 'error',
                    'icon': 'error',
                    'priority': 'high',
                    'time': 'Just now',
                    'action_url': None,
                    'socket_id': task_data.get('socket_id')
                }
                
                socketio.emit('new_notification', err_payload)
                redis_client.publish('global_notifications', json.dumps(err_payload))
        except Exception as inner_e:
            logger.error(f"Failed to send error notification: {inner_e}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point — run both workers in separate threads
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sync_thread = threading.Thread(target=process_sync_queue, daemon=True, name="SyncWorker")
    export_thread = threading.Thread(target=process_export_queue, daemon=True, name="ExportWorker")

    sync_thread.start()
    export_thread.start()

    logger.info("Both sync and export workers started.")

    # Keep the main thread alive
    sync_thread.join()
    export_thread.join()
