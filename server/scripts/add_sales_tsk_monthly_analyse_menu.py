"""Register only the new monthly report; never migrate an existing report menu."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from app.extensions import db
from app.models.rbac import Menu, Role, RoleMenu
from app.utils.rbac_cache import increment_rbac_version


def seed_monthly_menu():
    menu = Menu.query.filter_by(url='/sales-tsk-monthly-analyse').first()
    if not menu:
        sibling = Menu.query.filter_by(url='/sales-stock-composition-analysis').first()
        menu = Menu(title='Monthly Sales & TSK Analysis', url='/sales-tsk-monthly-analyse',
                    icon='table_chart', sort_order=82, parent_id=sibling.parent_id if sibling else None)
        db.session.add(menu)
        db.session.flush()
    admin = Role.query.filter_by(name='ADMIN').first()
    if admin and not db.session.get(RoleMenu, (admin.id, menu.id)):
        db.session.add(RoleMenu(role_id=admin.id, menu_id=menu.id))
    db.session.commit()
    increment_rbac_version()
    print('Monthly Sales & TSK Analysis menu registered.')


if __name__ == '__main__':
    with create_app().app_context():
        seed_monthly_menu()
