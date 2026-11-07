"""Register the live report. Additional role grants remain managed through RBAC."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from app.extensions import db
from app.models.rbac import Menu, Role, RoleMenu
from app.utils.rbac_cache import increment_rbac_version


def seed_sales_tsk_menu():
    menu = Menu.query.filter(Menu.url.in_(['/sales-tsk-analyse', '/sales-tsk-performance'])).order_by(Menu.id).first()
    if menu:
        # Update the existing row so role grants and sidebar placement survive.
        menu.url = '/sales-tsk-analyse'
    if not menu:
        sibling = Menu.query.filter_by(url='/sales-stock-composition-analysis').first()
        menu = Menu(title='Sales & TSK Performance', url='/sales-tsk-analyse', icon='monitoring',
                    sort_order=81, parent_id=sibling.parent_id if sibling else None)
        db.session.add(menu)
        db.session.flush()
    admin = Role.query.filter_by(name='ADMIN').first()
    if admin and not db.session.get(RoleMenu, (admin.id, menu.id)):
        db.session.add(RoleMenu(role_id=admin.id, menu_id=menu.id))
    db.session.commit()
    increment_rbac_version()
    print('Sales & TSK Performance menu registered.')


if __name__ == '__main__':
    with create_app().app_context():
        seed_sales_tsk_menu()
