import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Menu
from app.utils.rbac_cache import increment_rbac_version


def add_menu():
    app = create_app()
    with app.app_context():
        title = "Location Provision & Stock Analysis"
        url = "/location-provision-stock-analysis"
        sort_order = 89

        menu = Menu.query.filter_by(url=url).first()
        if menu:
            print(f"Menu already exists: {title}")
            return

        db.session.add(Menu(
            title=title,
            url=url,
            icon="analytics",
            sort_order=sort_order,
            permission_required="dashboard.view",
        ))
        db.session.commit()
        increment_rbac_version()
        print(f"Menu created: {title}")


if __name__ == "__main__":
    add_menu()
