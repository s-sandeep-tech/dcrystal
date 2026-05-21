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

def get_client_ip():
    """
    Extracts the original client IP from X-Forwarded-For header when behind proxies
    (like Nginx and Azure Application Gateway), falling back to remote_addr.
    """
    xff = request.headers.get('X-Forwarded-For')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr

def require_api_client(ip_env_var='ALLOWED_THIRD_PARTY_IPS'):
    """
    High-performance decorator to authenticate third-party clients using:
    1. Database-backed API keys hashed with bcrypt.
    2. Zero-CPU & Zero-DB lookup Redis cache (secured via SHA-256).
    3. Proxy-aware IP whitelisting.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            import os
            import hashlib
            from flask import current_app
            from datetime import datetime
            from app.extensions import redis_client
            from app.models.auth import ThirdPartyApiClient
            
            # 1. IP Whitelist Check (Optional if env var is configured)
            allowed_ips_str = os.getenv(ip_env_var)
            if allowed_ips_str:
                client_ip = get_client_ip()
                allowed_ips = [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()]
                if client_ip not in allowed_ips:
                    current_app.logger.warning(
                        f"Access denied from non-whitelisted IP: {client_ip}"
                    )
                    return jsonify({
                        "status": "error", 
                        "message": f"Access denied from IP address {client_ip}."
                    }), 403
            
            # 2. Bearer Token Check
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({
                    "status": "error", 
                    "message": "Authorization header is missing."
                }), 401
                
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return jsonify({
                    "status": "error", 
                    "message": "Authorization header must format as 'Bearer <client_id>.<token>'."
                }), 401
                
            full_token = parts[1]
            token_parts = full_token.split('.', 1)
            if len(token_parts) != 2:
                return jsonify({
                    "status": "error", 
                    "message": "Invalid token format. Must be '<client_id>.<token>'."
                }), 401
                
            client_id, raw_token = token_parts
            
            # 3. High Performance Redis Caching Layer
            # Generate a secure SHA-256 of the token to serve as a fast Redis key
            token_sha256 = hashlib.sha256(full_token.encode('utf-8')).hexdigest()
            cache_key = f"api_client_auth:{token_sha256}"
            
            cached_client_id = None
            try:
                cached_client_id = redis_client.get(cache_key)
            except Exception as e:
                current_app.logger.error(f"Redis cache lookup failed: {e}")
                
            if cached_client_id:
                if isinstance(cached_client_id, bytes):
                    cached_client_id = cached_client_id.decode('utf-8')
                if cached_client_id == client_id:
                    # Cache Hit! Skip database lookup and verification entirely.
                    return fn(*args, **kwargs)
            
            # 4. Cache Miss - Query DB & Verify Hashed Token via SHA-256
            client = ThirdPartyApiClient.query.filter_by(client_id=client_id, is_active=True).first()
            if not client:
                return jsonify({"status": "error", "message": "Invalid credentials."}), 403
                
            if client.expires_at and client.expires_at < datetime.utcnow():
                return jsonify({"status": "error", "message": "Credentials have expired."}), 403
                
            # Verify secret
            if not client.check_token(raw_token):
                return jsonify({"status": "error", "message": "Invalid credentials."}), 403
                
            # 5. Success! Populate Cache for subsequent requests (1 hour TTL)
            try:
                redis_client.setex(cache_key, 3600, client_id)
            except Exception as e:
                current_app.logger.error(f"Failed to cache auth token: {e}")
                
            return fn(*args, **kwargs)
        return wrapper
    return decorator

