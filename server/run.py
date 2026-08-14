import os

from app import create_app
from app.extensions import db, socketio

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    debug_enabled = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=debug_enabled,
        allow_unsafe_werkzeug=True,
    )
