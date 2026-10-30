"""Unit tests for Sales & Stock Composition Analysis for Purchase Plan."""
import unittest
from unittest.mock import patch, MagicMock
from datetime import date
from decimal import Decimal
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role, Menu, Permission, UserRole, RoleMenu, RolePermission
from app.models import SalesStockCompositionAnalysisSnapshot as Snapshot
from app.dashboard import dashboard_bp
from app.services.sales_stock_composition_analysis_for_purchase_plan import (
    SORT_KEYS,
    calculate_fy_factor,
    compute_ratio,
    compute_turn_ratio,
    sort_purchase_plan_rows,
    fetch_purchase_plan_composition_data,
    get_purchase_plan_options,
)


class PurchasePlanServiceTests(unittest.TestCase):
    def test_fy_factor_calculation(self):
        # 183 days elapsed in FY
        factor, total_days, elapsed_days, fy_label = calculate_fy_factor(date(2026, 9, 30))
        self.assertEqual(total_days, 365)
        self.assertEqual(elapsed_days, 183)
        self.assertEqual(fy_label, 'FY 2026-27')
        self.assertAlmostEqual(factor, 365 / 183)

        # None date returns default 1.0
        f, t, e, lbl = calculate_fy_factor(None)
        self.assertEqual(f, 1.0)
        self.assertEqual(t, 365)
        self.assertEqual(e, 365)

    def test_compute_ratio_and_turn_ratio(self):
        self.assertAlmostEqual(compute_ratio(50, 200), 25.0)
        self.assertIsNone(compute_ratio(50, 0))
        self.assertIsNone(compute_ratio(None, 100))

        self.assertAlmostEqual(compute_turn_ratio(120, 30), 4.0)
        self.assertIsNone(compute_turn_ratio(120, 0))
        self.assertIsNone(compute_turn_ratio(None, 30))

    def test_sort_purchase_plan_rows(self):
        for key in SORT_KEYS[1:]:
            rows = [{'label': label, key: val} for label, val in [
                ('Z', None), ('B', 10), ('C', -2), ('A', 10), ('D', 0), ('E', 2)
            ]]
            with self.subTest(key=key):
                sorted_asc = sort_purchase_plan_rows(rows, sort_by=key, sort_order='asc')
                self.assertEqual([r['label'] for r in sorted_asc], ['C', 'D', 'E', 'A', 'B', 'Z'])

                sorted_desc = sort_purchase_plan_rows(rows, sort_by=key, sort_order='desc')
                self.assertEqual([r['label'] for r in sorted_desc], ['A', 'B', 'E', 'D', 'C', 'Z'])

        rows = [{'label': 'zebra'}, {'label': 'Alpha'}, {'label': 'beta'}]
        self.assertEqual([r['label'] for r in sort_purchase_plan_rows(rows)], ['Alpha', 'beta', 'zebra'])
        self.assertEqual([r['label'] for r in sort_purchase_plan_rows(rows, sort_order='desc')], ['zebra', 'beta', 'Alpha'])

    def test_contributors_returns_both_sales_and_stock(self):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(app)
        with app.app_context():
            db.metadata.create_all(db.engine, tables=[Snapshot.__table__])
            db.session.add_all([
                Snapshot(id=1, branch_id=1, date=date(2026, 9, 30), section='BANGLE',
                         classification='GENERIC', gross_weight=500, provision_weight=200),
                Snapshot(id=2, branch_id=1, date=date(2026, 9, 30), section='BANGLE',
                         classification='BRAND', gross_weight=300, provision_weight=400),
                Snapshot(id=3, branch_id=1, date=None, section='BANGLE',
                         classification='LIFESTYLE', gross_weight=0, provision_weight=600),
            ])
            db.session.commit()

            result = fetch_purchase_plan_composition_data(
                source_date=date(2026, 9, 30),
                selections={},
                path=['BANGLE'],
                contributors=True
            )

            self.assertEqual(result['level'], 'classification')
            # Check sales contributors
            self.assertIn('sales', result)
            self.assertEqual(result['sales']['items'][0]['label'], 'GENERIC')
            self.assertEqual(result['sales']['items'][0]['weight'], 500)
            self.assertEqual(result['sales']['items'][1]['label'], 'BRAND')
            self.assertEqual(result['sales']['items'][1]['weight'], 300)

            # Check stock contributors
            self.assertIn('stock', result)
            self.assertEqual(result['stock']['items'][0]['label'], 'LIFESTYLE')
            self.assertEqual(result['stock']['items'][0]['weight'], 600)
            self.assertEqual(result['stock']['items'][1]['label'], 'BRAND')
            self.assertEqual(result['stock']['items'][1]['weight'], 400)
            self.assertEqual(result['stock']['items'][2]['label'], 'GENERIC')
            self.assertEqual(result['stock']['items'][2]['weight'], 200)


class PurchasePlanSecurityAndRouteTests(unittest.TestCase):
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
            ('GET', '/api/sales-stock-composition-analysis-for-purchase-plan/contributors'),
            ('GET', '/partial/sales-stock-composition-analysis-for-purchase-plan'),
            ('GET', '/partial/sales-stock-composition-analysis-for-purchase-plan/branch'),
            ('GET', '/api/sales-stock-composition-analysis-for-purchase-plan/options'),
            ('POST', '/api/sales-stock-composition-analysis-for-purchase-plan/export'),
            ('POST', '/api/sync/sales-stock-composition-analysis-for-purchase-plan'),
        ]

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def headers(self):
        return {'Authorization': 'Bearer ' + create_access_token(identity=str(self.user.id))}

    def test_anonymous_cannot_access(self):
        for method, path in self.paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.open(path, method=method).status_code, 401)
        response = self.client.get('/sales-stock-composition-analysis-for-purchase-plan')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login'))

    def test_unassigned_user_denied(self):
        for method, path in self.paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.open(path, method=method, headers=self.headers()).status_code, 403)

    def test_assigned_reader_access(self):
        self.role.menus.append(Menu(title='Sales & Stock Composition Purchase Plan',
                                    url='/sales-stock-composition-analysis-for-purchase-plan'))
        db.session.commit()
        self.assertEqual(self.client.get('/api/sales-stock-composition-analysis-for-purchase-plan/options',
                                         headers=self.headers()).status_code, 200)

    def test_options_and_partial_endpoints(self):
        self.role.menus.append(Menu(title='Purchase Plan',
                                    url='/sales-stock-composition-analysis-for-purchase-plan'))
        db.session.commit()

        result = {'rows': [], 'stats': {}, 'total': None, 'items': []}
        for endpoint in [
            '/partial/sales-stock-composition-analysis-for-purchase-plan',
            '/partial/sales-stock-composition-analysis-for-purchase-plan/branch',
            '/api/sales-stock-composition-analysis-for-purchase-plan/contributors',
        ]:
            with self.subTest(endpoint=endpoint), patch(
                'app.dashboard.routes.sales_stock_composition_analysis_for_purchase_plan.render_template',
                return_value='report',
            ), patch(
                'app.dashboard.routes.sales_stock_composition_analysis_for_purchase_plan.fetch_purchase_plan_composition_data',
                return_value=result,
            ) as calculate:
                response = self.client.get(endpoint + '?date=2026-01-01', headers=self.headers())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(calculate.call_args.args[0], date(2026, 1, 1))

    def test_sort_parameters_applied(self):
        self.role.menus.append(Menu(title='Purchase Plan',
                                    url='/sales-stock-composition-analysis-for-purchase-plan'))
        db.session.commit()
        for endpoint in [
            '/partial/sales-stock-composition-analysis-for-purchase-plan',
            '/partial/sales-stock-composition-analysis-for-purchase-plan/branch'
        ]:
            with self.subTest(endpoint=endpoint), patch(
                'app.dashboard.routes.sales_stock_composition_analysis_for_purchase_plan.render_template',
                return_value='report'
            ), patch(
                'app.dashboard.routes.sales_stock_composition_analysis_for_purchase_plan.fetch_purchase_plan_composition_data',
                return_value={'rows': []}
            ) as calculate:
                response = self.client.get(endpoint + '?sort_by=weight_turn&sort_order=desc', headers=self.headers())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(calculate.call_args.kwargs['sort_by'], 'weight_turn')
                self.assertEqual(calculate.call_args.kwargs['sort_order'], 'desc')

    def test_admin_sync_role(self):
        for role in ['ADMIN', 'DATA_SYNC_USER']:
            self.role.name = role
            db.session.commit()
            with patch('app.utils.sync_manager.sync_sales_stock_composition_analysis_data',
                       return_value={'status': 'queued'}) as enqueue:
                response = self.client.post('/api/sync/sales-stock-composition-analysis-for-purchase-plan', headers=self.headers())
                self.assertEqual(response.status_code, 200)
                enqueue.assert_called_once_with('EMP001')


class TemplateRenderingTests(unittest.TestCase):
    def setUp(self):
        templates_dir = Path(__file__).resolve().parents[1] / 'app/templates'
        self.env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

    def test_partial_table_contains_only_requested_columns(self):
        tmpl = self.env.get_template('partials/_view_sales_stock_composition_analysis_for_purchase_plan.html')
        rows = [{
            'label': 'GOLD',
            'sales_composition': 55.25,
            'stock_composition': 45.10,
            'weight_turn': 3.45,
            'turn_na_b': False,
        }]
        total = {
            'sales_composition': 100.0,
            'stock_composition': 100.0,
            'weight_turn': 3.45,
            'turn_na_b': False,
        }
        html = tmpl.render(rows=rows, total=total, stats={}, can_expand=True)

        # Check requested columns are present
        self.assertIn('Product Hierarchy', html)
        self.assertIn('Sales Composition %', html)
        self.assertIn('Stock Composition %', html)
        self.assertIn('Stock Turn in Weight %', html)

        # Check removed columns are NOT present
        self.assertNotIn('Stock Turn in Value', html)
        self.assertNotIn('TSK %', html)

        # Verify values rendered
        self.assertIn('55.25%', html)
        self.assertIn('45.10%', html)
        self.assertIn('3.45%', html)
        self.assertIn('GOLD', html)
        self.assertIn('Grand Total', html)
        self.assertIn('openPurchasePlanChart', html)

    def test_branch_template_renders_four_columns_only(self):
        tmpl = self.env.get_template('partials/_view_sales_stock_composition_analysis_for_purchase_plan_branch.html')
        rows = [{
            'label': 'CHAINS',
            'sales_composition': 20.0,
            'stock_composition': 15.0,
            'weight_turn': 2.1,
            'turn_na_b': False,
        }]
        html = tmpl.render(rows=rows, parent_path=['GOLD'], can_expand=True)

        self.assertIn('CHAINS', html)
        self.assertIn('20.00%', html)
        self.assertIn('15.00%', html)
        self.assertIn('2.10%', html)
        # Should have exactly 4 <td> elements
        self.assertEqual(html.count('<td '), 4)
        self.assertIn('openPurchasePlanChart', html)


if __name__ == '__main__':
    unittest.main()
