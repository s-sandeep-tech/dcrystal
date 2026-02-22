import os
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
        perm_data = json.loads('''[{"name": "rbac.role.view", "description": "Permission for rbac.role.view"}, {"name": "rbac.role.create", "description": "Permission for rbac.role.create"}, {"name": "rbac.role.update", "description": "Permission for rbac.role.update"}, {"name": "rbac.role.delete", "description": "Permission for rbac.role.delete"}, {"name": "rbac.menu.view", "description": "Permission for rbac.menu.view"}, {"name": "rbac.menu.create", "description": "Permission for rbac.menu.create"}, {"name": "rbac.menu.update", "description": "Permission for rbac.menu.update"}, {"name": "rbac.menu.delete", "description": "Permission for rbac.menu.delete"}, {"name": "rbac.user.assign_roles", "description": "Permission for rbac.user.assign_roles"}, {"name": "report.view", "description": "Permission for report.view"}, {"name": "report.export", "description": "Permission for report.export"}, {"name": "dashboard.view", "description": "Permission for dashboard.view"}]''')
        print("Syncing permissions...")
        for p_item in perm_data:
            perm = Permission.query.filter_by(name=p_item['name']).first()
            if not perm:
                perm = Permission(name=p_item['name'], description=p_item['description'])
                db.session.add(perm)
        db.session.commit()

        # 2. Create Roles
        role_data = json.loads('''[{"name": "ADMIN", "description": "ADMIN Role"}, {"name": "MANAGER_1", "description": "MANAGER_1 Role"}, {"name": "MANAGER_2", "description": "MANAGER_2 Role"}, {"name": "MANAGER_3", "description": "MANAGER_3 Role"}, {"name": "USER", "description": "USER Role"}]''')
        print("Syncing roles...")
        for r_item in role_data:
            role = Role.query.filter_by(name=r_item['name']).first()
            if not role:
                role = Role(name=r_item['name'], description=r_item['description'])
                db.session.add(role)
        db.session.commit()

        # 3. Create Menus
        menu_data = json.loads('''[{"id": 1, "parent_id": null, "title": "Dashboard", "url": "/", "icon": "home", "sort_order": 10, "permission_required": "dashboard.view"}, {"id": 6, "parent_id": null, "title": "Process Drill-Down", "url": "/inventory", "icon": "inventory_2", "sort_order": 20, "permission_required": "dashboard.view"}, {"id": 7, "parent_id": null, "title": "Order Status", "url": "/orderstatus", "icon": "precision_manufacturing", "sort_order": 30, "permission_required": "dashboard.view"}, {"id": 8, "parent_id": null, "title": "Location Wise Order Status", "url": "/locationwiseorderstatus", "icon": "map", "sort_order": 40, "permission_required": "dashboard.view"}, {"id": 9, "parent_id": null, "title": "Location Wise Stock Snapshot", "url": "/branchweight", "icon": "scale", "sort_order": 50, "permission_required": "dashboard.view"}, {"id": 10, "parent_id": null, "title": "Branch Weight Allocation & Refillv2", "url": "/branchweightv2", "icon": "dvr", "sort_order": 60, "permission_required": "dashboard.view"}, {"id": 11, "parent_id": null, "title": "Owner Wise Summary", "url": "/ownerwiseordersummary", "icon": "person_pin", "sort_order": 70, "permission_required": "dashboard.view"}, {"id": 12, "parent_id": null, "title": "Crystal General Issues", "url": "/crystal_issues", "icon": "report_problem", "sort_order": 80, "permission_required": "dashboard.view"}, {"id": 13, "parent_id": null, "title": "Quality Control", "url": "#", "icon": "fact_check", "sort_order": 90, "permission_required": "dashboard.view"}, {"id": 14, "parent_id": null, "title": "Dispatch", "url": "#", "icon": "local_shipping", "sort_order": 100, "permission_required": "dashboard.view"}]''')
        print("Syncing menus (hierarchical)...")
        # Step 1: Create menus without parent links
        id_map = {}
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
        role_perm_data = json.loads('''[{"role_name": "ADMIN", "perm_name": "rbac.role.view"}, {"role_name": "ADMIN", "perm_name": "rbac.menu.view"}, {"role_name": "ADMIN", "perm_name": "rbac.user.assign_roles"}, {"role_name": "ADMIN", "perm_name": "dashboard.view"}, {"role_name": "MANAGER_1", "perm_name": "dashboard.view"}, {"role_name": "MANAGER_2", "perm_name": "dashboard.view"}, {"role_name": "MANAGER_3", "perm_name": "dashboard.view"}, {"role_name": "USER", "perm_name": "dashboard.view"}]''')
        print("Syncing role-permission mappings...")
        for rpm in role_perm_data:
            role = Role.query.filter_by(name=rpm['role_name']).first()
            perm = Permission.query.filter_by(name=rpm['perm_name']).first()
            if role and perm:
                if not RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first():
                    db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db.session.commit()

        # 5. Map Role-Menus
        role_menu_data = json.loads('''[{"role_name": "ADMIN", "menu_title": "Dashboard"}, {"role_name": "ADMIN", "menu_title": "Process Drill-Down"}, {"role_name": "USER", "menu_title": "Order Status"}, {"role_name": "USER", "menu_title": "Owner Wise Summary"}, {"role_name": "MANAGER_2", "menu_title": "Dashboard"}, {"role_name": "MANAGER_2", "menu_title": "Process Drill-Down"}, {"role_name": "MANAGER_2", "menu_title": "Order Status"}, {"role_name": "MANAGER_2", "menu_title": "Location Wise Stock Snapshot"}, {"role_name": "MANAGER_2", "menu_title": "Owner Wise Summary"}, {"role_name": "MANAGER_2", "menu_title": "Quality Control"}]''')
        print("Syncing role-menu mappings...")
        for rmm in role_menu_data:
            role = Role.query.filter_by(name=rmm['role_name']).first()
            menu = Menu.query.filter_by(title=rmm['menu_title']).first()
            if role and menu:
                if not RoleMenu.query.filter_by(role_id=role.id, menu_id=menu.id).first():
                    db.session.add(RoleMenu(role_id=role.id, menu_id=menu.id))
        db.session.commit()

        # 6. Safety Sync: Map admin user to ADMIN role
        print("Ensuring admin user has ADMIN role...")
        try:
            from app.models.auth import User
            from app.models.rbac import UserRole
            admin_user = User.query.filter_by(username='admin').first()
            admin_role = Role.query.filter_by(name='ADMIN').first()
            if admin_user and admin_role:
                if not UserRole.query.filter_by(user_id=admin_user.id, role_id=admin_role.id).first():
                    db.session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
                    db.session.commit()
                    print("Mapped 'admin' user to 'ADMIN' role.")
        except Exception as e:
            print(f"Note: Could not auto-map admin user (this is normal if customized): {e}")

        increment_rbac_version()
        print("Production RBAC seed completed successfully!")

if __name__ == '__main__':
    seed_production_rbac()
