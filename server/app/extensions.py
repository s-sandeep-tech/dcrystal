import os
import redis
from flask_sqlalchemy import SQLAlchemy

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', 6379)

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Database
db = SQLAlchemy()

# SocketIO
from flask_socketio import SocketIO
# Using Redis as message queue for multi-process support
socketio = SocketIO(cors_allowed_origins="*", message_queue=f'redis://{REDIS_HOST}:{REDIS_PORT}')

# JWT
from flask_jwt_extended import JWTManager
jwt = JWTManager()
