import unittest
from unittest.mock import patch

from flask import Flask, session
from app.extensions import db
from app.models import Notification, PendingOrderDetailsSnapshot as S
from app.dashboard.routes import pending_order_details as routes


class PendingOrderAccessTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__)
        self.app.config.update(SECRET_KEY='test',SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(self.app)
        self.context=self.app.app_context();self.context.push()
        S.__table__.create(db.engine);Notification.__table__.create(db.engine)
        for i in (1,2):
            db.session.add(S(id=i,classification_owner=f'Owner {i}',make_owner=f'Make Owner {i}',
                collection_owner=f'Collection Owner {i}',make=f'Make {i}',supplier=f'Supplier {i}',
                total_pcs=i,total_weight=i*10))
        db.session.commit()

    def tearDown(self):
        db.session.remove();self.context.pop()

    def check_views(self,roles,count,query=''):
        views=(routes.pending_order_details,routes.get_pending_order_details_partial.__wrapped__,
               routes.get_pending_order_details_leaf_detail.__wrapped__)
        for view in views:
            leaf=view.__name__=='get_pending_order_details_leaf_detail'
            params=query+('&parent_classification_owner=Owner+2&parent_make_owner=Make+Owner+2&parent_collection_owner=Collection+Owner+2' if leaf else '')
            with self.subTest(view=view.__name__,roles=roles),self.app.test_request_context('/?'+params):
                session['roles']=roles;session['user_id']='1'
                with patch.object(routes,'get_owner_names_by_emp_code',return_value=(('Make Owner 1',),())), \
                     patch.object(routes,'render_template',side_effect=lambda template,**context:context):
                    result=view()
                self.assertIsInstance(result,dict,result)
                expected=(0 if roles==['OWNER'] else 1) if leaf else count
                self.assertEqual(len(result.get('rows',result.get('supplier_summaries',[]))),expected)
                if 'filter_options' in result and not query:
                    self.assertEqual(len(result['filter_options']['makes']),count)

    def test_director_matches_manager_on_page_options_ajax_and_leaf(self):
        for roles in [['MANAGER_2'],['EXECUTIVE_DIRECTOR'],['executive_director'],['EXECUTIVE_DIRECTOR','MANAGER_KMU']]:
            self.check_views(roles,2)

    def test_owner_scope_and_selected_filters_remain(self):
        self.check_views(['OWNER'],1)
        self.check_views(['EXECUTIVE_DIRECTOR'],1,'make=Make+2')


if __name__=='__main__':
    unittest.main()
