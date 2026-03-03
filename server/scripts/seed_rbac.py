import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role, Permission, Menu, RoleMenu, RolePermission, UserRole
from app.utils.rbac_cache import increment_rbac_version

def seed_rbac():
    app = create_app()
    with app.app_context():
        print("Starting RBAC core seed process...")
        
        # 1. Create Permissions
        perms = [
            'rbac.role.view', 'rbac.role.create', 'rbac.role.update', 'rbac.role.delete',
            'rbac.menu.view', 'rbac.menu.create', 'rbac.menu.update', 'rbac.menu.delete',
            'rbac.user.assign_roles',
            'report.view', 'report.export',
            'dashboard.view'
        ]
        
        print("Creating permissions...")
        perm_objects = {}
        for p in perms:
            perm = Permission.query.filter_by(name=p).first()
            if not perm:
                perm = Permission(name=p, description=f"Permission for {p}")
                db.session.add(perm)
            perm_objects[p] = perm
        db.session.commit()

        # 2. Create Roles
        print("Creating roles...")
        roles_data = ['ADMIN', 'MANAGER_1', 'MANAGER_2', 'MANAGER_3', 'USER']
        role_objects = {}
        for r in roles_data:
            role = Role.query.filter_by(name=r).first()
            if not role:
                role = Role(name=r, description=f"{r} Role")
                db.session.add(role)
            role_objects[r] = role
        db.session.commit()

        # 3. Create Menus
        print("Creating menus...")
        
        # Core Dashboard Items
        app_menus = [
            {"title": "Dashboard", "url": "/", "icon": "grid_view", "order": 10},
            {"title": "Process Drill-Down", "url": "/inventory", "icon": "inventory_2", "order": 20},
            {"title": "Order Status", "url": "/orderstatus", "icon": "precision_manufacturing", "order": 30},
            {"title": "Location Wise Order Status", "url": "/locationwiseorderstatus", "icon": "map", "order": 40},
            {"title": "Location Wise Stock Snapshot", "url": "/branchweight", "icon": "scale", "order": 50},
            {"title": "Branch Weight Allocation & Refillv2", "url": "/branchweightv2", "icon": "dvr", "order": 60},
            {"title": "StageLevel Delay Report", "url": "/stageleveldelay", "icon": "query_stats", "order": 65},
            {"title": "Owner Wise Summary", "url": "/ownerwiseordersummary", "icon": "person_pin", "order": 70},
            {"title": "Outstanding PO Status", "url": "/outstanding_purchase_orders", "icon": "receipt_long", "order": 75},
            {"title": "Crystal General Issues", "url": "/crystal_issues", "icon": "report_problem", "order": 80},
            {"title": "Quality Control", "url": "#", "icon": "fact_check", "order": 90},
            {"title": "Dispatch", "url": "#", "icon": "local_shipping", "order": 100}
        ]
        
        for m_data in app_menus:
            menu = Menu.query.filter_by(title=m_data["title"]).first()
            if not menu:
                menu = Menu(title=m_data["title"], url=m_data["url"], icon=m_data["icon"], sort_order=m_data["order"], permission_required='dashboard.view')
                db.session.add(menu)
        
        # RBAC Admin menus were moved to the Settings page. 
        # Remove them if they exist in the database from an older seed.
        for cleanup_title in ["Security Admin", "Manage Roles", "Manage Menus", "User Mappings"]:
            m = Menu.query.filter_by(title=cleanup_title).first()
            if m:
                print(f"Cleaning up old '{cleanup_title}' menu since it moved to Settings...")
                db.session.delete(m)
        db.session.commit()

        # 4. Map Admin Role to Base Admin Permissions (Though ADMIN gets virtual bypass, good for explicit tracking)
        print("Mapping admin permissions...")
        base_admin_perms = ['rbac.role.view', 'rbac.menu.view', 'rbac.user.assign_roles']
        role_admin = role_objects['ADMIN']
        for p in base_admin_perms:
            if not RolePermission.query.filter_by(role_id=role_admin.id, permission_id=perm_objects[p].id).first():
                db.session.add(RolePermission(role_id=role_admin.id, permission_id=perm_objects[p].id))

        print("Mapping dashboard permissions to all roles...")
        base_dashboard_perms = ['dashboard.view']
        for r_name in roles_data:
            role = role_objects[r_name]
            for p in base_dashboard_perms:
                if not RolePermission.query.filter_by(role_id=role.id, permission_id=perm_objects[p].id).first():
                    db.session.add(RolePermission(role_id=role.id, permission_id=perm_objects[p].id))


        # 5. Assign default admin user the ADMIN role
        print("Mapping admin user to ADMIN role...")
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            if not UserRole.query.filter_by(user_id=admin_user.id, role_id=role_objects['ADMIN'].id).first():
                db.session.add(UserRole(user_id=admin_user.id, role_id=role_objects['ADMIN'].id))
        else:
            print("Warning: Default 'admin' user not found. Run main app first to create it.")

        db.session.commit()
        
        # Bump the cache version to enforce clear
        increment_rbac_version()
        
        print("RBAC Core seed completed successfully!")

if __name__ == '__main__':
    seed_rbac()
