from functools import wraps
from flask import jsonify, redirect, url_for, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.utils.rbac_cache import get_user_permissions

def require_perm(permission_name):
    """
    Decorator to ensure user has a specific permission.
    If the user has the 'ADMIN' virtual permission, authorization naturally passes.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                if request.path.startswith('/api/'):
                    return jsonify({"msg": "Unauthorized. Please log in."}), 401
                return redirect(url_for('dashboard.login'))

            user_id = get_jwt_identity()
            perms = get_user_permissions(user_id)
            if 'ADMIN' not in perms and permission_name not in perms:
                if request.path.startswith('/api/'):
                    return jsonify({"msg": f"Forbidden. Missing permission: {permission_name}"}), 403
                return jsonify({"msg": f"Forbidden. Missing permission: {permission_name}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def require_role(role_name):
    """
    Decorator to ensure user holds a specific role.
    For ADMIN role specifically, we check the virtual 'ADMIN' permission in the sets.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                if request.path.startswith('/api/'):
                    return jsonify({"msg": "Unauthorized. Please log in."}), 401
                return redirect(url_for('dashboard.login'))

            user_id = get_jwt_identity()
            perms = get_user_permissions(user_id)
            if role_name == 'ADMIN' and 'ADMIN' not in perms:
                return jsonify({"msg": "Forbidden. Admin role required."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
