import os
import sys
import json

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Role, Permission, Menu, RoleMenu, RolePermission, UserRole
from app.models.auth import User

def export_rbac():
    app = create_app()
    with app.app_context():
        print("Exporting RBAC data...")

        # 1. Export Permissions
        permissions = Permission.query.all()
        perm_data = [{"name": p.name, "description": p.description} for p in permissions]

        # 2. Export Roles
        roles = Role.query.all()
        role_data = [{"name": r.name, "description": r.description} for r in roles]

        # 3. Export Menus
        menus = Menu.query.order_by(Menu.id).all()
        menu_data = []
        for m in menus:
            menu_data.append({
                "id": m.id,
                "parent_id": m.parent_id,
                "title": m.title,
                "url": m.url,
                "icon": m.icon,
                "sort_order": m.sort_order,
                "permission_required": m.permission_required
            })

        # 4. Export Role-Permission Mappings
        role_perms = RolePermission.query.all()
        role_perm_data = []
        for rp in role_perms:
            role = db.session.get(Role, rp.role_id)
            perm = db.session.get(Permission, rp.permission_id)
            role_perm_data.append({"role_name": role.name, "perm_name": perm.name})

        # 5. Export Role-Menu Mappings
        role_menus = RoleMenu.query.all()
        role_menu_data = []
        for rm in role_menus:
            role = db.session.get(Role, rm.role_id)
            menu = db.session.get(Menu, rm.menu_id)
            role_menu_data.append({"role_name": role.name, "menu_title": menu.title})

        # 6. Export User-Role Mappings
        user_roles = UserRole.query.all()
        user_role_data = []
        for ur in user_roles:
            user = db.session.get(User, ur.user_id)
            role = db.session.get(Role, ur.role_id)
            if user and role:
                user_role_data.append({"user_id": user.user_id, "role_name": role.name})

        # Generate the seed script content
        seed_script = f"""import os
import sys
import json

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Role, Permission, Menu, RoleMenu, RolePermission, UserRole
from app.models.auth import User
from app.utils.rbac_cache import increment_rbac_version

def seed_production_rbac():
    app = create_app()
    with app.app_context():
        print("Starting user-role mapping sync...")

        # Sync User-Role Mappings
        user_role_data = json.loads('''{json.dumps(user_role_data)}''')
        print("Syncing user-role mappings...")
        for urm in user_role_data:
            user = User.query.filter_by(user_id=urm['user_id']).first()
            role = Role.query.filter_by(name=urm['role_name']).first()
            if user and role:
                if not UserRole.query.filter_by(user_id=user.id, role_id=role.id).first():
                    db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.commit()

        increment_rbac_version()
        print("User-role synchronization completed successfully!")

if __name__ == '__main__':
    seed_production_rbac()
"""

        with open('scripts/seed_rbac_production.py', 'w') as f:
            f.write(seed_script)
        
        print(f"Exported to scripts/seed_rbac_production.py")

if __name__ == '__main__':
    export_rbac()
