from flask import render_template, session, redirect, url_for, request, current_app
from app.dashboard import dashboard_bp
from app.models import Order, DashboardStats, Notification, User
from app.extensions import db
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.utils.decorators import require_perm
from app.models.rbac import Menu
import json

@dashboard_bp.route('/my_account')
def my_account():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('dashboard.login'))
        
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return redirect(url_for('dashboard.login'))
        
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    return render_template('my_account.html', 
                         user=user,
                         unread_count=unread_count,
                         sync_time=sync_time)

@dashboard_bp.route('/settings')
def settings():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('dashboard.login'))
        
    from app.extensions import redis_client
    redis_status = False
    try:
        redis_status = redis_client.ping()
    except Exception:
        redis_status = False
        
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    
    return render_template('settings.html',
                         redis_status=redis_status,
                         is_admin='ADMIN' in session.get('roles', []),
                         is_data_sync_user='DATA_SYNC_USER' in session.get('roles', []),
                         unread_count=unread_count,
                         sync_time=sync_time)

@dashboard_bp.route('/settings/sync-data', methods=['POST'])
def sync_data():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_owner_wise_data
    result = sync_owner_wise_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-owner-showroom', methods=['POST'])
def sync_owner_and_showroom_wise():
    """Enqueues the combined Owner Wise + Showroom Wise Order Summary sync task."""
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401

    from app.utils.sync_manager import sync_owner_and_showroom_wise_data
    result = sync_owner_and_showroom_wise_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-process-delay', methods=['POST'])
def sync_process_delay():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_process_level_delay_data
    result = sync_process_level_delay_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-outstanding-po', methods=['POST'])
def sync_outstanding_po():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_outstanding_purchase_order_data
    result = sync_outstanding_purchase_order_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-stage-delay', methods=['POST'])
def sync_stage_delay():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_stage_level_delay_data
    result = sync_stage_level_delay_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-order-delay', methods=['POST'])
def sync_order_delay():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_order_delay_tracking_data
    result = sync_order_delay_tracking_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-pending-acceptance', methods=['POST'])
def sync_pending_acceptance():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_pending_acceptance_data
    result = sync_pending_acceptance_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-hallmarking-delayed', methods=['POST'])
def sync_hallmarking_delayed():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_hallmarking_delayed_data
    result = sync_hallmarking_delayed_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-qc-delayed', methods=['POST'])
def sync_qc_delayed():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_qc_delayed_data
    result = sync_qc_delayed_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-rejected-weight', methods=['POST'])
def sync_rejected_weight():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_rejected_weight_data
    result = sync_rejected_weight_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-provision-allocation', methods=['POST'])
def settings_sync_provision_allocation():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_provision_allocation_data
    result = sync_provision_allocation_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-provision-stock-status', methods=['POST'])
def settings_sync_provision_stock_status():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    from app.utils.sync_manager import sync_provision_stock_status_data
    result = sync_provision_stock_status_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500
@dashboard_bp.route('/settings/sync-order-processing-pending', methods=['POST'])
def settings_sync_order_processing_pending():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
    from app.utils.sync_manager import sync_order_processing_pending_data
    result = sync_order_processing_pending_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-supplier-hm-issue', methods=['POST'])
def settings_sync_supplier_hm_issue():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    from app.utils.sync_manager import sync_supplier_hm_issue_data
    result = sync_supplier_hm_issue_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-hm-return-pending', methods=['POST'])
def settings_sync_hm_return_pending():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    from app.utils.sync_manager import sync_hm_return_pending_data
    result = sync_hm_return_pending_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-hm-qc-issue-pending', methods=['POST'])
def settings_sync_hm_qc_issue_pending():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    from app.utils.sync_manager import sync_hm_qc_issue_pending_data
    result = sync_hm_qc_issue_pending_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-supplier-qc-issue-receipt', methods=['POST'])
def settings_sync_supplier_qc_issue_receipt():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    from app.utils.sync_manager import sync_supplier_qc_issue_receipt_pending_data
    result = sync_supplier_qc_issue_receipt_pending_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-qc-completed-invoice', methods=['POST'])
def settings_sync_qc_completed_invoice():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    from app.utils.sync_manager import sync_qc_completed_invoice_pending_data
    result = sync_qc_completed_invoice_pending_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-branch-authority', methods=['POST'])
def settings_sync_branch_authority():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    from app.utils.sync_manager import sync_branch_authority_data
    result = sync_branch_authority_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-invoice-completed-deliver', methods=['POST'])
def settings_sync_invoice_completed_deliver():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    from app.utils.sync_manager import sync_invoice_completed_pending_deliver_data
    result = sync_invoice_completed_pending_deliver_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500

@dashboard_bp.route('/settings/sync-qc-delay-management', methods=['POST'])
def settings_sync_qc_delay_management():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    from app.utils.sync_manager import sync_qc_delay_management_data
    result = sync_qc_delay_management_data(session.get('user_id'))
    return result, 200 if result.get('status') == 'success' else 500


@dashboard_bp.route('/settings/clear-cache', methods=['POST'])
def clear_cache():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized: Admin or Data Sync role required"}, 401
        
    try:
        from app.extensions import redis_client
        redis_client.flushdb()
        
        # Publish notification for UI feedback across sessions
        import json
        payload = {
            "title": "Cache Cleared",
            "message": "Application cache has been successfully cleared.",
            "type": "success"
        }
        redis_client.publish('global_notifications', json.dumps(payload))
        
        return {"status": "success", "message": "Cache cleared successfully"}, 200
    except Exception as e:
        current_app.logger.error(f"Failed to clear cache: {e}")
        return {"status": "error", "message": str(e)}, 500

@dashboard_bp.route('/settings/notifications')
def get_settings_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return {"status": "error", "message": "Unauthorized"}, 401
    
    # Notifications can be user-specific or global (user_id is NULL)
    notifications = Notification.query.filter(
        (Notification.user_id == user_id) | (Notification.user_id == None)
    ).order_by(Notification.created_at.desc()).all()
    
    return {
        "status": "success",
        "notifications": [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'notification_type': n.notification_type,
            'icon': n.icon,
            'priority': n.priority,
            'is_read': n.is_read,
            'action_url': n.action_url,
            'created_at': n.created_at.isoformat() + 'Z',
            'time_ago': n.get_time_ago()
        } for n in notifications]
    }


@dashboard_bp.route('/settings/sync-logs')
def get_sync_logs():
    if not session.get('user_id') or ('ADMIN' not in session.get('roles', []) and 'DATA_SYNC_USER' not in session.get('roles', [])):
        return {"status": "error", "message": "Unauthorized"}, 401
    
    from app.models.core import SyncLog
    from app.models.auth import User
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    pagination = SyncLog.query.order_by(SyncLog.start_time.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    user_ids = [log.initiated_by for log in pagination.items if log.initiated_by]
    users_dict = {}
    if user_ids:
        users = User.query.filter(User.user_id.in_(user_ids)).all()
        users_dict = {u.user_id: u.username for u in users}
        
    logs_data = []
    for log in pagination.items:
        log_dict = log.to_dict()
        if log.initiated_by and log.initiated_by in users_dict:
            log_dict['initiated_by'] = f"{users_dict[log.initiated_by]} ({log.initiated_by})"
        logs_data.append(log_dict)
    
    return {
        "status": "success",
        "logs": logs_data,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    }

@dashboard_bp.route('/')
@require_perm('dashboard.view')
def index():

    # Fetch stats (take the first record or create dummy)
    stats = DashboardStats.query.first()
    if not stats:
        stats = DashboardStats(
            active_orders=2840,
            critical_delay=142,
            sla_compliance=96.8,
            avg_response_time="1.4h"
        )
        db.session.add(stats)
        db.session.commit()

    # Fetch orders (ensure we have the full sample set for demo)
    if Order.query.count() != 5:
        # Clear existing if any to avoid duplicates or incomplete sets
        Order.query.delete()
        dummy_orders = [
            Order(
                order_id="#ORD-82910",
                priority="P1 - Urgent",
                collection_type="Winter Essentials",
                sub_type="Retail / High Volume",
                origin="NYC",
                destination="BER",
                risk_level=80,
                status="In Customs",
                sla_timer="04:22:10"
            ),
            Order(
                order_id="#ORD-82911",
                priority="P3 - Routine",
                collection_type="Spring Footwear",
                sub_type="Apparel / Standard",
                origin="SFO",
                destination="LON",
                risk_level=20,
                status="Cleared",
                sla_timer="00:00:00"
            ),
            Order(
                order_id="#ORD-82912",
                priority="P2 - High",
                collection_type="Summer Trends",
                sub_type="Fashion / Fast Moving",
                origin="PAR",
                destination="TOK",
                risk_level=55,
                status="Logistics",
                sla_timer="12:45:00"
            ),
            Order(
                order_id="#ORD-82913",
                priority="P1 - Urgent",
                collection_type="Tech Gadgets",
                sub_type="Electronics / Fragile",
                origin="SHZ",
                destination="LAX",
                risk_level=92,
                status="Manual Review",
                sla_timer="02:15:30"
            ),
            Order(
                order_id="#ORD-82914",
                priority="P3 - Routine",
                collection_type="Home Decor",
                sub_type="Furniture / Bulk",
                origin="HAM",
                destination="SYD",
                risk_level=15,
                status="Cleared",
                sla_timer="00:00:00"
            )
        ]
        db.session.add_all(dummy_orders)
        db.session.commit()
    
    orders = Order.query.all()

    # Initialize notifications if none exist
    if Notification.query.count() == 0:
        now = datetime.utcnow()
        dummy_notifications = [
            # Success notifications
            Notification(
                title="Order Cleared Successfully",
                message="Order #ORD-82911 has been cleared and is ready for shipment.",
                notification_type="success",
                icon="check_circle",
                priority="low",
                related_order_id="#ORD-82911",
                created_at=now - timedelta(minutes=2),
                is_read=False
            ),
            Notification(
                title="SLA Compliance Achieved",
                message="All orders in the EMEA region met SLA targets this hour.",
                notification_type="success",
                icon="verified",
                priority="medium",
                created_at=now - timedelta(hours=3),
                is_read=True
            ),
            # Warning notifications
            Notification(
                title="Customs Delay on #ORD-82910",
                message="Flagged for manual review in BER. Expected delay: 4-6 hours.",
                notification_type="warning",
                icon="warning",
                priority="high",
                related_order_id="#ORD-82910",
                created_at=now - timedelta(minutes=5),
                is_read=False
            ),
            Notification(
                title="Approaching SLA Deadline",
                message="Order #ORD-82912 has 2 hours remaining before SLA breach.",
                notification_type="warning",
                icon="schedule",
                priority="high",
                related_order_id="#ORD-82912",
                created_at=now - timedelta(minutes=45),
                is_read=False
            ),
            Notification(
                title="Weather Alert - Tokyo",
                message="Severe weather may impact deliveries to TOK region.",
                notification_type="warning",
                icon="cloud",
                priority="medium",
                created_at=now - timedelta(hours=2),
                is_read=True
            ),
            # Error notifications
            Notification(
                title="Manual Review Required",
                message="High risk profile detected on #ORD-82913. Immediate action needed.",
                notification_type="error",
                icon="error",
                priority="high",
                related_order_id="#ORD-82913",
                created_at=now - timedelta(minutes=15),
                is_read=False
            ),
            Notification(
                title="Critical SLA Breach",
                message="Order #ORD-82908 has exceeded SLA by 6 hours.",
                notification_type="error",
                icon="report_problem",
                priority="high",
                created_at=now - timedelta(hours=1),
                is_read=False
            ),
            # Info notifications
            Notification(
                title="System Update Completed",
                message="Dashboard analytics engine upgraded to v2.4.1.",
                notification_type="info",
                icon="info",
                priority="low",
                created_at=now - timedelta(hours=4),
                is_read=True
            ),
            Notification(
                title="Configuration Change",
                message="SLA threshold updated from 18h to 24h for bulk orders.",
                notification_type="info",
                icon="settings",
                priority="medium",
                created_at=now - timedelta(hours=1),
                is_read=True
            ),
            Notification(
                title="New Team Member Added",
                message="Sarah Johnson joined Compliance EMEA team.",
                notification_type="info",
                icon="person_add",
                priority="low",
                created_at=now - timedelta(hours=5),
                is_read=True
            ),
            # Alert notifications
            Notification(
                title="SLA Threshold Peak",
                message="APAC region experiencing response time bottleneck. 12 orders affected.",
                notification_type="alert",
                icon="notifications_active",
                priority="high",
                created_at=now - timedelta(minutes=30),
                is_read=False
            ),
            Notification(
                title="Unusual Activity Detected",
                message="Spike in manual review requests from SHZ origin (3x normal).",
                notification_type="alert",
                icon="security",
                priority="high",
                created_at=now - timedelta(hours=2),
                is_read=False
            ),
        ]
        db.session.add_all(dummy_notifications)
        db.session.commit()

    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")

    return render_template('index.html', 
                         stats=stats, 
                         orders=orders, 
                         unread_count=unread_count,
                         sync_time=sync_time)

@dashboard_bp.route('/upload-file', methods=['POST'])
def upload_file():
    if 'ADMIN' not in session.get('roles', []):
        return {"error": "Unauthorized"}, 403
        
    if 'file' not in request.files:
        return {"error": "No file part"}, 400
        
    file = request.files['file']
    if file.filename == '':
        return {"error": "No selected file"}, 400
        
    if file:
        import os
        # Use UPLOAD_FOLDER env var for Docker-friendly configuration; default to /app/uploads
        upload_folder = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
        try:
            os.makedirs(upload_folder, exist_ok=True)
        except Exception as e:
            current_app.logger.error(f"Failed to create upload folder {upload_folder}: {str(e)}")
            return {"error": f"Failed to create upload directory: {str(e)}"}, 500

        file_path = os.path.join(upload_folder, file.filename)
        try:
            file.save(file_path)
            current_app.logger.info(f"File {file.filename} uploaded successfully to {file_path}")
            return {"message": f"File {file.filename} uploaded successfully"}, 200
        except Exception as e:
            current_app.logger.error(f"Failed to save file {file.filename} to {file_path}: {str(e)}")
            return {"error": f"Failed to save file: {str(e)}"}, 500

@dashboard_bp.route('/login')
def login():
    return render_template('login.html')

@dashboard_bp.route('/inventory')
def inventory():
    if not session.get('user_id'):
        return redirect(url_for('dashboard.login'))

    from app.models import Notification
    unread_count = Notification.query.filter_by(is_read=False).count()
    sync_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
    return render_template('inventory.html', 
                         unread_count=unread_count,
                         sync_time=sync_time,
                         stats={},
                         rows=[],
                         pagination=None,
                         footer_totals={})
@dashboard_bp.route('/logout-success')
def logout_success():
    return render_template('logout_success.html')

@dashboard_bp.before_request
def check_report_offline():
    from flask import request, session, redirect, url_for
    import json
    
    # Exclude certain routes from being blocked by the "Report Offline" feature
    excluded_endpoints = [
        'dashboard.report_offline',
        'dashboard.login',
        'dashboard.logout',
        'dashboard.settings',
        'dashboard.get_report_offline_status',
        'dashboard.toggle_report_offline',
        'static'
    ]
    
    if request.endpoint in excluded_endpoints or request.endpoint is None:
        return
        
    # Check if user is an admin - administrators are exempt
    user_roles = session.get('roles', [])
    if 'ADMIN' in user_roles:
        return
        
    # Check current path/endpoint in Redis for offline status
    from app.extensions import redis_client
    
    # Check if this specific URL is marked offline in Redis
    # We store offline statuses in Redis as dcrystal:offline_reports: <json_dict>
    current_path = request.path
    try:
        offline_reports_json = redis_client.get('dcrystal:offline_reports')
        if offline_reports_json:
            offline_reports = json.loads(offline_reports_json)
            if current_path in offline_reports and offline_reports[current_path]:
                return redirect(url_for('dashboard.report_offline', next=current_path))
    except Exception as e:
        print(f"Error checking offline status: {e}")

@dashboard_bp.route('/report-offline')
def report_offline():
    return render_template('report_offline.html')

@dashboard_bp.route('/force-reset')
def force_reset():
    # Only allow access if user is logged in and MUST reset password
    if not session.get('user_id') or not session.get('must_reset_password'):
        return redirect(url_for('dashboard.index'))
    
    # We don't need to fetch unread_count etc. for this exclusive page
    return render_template('force_reset.html')

@dashboard_bp.route('/settings/report-offline-status')
def get_report_offline_status():
    from flask import session
    from app.models.rbac import Menu
    if 'ADMIN' not in session.get('roles', []):
        return {"status": "error", "message": "Unauthorized"}, 403
        
    # Fetch from DB (source of truth)
    menus = Menu.query.filter(Menu.url != None, Menu.url != '#', Menu.url != '').all()
    status_data = {menu.url: menu.is_offline for menu in menus}
    
    return {"status": "success", "reports": status_data}

@dashboard_bp.route('/settings/toggle-report-offline', methods=['POST'])
def toggle_report_offline():
    from flask import request, session
    from app.models.rbac import Menu
    from app.extensions import db, redis_client
    import json
    
    if 'ADMIN' not in session.get('roles', []):
        return {"status": "error", "message": "Unauthorized"}, 403
        
    data = request.get_json()
    report_url = data.get('url')
    is_offline = data.get('is_offline', False)
    
    if not report_url:
        return {"status": "error", "message": "URL is required"}, 400
        
    # Update DB
    menu = Menu.query.filter_by(url=report_url).first()
    if not menu:
        return {"status": "error", "message": "Report not found"}, 404
        
    menu.is_offline = is_offline
    db.session.commit()
    
    # Update Redis cache
    try:
        offline_reports_json = redis_client.get('dcrystal:offline_reports')
        offline_reports = json.loads(offline_reports_json) if offline_reports_json else {}
        offline_reports[report_url] = is_offline
        redis_client.set('dcrystal:offline_reports', json.dumps(offline_reports))
    except Exception as e:
        print(f"Failed to update redis: {e}")
    
    return {"status": "success", "message": f"Report {'offline' if is_offline else 'online'} successfully"}

@dashboard_bp.route('/debug-origin')
def debug_origin():
    from flask import request, jsonify
    header_value = request.headers.get('X-Access-Channel')
    if header_value:
        return jsonify({"origin": header_value})
    return "Header Not Found"
