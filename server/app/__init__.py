from flask import Flask, render_template
from flask_cors import CORS
from app.extensions import db, socketio, jwt, migrate, limiter
import os

def create_app():
    app = Flask(__name__)
    CORS(app)
    # Import models to register them with SQLAlchemy
    from app.models import (
        User, Notification, Order, DashboardStats, ExportDownloadLog,
        OrderStatusReportSnapshot, ShortStatusReportSnapshot, OrderProvisionSummaryReport,
        LocationWiseOrderSnapshot, AllocatedBarcodesSnapshot, OwnerWiseOrderSummarySnapshot
    )

    # Database Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'SQLALCHEMY_DATABASE_URI', 
        'postgresql+psycopg2://meetaccess:meetpass@localhost:5432/dcrystaldb'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "pool_timeout": 900, # 15 minutes
        "connect_args": {
            "connect_timeout": 60
        }
    }
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret-key-change-me')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-123')
    app.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']
    app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    socketio.init_app(app)
    jwt.init_app(app)
    
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        user_id = jwt_payload['sub']
        token_version = jwt_payload.get('session_version')
        
        user = User.query.get(user_id)
        if not user:
            return True
            
        # If token doesn't have a version (old token), or version doesn't match, revoke it
        if token_version is None or user.session_version != token_version:
            return True
            
        return False

    # Ensure all tables are created (including Notification)
    with app.app_context():
        # db.create_all() # Handled by migrations
        
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

    # Session Recovery Middleware
    from flask import session, request, g
    from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
    from app.models import User

    @app.before_request
    def restore_session_from_jwt():
        # Only attempt recovery if session is lost
        if 'user_id' not in session:
            try:
                token = request.cookies.get('access_token')
                if token:
                    from flask_jwt_extended import decode_token
                    decoded = decode_token(token)
                    user_primary_id = decoded['sub']
                    token_version = decoded.get('session_version')
                    
                    user = User.query.get(user_primary_id)
                    if user:
                        # Validate session version for restored sessions too
                        if token_version is not None and user.session_version == token_version:
                            session['user_id'] = user.user_id
                            session['username'] = user.username
                            session['is_admin'] = user.is_admin
                            session['roles'] = [r.name for r in user.roles]
                            app.logger.info(f"Restored session for {user.username} from JWT cookie")
                        else:
                            g.clear_token_cookie = True
                            app.logger.warning(f"Session version mismatch for {user.username}. Clearing cookie.")
            except Exception as e:
                # If token is invalid or expired, flag it for removal to prevent redundant attempts
                g.clear_token_cookie = True
                app.logger.warning(f"Invalid JWT detected during session restoration: {str(e)}")

    @app.after_request
    def clear_invalid_token_cookie(response):
        if hasattr(g, 'clear_token_cookie') and g.clear_token_cookie:
            response.delete_cookie('access_token')
            app.logger.info("Cleared invalid access_token cookie")
        return response

    # Register Blueprints
    from app.api.routes import api_bp
    from app.dashboard import dashboard_bp
    from app.api.auth import auth_bp
    from app.api.admin_rbac import admin_rbac_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_rbac_bp, url_prefix='/api/admin')

    # Context Processor for Global Template Variables
    @app.context_processor
    def inject_global_vars():
        from flask import session
        from app.models import Notification
        from app.utils.rbac_cache import get_user_permissions
        from sqlalchemy import or_
        
        user_id = session.get('user_id')
        unread_count = 0
        permissions = set()
        
        if user_id:
            unread_count = Notification.query.filter(
                Notification.is_read == False,
                or_(Notification.user_id == user_id, Notification.user_id == None)
            ).count()
            # Fetch permissions for the logged-in user
            permissions = get_user_permissions(user_id)
        
        return dict(unread_count=unread_count, permissions=permissions)

    # Register Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    return app
