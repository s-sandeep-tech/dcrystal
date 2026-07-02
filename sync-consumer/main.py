import time
import json
import logging
import threading
import sys
import os

# DEFENSIVE: Explicitly manage the search path
base_dir = os.path.abspath(os.path.dirname(__file__))
server_dir = os.path.join(base_dir, 'server')

# Prioritize the server directory which contains the 'app' package
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

# Ensure the working directory is also in path but at lower priority
if base_dir not in sys.path:
    sys.path.append(base_dir)

# Clear any shadowed or stale 'app' module from cache
if 'app' in sys.modules:
    del sys.modules['app']

try:
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
        sync_showroom_wise_order_summary_task,
        sync_owner_and_showroom_wise_task,
        sync_provision_stock_status_data_task,
        sync_hallmarking_delayed_data_task,
        sync_qc_delayed_data_task,
        sync_order_processing_pending_data_task,
        sync_hm_completed_return_data_task,
        sync_supplier_hm_issue_data_task,
        sync_hm_return_qc_issue_data_task,
        sync_supplier_qc_issue_receipt_pending_data_task,
        sync_qc_completed_invoice_pending_data_task,
        sync_invoice_completed_pending_deliver_data_task,
        sync_branch_authority_data_task,
        sync_qc_delay_management_data_task,
        sync_hm_delay_management_data_task,
        sync_qc_receipt_completed_pending_data_task,
        sync_qc_completed_invoice_request_pending_data_task,
        sync_party_delay_management_data_task,
        sync_order_fulfillment_aging_matrix_task,
        sync_pending_order_details_task,
        emit_sync_update
    )
    from apscheduler.schedulers.background import BackgroundScheduler
    from app.utils.sync_manager import enqueue_sync_task, sync_pending_order_details_data

    from app.utils.sync_manager import sync_order_fulfillment_aging_matrix_data
except Exception as e:
    # We can't log to the logger yet as it's defined later, but we can print
    print(f"CRITICAL IMPORT ERROR: {str(e)}")
    raise e

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SyncConsumer")

flask_app = create_app()

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
            user_id = task_data.get('user_id')

            logger.info(f"[sync_queue] Processing task: {task_type}")

            with flask_app.app_context():
                from app.models.core import SyncLog
                from app.extensions import db
                from datetime import datetime
                import time
                
                sync_log = SyncLog(
                    task_name=task_type,
                    status='processing',
                    start_time=datetime.utcnow(),
                    initiated_by=str(user_id) if user_id else None
                )
                db.session.add(sync_log)
                db.session.commit()
                
                start_t = time.time()
                res = None
                try:
                    if task_type == 'owner_wise':
                        res = sync_owner_wise_data_task()
                    elif task_type == 'process_delay':
                        res = sync_process_level_delay_data_task()
                    elif task_type == 'outstanding_po':
                        res = sync_outstanding_purchase_order_data_task()
                    elif task_type == 'stage_delay':
                        res = sync_stage_level_delay_data_task()
                    elif task_type == 'order_delay_tracking':
                        res = sync_order_delay_tracking_data_task()
                    elif task_type == 'pending_acceptance':
                        res = sync_pending_acceptance_data_task()
                    elif task_type == 'rejected_weight':
                        res = sync_rejected_weight_data_task()
                    elif task_type == 'showroom_wise_order':
                        res = sync_showroom_wise_order_summary_task()
                    elif task_type == 'owner_showroom_combined':
                        max_retries = 5
                        for attempt in range(max_retries):
                            try:
                                res = sync_owner_and_showroom_wise_task()
                            except Exception as retry_error:
                                res = {"status": "error", "message": str(retry_error)}

                            if res and res.get('status') == 'success':
                                break

                            if attempt < max_retries - 1:
                                retry_msg = f"Task {task_type} failed (Attempt {attempt + 1}/{max_retries}). Retrying in 5s..."
                                logger.warning(retry_msg)
                                emit_sync_update('processing', retry_msg, data_type=task_type)
                                time.sleep(5)
                    elif task_type == 'provision_stock_status':
                        res = sync_provision_stock_status_data_task()
                    elif task_type == 'hallmarking_delayed':
                        res = sync_hallmarking_delayed_data_task()
                    elif task_type == 'qc_delayed':
                        res = sync_qc_delayed_data_task()
                    elif task_type == 'order_processing_pending':
                        res = sync_order_processing_pending_data_task()
                    elif task_type == 'supplier_hm_issue':
                        res = sync_supplier_hm_issue_data_task()
                    elif task_type == 'hm_return_pending':
                        res = sync_hm_completed_return_data_task()
                    elif task_type == 'hm_qc_issue_pending':
                        res = sync_hm_return_qc_issue_data_task()
                    elif task_type == 'supplier_qc_issue_receipt_pending':
                        res = sync_supplier_qc_issue_receipt_pending_data_task()
                    elif task_type == 'qc_completed_invoice_pending':
                        # Special retry logic: 10 attempts with 5s delay and UI updates
                        max_retries = 10
                        for attempt in range(max_retries):
                            res = sync_qc_completed_invoice_pending_data_task()
                            if res.get('status') == 'success':
                                break
                            
                            if attempt < max_retries - 1:
                                retry_msg = f"Task {task_type} failed (Attempt {attempt + 1}/{max_retries}). Retrying in 5s..."
                                logger.warning(retry_msg)
                                # Update UI via SocketIO
                                emit_sync_update('processing', retry_msg, data_type=task_type)
                                time.sleep(5)
                    elif task_type == 'qc_completed_invoice_request_pending':
                        res = sync_qc_completed_invoice_request_pending_data_task()
                    elif task_type == 'invoice_completed_pending_deliver':
                        res = sync_invoice_completed_pending_deliver_data_task()
                    elif task_type == 'branch_authority':
                        res = sync_branch_authority_data_task()
                    elif task_type == 'qc_delay_management':
                        res = sync_qc_delay_management_data_task()
                    elif task_type == 'hm_delay_management':
                        res = sync_hm_delay_management_data_task()
                    elif task_type == 'qc_receipt_completed_pending':
                        res = sync_qc_receipt_completed_pending_data_task()
                    elif task_type == 'party_delay_management':
                        res = sync_party_delay_management_data_task()
                    elif task_type == 'order_fulfillment_aging_matrix':
                        res = sync_order_fulfillment_aging_matrix_task()
                    elif task_type == 'pending_order_details':
                        res = sync_pending_order_details_task()
                    else:
                        logger.error(f"Unknown sync task type: {task_type}")

                        emit_sync_update('error', f'Unknown task type: {task_type}')
                        res = {"status": "error", "message": f"Unknown task type: {task_type}"}
                        
                        
                    sync_log.end_time = datetime.utcnow()
                    sync_log.duration = time.time() - start_t
                    if res and res.get('status') == 'success':
                        sync_log.status = 'success'
                        # Handle combined task response with multiple counts
                        if task_type == 'owner_showroom_combined':
                            sync_log.details = {"owner_count": res.get("owner_count"), "showroom_count": res.get("showroom_count")}
                        else:
                            sync_log.details = {"count": res.get("count")}
                    else:
                        sync_log.status = 'error'
                        sync_log.details = {"error": res.get("message") if res else "Unknown error"}
                        
                    db.session.commit()
                except Exception as e:
                    sync_log.end_time = datetime.utcnow()
                    sync_log.duration = time.time() - start_t
                    sync_log.status = 'error'
                    sync_log.details = {"error": str(e)}
                    db.session.commit()
                    raise e

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

            with flask_app.app_context():
                if task_type == 'export_opo':
                    _handle_export_opo(task_data)
                elif task_type == 'export_pending_acceptance':
                    _handle_export_pending_acceptance(task_data)
                elif task_type == 'export_provision_allocation':
                    _handle_export_provision_allocation(task_data)
                elif task_type == 'export_location_physical_stock_status':
                    _handle_export_location_physical_stock_status(task_data)
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
            with flask_app.app_context():
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


def _handle_export_pending_acceptance(task_data: dict):
    """Generate Pending Acceptance Excel export and push a download notification."""
    from datetime import datetime, timezone, timedelta
    from app.models import Notification
    from app.extensions import db, socketio
    from app.utils.export_service import generate_pending_acceptance_export

    filters = task_data.get('filters', {})

    try:
        filename = generate_pending_acceptance_export(filters)
        download_url = f'/exports/download/{filename}'

        notification = Notification(
            title='Export Ready — Pending Acceptance Feedback',
            message='Success! Your Pending Acceptance Feedback Excel file is ready. Open the notification window and click Download to download your file.',
            notification_type='success',
            icon='download',
            priority='high',
            user_id=task_data.get('user_id'),
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
        logger.error(f"Pending Acceptance export failed: {str(e)}")
        try:
            with flask_app.app_context():
                notification = Notification(
                    title='Export Failed — Pending Acceptance',
                    message=f'Pending Acceptance export could not be generated. Please try again.',
                    notification_type='error',
                    icon='error',
                    priority='high',
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


def _handle_export_provision_allocation(task_data: dict):
    """Generate Provision Allocation Summary Excel export and push a download notification."""
    from datetime import datetime, timezone, timedelta
    from app.models import Notification
    from app.extensions import db, socketio
    from app.utils.export_service import generate_provision_allocation_export

    filters = task_data.get('filters', {})

    try:
        filename = generate_provision_allocation_export(filters)
        download_url = f'/exports/download/{filename}'

        notification = Notification(
            title='Export Ready — Provision Allocation Summary',
            message='Success! Your Provision Allocation Summary Excel file is ready. Open the notification window and click Download to download your file.',
            notification_type='success',
            icon='download',
            priority='high',
            user_id=task_data.get('user_id'),
            created_at=datetime.utcnow(),
            is_read=False,
            action_url=download_url
        )
        db.session.add(notification)
        db.session.commit()

        socket_id = task_data.get('socket_id')
        socketio_payload = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'icon': notification.icon,
            'priority': notification.priority,
            'time': notification.get_time_ago(),
            'related_order_id': None,
            'action_url': download_url,
            'socket_id': socket_id,
            'user_id': task_data.get('user_id')
        }
        
        # 1. Internal SocketIO emit
        socketio.emit('new_notification', socketio_payload)

        # 2. Bridge to Node.js socket server via Redis
        redis_client.publish('global_notifications', json.dumps(socketio_payload))

        logger.info(f"Provision allocation export notification sent for file: {filename}")

    except Exception as e:
        logger.error(f"Provision allocation export failed: {str(e)}")
        try:
            with flask_app.app_context():
                notification = Notification(
                    title='Export Failed — Provision Allocation Summary',
                    message=f'Provision Allocation Summary export could not be generated. Please try again.',
                    notification_type='error',
                    icon='error',
                    priority='high',
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


def _handle_export_location_physical_stock_status(task_data: dict):
    """Generate Location Physical Stock Status Excel export and push a download notification."""
    from datetime import datetime, timezone, timedelta
    from app.models import Notification
    from app.extensions import db, socketio
    from app.utils.export_service import generate_location_physical_stock_status_export

    filters = task_data.get('filters', {})

    try:
        filename = generate_location_physical_stock_status_export(filters)
        download_url = f'/exports/download/{filename}'

        notification = Notification(
            title='Export Ready — Location Physical Stock Status',
            message='Success! Your Location Physical Stock Status Excel file is ready. Open the notification window and click Download to download your file.',
            notification_type='success',
            icon='download',
            priority='high',
            user_id=task_data.get('user_id'),
            created_at=datetime.utcnow(),
            is_read=False,
            action_url=download_url
        )
        db.session.add(notification)
        db.session.commit()

        socket_id = task_data.get('socket_id')
        socketio_payload = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'icon': notification.icon,
            'priority': notification.priority,
            'time': notification.get_time_ago(),
            'related_order_id': None,
            'action_url': download_url,
            'socket_id': socket_id,
            'user_id': task_data.get('user_id')
        }
        
        # 1. Internal SocketIO emit
        socketio.emit('new_notification', socketio_payload)

        # 2. Bridge to Node.js socket server via Redis
        redis_client.publish('global_notifications', json.dumps(socketio_payload))

        logger.info(f"Location physical stock status export notification sent for file: {filename}")

    except Exception as e:
        logger.error(f"Location physical stock status export failed: {str(e)}")
        try:
            with flask_app.app_context():
                notification = Notification(
                    title='Export Failed — Location Physical Stock Status',
                    message=f'Location Physical Stock Status export could not be generated. Please try again.',
                    notification_type='error',
                    icon='error',
                    priority='high',
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
# Automated Scheduler setup
# ─────────────────────────────────────────────────────────────────────────────
def setup_scheduler():
    """Initializes and starts the background scheduler for automated tasks."""
    from datetime import timezone as datetime_timezone, timedelta
    IST = datetime_timezone(timedelta(hours=5, minutes=30))
    scheduler = BackgroundScheduler(timezone=IST)

    # Schedule "Provision & Stock Status Sync" every day at 11 AM IST
    # Task type 'provision_stock_status' matches sync_manager.py
    scheduler.add_job(
        func=enqueue_sync_task,
        trigger='cron',
        hour=11,
        minute=0,
        args=['provision_stock_status'],
        id='daily_provision_stock_sync',
        replace_existing=True
    )

    # Schedule "Branch Authority Sync" every day at 10:00 AM and 4:00 PM IST
    # Task type 'branch_authority' matches sync_manager.py
    scheduler.add_job(
        func=enqueue_sync_task,
        trigger='cron',
        hour='10,16',
        minute=0,
        args=['branch_authority'],
        id='branch_authority_sync',
        replace_existing=True
    )

    # Schedule "QC Delay Summary Sync" every day at 9:00 AM IST
    scheduler.add_job(
        func=enqueue_sync_task,
        trigger='cron',
        hour=9,
        minute=0,
        args=['qc_delay_management'],
        id='qc_delay_management_sync',
        replace_existing=True
    )

    # Schedule "HM Delay Management Sync" every day at 9:05 AM IST (5-min gap)
    scheduler.add_job(
        func=enqueue_sync_task,
        trigger='cron',
        hour=9,
        minute=5,
        args=['hm_delay_management'],
        id='hm_delay_management_sync',
        replace_existing=True
    )

    # Schedule "Vendor Delay Management Sync" every day at 9:10 AM IST (5-min gap)
    scheduler.add_job(
        func=enqueue_sync_task,
        trigger='cron',
        hour=9,
        minute=10,
        args=['party_delay_management'],
        id='party_delay_management_sync',
        replace_existing=True
    )

    # Schedule "Owner & Showroom Wise Order Summary Sync" daily at 10:30 AM and 2:30 PM IST
    # Task type 'owner_showroom_combined' matches sync_manager.py
    scheduler.add_job(
        func=enqueue_sync_task,
        trigger='cron',
        hour='10,14',
        minute=30,
        args=['owner_showroom_combined'],
        id='owner_showroom_sync',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Background Scheduler started. 'Provision & Stock Status Sync' scheduled for 11:00 IST daily.")
    logger.info("Branch Authority Sync scheduled for 10:00 IST and 16:00 IST daily.")
    logger.info("Owner & Showroom Wise Order Summary Sync scheduled for 10:30 IST and 14:30 IST daily.")
    logger.info("QC Delay Summary Sync scheduled for 9:00 IST daily.")
    logger.info("HM Delay Management Sync scheduled for 9:05 IST daily.")
    logger.info("Vendor Delay Management Sync scheduled for 9:10 IST daily.")

# ─────────────────────────────────────────────────────────────────────────────
# Entry point — run workers and scheduler
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start the automated scheduler
    setup_scheduler()

    sync_thread = threading.Thread(target=process_sync_queue, daemon=True, name="SyncWorker")
    export_thread = threading.Thread(target=process_export_queue, daemon=True, name="ExportWorker")

    sync_thread.start()
    export_thread.start()

    logger.info("Both sync and export workers started.")

    # Keep the main thread alive
    sync_thread.join()
    export_thread.join()
