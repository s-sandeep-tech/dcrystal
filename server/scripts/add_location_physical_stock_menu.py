import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.rbac import Menu
from app.utils.rbac_cache import increment_rbac_version

def add_menu():
    app = create_app()
    with app.app_context():
        title = "Provision and Stock – Location Physical Stock Status"
        url = "/location-physical-stock-status"
        icon = "inventory_2"
        # Find order of "Provision & Stock Status" and place it nearby
        original_menu = Menu.query.filter_by(url="/provision-stock-status").first()
        order = 88 
        if original_menu:
            order = original_menu.sort_order + 1
        
        menu = Menu.query.filter_by(title=title).first()
        if not menu:
            print(f"Creating menu: {title}")
            menu = Menu(title=title, url=url, icon=icon, sort_order=order, permission_required='dashboard.view')
            db.session.add(menu)
            db.session.commit()
            increment_rbac_version()
            print("Menu created successfully.")
        else:
            print(f"Menu '{title}' already exists.")

if __name__ == '__main__':
    add_menu()
