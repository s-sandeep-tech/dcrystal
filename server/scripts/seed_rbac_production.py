import os
import sys
import json

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Role, Permission, Menu, RoleMenu, RolePermission, UserRole
from app.models.auth import User
from app.utils.rbac_cache import increment_rbac_version

def seed_default_user_role_for_roleless_users():
    app = create_app()
    with app.app_context():
        print("Starting default role assignment for roleless users...")

        # 1) Fetch the default role
        default_role = Role.query.filter_by(name="USER").first()
        if not default_role:
            raise RuntimeError('Default role "USER" not found in Role table.')

        # 2) Fetch all users
        users = User.query.all()
        if not users:
            print("No users found. Nothing to do.")
            return

        assigned_count = 0

        # 3) For each user, check whether they have any role mapping
        for user in users:
            has_any_role = (
                db.session.query(UserRole.id)
                .filter(UserRole.user_id == user.id)
                .first()
                is not None
            )

            # 4) If user has no roles -> assign USER role
            if not has_any_role:
                db.session.add(UserRole(user_id=user.id, role_id=default_role.id))
                assigned_count += 1

        # 5) Commit once
        db.session.commit()

        if assigned_count > 0:
            increment_rbac_version()

        print(f"Completed. Assigned USER role to {assigned_count} roleless users.")

if __name__ == '__main__':
    seed_default_user_role_for_roleless_users()
