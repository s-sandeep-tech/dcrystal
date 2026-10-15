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

    def test_date_filter_is_removed_from_options_and_report_requests(self):
        self.role.menus.append(Menu(title='Sales & Stock Composition', url='/sales-stock-composition-analysis'))
        db.session.commit()
        options = self.client.get('/api/sales-stock-composition-analysis/options',
                                  headers=self.headers()).get_json()
        self.assertNotIn('dates', options)
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
                self.assertIsNone(calculate.call_args.args[0])

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

        data = composition_analysis_data(date(2026, 9, 25), {'branch_id': ['2']})
        self.assertEqual(data['stats']['provision_weight'], 50)
        self.assertEqual(data['stats']['sales_weight'], 4)
        self.assertEqual(data['total']['provision_value'], 160)
        self.assertEqual(sum(row['stock_weight'] for row in data['rows']), 50)
        chain = next(row for row in data['rows'] if row['label'] == 'CHAIN')
        self.assertEqual(chain['stock_weight'], 30)
        self.assertEqual(chain['stock_composition'], 60)
        self.assertAlmostEqual(chain['weight_turn'], 3 * data['factor'] / 30)
        self.assertAlmostEqual(chain['value_turn'], 30 * data['factor'] / 80)

        filtered = composition_analysis_data(date(2026, 9, 25),
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
        data = composition_analysis_data(date(2026, 9, 25), {'branch_id': ['2']})
        self.assertEqual(data['stats']['provision_weight'], 15)
        self.assertIsNone(data['total']['provision_value'])
        self.assertIsNone(data['total']['value_turn'])

    def test_summary_without_transaction_type_uses_global_date_and_design(self):
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
        self.assertAlmostEqual(data['factor'], 365 / 183)
        self.assertAlmostEqual(data['total']['weight_turn'], 90 * 365 / 183 / 20)
        self.assertAlmostEqual(data['total']['value_turn'], 900 * 365 / 183 / 200)
        contributors = composition_analysis_data(None, {'branch_id': ['2']},
            ['CHAIN', 'BRAND', 'CUSTOM', 'LIGHT', 'C1', 'M1', '920'], contributors=True)
        self.assertEqual(contributors['level'], 'design_no')
        self.assertEqual(contributors['items'], [{'label': 'DESIGN-1', 'weight': 100}])
        self.assertEqual(contributors['net_weight'], 90)


class SummarySyncTests(unittest.TestCase):
    def test_new_source_maps_date_location_and_design(self):
        from app.utils import sync_tasks
        connection = MagicMock()
        connection.cursor.return_value.fetchmany.side_effect = [[{
            'max_trans_date': datetime(2026, 9, 30, 16, 30),
            'location': ' THRISSUR ROUND ', 'branch_id': 12,
            'design_no': 'D-001', 'size': Decimal('22'),
            'gross_weight': Decimal('-2.5'), 'turn_over': Decimal('-100'),
            'provision_weight': Decimal('10'), 'purchase_board_rate': 5000,
        }], []]
        with patch.object(sync_tasks, 'get_external_db_connection', return_value=connection), \
                patch.object(sync_tasks, 'emit_combined_sync_update'), \
                patch.object(sync_tasks, 'db') as database, \
                patch.object(Snapshot.__table__, 'create'):
            result = sync_tasks.sync_sales_stock_composition_analysis_task()
        self.assertEqual(result['status'], 'success')
        connection.cursor.return_value.execute.assert_any_call(
            'SELECT * FROM ext_view.item_wise_tsk_summary_view')
        record = database.session.bulk_insert_mappings.call_args.args[1][0]
        self.assertEqual(record['date'], date(2026, 9, 30))
        self.assertEqual(record['location_name'], 'THRISSUR ROUND')
        self.assertEqual(record['barcode'], 'D-001')
        self.assertEqual(record['size_label'], '22')
        self.assertEqual(record['gross_weight'], Decimal('-2.5'))
        self.assertEqual(record['purchase_board_rate'], Decimal('5000'))
        self.assertIsNone(record['trans_type'])
        database.session.commit.assert_called_once()

    def test_streams_multiple_batches_and_final_partial_batch(self):
        from app.utils import sync_tasks
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchmany.side_effect = [[{'gross_weight': 1}] * 5000,
                                       [{'gross_weight': -1}] * 5000,
                                       [{'gross_weight': 2}], []]
        with patch.object(sync_tasks, 'get_external_db_connection', return_value=connection), \
                patch.object(sync_tasks, 'emit_combined_sync_update'), \
                patch.object(sync_tasks, 'db') as database, \
                patch.object(Snapshot.__table__, 'create'):
            result = sync_tasks.sync_sales_stock_composition_analysis_task()
        self.assertEqual(result, {'status': 'success', 'count': 10001})
        self.assertEqual([len(call.args[1]) for call in
                          database.session.bulk_insert_mappings.call_args_list], [5000, 5000, 1])
        cursor.fetchall.assert_not_called()
        self.assertTrue(all(call.args == (5000,) for call in cursor.fetchmany.call_args_list))
        self.assertEqual(connection.cursor.call_args.kwargs['name'], 'sales_stock_composition_stream')
        database.session.commit.assert_called_once()
        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    def test_failed_stream_rolls_back_and_retries_without_partial_commit(self):
        from app.utils import sync_tasks
        connection = MagicMock()
        connection.cursor.return_value.fetchmany.side_effect = sum(
            ([[{}] * 5000, RuntimeError('stream interrupted')] for _ in range(5)), [])
        with patch.object(sync_tasks, 'get_external_db_connection', return_value=connection), \
                patch.object(sync_tasks, 'emit_combined_sync_update'), \
                patch.object(sync_tasks, 'db') as database, \
                patch.object(Snapshot.__table__, 'create'), \
                patch.object(sync_tasks.time, 'sleep'), patch.object(sync_tasks.logger, 'exception'):
            result = sync_tasks.sync_sales_stock_composition_analysis_task()
        self.assertEqual(result['status'], 'error')
        self.assertEqual(database.session.rollback.call_count, 5)
        self.assertEqual(connection.close.call_count, 5)
        database.session.commit.assert_not_called()


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
