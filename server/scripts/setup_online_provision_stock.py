"""Create only online-stock tables and register its independent report menu."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extensions import db
from app.models.online_provision_stock import OnlineProvisionStockRawSnapshot, OnlineProvisionStockRawStaging
from app.models.rbac import Menu
from app.utils.rbac_cache import increment_rbac_version

URL = '/online-provision-stock-status'
TITLE = 'Online Provision Stock status'


def setup_online_provision_stock():
    for model in (OnlineProvisionStockRawSnapshot, OnlineProvisionStockRawStaging):
        model.__table__.create(db.engine, checkfirst=True)
    menu = Menu.query.filter_by(url=URL).first()
    if menu is None:
        original = Menu.query.filter_by(url='/location-physical-stock-status').first()
        menu = Menu(title=TITLE, url=URL, icon='inventory_2',
                    sort_order=(original.sort_order + 1 if original else 89),
                    permission_required=(original.permission_required if original else 'dashboard.view'))
        db.session.add(menu)
        db.session.flush()
        if original:
            # Same audience as the source report; do not add broader role grants.
            for role in original.roles.all():
                role.menus.append(menu)
        db.session.commit()
        increment_rbac_version()
    return menu


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        setup_online_provision_stock()
        print('Online Provision Stock status tables and menu are ready.')
