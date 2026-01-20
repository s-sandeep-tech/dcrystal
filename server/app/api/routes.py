import json
from flask import Blueprint, request, jsonify
from app.extensions import redis_client as r

api_bp = Blueprint('api', __name__)

@api_bp.route('/health')
def health():
    try:
        return jsonify({"status": "healthy", "redis": r.ping()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/update', methods=['POST'])
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
def get_dashboard_data(view_id):
    cached_data = r.get(f"dashboard:{view_id}")
    if cached_data:
        return jsonify(json.loads(cached_data))
    return jsonify({}), 404
