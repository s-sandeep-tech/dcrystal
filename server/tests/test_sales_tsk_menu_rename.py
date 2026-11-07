import unittest
from unittest.mock import patch
from flask import Flask
from app.extensions import db
from app.models.rbac import Menu, Role, RoleMenu, Permission, RolePermission
from scripts.add_sales_tsk_performance_menu import seed_sales_tsk_menu


class SalesTskMenuRenameTests(unittest.TestCase):
    def test_existing_grants_and_placement_survive_idempotent_rename(self):
        app=Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///:memory:'
        db.init_app(app)
        with app.app_context(), patch('scripts.add_sales_tsk_performance_menu.increment_rbac_version'):
            db.metadata.create_all(db.engine,tables=[model.__table__ for model in [Role,Permission,RolePermission,Menu,RoleMenu]])
            admin=Role(name='ADMIN'); viewer=Role(name='READER')
            parent=Menu(title='Sales',url='#')
            db.session.add_all([admin,viewer,parent]);db.session.flush()
            old=Menu(title='Sales & TSK Performance',url='/sales-tsk-performance',parent_id=parent.id,sort_order=42)
            db.session.add(old);db.session.flush()
            old_id=old.id
            db.session.add(RoleMenu(role_id=viewer.id,menu_id=old_id));db.session.commit()
            seed_sales_tsk_menu();seed_sales_tsk_menu()
            menu=Menu.query.filter_by(url='/sales-tsk-analyse').one()
            self.assertEqual(menu.id,old_id)
            self.assertEqual(menu.parent_id,parent.id)
            self.assertEqual(menu.sort_order,42)
            self.assertIsNotNone(db.session.get(RoleMenu,(viewer.id,old_id)))
            self.assertIsNotNone(db.session.get(RoleMenu,(admin.id,old_id)))
            self.assertEqual(Menu.query.filter_by(url='/sales-tsk-performance').count(),0)
            db.session.remove()


if __name__=='__main__':unittest.main()
