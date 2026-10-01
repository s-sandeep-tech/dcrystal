import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from flask import Flask, session
from flask_jwt_extended import JWTManager, create_access_token
from app.extensions import db
from app.models.customer_order_analysis import CustomerOrderAnalysisSnapshot as Snapshot
from app.models.snapshots import BranchAuthoritySnapshot
from app.dashboard.routes.customer_order_monitoring import (
    customer_order_monitoring_data, customer_order_monitoring_export,
)


class MonitoringRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder='../app/templates')
        self.app.config.update(TESTING=True, SECRET_KEY='test-secret-key-at-least-32-chars',
                               JWT_SECRET_KEY='test-jwt-secret-key-at-least-32-chars',
                               SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(self.app)
        JWTManager(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        Snapshot.__table__.create(db.engine)
        BranchAuthoritySnapshot.__table__.create(db.engine)
        self.app.add_url_rule('/api/monitor', view_func=customer_order_monitoring_data)
        self.app.add_url_rule('/api/monitor/export', view_func=customer_order_monitoring_export)
        self.client = self.app.test_client()
        self.headers = {'Authorization': 'Bearer ' + create_access_token(identity='1')}
        for i in range(1, 4):
            db.session.add(Snapshot(id=i, request_no=f'R{i}', sooc=f'S{i}', branch_id=i,
                location=f'Branch {i}', bh_emp_code=str(i), party_name=f'Supplier {i}', party_code=f'Code {i}',
                order_status='Delivered to shop', total_pending_pcs=i, total_pending_wt=i * 10,
                customer_delivery_pending_pcs=i, expected_delivery_date=datetime.now() - timedelta(days=3)))
        db.session.add(BranchAuthoritySnapshot(branch_id=2, emp_code=1235))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def login(self, roles, user_id='1'):
        with self.client.session_transaction() as s:
            s['user_id'] = user_id
            s['roles'] = roles

    def test_auth_required_even_for_admin_role_without_identity(self):
        self.assertEqual(self.client.get('/api/monitor').status_code, 401)
        self.assertEqual(self.client.get('/api/monitor', headers=self.headers).status_code, 401)

    def test_admin_all_rows_and_filters(self):
        self.login(['ADMIN'])
        data = self.client.get('/api/monitor', headers=self.headers).get_json()
        self.assertEqual(data['stats']['pieces'], 6)
        data = self.client.get('/api/monitor?location=Branch+2', headers=self.headers).get_json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['stats']['pieces'], 2)

    def test_business_head_scope_and_masking(self):
        self.login(['BUSINESS_HEAD'], '2')
        data = self.client.get('/api/monitor', headers=self.headers).get_json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['options']['location'], ['Branch 2'])
        self.assertNotIn('Supplier 2', data['html'])
        self.assertNotIn('Code 2', data['html'])
        self.assertIn('XXX', data['html'])

    def test_showroom_scope_and_no_mapping(self):
        self.login(['SHOWROOM_MANAGER'], '1235')
        data = self.client.get('/api/monitor', headers=self.headers).get_json()
        self.assertEqual(data['total'], 1)
        self.assertNotIn('Supplier', data['html'].split('<tbody>')[1])
        self.login(['SHOWROOM_MANAGER'], '999')
        data = self.client.get('/api/monitor', headers=self.headers).get_json()
        self.assertEqual(data['total'], 0)

    def test_export_permission_and_masking(self):
        self.login(['BUSINESS_HEAD'], '2')
        with patch('app.utils.decorators.get_user_permissions', return_value={'report.export'}):
            response = self.client.get('/api/monitor/export', headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertIn('XXX', response.text)
            self.assertNotIn('Supplier 2', response.text)
            self.assertNotIn('Branch 1', response.text)

    def test_conflicting_sooc_stops_aggregation(self):
        self.login(['ADMIN'])
        db.session.add(Snapshot(request_no='Other', sooc='S1'))
        db.session.commit()
        self.assertEqual(self.client.get('/api/monitor', headers=self.headers).status_code, 409)
