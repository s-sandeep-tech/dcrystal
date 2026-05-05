from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from .extensions import db, socketio, jwt, migrate, limiter
import os

def create_app():
    app = Flask(__name__)
    CORS(app)
    # Import models to register them with SQLAlchemy
    from .models import (
        User, Notification, Order, DashboardStats, ExportDownloadLog,
        OrderStatusReportSnapshot, ShortStatusReportSnapshot, OrderProvisionSummaryReport,
        LocationWiseOrderSnapshot, AllocatedBarcodesSnapshot, OwnerWiseOrderSummarySnapshot,
        ProvisionStockRawSnapshot, AKTTransactionPerformance
    )

    # Database Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'SQLALCHEMY_DATABASE_URI', 
        'postgresql+psycopg2://meetaccess:meetpass@localhost:5432/dcrystaldb'
    )
    # AKT Dashboard Database Bind (Only active in production or if enabled)
    akt_db_uri = 'postgresql+psycopg2://reportuser:rEp%40eP%40mU%4020_78@kj-az1-prod1-dexcd-psql-db1.postgres.database.azure.com:5432/KJCHPilotDB?sslmode=require'
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('ENABLE_AKT_DB') == 'true':
        app.config['SQLALCHEMY_BINDS'] = {'akt_db': akt_db_uri}
    else:
        # Fallback to main DB for local development to avoid resolution errors
        app.config['SQLALCHEMY_BINDS'] = {'akt_db': app.config['SQLALCHEMY_DATABASE_URI']}
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
        
    @jwt.revoked_token_loader
    def custom_revoked_token_response(jwt_header, jwt_payload):
        msg = """
        <div class="flex flex-col sm:flex-row items-center justify-between p-4 mb-4 text-sm text-red-800 border border-red-300 rounded-xl bg-red-50 dark:bg-gray-800 dark:text-red-400 dark:border-red-800 shadow-sm" role="alert">
            <div class="flex items-center mb-3 sm:mb-0">
                <span class="material-symbols-outlined mr-3 text-2xl text-red-500">lock_circle</span>
                <div>
                    <span class="font-bold block text-base text-red-900 dark:text-red-300">Session Revoked</span>
                    <span class="text-red-700 dark:text-red-400">Your security token has been invalidated.</span>
                </div>
            </div>
            <a href='/login' class="flex items-center justify-center text-white bg-red-600 hover:bg-red-700 focus:ring-4 focus:outline-none focus:ring-red-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-red-600 dark:hover:bg-red-700 transition-all shadow-md w-full sm:w-auto">
                <span class="material-symbols-outlined mr-2 text-sm">login</span> Login again
            </a>
        </div>
        """
        if request.path.startswith('/api/'):
            return jsonify({"msg": msg}), 401
            
        if 'text/html' in request.headers.get('Accept', ''):
            return render_template('errors/401.html'), 401
            
        return jsonify({"msg": msg}), 401

    @jwt.unauthorized_loader
    def custom_unauthorized_response(callback):
        if request.path.startswith('/api/'):
            return jsonify({"msg": "Missing JWT in headers or cookies (Missing Authorization Header; Missing cookie \"access_token\")"}), 401
        
        # Check if request prefers HTML
        if 'text/html' in request.headers.get('Accept', ''):
            return render_template('errors/401.html'), 401
            
        return jsonify({"msg": "Missing JWT in headers or cookies (Missing Authorization Header; Missing cookie \"access_token\")"}), 401

    @jwt.expired_token_loader
    def custom_expired_token_response(jwt_header, jwt_payload):
        msg = """
        <div class="flex flex-col sm:flex-row items-center justify-between p-4 mb-4 text-sm border rounded-xl shadow-sm bg-amber-50 border-amber-300 text-amber-800 dark:bg-gray-800 dark:border-amber-800 dark:text-amber-400" role="alert">
            <div class="flex items-center mb-3 sm:mb-0">
                <span class="material-symbols-outlined mr-3 text-2xl text-amber-500">timer</span>
                <div>
                    <span class="font-bold block text-base text-amber-900 dark:text-amber-300">Session Expired</span>
                    <span class="text-amber-700 dark:text-amber-400">Your secure session has timed out due to inactivity.</span>
                </div>
            </div>
            <a href='/login' class="flex items-center justify-center text-white bg-amber-600 hover:bg-amber-700 focus:ring-4 focus:outline-none focus:ring-amber-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-amber-600 dark:hover:bg-amber-700 transition-all shadow-md w-full sm:w-auto">
                <span class="material-symbols-outlined mr-2 text-sm">login</span> Login again
            </a>
        </div>
        """
        if request.path.startswith('/api/'):
            return jsonify({"msg": msg}), 401
            
        if 'text/html' in request.headers.get('Accept', ''):
            return render_template('errors/401.html'), 401
            
        return jsonify({"msg": msg}), 401

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

        # Sync offline reports to Redis on startup
        try:
            from .models.rbac import Menu
            from .extensions import redis_client
            import json
            
            offline_menus = Menu.query.filter_by(is_offline=True).all()
            offline_status = {menu.url: True for menu in offline_menus if menu.url}
            
            if offline_status:
                redis_client.set('dcrystal:offline_reports', json.dumps(offline_status))
                print(f"Synced {len(offline_status)} offline reports to Redis.")
            else:
                # Clear if none are offline to ensure cache is fresh
                redis_client.delete('dcrystal:offline_reports')
        except Exception as e:
            app.logger.error(f"Failed to sync offline reports to Redis on startup: {e}")

    # Session Recovery Middleware
    from flask import session, request, g
    from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
    from .models import User

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
                            session['must_reset_password'] = user.must_reset_password
                            app.logger.info(f"Restored session for {user.username} from JWT cookie")
                        else:
                            g.clear_token_cookie = True
                            app.logger.warning(f"Session version mismatch for {user.username}. Clearing cookie.")
            except Exception as e:
                # If token is invalid or expired, flag it for removal to prevent redundant attempts
                g.clear_token_cookie = True
                app.logger.warning(f"Invalid JWT detected during session restoration: {str(e)}")

    @app.before_request
    def enforce_forced_password_reset():
        # Exclude routes that must remain accessible
        # We check both request.path and request.endpoint for robustness
        reset_excluded_endpoints = [
            'dashboard.force_reset', 
            'dashboard.logout', 
            'dashboard.login',
            'auth.logout',
            'auth.update_password',
            'static'
        ]
        
        if request.endpoint in reset_excluded_endpoints:
            return
            
        # Also check path prefixes for API or other untracked routes
        if request.path.startswith('/static/') or request.path == '/force-reset' or request.path == '/logout':
            return

        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        
        user_id = session.get('user_id')
        
        # If not in session, try to identify user from JWT (handles API clients with Bearer tokens)
        if not user_id:
            try:
                verify_jwt_in_request(optional=True)
                user_id = get_jwt_identity()
            except Exception:
                pass

        must_reset = False
        if user_id:
            # Always check the DB for the most current status to prevent real-time bypass
            # Identity map in SQLAlchemy makes this efficient for repeated calls in one request
            # Robust lookup to handle both primary key (numeric) and alphanumeric user_id
            user = None
            if not user:
                user = User.query.filter_by(user_id=str(user_id)).first()

            if user and user.must_reset_password:
                must_reset = True
                session['must_reset_password'] = True
            else:
                session['must_reset_password'] = False

        if must_reset:
            if request.path.startswith('/api/'):
                return jsonify({
                    "msg": "Action Required: Password reset is mandatory for your account.",
                    "force_reset": True
                }), 403
            return redirect(url_for('dashboard.force_reset'))

    @app.after_request
    def clear_invalid_token_cookie(response):
        if hasattr(g, 'clear_token_cookie') and g.clear_token_cookie:
            response.delete_cookie('access_token')
            app.logger.info("Cleared invalid access_token cookie")
        return response

    # Register Blueprints
    from .api.routes import api_bp
    from .dashboard import dashboard_bp
    from .api.auth import auth_bp
    from .api.admin_rbac import admin_rbac_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_rbac_bp, url_prefix='/api/admin')

    # Context Processor for Global Template Variables
    @app.context_processor
    def inject_global_vars():
        from flask import session
        from .models import Notification
        from .utils.rbac_cache import get_user_permissions
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
