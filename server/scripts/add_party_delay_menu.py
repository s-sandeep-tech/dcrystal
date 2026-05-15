import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Role, Menu, RoleMenu
from app.utils.rbac_cache import increment_rbac_version

def seed_party_delay_menu():
    app = create_app()
    with app.app_context():
        print("Adding Party Delay Management menu...")
        
        # 1. Find or create Order Tracking parent (or use a suitable one)
        parent = Menu.query.filter_by(title="Order Tracking").first()
        if not parent:
            parent = Menu(title="Order Tracking", url="#", icon="track_changes", sort_order=80)
            db.session.add(parent)
            db.session.commit()
            print("Created 'Order Tracking' parent menu.")

        # 2. Add or update Vendor Delay Management as child
        menu_title = "Vendor Delay Management"
        menu = Menu.query.filter_by(url="/party-delay-management").first()
        if not menu:
            menu = Menu(
                title=menu_title,
                url="/party-delay-management",
                icon="groups",
                sort_order=81,
                parent_id=parent.id,
                permission_required='dashboard.view'
            )
            db.session.add(menu)
            db.session.commit()
            print(f"Added '{menu_title}' menu.")
        else:
            if menu.title != menu_title:
                menu.title = menu_title
                db.session.commit()
                print(f"Updated menu title to '{menu_title}'.")
            else:
                print(f"'{menu_title}' menu already exists.")

        # 3. Associate with ADMIN role
        admin_role = Role.query.filter_by(name="ADMIN").first()
        if admin_role:
            if not RoleMenu.query.filter_by(role_id=admin_role.id, menu_id=menu.id).first():
                db.session.add(RoleMenu(role_id=admin_role.id, menu_id=menu.id))
                
            # Also ensure parent is mapped
            if not RoleMenu.query.filter_by(role_id=admin_role.id, menu_id=parent.id).first():
                db.session.add(RoleMenu(role_id=admin_role.id, menu_id=parent.id))
                
            db.session.commit()
            print("Mapped menu to ADMIN role.")

        increment_rbac_version()
        print("Done!")

if __name__ == '__main__':
    seed_party_delay_menu()
