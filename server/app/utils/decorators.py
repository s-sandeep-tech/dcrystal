from functools import wraps
from flask import jsonify, redirect, url_for, request, render_template
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
                return render_template('errors/403.html', permission=permission_name), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def require_role(role_name):
    """
    Decorator to ensure user holds a specific role (or one of several roles).
    role_name can be a single string or a list of strings.
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
            
            required_roles = [role_name] if isinstance(role_name, str) else role_name
            
            # Authorization passes if user is ADMIN or has ANY of the required roles
            if 'ADMIN' not in perms and not any(r in perms for r in required_roles):
                if request.path.startswith('/api/'):
                    return jsonify({"msg": f"Forbidden. One of these roles required: {required_roles}"}), 403
                return render_template('errors/403.html', permission=str(required_roles)), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator
