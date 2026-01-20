import os
import redis
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', 6379)
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "redis": r.ping()})

@app.route('/update', methods=['POST'])
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

@app.route('/data/<view_id>')
def get_dashboard_data(view_id):
    cached_data = r.get(f"dashboard:{view_id}")
    if cached_data:
        return jsonify(json.loads(cached_data))
    return jsonify({}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
