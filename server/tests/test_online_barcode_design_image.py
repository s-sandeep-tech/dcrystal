import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from alembic.migration import MigrationContext
from alembic.operations import Operations
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine, inspect, text

from app.utils import sync_tasks as sync
from app.models.snapshots import SizeLevelNIPBarcodeSnapshot, SizeLevelNIPBarcodeStaging

ROOT = Path(__file__).resolve().parents[1]


class OnlineBarcodeDesignImageTests(unittest.TestCase):
    def test_barcode_sync_carries_design_uid_through_staging_and_publish(self):
        uid = UUID('8b97ef62-b96e-41b0-b65a-bf0a76d38e25')
        count_connection, page_connection = MagicMock(), MagicMock()
        count_connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (2,)
        page_cursor = page_connection.cursor.return_value.__enter__.return_value
        page_cursor.fetchall.return_value = [dict(uid='barcode-1', design_no='A', design_uid=uid),
                                             dict(uid='barcode-2', design_no='B', design_uid=None)]
        session = MagicMock()
        session.execute.return_value.one.return_value = SimpleNamespace(
            distinct_uids=2, missing_uids=0, total_rows=2)
        with patch.object(sync, 'get_external_db_connection', side_effect=[count_connection, page_connection]), patch.object(
            sync, 'db', SimpleNamespace(session=session)
        ), patch.object(sync, 'emit_sync_update'):
            result = sync.sync_size_level_nip_barcode_task()
        self.assertEqual(result, {'status': 'success', 'count': 2})
        self.assertIn('"design_uid"', page_cursor.execute.call_args.args[0])
        model, rows = session.bulk_insert_mappings.call_args.args
        self.assertIs(model, SizeLevelNIPBarcodeStaging)
        self.assertEqual(rows[0]['design_uid'], str(uid))
        self.assertEqual(rows[0]['uid'], 'barcode-1')
        self.assertIsNone(rows[1]['design_uid'])
        publish = next(str(c.args[0]) for c in session.execute.call_args_list
                       if str(c.args[0]).startswith('INSERT INTO size_level_nip_barcode_snapshot'))
        self.assertEqual(publish.count('"design_uid"'), 2)
        count_connection.close.assert_called_once()
        page_connection.close.assert_called_once()

    def test_modal_design_links_use_barcode_uid_and_escape_html(self):
        env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())
        template = env.get_template('partials/_view_online_provision_stock_in_shop_details.html')
        row = dict(design_no='A"<B', design_uid='uid"123', barcode_no='BARCODE', weight=8,
                   pieces=1, gross_wt=8.613)
        def render():
            return template.render(rows=[row], total_records=1, total_pieces=1, total_gross_wt=8.613,
                                   page=1, total_pages=1)
        html = render()
        self.assertIn('data-design-image="A&#34;&lt;B"', html)
        self.assertIn('data-design-uid="uid&#34;123"', html)
        self.assertIn('data-design-preview="A&#34;&lt;B"', html)
        for missing in (None, ''):
            row['design_uid'] = missing
            self.assertNotIn('data-design-image=', render())
            self.assertNotIn('data-design-preview=', render())

    def test_migration_preserves_existing_rows_and_is_idempotent(self):
        path = ROOT / 'migrations/versions/add_nip_barcode_design_uid.py'
        spec = importlib.util.spec_from_file_location('barcode_uid_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine('sqlite:///:memory:')
        tables = ('size_level_nip_barcode_snapshot', 'size_level_nip_barcode_staging')
        with engine.begin() as connection:
            for table in tables:
                connection.execute(text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, design_no TEXT)'))
                connection.execute(text(f"INSERT INTO {table} VALUES (1, 'DESIGN-A')"))
            with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
                migration.upgrade()
                migration.upgrade()
            for table in tables:
                self.assertIn('design_uid', {c['name'] for c in inspect(connection).get_columns(table)})
                self.assertEqual(connection.execute(text(f'SELECT design_no, design_uid FROM {table}')).one(), ('DESIGN-A', None))
        engine.dispose()
        for model in (SizeLevelNIPBarcodeSnapshot, SizeLevelNIPBarcodeStaging):
            self.assertIn('design_uid', model.__table__.columns)


if __name__ == '__main__':
    unittest.main()
