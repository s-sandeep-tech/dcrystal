import os
import redis
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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

# Migrations
from flask_migrate import Migrate
migrate = Migrate()

# Limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{REDIS_HOST}:{REDIS_PORT}",
    default_limits=[]
)
