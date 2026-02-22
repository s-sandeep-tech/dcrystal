import os
import sys
import json

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Role, Permission, Menu, RoleMenu, RolePermission

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

        # Generate the seed script content
        seed_script = f"""import os
import sys
import json

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Role, Permission, Menu, RoleMenu, RolePermission
from app.utils.rbac_cache import increment_rbac_version

def seed_production_rbac():
    app = create_app()
    with app.app_context():
        print("Starting production RBAC seed process...")

        # 1. Create Permissions
        perm_data = json.loads('''{json.dumps(perm_data)}''')
        print("Syncing permissions...")
        for p_item in perm_data:
            perm = Permission.query.filter_by(name=p_item['name']).first()
            if not perm:
                perm = Permission(name=p_item['name'], description=p_item['description'])
                db.session.add(perm)
        db.session.commit()

        # 2. Create Roles
        role_data = json.loads('''{json.dumps(role_data)}''')
        print("Syncing roles...")
        for r_item in role_data:
            role = Role.query.filter_by(name=r_item['name']).first()
            if not role:
                role = Role(name=r_item['name'], description=r_item['description'])
                db.session.add(role)
        db.session.commit()

        # 3. Create Menus
        menu_data = json.loads('''{json.dumps(menu_data)}''')
        print("Syncing menus (hierarchical)...")
        # Step 1: Create menus without parent links
        id_map = {{}}
        for m_item in menu_data:
            menu = Menu.query.filter_by(title=m_item['title']).first()
            if not menu:
                menu = Menu(
                    title=m_item['title'], 
                    url=m_item['url'], 
                    icon=m_item['icon'], 
                    sort_order=m_item['sort_order'],
                    permission_required=m_item['permission_required']
                )
                db.session.add(menu)
                db.session.flush() # Get the auto-generated ID
            id_map[m_item['id']] = menu.id
        
        # Step 2: Update parent links
        for m_item in menu_data:
            if m_item['parent_id']:
                current_menu = db.session.get(Menu, id_map[m_item['id']])
                current_menu.parent_id = id_map.get(m_item['parent_id'])
        db.session.commit()

        # 4. Map Role-Permissions
        role_perm_data = json.loads('''{json.dumps(role_perm_data)}''')
        print("Syncing role-permission mappings...")
        for rpm in role_perm_data:
            role = Role.query.filter_by(name=rpm['role_name']).first()
            perm = Permission.query.filter_by(name=rpm['perm_name']).first()
            if role and perm:
                if not RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first():
                    db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db.session.commit()

        # 5. Map Role-Menus
        role_menu_data = json.loads('''{json.dumps(role_menu_data)}''')
        print("Syncing role-menu mappings...")
        for rmm in role_menu_data:
            role = Role.query.filter_by(name=rmm['role_name']).first()
            menu = Menu.query.filter_by(title=rmm['menu_title']).first()
            if role and menu:
                if not RoleMenu.query.filter_by(role_id=role.id, menu_id=menu.id).first():
                    db.session.add(RoleMenu(role_id=role.id, menu_id=menu.id))
        db.session.commit()

        increment_rbac_version()
        print("Production RBAC seed completed successfully!")

if __name__ == '__main__':
    seed_production_rbac()
"""

        with open('scripts/seed_rbac_production.py', 'w') as f:
            f.write(seed_script)
        
        print(f"Exported to scripts/seed_rbac_production.py")

if __name__ == '__main__':
    export_rbac()
