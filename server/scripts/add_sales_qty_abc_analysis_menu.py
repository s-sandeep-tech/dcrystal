"""Idempotently register the independent quantity ABC report and its ADMIN grant."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from app.extensions import db
from app.models.rbac import Menu, Role, RoleMenu
from app.utils.rbac_cache import increment_rbac_version


def seed_abc_menu():
    menu = Menu.query.filter_by(url='/sales-qty-abc-analysis').first()
    if not menu:
        sibling = Menu.query.filter_by(url='/sales-tsk-monthly-analyse').first()
        menu = Menu(title='Sales Quantity ABC Analysis', url='/sales-qty-abc-analysis',
                    icon='account_tree', sort_order=83, parent_id=sibling.parent_id if sibling else None)
        db.session.add(menu)
        db.session.flush()
    admin = Role.query.filter_by(name='ADMIN').first()
    if admin and not db.session.get(RoleMenu, (admin.id, menu.id)):
        db.session.add(RoleMenu(role_id=admin.id, menu_id=menu.id))
    db.session.commit()
    increment_rbac_version()
    print('Sales Quantity ABC Analysis menu registered.')


if __name__ == '__main__':
    with create_app().app_context():
        seed_abc_menu()
