from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role, Menu, UserRole, RoleMenu, Permission, RolePermission, AuditLog, UserPasswordHistory
from app.utils.decorators import require_role, require_perm
from app.utils.rbac_cache import increment_rbac_version, invalidate_user_cache
from datetime import datetime

admin_rbac_bp = Blueprint('admin_rbac', __name__)

def log_audit(user_id, action, t_type, t_id, details):
    db.session.add(AuditLog(
        user_id=user_id, 
        action=action, 
        target_type=t_type, 
        target_id=str(t_id), 
        details=details
    ))

@admin_rbac_bp.route('/roles', methods=['GET', 'POST'])
@jwt_required()
@require_role('ADMIN')
def manage_roles():
    if request.method == 'GET':
        roles = Role.query.all()
        return jsonify([{"id": r.id, "name": r.name, "description": r.description} for r in roles])
    
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        if not name:
            return jsonify({"msg": "Role name is required"}), 400
            
        role = Role(name=name, description=data.get('description'))
        db.session.add(role)
        db.session.commit()
        
        log_audit(get_jwt_identity(), "CREATE", "ROLE", role.id, {"name": role.name})
        db.session.commit()
        return jsonify({"msg": "Role created", "id": role.id}), 201

@admin_rbac_bp.route('/roles/<int:role_id>', methods=['PUT', 'DELETE'])
@jwt_required()
@require_role('ADMIN')
def update_delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    
    if request.method == 'DELETE':
        db.session.delete(role)
        db.session.commit()
        increment_rbac_version() # Invalidate globally since users might have this role
        log_audit(get_jwt_identity(), "DELETE", "ROLE", role_id, {"name": role.name})
        db.session.commit()
        return jsonify({"msg": "Role deleted"}), 200
        
    if request.method == 'PUT':
        data = request.json
        role.name = data.get('name', role.name)
        role.description = data.get('description', role.description)
        db.session.commit()
        log_audit(get_jwt_identity(), "UPDATE", "ROLE", role_id, {"name": role.name})
        db.session.commit()
        return jsonify({"msg": "Role updated"})

@admin_rbac_bp.route('/menus', methods=['GET', 'POST'])
@jwt_required()
@require_role('ADMIN')
def manage_menus():
    if request.method == 'GET':
        menus = Menu.query.order_by(Menu.sort_order).all()
        return jsonify([{
            "id": m.id, 
            "parent_id": m.parent_id, 
            "title": m.title, 
            "url": m.url, 
            "icon": m.icon,
            "sort_order": m.sort_order,
            "permission_required": m.permission_required
        } for m in menus])
        
    if request.method == 'POST':
        data = request.json
        menu = Menu(
            parent_id=data.get('parent_id'),
            title=data.get('title'),
            url=data.get('url'),
            icon=data.get('icon'),
            sort_order=data.get('sort_order', 0),
            permission_required=data.get('permission_required')
        )
        db.session.add(menu)
        db.session.commit()
        increment_rbac_version()
        log_audit(get_jwt_identity(), "CREATE", "MENU", menu.id, {"title": menu.title})
        db.session.commit()
        return jsonify({"msg": "Menu created", "id": menu.id}), 201

@admin_rbac_bp.route('/menus/<int:menu_id>', methods=['PUT', 'DELETE'])
@jwt_required()
@require_role('ADMIN')
def update_delete_menu(menu_id):
    menu = Menu.query.get_or_404(menu_id)
    if request.method == 'DELETE':
        db.session.delete(menu)
        db.session.commit()
        increment_rbac_version()
        log_audit(get_jwt_identity(), "DELETE", "MENU", menu_id, {"title": menu.title})
        db.session.commit()
        return jsonify({"msg": "Menu deleted"}), 200
        
    if request.method == 'PUT':
        data = request.json
        menu.parent_id = data.get('parent_id', menu.parent_id)
        menu.title = data.get('title', menu.title)
        menu.url = data.get('url', menu.url)
        menu.icon = data.get('icon', menu.icon)
        menu.sort_order = data.get('sort_order', menu.sort_order)
        menu.permission_required = data.get('permission_required', menu.permission_required)
        db.session.commit()
        increment_rbac_version()
        log_audit(get_jwt_identity(), "UPDATE", "MENU", menu_id, {"title": menu.title})
        db.session.commit()
        return jsonify({"msg": "Menu updated"})

@admin_rbac_bp.route('/users/<int:u_id>/roles', methods=['PUT'])
@jwt_required()
@require_role('ADMIN')
def manage_user_roles(u_id):
    data = request.json
    role_ids = data.get('role_ids', [])
    
    current_user_id = int(get_jwt_identity())
    admin_role = Role.query.filter_by(name='ADMIN').first()
    
    UserRole.query.filter_by(user_id=u_id).delete()
    for rid in role_ids:
        db.session.add(UserRole(user_id=u_id, role_id=rid))
        
    # Edge Case: Prevent removing ADMIN from yourself
    if current_user_id == u_id and admin_role and admin_role.id not in role_ids:
        db.session.rollback()
        return jsonify({"msg": "Cannot remove your own ADMIN role"}), 400

    db.session.commit()
    invalidate_user_cache(u_id)
    log_audit(current_user_id, "UPDATE_USER_ROLES", "USER", str(u_id), {"roles": role_ids})
    db.session.commit()
    return jsonify({"msg": "User roles updated"})

@admin_rbac_bp.route('/users', methods=['GET', 'POST'])
@jwt_required()
@require_role('ADMIN')
def manage_users():
    if request.method == 'GET':
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 8, type=int)
        search = request.args.get('search', '')
        
        query = User.query
        if search:
            query = query.filter((User.username.ilike(f'%{search}%')) | (User.email.ilike(f'%{search}%')))
            
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        users = pagination.items
        
        return jsonify({
            "users": [u.to_dict() for u in users],
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": pagination.page
        })

    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        user_id = data.get('user_id')
        
        if not username or not email or not password or not user_id:
            return jsonify({"msg": "All fields are required"}), 400
            
        if User.query.filter_by(username=username).first():
            return jsonify({"msg": "Username already exists"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"msg": "Email already exists"}), 400
        if User.query.filter_by(user_id=user_id).first():
            return jsonify({"msg": "User ID already exists"}), 400
            
        user = User(username=username, email=email, user_id=user_id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        log_audit(get_jwt_identity(), "CREATE", "USER", user.id, {"username": user.username})
        db.session.commit()
        return jsonify({"msg": "User created", "id": user.id}), 201

@admin_rbac_bp.route('/users/<int:id>', methods=['PUT', 'DELETE'])
@jwt_required()
@require_role('ADMIN')
def update_delete_user(id):
    user = User.query.get_or_404(id)
    if request.method == 'DELETE':
        db.session.delete(user)
        db.session.commit()
        log_audit(get_jwt_identity(), "DELETE", "USER", id, {"username": user.username})
        db.session.commit()
        return jsonify({"msg": "User deleted"}), 200
        
    if request.method == 'PUT':
        data = request.json
        user.username = data.get('username', user.username)
        user.email = data.get('email', user.email)
        user.user_id = data.get('user_id', user.user_id)
        
        if data.get('password'):
            # Security: Admins cannot reset other ADMIN passwords through this UI
            if user.is_admin:
                return jsonify({"msg": "Administrator passwords cannot be reset through the user management interface."}), 403
            
            user.set_password(data.get('password'))
            # Log history
            history = UserPasswordHistory(
                target_user_id=id,
                changed_by_id=get_jwt_identity()
            )
            db.session.add(history)
            
        db.session.commit()
        log_audit(get_jwt_identity(), "UPDATE", "USER", id, {"username": user.username})
        db.session.commit()
        return jsonify({"msg": "User updated"})

@admin_rbac_bp.route('/users/<int:user_id>/password', methods=['PUT'])
@jwt_required()
@require_role('ADMIN')
def change_user_password(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json
    new_password = data.get('password')
    
    if not new_password:
        return jsonify({"msg": "Password is required"}), 400
        
    # Security: Admins cannot reset other ADMIN passwords through this UI
    if user.is_admin:
        return jsonify({"msg": "Administrator passwords cannot be reset through the user management interface."}), 403
        
    # Update password
    user.set_password(new_password)
    
    # Log history
    history = UserPasswordHistory(
        target_user_id=user_id,
        changed_by_id=get_jwt_identity()
    )
    db.session.add(history)
    
    # Audit log
    log_audit(get_jwt_identity(), "UPDATE_PASSWORD", "USER", user_id, {"username": user.username})
    
    db.session.commit()
    return jsonify({"msg": "Password updated successfully"}), 200

@admin_rbac_bp.route('/users/<int:user_id>/clear-lockout', methods=['POST'])
@jwt_required()
@require_role('ADMIN')
def clear_user_lockout(user_id):
    user = User.query.get_or_404(user_id)
    
    # Reset security fields
    user.failed_attempt_count = 0
    user.lockout_until = None
    user.last_failed_at = None
    
    # Audit log
    log_audit(get_jwt_identity(), "CLEAR_LOCKOUT", "USER", user_id, {"username": user.username})
    
    db.session.commit()
    return jsonify({"msg": f"Lockout cleared for user {user.username}"}), 200

@admin_rbac_bp.route('/users/search', methods=['GET'])
@jwt_required()
@require_role('ADMIN')
def search_users():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    users = User.query.filter(
        (User.username.ilike(f'%{query}%')) | 
        (User.email.ilike(f'%{query}%'))
    ).limit(10).all()
    
    return jsonify([{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "user_id": getattr(u, 'user_id', 'N/A')
    } for u in users])

@admin_rbac_bp.route('/users/<int:u_id>/roles', methods=['GET'])
@jwt_required()
@require_role('ADMIN')
def get_user_roles(u_id):
    roles = Role.query.join(UserRole).filter(UserRole.user_id == u_id).all()
    return jsonify([r.id for r in roles])

@admin_rbac_bp.route('/roles/<int:role_id>/menus', methods=['PUT'])
@jwt_required()
@require_role('ADMIN')
def manage_role_menus(role_id):
    data = request.json
    menu_ids = data.get('menu_ids', [])
    
    RoleMenu.query.filter_by(role_id=role_id).delete()
    for mid in menu_ids:
        db.session.add(RoleMenu(role_id=role_id, menu_id=mid))
    db.session.commit()
    increment_rbac_version()
    log_audit(get_jwt_identity(), "UPDATE_ROLE_MENUS", "ROLE", role_id, {"menus": menu_ids})
    db.session.commit()
    return jsonify({"msg": "Role menus updated"})

@admin_rbac_bp.route('/roles/<int:role_id>/menus', methods=['GET'])
@jwt_required()
@require_role('ADMIN')
def get_role_menus(role_id):
    role = Role.query.get_or_404(role_id)
    return jsonify([m.id for m in role.menus])

@admin_rbac_bp.route('/roles/<int:role_id>/permissions', methods=['PUT'])
@jwt_required()
@require_role('ADMIN')
def manage_role_permissions(role_id):
    data = request.json
    perm_ids = data.get('permission_ids', [])
    
    RolePermission.query.filter_by(role_id=role_id).delete()
    for pid in perm_ids:
        db.session.add(RolePermission(role_id=role_id, permission_id=pid))
    db.session.commit()
    increment_rbac_version()
    log_audit(get_jwt_identity(), "UPDATE_ROLE_PERMS", "ROLE", role_id, {"permissions": perm_ids})
    db.session.commit()
    return jsonify({"msg": "Role permissions updated"})

@admin_rbac_bp.route('/permissions', methods=['GET', 'POST'])
@jwt_required()
@require_role('ADMIN')
def manage_permissions():
    if request.method == 'GET':
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 8, type=int)
        search = request.args.get('search', '')
        
        query = Permission.query
        if search:
            query = query.filter((Permission.name.ilike(f'%{search}%')) | (Permission.description.ilike(f'%{search}%')))
            
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        perms = pagination.items
        
        return jsonify({
            "permissions": [{"id": p.id, "name": p.name, "description": p.description} for p in perms],
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": pagination.page
        })
    
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        if not name:
            return jsonify({"msg": "Permission name is required"}), 400
            
        if Permission.query.filter_by(name=name).first():
            return jsonify({"msg": "Permission already exists"}), 400
            
        perm = Permission(name=name, description=data.get('description'))
        db.session.add(perm)
        db.session.commit()
        
        log_audit(get_jwt_identity(), "CREATE", "PERMISSION", perm.id, {"name": perm.name})
        db.session.commit()
        return jsonify({"msg": "Permission created", "id": perm.id}), 201

@admin_rbac_bp.route('/permissions/<int:perm_id>', methods=['PUT', 'DELETE'])
@jwt_required()
@require_role('ADMIN')
def update_delete_permission(perm_id):
    perm = Permission.query.get_or_404(perm_id)
    
    if request.method == 'DELETE':
        db.session.delete(perm)
        db.session.commit()
        increment_rbac_version()
        log_audit(get_jwt_identity(), "DELETE", "PERMISSION", perm_id, {"name": perm.name})
        db.session.commit()
        return jsonify({"msg": "Permission deleted"}), 200
        
    if request.method == 'PUT':
        data = request.json
        perm.name = data.get('name', perm.name)
        perm.description = data.get('description', perm.description)
        db.session.commit()
        increment_rbac_version()
        log_audit(get_jwt_identity(), "UPDATE", "PERMISSION", perm_id, {"name": perm.name})
        db.session.commit()
        return jsonify({"msg": "Permission updated"})

@admin_rbac_bp.route('/audit', methods=['GET'])
@jwt_required()
@require_role('ADMIN')
def get_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify([{
        "id": l.id,
        "user_id": l.user_id,
        "action": l.action,
        "target_type": l.target_type,
        "target_id": l.target_id,
        "details": l.details,
        "created_at": l.created_at.isoformat()
    } for l in logs])

@admin_rbac_bp.route('/users/batch', methods=['POST'])
@jwt_required()
@require_role('ADMIN')
def get_users_batch():
    data = request.json
    user_ids = data.get('user_ids', [])
    if not user_ids:
        return jsonify({})
    
    # query by primary key `id` because JWT `sub` is `user.id` (which comes as `user_id` from Socket)
    users = User.query.filter(User.id.in_(user_ids)).all()
    result = {
        str(u.id): {
            "username": u.username,
            "user_id": getattr(u, 'user_id', 'N/A')
        } 
        for u in users
    }
    return jsonify(result)
