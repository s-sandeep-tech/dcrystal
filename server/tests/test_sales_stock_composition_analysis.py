"""Unit tests for Sales & Stock Composition Analysis."""
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
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
from app.services.sales_stock_composition_analysis import calculate_fy_factor, HIERARCHY, FILTERS, composition_analysis_data


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
            ('GET', '/api/sales-stock-composition-analysis/contributors'),
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

    def test_date_filter_options_and_report_requests(self):
        self.role.menus.append(Menu(title='Sales & Stock Composition', url='/sales-stock-composition-analysis'))
        db.session.commit()
        options = self.client.get('/api/sales-stock-composition-analysis/options',
                                  headers=self.headers()).get_json()
        self.assertEqual(options['dates'], [])
        result = {'rows': [], 'stats': {}, 'total': None, 'items': []}
        for endpoint in [
            '/partial/sales-stock-composition-analysis',
            '/partial/sales-stock-composition-analysis/branch',
            '/api/sales-stock-composition-analysis/contributors',
        ]:
            with self.subTest(endpoint=endpoint), patch(
                'app.dashboard.routes.sales_stock_composition_analysis.render_template',
                return_value='report',
            ), patch(
                'app.dashboard.routes.sales_stock_composition_analysis.composition_analysis_data',
                return_value=result,
            ) as calculate:
                response = self.client.get(endpoint + '?date=2026-01-01', headers=self.headers())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(calculate.call_args.args[0], date(2026, 1, 1))

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

    def test_contributor_top_ten_and_signed_returns(self):
        for i in range(12):
            db.session.add(Snapshot(id=i + 1, date=date(2026, 9, 25), branch_id=2,
                section='CHAIN', classification=f'C{i:02}', trans_type='INVOICE', gross_weight=i + 1))
        db.session.add(Snapshot(id=13, date=date(2026, 9, 25), branch_id=2,
            section='CHAIN', classification='Returns', trans_type='SR', gross_weight=-5))
        db.session.add(Snapshot(id=14, date=date(2026, 9, 25), branch_id=3,
            section='CHAIN', classification='Other branch', trans_type='INVOICE', gross_weight=999))
        db.session.commit()
        data = composition_analysis_data(None, {'branch_id': ['2']}, ['CHAIN'], contributors=True)
        self.assertEqual(data['level'], 'classification')
        self.assertEqual(len(data['items']), 11)
        self.assertEqual(data['items'][0], {'label': 'C11', 'weight': 12})
        self.assertEqual(data['items'][-1], {'label': 'Others', 'weight': 3})
        self.assertEqual(data['negative_weight'], -5)
        self.assertEqual(data['net_weight'], 73)
        empty = composition_analysis_data(None, {'branch_id': ['99']}, [], contributors=True)
        self.assertEqual(empty['items'], [])

    def test_provision_sums_repeated_rows_across_all_dates(self):
        for row_id, row_date, section, provision, rate, branch in [
            (1, date(2026, 3, 31), 'CHAIN', 10, 2, 2),
            (2, date(2026, 9, 25), 'CHAIN', 10, 3, 2),
            (3, date(2026, 9, 25), 'CHAIN', 10, 3, 2),
            (4, date(2026, 10, 1), 'BANGLE', 20, 4, 2),
            (5, date(2026, 9, 25), 'CHAIN', 999, 2, 3),
        ]:
            db.session.add(Snapshot(
                id=row_id, date=row_date, branch_id=branch, item_definition_id=1,
                section=section, trans_type='INVOICE', gross_weight=1,
                turn_over=10, provision_weight=provision, purchase_board_rate=rate,
            ))
        db.session.commit()

        data = composition_analysis_data(None, {'branch_id': ['2']})
        self.assertEqual(data['stats']['provision_weight'], 50)
        self.assertEqual(data['stats']['sales_weight'], 4)
        self.assertEqual(data['total']['provision_value'], 160)
        self.assertEqual(sum(row['stock_weight'] for row in data['rows']), 50)
        chain = next(row for row in data['rows'] if row['label'] == 'CHAIN')
        self.assertEqual(chain['stock_weight'], 30)
        self.assertEqual(chain['stock_composition'], 60)
        self.assertAlmostEqual(chain['weight_turn'], 3 * data['factor'] / 30)
        self.assertAlmostEqual(chain['value_turn'], 30 * data['factor'] / 80)

        filtered = composition_analysis_data(None,
            {'branch_id': ['2'], 'section': ['BANGLE']})
        self.assertEqual(filtered['stats']['provision_weight'], 20)
        self.assertEqual(filtered['rows'][0]['stock_composition'], 100)

    def test_missing_rate_does_not_hide_provision_weight(self):
        db.session.add_all([
            Snapshot(id=1, date=date(2026, 9, 25), branch_id=2,
                section='CHAIN', trans_type='INVOICE', provision_weight=10,
                purchase_board_rate=2),
            Snapshot(id=2, date=date(2026, 10, 1), branch_id=2,
                section='CHAIN', provision_weight=5, purchase_board_rate=None),
        ])
        db.session.commit()
        data = composition_analysis_data(None, {'branch_id': ['2']})
        self.assertEqual(data['stats']['provision_weight'], 15)
        self.assertIsNone(data['total']['provision_value'])
        self.assertIsNone(data['total']['value_turn'])

    def test_summary_without_transaction_type_uses_location_date_and_design(self):
        dimensions = dict(zip(HIERARCHY, ['CHAIN', 'BRAND', 'CUSTOM', 'LIGHT', 'C1', 'M1', 920]))
        db.session.add_all([
            Snapshot(id=1, branch_id=2, date=date(2026, 8, 1), barcode='DESIGN-1',
                     gross_weight=100, turn_over=1000, provision_weight=20,
                     purchase_board_rate=10, total_tsk_plusit_charge=50, **dimensions),
            Snapshot(id=2, branch_id=2, date=None, barcode='DESIGN-2',
                     gross_weight=-10, turn_over=-100, **dimensions),
            Snapshot(id=3, branch_id=3, date=date(2026, 9, 30), gross_weight=999),
        ])
        db.session.commit()
        data = composition_analysis_data(None, {'branch_id': ['2']})
        self.assertEqual(data['stats']['sales_weight'], 90)
        self.assertEqual(data['stats']['cutoff_date'], '2026-09-30')
        self.assertAlmostEqual(data['factor'], 365 / 123)
        self.assertAlmostEqual(data['total']['weight_turn'], 90 * 365 / 123 / 20)
        self.assertAlmostEqual(data['total']['value_turn'], 900 * 365 / 123 / 200)
        contributors = composition_analysis_data(None, {'branch_id': ['2']},
            ['CHAIN', 'BRAND', 'CUSTOM', 'LIGHT', 'C1', 'M1', '920'], contributors=True)
        self.assertEqual(contributors['level'], 'design_no')
        self.assertEqual(contributors['items'], [{'label': 'DESIGN-1', 'weight': 100}])
        self.assertEqual(contributors['net_weight'], 90)

    def test_selected_max_date_filters_sales_stock_and_factor(self):
        db.session.add_all([
            Snapshot(id=1, date=date(2026, 9, 30), branch_id=2, section='CHAIN',
                     gross_weight=100, turn_over=1000, provision_weight=20, purchase_board_rate=10),
            Snapshot(id=2, date=date(2026, 10, 15), branch_id=2, section='CHAIN',
                     gross_weight=900, turn_over=9000, provision_weight=180, purchase_board_rate=10),
            Snapshot(id=3, date=None, branch_id=2, section='CHAIN', gross_weight=50),
            Snapshot(id=4, date=date(2026, 9, 1), branch_id=2, section='CHAIN',
                     gross_weight=25, turn_over=250, provision_weight=5, purchase_board_rate=10),
        ])
        db.session.commit()
        data = composition_analysis_data(date(2026, 9, 30), {'branch_id': ['2']})
        self.assertEqual(data['stats']['sales_weight'], 125)
        self.assertEqual(data['stats']['turnover'], 1250)
        self.assertEqual(data['stats']['provision_weight'], 25)
        self.assertEqual(data['total']['provision_value'], 250)
        self.assertAlmostEqual(data['factor'], 365 / 183)
        self.assertAlmostEqual(data['total']['value_turn'], 1250 * 365 / 183 / 250)
        chart = composition_analysis_data(date(2026, 9, 30), {'branch_id': ['2']}, contributors=True)
        self.assertEqual(chart['net_weight'], 125)
        between = composition_analysis_data(date(2026, 10, 1), {'branch_id': ['2']})
        self.assertEqual(between['stats']['sales_weight'], 125)
        self.assertAlmostEqual(between['factor'], 365 / 183)
        self.role.menus.append(Menu(title='Composition', url='/sales-stock-composition-analysis'))
        db.session.commit()
        options = self.client.get('/api/sales-stock-composition-analysis/options', headers=self.headers()).get_json()
        self.assertEqual(options['dates'], ['2026-10-15', '2026-09-30', '2026-09-01'])

    def test_location_factors_are_applied_before_aggregation_and_product_filters(self):
        db.session.add_all([
            Snapshot(id=1, branch_id=1, date=date(2026, 8, 1), section='CHAIN',
                     classification='C1', gross_weight=100, turn_over=1000,
                     provision_weight=20, purchase_board_rate=10),
            Snapshot(id=2, branch_id=1, date=date(2026, 9, 30), section='RING'),
            Snapshot(id=3, branch_id=2, date=date(2026, 8, 31), section='CHAIN',
                     classification='C1', gross_weight=200, turn_over=2000,
                     provision_weight=40, purchase_board_rate=10),
            Snapshot(id=4, branch_id=2, date=date(2026, 10, 15), section='CHAIN',
                     gross_weight=999, turn_over=9999),
        ])
        db.session.commit()
        expected_weight = (100 * 365 / 183 + 200 * 365 / 153) / 60
        expected_value = (1000 * 365 / 183 + 2000 * 365 / 153) / 600
        for path in ([], ['CHAIN']):
            data = composition_analysis_data(date(2026, 10, 1), {'section': ['CHAIN']}, path)
            self.assertIsNone(data['factor'])
            self.assertEqual(len(data['stats']['location_factors']), 2)
            self.assertEqual(data['stats']['turnover'], 3000)
            self.assertEqual(data['stats']['sales_weight'], 300)
            self.assertAlmostEqual(data['total']['weight_turn'], expected_weight)
            self.assertAlmostEqual(data['total']['value_turn'], expected_value)
            self.assertAlmostEqual(data['rows'][0]['value_turn'], expected_value)
            self.assertEqual(data['rows'][0]['sales_composition'], 100)

    def test_undated_location_does_not_silently_drop_annualised_sales(self):
        db.session.add_all([
            Snapshot(id=1, branch_id=1, date=None, gross_weight=10, turn_over=100,
                     provision_weight=10, purchase_board_rate=10),
            Snapshot(id=2, branch_id=2, date=date(2026, 9, 30), gross_weight=20,
                     turn_over=200, provision_weight=20, purchase_board_rate=10),
        ])
        db.session.commit()
        data = composition_analysis_data(None, {})
        self.assertEqual(data['stats']['turnover'], 300)
        self.assertTrue(data['stats']['missing_factor'])
        self.assertIsNone(data['total']['weight_turn'])
        self.assertIsNone(data['total']['value_turn'])


class SummarySyncTests(unittest.TestCase):
    def test_source_mapping_and_atomic_commit(self):
        from app.utils import sync_tasks
        rows = [{'branch_id': 12, 'item_definition_id': i,
                 'max_trans_date': datetime(2026, 9, 30, 16, 30),
                 'location': ' THRISSUR ROUND ', 'design_no': 'D-001',
                 'size': Decimal('22'), 'gross_weight': Decimal('-2.5'),
                 'purchase_board_rate': 5000} for i in range(30001)]
        with patch.object(sync_tasks, 'composition_source_rows', return_value=iter_rows(rows)) as source, \
                patch.object(sync_tasks, 'emit_combined_sync_update'), \
                patch.object(sync_tasks, 'db') as database, \
                patch.object(Snapshot.__table__, 'create'):
            result = sync_tasks.sync_sales_stock_composition_analysis_task()
        self.assertEqual(result, {'status': 'success', 'count': 30001})
        self.assertEqual(source.call_args.kwargs['batch_size'], 30000)
        batches = database.session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(c.args[1]) for c in batches], [30000, 1])
        record = batches[0].args[1][0]
        self.assertEqual(record['date'], date(2026, 9, 30))
        self.assertEqual(record['location_name'], 'THRISSUR ROUND')
        self.assertEqual(record['barcode'], 'D-001')
        self.assertEqual(record['gross_weight'], Decimal('-2.5'))
        database.session.commit.assert_called_once()
        database.session.rollback.assert_not_called()

    def test_exhausted_source_does_not_restart_from_beginning(self):
        from app.utils import sync_tasks
        def failed():
            yield from ({'branch_id': 1, 'item_definition_id': i} for i in range(30000))
            raise sync_tasks.CompositionSourceError('connection retries exhausted')
        with patch.object(sync_tasks, 'composition_source_rows', return_value=failed()) as source, \
                patch.object(sync_tasks, 'emit_combined_sync_update'), \
                patch.object(sync_tasks, 'db') as database, \
                patch.object(Snapshot.__table__, 'create'), \
                patch.object(sync_tasks.logger, 'exception'):
            result = sync_tasks.sync_sales_stock_composition_analysis_task()
        self.assertEqual(result['status'], 'error')
        source.assert_called_once()
        database.session.bulk_insert_mappings.assert_called_once()
        database.session.rollback.assert_called_once()
        database.session.commit.assert_not_called()


def iter_rows(rows):
    yield from rows


class TSKBarTests(unittest.TestCase):
    def test_signed_zero_missing_and_overflow(self):
        env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'app/templates'), autoescape=True)
        macro = env.get_template('partials/_sales_stock_tsk_cell.html').module.tsk_cell
        for value, width, color in [(3.1, '3.1', 'bg-emerald-400'), (-12, '12', 'bg-red-400'),
                                     (0, '0', 'bg-emerald-400'), (150, '100', 'bg-emerald-400')]:
            html = str(macro(value))
            self.assertIn(f'{value:,.2f}%', html)
            self.assertIn(f'width: {width}%;', html)
            self.assertIn(color, html)
        self.assertNotIn('role="img"', str(macro(None)))
        self.assertIn('N/A', str(macro(None)))


if __name__ == '__main__':
    unittest.main()
