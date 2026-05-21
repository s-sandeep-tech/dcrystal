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

