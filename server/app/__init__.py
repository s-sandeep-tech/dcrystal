from flask import Flask
from flask_cors import CORS
from app.extensions import db, socketio, jwt
import os

def create_app():
    app = Flask(__name__)
    CORS(app)
    # Import models to register them with SQLAlchemy
    from app.models import (
        User, Notification, Order, DashboardStats,
        OrderStatusReportSnapshot, ShortStatusReportSnapshot, OrderProvisionSummaryReport,
        LocationWiseOrderSnapshot, AllocatedBarcodesSnapshot, OwnerWiseOrderSummarySnapshot
    )

    # Database Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'SQLALCHEMY_DATABASE_URI', 
        'postgresql+psycopg2://meetaccess:meetpass@localhost:5432/dcrystaldb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret-key-change-me')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-123')

    db.init_app(app)
    socketio.init_app(app)
    jwt.init_app(app)
    # Ensure all tables are created (including Notification)
    with app.app_context():
        db.create_all()
        
        # Create a default user if none exists
        from app.models import User
        admin = User.query.filter_by(username='admin').first()
        if admin is None:
            admin = User(user_id='U001', username='admin', email='admin@example.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Default user 'admin' with password 'admin123' and is_admin=True created.")
        else:
            if not admin.is_admin:
                admin.is_admin = True
                db.session.commit()
                print("Existing 'admin' user updated to is_admin=True.")

    # Register Blueprints
    from app.api.routes import api_bp
    from app.dashboard import dashboard_bp
    from app.api.auth import auth_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    return app
