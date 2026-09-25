"""Unit tests for Sales & Stock Composition Analysis."""
import unittest
from unittest.mock import patch
from datetime import date
from decimal import Decimal

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role, Menu, Permission, UserRole, RoleMenu, RolePermission
from app.models import SalesStockCompositionAnalysisSnapshot as Snapshot
from app.dashboard import dashboard_bp
from app.services.sales_stock_composition_analysis import calculate_fy_factor, HIERARCHY, FILTERS


class SalesStockCompositionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY='test-only-session-key-with-32-characters',
            JWT_SECRET_KEY='test-only-jwt-key-with-32-characters'
        )
        db.init_app(self.app)
        JWTManager(self.app)
        self.app.register_blueprint(dashboard_bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.metadata.create_all(db.engine, tables=[m.__table__ for m in
                              [User, Role, Menu, Permission, UserRole, RoleMenu, RolePermission, Snapshot]])
        self.role = Role(name='READER')
        self.user = User(user_id='EMP001', username='reader', email='reader@example.com',
                         password_hash='unused', is_active=True, roles=[self.role])
        db.session.add(self.user)
        db.session.commit()
        self.client = self.app.test_client()
        self.paths = [
            ('GET', '/partial/sales-stock-composition-analysis'),
            ('GET', '/partial/sales-stock-composition-analysis/branch'),
            ('GET', '/api/sales-stock-composition-analysis/options'),
            ('POST', '/api/sales-stock-composition-analysis/export'),
            ('POST', '/api/sync/sales-stock-composition-analysis'),
        ]

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def headers(self):
        return {'Authorization': 'Bearer ' + create_access_token(identity=str(self.user.id))}

    def test_anonymous_cannot_read_or_sync(self):
        for method, path in self.paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.open(path, method=method).status_code, 401)
        response = self.client.get('/sales-stock-composition-analysis')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login'))

    def test_unassigned_user_denied(self):
        for method, path in self.paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.open(path, method=method, headers=self.headers()).status_code, 403)

    def test_assigned_reader_options_and_sync_denial(self):
        self.role.menus.append(Menu(title='Sales & Stock Composition', url='/sales-stock-composition-analysis'))
        db.session.commit()
        self.assertEqual(self.client.get('/api/sales-stock-composition-analysis/options',
                                         headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.post('/api/sync/sales-stock-composition-analysis',
                                          headers=self.headers()).status_code, 403)

    def test_admin_and_sync_role(self):
        for role in ['ADMIN', 'DATA_SYNC_USER']:
            self.role.name = role
            db.session.commit()
            with patch('app.utils.sync_manager.sync_sales_stock_composition_analysis_data',
                       return_value={'status': 'queued'}) as enqueue:
                response = self.client.post('/api/sync/sales-stock-composition-analysis', headers=self.headers())
                self.assertEqual(response.status_code, 200)
                enqueue.assert_called_once_with('EMP001')

    def test_fy_factor_calculation(self):
        factor, fy_days, elapsed_days, fy_label = calculate_fy_factor(date(2026, 4, 1))
        self.assertGreaterEqual(factor, Decimal('365'))
        self.assertEqual(elapsed_days, 1)

        factor_end, fy_days_end, elapsed_days_end, fy_label_end = calculate_fy_factor(date(2027, 3, 31))
        self.assertEqual(round(factor_end, 2), Decimal('1.00'))

    def test_hierarchy_levels(self):
        self.assertEqual(HIERARCHY, [
            'section',
            'classification',
            'make',
            'wide_range',
            'collection',
            'master_collection',
            'purity'
        ])


if __name__ == '__main__':
    unittest.main()
