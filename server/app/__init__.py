from flask import Flask
from flask_cors import CORS
from app.extensions import db, socketio, jwt
import os

def create_app():
    app = Flask(__name__)
    CORS(app)
    # Import models to register them with SQLAlchemy
    from app.models import User, Notification, Order, DashboardStats

    # Database Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'SQLALCHEMY_DATABASE_URI', 
        'postgresql+psycopg2://meetaccess:meetpass@localhost:5432/dcrystaldb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret-key-change-me')

    db.init_app(app)
    socketio.init_app(app)
    jwt.init_app(app)
    # Ensure all tables are created (including Notification)
    with app.app_context():
        db.create_all()
        
        # Create a default user if none exists
        from app.models import User
        if User.query.filter_by(username='admin').first() is None:
            admin = User(username='admin', email='admin@example.com')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Default user 'admin' with password 'admin123' created.")

    # Register Blueprints
    from app.api.routes import api_bp
    from app.dashboard.routes import dashboard_bp
    from app.api.auth import auth_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    return app
