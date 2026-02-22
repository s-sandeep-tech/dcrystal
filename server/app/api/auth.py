from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import User, UserPasswordHistory
from app.extensions import db
from datetime import timedelta

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({"msg": "Missing user id or password"}), 400

    user = User.query.filter_by(user_id=user_id).first()
    if user and user.check_password(password):
        # Store in session for server-side auth checks (e.g. data filtering)
        session['user_id'] = user.user_id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
        
        access_token = create_access_token(identity=str(user.id), expires_delta=timedelta(days=1))
        
        response = jsonify(access_token=access_token, user=user.to_dict())
        # Set cookie for session recovery (standard GET requests)
        response.set_cookie('access_token', access_token, 
                            httponly=True, 
                            max_age=24*3600, 
                            samesite='Lax')
        
        return response, 200

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
        
    user = User.query.filter_by(user_id=session['user_id']).first()
    if not user or not user.check_password(current_password):
        return jsonify({"msg": "Incorrect current password"}), 401
        
    user.set_password(new_password)
    
    # Log history
    history = UserPasswordHistory(
        target_user_id=user.id,
        changed_by_id=user.id # Self-update
    )
    db.session.add(history)
    
    db.session.commit()
    
    return jsonify({"msg": "Password updated successfully"}), 200
