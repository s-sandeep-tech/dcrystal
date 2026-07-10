import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import redis_client as r

api_bp = Blueprint('api', __name__)

@api_bp.route('/health')
def health():
    try:
        return jsonify({"status": "healthy", "redis": r.ping()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/update', methods=['POST'])
@jwt_required()
def update_dashboard():
    data = request.json
    view_id = data.get('view_id', 'default')
    payload = data.get('payload', {})
    
    # Cache the latest data for this view
    r.set(f"dashboard:{view_id}", json.dumps(payload))
    
    # Publish update to Redis for Socket.IO server
    event_data = {
        "view_id": view_id,
        "payload": payload
    }
    r.publish('dashboard_updates', json.dumps(event_data))
    
    return jsonify({"message": f"Updated {view_id}", "data": event_data})

@api_bp.route('/data/<view_id>')
@jwt_required()
def get_dashboard_data(view_id):
    cached_data = r.get(f"dashboard:{view_id}")
    if cached_data:
        return jsonify(json.loads(cached_data))
    return jsonify({}), 404

@api_bp.route('/sync/provision-stock-status', methods=['POST'])
def trigger_external_provision_stock_status():
    """
    Exposed endpoint for third parties to trigger the "Provision & Stock Status Sync"
    once external view processing is complete.
    """
    from app.utils.decorators import require_api_client
    from app.utils.sync_manager import sync_provision_stock_status_data
    from flask import current_app
    import json

    # We manually trigger the decorator logic here to support dynamic import/handling
    @require_api_client('ALLOWED_THIRD_PARTY_IPS')
    def authenticated_trigger():
        # 1. Payload validation (optional JSON)
        payload = {}
        if request.data:
            try:
                payload = request.get_json(force=True) or {}
            except Exception:
                return jsonify({
                    "status": "error",
                    "message": "Invalid JSON format in request body."
                }), 400

        # 2. Verify external processing status if provided
        status = payload.get('status')
        if status and status.lower() not in ['success', 'completed']:
            current_app.logger.warning(f"Sync trigger aborted. External status reported as: {status}")
            return jsonify({
                "status": "error",
                "message": f"Sync trigger aborted because external status is '{status}'."
            }), 400

        # 3. Enqueue the sync task
        result = sync_provision_stock_status_data(user_id='THIRD_PARTY')
        
        if result.get('status') == 'success':
            # Cache metadata temporarily in Redis to merge with SyncLog details on execution
            if payload:
                try:
                    r.setex(
                        "sync_meta:provision_stock_status:last", 
                        3600, 
                        json.dumps(payload)
                    )
                except Exception as e:
                    current_app.logger.error(f"Failed to cache metadata in Redis: {e}")

            return jsonify({
                "status": "success",
                "message": "Provision & Stock Status Sync task has been successfully enqueued.",
                "task": "provision_stock_status"
            }), 202
        else:
            return jsonify(result), 500

    return authenticated_trigger()


@api_bp.route('/sync/tasks', methods=['POST'])
def trigger_external_sync_tasks():
    """
    Exposed endpoint for third parties to trigger one or more allowed sync tasks.

    Payload examples:
        {"task_key": "provision_stock_status", "status": "success"}
        {"task_keys": ["provision_stock_status", "owner_showroom_combined"], "status": "completed"}
    """
    from app.utils.decorators import require_api_client
    from app.utils.sync_manager import ALLOWED_SYNC_TASKS, enqueue_sync_task
    from flask import current_app
    import json

    @require_api_client('ALLOWED_THIRD_PARTY_IPS')
    def authenticated_trigger():
        payload = {}
        if request.data:
            try:
                payload = request.get_json(force=True) or {}
            except Exception:
                return jsonify({
                    "status": "error",
                    "message": "Invalid JSON format in request body."
                }), 400

        status = payload.get('status')
        if status and status.lower() not in ['success', 'completed']:
            current_app.logger.warning(f"Sync trigger aborted. External status reported as: {status}")
            return jsonify({
                "status": "error",
                "message": f"Sync trigger aborted because external status is '{status}'."
            }), 400

        task_keys = payload.get('task_keys') or payload.get('tasks') or payload.get('task_key')
        if isinstance(task_keys, str):
            task_keys = [task_keys]

        if not isinstance(task_keys, list) or not task_keys:
            return jsonify({
                "status": "error",
                "message": "Payload must include task_key or task_keys."
            }), 400

        task_keys = [str(task_key).strip() for task_key in task_keys if str(task_key).strip()]
        invalid_tasks = [task_key for task_key in task_keys if task_key not in ALLOWED_SYNC_TASKS]
        if invalid_tasks:
            return jsonify({
                "status": "error",
                "message": "Unsupported sync task key.",
                "invalid_tasks": invalid_tasks,
                "allowed_tasks": sorted(ALLOWED_SYNC_TASKS)
            }), 400

        queued_tasks = []
        failed_tasks = []
        for task_key in task_keys:
            result = enqueue_sync_task(task_key, user_id='THIRD_PARTY')
            if result.get('status') == 'success':
                queued_tasks.append(task_key)
                if payload:
                    try:
                        r.setex(
                            f"sync_meta:{task_key}:last",
                            3600,
                            json.dumps(payload)
                        )
                    except Exception as e:
                        current_app.logger.error(f"Failed to cache sync metadata for {task_key}: {e}")
            else:
                failed_tasks.append({
                    "task": task_key,
                    "message": result.get('message')
                })

        if failed_tasks:
            return jsonify({
                "status": "error",
                "message": "One or more sync tasks failed to enqueue.",
                "queued_tasks": queued_tasks,
                "failed_tasks": failed_tasks
            }), 500

        return jsonify({
            "status": "success",
            "message": "Sync task(s) have been successfully enqueued.",
            "tasks": queued_tasks
        }), 202

    return authenticated_trigger()
