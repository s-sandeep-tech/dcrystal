"""Clone isolation, unchanged query arithmetic, sync, and wiring regressions."""
import ast
import inspect
import re
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from app.extensions import db
from app.dashboard.routes import location_physical_stock_status as physical
from app.dashboard.routes import online_provision_stock_status as online
from app.models.snapshots import ProvisionStockRawSnapshot, ProvisionStockRawStaging
from app.models.online_provision_stock import OnlineProvisionStockRawSnapshot, OnlineProvisionStockRawStaging
from app.utils import online_provision_stock_sync as sync

ROOT = Path(__file__).resolve().parents[1]


def sql_constants(path):
    return [n.value.replace('online_provision_stock_raw_snapshot', 'provision_stock_raw_snapshot')
            for n in ast.walk(ast.parse(path.read_text()))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and re.search(r'\b(SELECT|WITH)\b', n.value)]


class OnlineStockCloneTests(unittest.TestCase):
    def test_all_query_arithmetic_is_exact_copy(self):
        self.assertEqual(sql_constants(Path(physical.__file__)), sql_constants(Path(online.__file__)))
        original = ast.parse((ROOT / 'app/utils/export_service.py').read_text())
        function = next(n for n in original.body if getattr(n, 'name', '') == 'generate_location_physical_stock_status_export')
        target = ast.parse((ROOT / 'app/utils/online_provision_stock_export.py').read_text())
        clone = next(n for n in target.body if getattr(n, 'name', '') == 'generate_online_provision_stock_status_export')
        # Complete export function (including Excel cell values/formulas), not only its SQL.
        source = ast.unparse(function)
        copied = ast.unparse(clone)
        copied = copied.replace('online_provision_stock', 'location_physical_stock')
        copied = copied.replace('location_physical_stock_raw_snapshot', 'provision_stock_raw_snapshot')
        copied = copied.replace('Online Provision Stock status', 'Location Physical Stock Status')
        self.assertEqual(source, copied)

    def test_models_have_identical_types_and_distinct_tables_indexes(self):
        for original, clone in [(ProvisionStockRawSnapshot, OnlineProvisionStockRawSnapshot),
                                (ProvisionStockRawStaging, OnlineProvisionStockRawStaging)]:
            self.assertNotEqual(original.__tablename__, clone.__tablename__)
            self.assertEqual([(c.name, str(c.type), c.nullable) for c in original.__table__.columns],
                             [(c.name, str(c.type), c.nullable) for c in clone.__table__.columns])
        self.assertTrue({i.name for i in ProvisionStockRawSnapshot.__table__.indexes}.isdisjoint(
            {i.name for i in OnlineProvisionStockRawSnapshot.__table__.indexes}))

    def test_source_validation_and_mapping_preserve_nulls_and_decimals(self):
        columns = sync.source_columns()
        sync.validate_source_columns([SimpleNamespace(name=c) for c in columns])
        with self.assertRaisesRegex(ValueError, 'missing required columns:.*prov_gr_wt'):
            sync.validate_source_columns([(c,) for c in columns if c != 'prov_gr_wt'])
        row = {c: None for c in columns}
        row.update({'group': 'GOLD', 'prov_gr_wt': Decimal('123.456'), 'stock_qty': Decimal('0')})
        started = datetime(2026, 11, 24)
        mapped = sync.map_source_row(row, started)
        self.assertEqual(mapped['group_name'], 'GOLD')
        self.assertEqual(mapped['prov_gr_wt'], Decimal('123.456'))
        self.assertIsNone(mapped['in_shop_wt'])
        self.assertEqual(mapped['snapshot_date'], started)
        row['last_updated_at'] = datetime(2026, 11, 23)
        self.assertEqual(sync.map_source_row(row, started)['snapshot_date'], row['last_updated_at'])

    def test_independent_routes_and_every_popup_template(self):
        source = Path(online.__file__).read_text()
        self.assertNotIn('FROM provision_stock_raw_snapshot', source)
        self.assertNotIn('/location-physical-stock-status', source)
        self.assertNotIn('loc_phys_stock', source)
        for template in re.findall(r"'((?:partials/)?[^']+\.html)'", source):
            self.assertTrue((ROOT / 'app/templates' / template).exists(), template)
            self.assertIn('online_provision_stock', template)
        self.assertFalse(hasattr(online, 'queue_stock_drilldown_details'))

    def test_modal_functions_and_ids_are_independent(self):
        html = (ROOT / 'app/templates/online_provision_stock_status.html').read_text()
        js = (ROOT / 'app/static/js/online_provision_stock_status.js').read_text()
        for modal in ('drillDownModal', 'provisionDetailsModal', 'inShopDetailsModal', 'stockComparisonModal'):
            self.assertIn(f'id="online-{modal}"', html)
            self.assertIn(f"'online-{modal}'", js)
        self.assertIn("data.type !== 'online_provision_stock_status'", js)
        self.assertNotIn('/location-physical-stock-status', js)
        self.assertIn('onlineOpenDrillDownModal', js)
        self.assertIn('onlineOpenInShopDetailsModal', js)

    def test_validation_failure_does_not_replace_snapshot(self):
        database = MagicMock()
        database.session.query.return_value.one.return_value = (3, Decimal('10'))
        with patch.object(sync, 'db', database), self.assertRaisesRegex(ValueError, 'previous snapshot retained'):
            sync.publish_staging(4, Decimal('10'))
        database.session.execute.assert_not_called()
        database.session.commit.assert_not_called()

    def test_source_failure_never_touches_staging_or_live_tables(self):
        database = MagicMock()
        database.engine.dialect.name = 'sqlite'
        with patch.object(sync, 'db', database), patch(
            'app.utils.sync_tasks.get_external_db_connection', side_effect=RuntimeError('source unavailable')
        ), patch('app.utils.sync_tasks.emit_sync_update') as emit, self.assertLogs(sync.logger, level='ERROR'):
            result = sync.sync_online_provision_stock_status_data_task()
        self.assertEqual(result['status'], 'error')
        database.session.query.assert_not_called()
        database.session.execute.assert_not_called()
        self.assertEqual(emit.call_args.args[-1], sync.TASK)

    def test_export_handler_defined_before_worker_startup(self):
        worker = ROOT.parent / 'sync-consumer/main.py'
        source = worker.read_text()
        self.assertLess(source.index('def _handle_export_online_provision_stock_status('),
                        source.index('if __name__ == "__main__":'))
        self.assertIn("elif task_type == 'export_online_provision_stock_status':", source)
        self.assertIn("elif task_type == 'online_provision_stock_status':", source)


class OnlineStockAccessTests(unittest.TestCase):
    def setUp(self):
        from flask_jwt_extended import JWTManager
        from app.dashboard import dashboard_bp
        from app.models.auth import User
        from app.models.rbac import Role, Menu, Permission, UserRole, RoleMenu, RolePermission
        self.app = Flask(__name__, template_folder=str(ROOT / 'app/templates'))
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SECRET_KEY='test-only-session-key-with-32-characters', JWT_SECRET_KEY='test-only-jwt-key-with-32-characters')
        db.init_app(self.app); JWTManager(self.app); self.app.register_blueprint(dashboard_bp)
        self.ctx = self.app.app_context(); self.ctx.push()
        db.metadata.create_all(db.engine, tables=[m.__table__ for m in
            (User, Role, Menu, Permission, UserRole, RoleMenu, RolePermission, OnlineProvisionStockRawSnapshot)])
        self.role = Role(name='READER')
        self.user = User(user_id='TEST-ONLINE', username='online-reader', email='online@example.test',
            password_hash='unused', is_active=True, roles=[self.role])
        db.session.add(self.user); db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove(); self.ctx.pop()

    def headers(self):
        from flask_jwt_extended import create_access_token
        return {'Authorization': 'Bearer ' + create_access_token(identity=str(self.user.id))}

    def test_all_report_endpoints_require_own_menu_access(self):
        from app.models.rbac import Menu
        self.role.menus.append(Menu(title='Physical Stock', url='/location-physical-stock-status'))
        db.session.commit()
        paths = ['/online-provision-stock-status', '/partial/online-provision-stock-status'] + [
            '/api/online-provision-stock-status/' + suffix for suffix in
            ('options', 'collections/search', 'makes/search', 'drilldown', 'in-shop-details',
             'ordered-details', 'provision-details', 'stock-comparison', 'stock-comparison-barcodes')]
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(self.client.get(path).status_code, (302, 401))
                self.assertEqual(self.client.get(path, headers=self.headers()).status_code, 403)
        self.assertEqual(self.client.post('/api/online-provision-stock-status/export', headers=self.headers()).status_code, 403)
        self.role.menus.append(Menu(title='Online Stock', url='/online-provision-stock-status'))
        db.session.commit()
        with patch.object(online, 'redis_client') as redis:
            redis.get.return_value = None
            response = self.client.get('/api/online-provision-stock-status/options', headers=self.headers())
        self.assertEqual(response.status_code, 200)

    def test_sync_uses_only_online_task_and_requires_sync_role(self):
        from app.utils import sync_manager
        endpoint = '/api/sync/online-provision-stock-status'
        self.assertEqual(self.client.post(endpoint, headers=self.headers()).status_code, 403)
        self.role.name = 'DATA_SYNC_USER'; db.session.commit()
        with patch.object(sync_manager, 'redis_client') as redis:
            response = self.client.post(endpoint, headers=self.headers())
        self.assertEqual(response.status_code, 200)
        import json
        self.assertEqual(redis.rpush.call_args.args[0], 'sync_queue')
        self.assertEqual(json.loads(redis.rpush.call_args.args[1])['type'], sync.TASK)

    def test_settings_sync_button_endpoint_queues_online_only(self):
        from app.utils import sync_manager
        endpoint = '/settings/sync-online-provision-stock-status'
        self.assertEqual(self.client.post(endpoint).status_code, 401)
        with self.client.session_transaction() as session:
            session.update(user_id='TEST-ONLINE', roles=['DATA_SYNC_USER'])
        with patch.object(sync_manager, 'sync_online_provision_stock_status_data', return_value={'status':'success'}) as queue:
            response = self.client.post(endpoint)
        self.assertEqual(response.status_code, 200)
        queue.assert_called_once_with('TEST-ONLINE')
