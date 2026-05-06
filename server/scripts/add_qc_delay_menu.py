import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Role, Menu, RoleMenu
from app.utils.rbac_cache import increment_rbac_version

def seed_qc_menu():
    app = create_app()
    with app.app_context():
        print("Adding QC Delay Management menu...")
        
        # 1. Find or create Quality Control parent
        qc_parent = Menu.query.filter_by(title="Quality Control").first()
        if not qc_parent:
            qc_parent = Menu(title="Quality Control", url="#", icon="fact_check", sort_order=90)
            db.session.add(qc_parent)
            db.session.commit()
            print("Created 'Quality Control' parent menu.")

        # 2. Add QC Delay Management as child
        menu_title = "QC Delay Management"
        qc_menu = Menu.query.filter_by(title=menu_title).first()
        if not qc_menu:
            qc_menu = Menu(
                title=menu_title,
                url="/qc-delay-management",
                icon="speed",
                sort_order=91,
                parent_id=qc_parent.id,
                permission_required='dashboard.view'
            )
            db.session.add(qc_menu)
            db.session.commit()
            print(f"Added '{menu_title}' menu.")
        else:
            print(f"'{menu_title}' menu already exists.")

        # 3. Associate with ADMIN role
        admin_role = Role.query.filter_by(name="ADMIN").first()
        if admin_role:
            if not RoleMenu.query.filter_by(role_id=admin_role.id, menu_id=qc_menu.id).first():
                db.session.add(RoleMenu(role_id=admin_role.id, menu_id=qc_menu.id))
                
            # Also ensure parent is mapped
            if not RoleMenu.query.filter_by(role_id=admin_role.id, menu_id=qc_parent.id).first():
                db.session.add(RoleMenu(role_id=admin_role.id, menu_id=qc_parent.id))
                
            db.session.commit()
            print("Mapped menu to ADMIN role.")

        increment_rbac_version()
        print("Done!")

if __name__ == '__main__':
    seed_qc_menu()
