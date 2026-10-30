import unittest
from datetime import date
from unittest.mock import patch

from flask import Flask, session
from app.extensions import db
from app.models import Notification, OwnerWiseOrderSummarySnapshot as S
from app.dashboard.routes import owner_wise_order as routes


class OwnerWiseAccessTests(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__)
        app.config.update(SECRET_KEY='test',SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(app)
        self.app=app
        self.context=app.app_context();self.context.push()
        S.__table__.create(db.engine)
        Notification.__table__.create(db.engine)
        for i in (1,2):
            db.session.add(S(classification_owner=f'Owner {i}',make_owner=f'Make Owner {i}',collection_owner=f'Collection Owner {i}',
                batch='Batch',division='Gold',group_name='Gold',purity=750,classification='Generic',collection='Collection',
                order_request_type='Customer',order_type='Customer',order_date=date(2026,10,30),order_ro='RO',
                provision_type='Individual',branch_provision_type='Individual',branch_type='Shop',
                make_owner_emp_code=str(i),collection_owner_emp_code=str(i),
                make=f'Make {i}',supplier=f'Supplier {i}',ordered_pcs=i,ordered_wt=i*10,
                pending_to_be_delv_pcs=i,pending_to_be_delv_wt=i*10))
        db.session.commit()

    def tearDown(self):
        db.session.remove();self.context.pop()

    def check_views(self,roles,expected_count,query=''):
        for view in (routes.owner_wise_order_summary,routes.get_owner_wise_partial.__wrapped__,routes.get_leaf_detail.__wrapped__):
            with self.subTest(view=view.__name__,roles=roles), self.app.test_request_context('/?'+query):
                session['roles']=roles;session['user_id']='1'
                with patch.object(routes,'render_template',side_effect=lambda template,**context:context):
                    result=view()
                self.assertIsInstance(result,dict,result)
                if 'rows' in result:
                    self.assertEqual(len(result['rows']),expected_count)
                else:
                    self.assertEqual(len(result['data']),expected_count)
                if 'filter_options' in result and not query:
                    self.assertEqual(len(result['filter_options']['makes']),expected_count)

    def test_director_matches_manager_in_page_options_ajax_and_details(self):
        for roles in [['MANAGER_2'],['EXECUTIVE_DIRECTOR'],['executive_director'],['EXECUTIVE_DIRECTOR','MANAGER_KMU']]:
            self.check_views(roles,2)

    def test_regular_owner_scope_and_explicit_filters_remain(self):
        self.check_views(['OWNER'],1)
        self.check_views(['EXECUTIVE_DIRECTOR'],1,'make=Make+2')


if __name__=='__main__':
    unittest.main()
