from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import User, UserPasswordHistory, LoginAttemptLog
from app.extensions import db, limiter
from datetime import timedelta
from app.services.auth_service import auth_service
from app.utils.decorators import require_role

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute per IP")
def login():
    data = request.json
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({"msg": "Missing user id or password"}), 400

    user = User.query.filter_by(user_id=user_id).first()

    # Rate limit per account identifier (custom limit)
    # Note: Flask-Limiter doesn't easily support dynamic identifiers in @limit decorators for complex logic,
    # but we handle it via AuthService lockout.

    if user and auth_service.is_locked_out(user):
        auth_service.log_attempt(user_id, user_id=user.user_id, status='failure', failure_reason='locked_out')
        return jsonify({"msg": "Account is temporarily locked. Please try again later."}), 423

    if user and not user.is_active:
        auth_service.log_attempt(user_id, user_id=user.user_id, status='failure', failure_reason='account_disabled')
        return jsonify({"msg": "This account has been disabled. Please contact your administrator."}), 403

    if user and user.check_password(password):
        # Store in session for server-side auth checks (e.g. data filtering)
        session['user_id'] = user.user_id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
        session['roles'] = [r.name for r in user.roles]
        
        auth_service.handle_successful_login(user, request.remote_addr)
        
        access_token = create_access_token(
            identity=str(user.id), 
            expires_delta=timedelta(days=7),
            additional_claims={'session_version': user.session_version}
        )
        
        response = jsonify(
            access_token=access_token, 
            user=user.to_dict(),
            force_reset=user.must_reset_password
        )
        # Set cookie for session recovery (standard GET requests)
        response.set_cookie('access_token', access_token, 
                            httponly=True, 
                            max_age=7*24*3600, 
                            samesite='Lax')
        
        return response, 200

    # Handle failure (user exists or not)
    auth_service.handle_failed_login(user, user_id)
    return jsonify({"msg": "Bad user id or password"}), 401

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    user_id = data.get('user_id')
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    if not user_id or not username or not password or not email:
        return jsonify({"msg": "Missing required fields"}), 400

    if User.query.filter_by(user_id=user_id).first():
        return jsonify({"msg": "User ID already exists"}), 400

    new_user = User(user_id=user_id, username=username, email=email)
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"msg": "User created successfully"}), 201

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404
    return jsonify(user.to_dict()), 200

from app.utils.rbac_cache import build_menu_tree, get_user_permissions

@auth_bp.route('/me/menus', methods=['GET'])
@jwt_required()
def get_my_menus():
    user_id = get_jwt_identity()
    menus = build_menu_tree(user_id)
    perms = list(get_user_permissions(user_id))
    return jsonify({"menus": menus, "permissions": perms}), 200
@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    response = jsonify({"msg": "Logged out successfully"})
    response.delete_cookie('access_token')
    return response, 200

@auth_bp.route('/update-password', methods=['POST'])
def update_password():
    if 'user_id' not in session:
        return jsonify({"msg": "Unauthorized"}), 401
    
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        return jsonify({"msg": "Missing required fields"}), 400
        
    if new_password != confirm_password:
        return jsonify({"msg": "New passwords do not match"}), 400
        
    if current_password == new_password:
        return jsonify({"msg": "New password cannot be the same as current password"}), 400
        
    user = User.query.filter_by(user_id=session['user_id']).first()
    if not user or not user.check_password(current_password):
        return jsonify({"msg": "Incorrect current password"}), 401
        
    user.set_password(new_password)
    user.session_version += 1
    user.must_reset_password = False
    
    # Log history
    history = UserPasswordHistory(
        target_user_id=user.id,
        changed_by_id=user.id # Self-update
    )
    db.session.add(history)
    
    db.session.commit()
    
    return jsonify({"msg": "Password updated successfully"}), 200

@auth_bp.route('/debug/auth-status/<user_id>', methods=['GET'])
@jwt_required()
def get_auth_status(user_id):
    # Check if requester is admin
    admin_id = get_jwt_identity()
    admin = User.query.get(admin_id)
    if not admin or not admin.is_admin:
        return jsonify({"msg": "Admin access required"}), 403

    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return jsonify({"msg": "User not found"}), 404

    return jsonify({
        "user_id": user.user_id,
        "failed_attempt_count": user.failed_attempt_count,
        "lockout_until": user.lockout_until.isoformat() if user.lockout_until else None,
        "is_locked_out": auth_service.is_locked_out(user),
        "last_failed_at": user.last_failed_at.isoformat() if user.last_failed_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "last_login_ip": user.last_login_ip
    }), 200

@auth_bp.route('/debug/recent-logs', methods=['GET'])
@jwt_required()
@require_role('ADMIN')
def get_recent_logs():
    """Debug endpoint to see recent login attempts (Admin only)"""
    logs = LoginAttemptLog.query.order_by(LoginAttemptLog.timestamp.desc()).limit(50).all()
    return jsonify([{
        "id": log.id,
        "username": log.username_submitted,
        "ip": log.ip_address,
        "status": log.status,
        "reason": log.failure_reason,
        "timestamp": log.timestamp.isoformat() + 'Z' if log.timestamp else None
    } for log in logs])

from sqlalchemy import or_

@auth_bp.route('/login-logs', methods=['GET'])
@jwt_required()
@require_role('ADMIN')
def get_login_logs():
    """Get paginated login logs (Admin only)"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Robust join to find the user name even if log mapping is inconsistent
    query = db.session.query(LoginAttemptLog, User.username).outerjoin(
        User, or_(
            LoginAttemptLog.user_id == User.user_id,
            LoginAttemptLog.username_submitted == User.user_id,
            LoginAttemptLog.username_submitted == User.username
        )
    )
    
    pagination = query.order_by(LoginAttemptLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        "logs": [{
            "id": log.id,
            "user_code": log.user_id if log.user_id else log.username_submitted,
            "user_name": username if username else "-",
            "ip": log.ip_address,
            "status": log.status,
            "reason": log.failure_reason,
            "timestamp": log.timestamp.isoformat() + 'Z' if log.timestamp else None
        } for log, username in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page
    }), 200
