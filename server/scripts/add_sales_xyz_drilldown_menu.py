"""Register Sales XYZ Drilldown and grant the ADMIN role access."""
from app import create_app
from app.extensions import db
from app.models.rbac import Menu, Role, RoleMenu
from app.utils.rbac_cache import increment_rbac_version


def seed_menu():
    url = '/sales-xyz-drilldown'
    menu = Menu.query.filter_by(url=url).first()
    if menu is None:
        sibling = Menu.query.filter_by(url='/sales-tsk-monthly-analyse').first()
        menu = Menu(title='Sales XYZ Drilldown', url=url, icon='account_tree',
                    sort_order=84, parent_id=sibling.parent_id if sibling else None)
        db.session.add(menu)
        db.session.flush()
    admin = Role.query.filter_by(name='ADMIN').first()
    if admin and not db.session.get(RoleMenu, (admin.id, menu.id)):
        db.session.add(RoleMenu(role_id=admin.id, menu_id=menu.id))
    db.session.commit()
    increment_rbac_version()


if __name__ == '__main__':
    with create_app().app_context():
        seed_menu()
