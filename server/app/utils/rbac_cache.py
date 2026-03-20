import json
import logging
from app.extensions import redis_client, db
from app.models import User
from app.models.rbac import Role, Permission, Menu, UserRole, RolePermission, RoleMenu

logger = logging.getLogger(__name__)

def get_rbac_version():
    try:
        val = redis_client.get('rbac:version')
        if not val:
            redis_client.set('rbac:version', '1')
            return '1'
        return val
    except Exception as e:
        logger.error(f"Redis error getting rbac version: {e}")
        return 'fallback'

def invalidate_user_cache(user_id):
    try:
        v = get_rbac_version()
        redis_client.delete(f"user:{user_id}:v{v}:permissions")
        redis_client.delete(f"user:{user_id}:v{v}:menus")
    except Exception as e:
        logger.error(f"Redis error invalidating cache for user {user_id}: {e}")

def increment_rbac_version():
    try:
        redis_client.incr('rbac:version')
    except Exception as e:
        logger.error(f"Redis error incrementing rbac version: {e}")

def get_user_permissions(user_id):
    v = get_rbac_version()
    cache_key = f"user:{user_id}:v{v}:permissions"
    try:
        if v != 'fallback' and redis_client.exists(cache_key):
            return set(redis_client.smembers(cache_key))
    except Exception as e:
        logger.error(f"Redis error getting user permissions: {e}")

    # DB Fallback
    try:
        user = None
        # Try as primary key first if it's numeric
        if str(user_id).isdigit():
            user = db.session.get(User, int(user_id))
        
        # If not found by PK, try by user_id string
        if not user:
            user = User.query.filter_by(user_id=str(user_id)).first()
    except Exception as e:
        logger.error(f"Error querying user {user_id}: {e}")
        return set()

    if not user:
        return set()
        
    roles = db.session.query(Role).join(UserRole).filter(UserRole.user_id == user.id).all()
    perms = set()
    is_admin = user.is_admin or user.username == 'admin' # Double fallback for admin
    
    for r in roles:
        if r.name == 'ADMIN':
            is_admin = True
        for p in r.permissions:
            perms.add(p.name)
            
    if is_admin:
        perms.add('ADMIN') # Virtual permission for ADMIN role
        
    try:
        if v != 'fallback' and perms:
            redis_client.sadd(cache_key, *perms)
            redis_client.expire(cache_key, 86400) # 24h
    except Exception as e:
        logger.error(f"Redis error setting user permissions: {e}")
        
    return perms

def build_menu_tree(user_id):
    # Try cache
    v = get_rbac_version()
    cache_key = f"user:{user_id}:v{v}:menus"
    try:
        if v != 'fallback':
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis error getting user menu tree: {e}")

    # Fallback to DB
    perms = get_user_permissions(user_id)
    is_admin = 'ADMIN' in perms
    
    try:
        user = None
        if str(user_id).isdigit():
            user = db.session.get(User, int(user_id))
            
        if not user:
            user = User.query.filter_by(user_id=str(user_id)).first()
            
        role_ids = [r.role_id for r in UserRole.query.filter_by(user_id=user.id).all()] if user else []
    except Exception as e:
        logger.error(f"Error getting role IDs for {user_id}: {e}")
        role_ids = []
    
    if is_admin:
        allowed_menus = Menu.query.order_by(Menu.sort_order).all()
    else:
        # Menus connected to user's roles
        allowed_menus = db.session.query(Menu).join(RoleMenu).filter(RoleMenu.role_id.in_(role_ids)).order_by(Menu.sort_order).all()
        # Filter by required permission
        allowed_menus = [m for m in allowed_menus if not m.permission_required or m.permission_required in perms]

    # Build tree
    menu_dict = {m.id: {"id": m.id, "title": m.title, "url": m.url, "icon": m.icon, "children": []} for m in allowed_menus}
    
    tree = []
    for m in allowed_menus:
        if m.parent_id and m.parent_id in menu_dict:
            menu_dict[m.parent_id]["children"].append(menu_dict[m.id])
        elif not m.parent_id:
            tree.append(menu_dict[m.id])
            
    # Prune empty parents recursively
    def prune(node_list):
        valid = []
        for node in node_list:
            if node["children"]:
                node["children"] = prune(node["children"])
            # Keep if it has children, OR it's a valid nav item (leaf with URL)
            if node["children"] or node["url"]:
                valid.append(node)
        return valid

    pruned_tree = prune(tree)
    
    try:
        if v != 'fallback':
            redis_client.set(cache_key, json.dumps(pruned_tree), ex=86400)
    except Exception as e:
        logger.error(f"Redis error setting user menu tree: {e}")
        
    return pruned_tree
