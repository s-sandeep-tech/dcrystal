"""Optional real-PostgreSQL parity checks in an isolated, disposable schema.

Set TEST_POSTGRES_URI to run; never writes existing application tables.
"""
import inspect
import os
import re
import tempfile
import unittest
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask, session
from sqlalchemy import create_engine, event, text
from openpyxl import load_workbook

from app.extensions import db
from app.dashboard.routes import location_physical_stock_status as physical
from app.dashboard.routes import online_provision_stock_status as online
from app.models.snapshots import ProvisionStockRawSnapshot as Physical, BranchAuthoritySnapshot, SizeLevelNIPBarcodeSnapshot
from app.models.online_provision_stock import OnlineProvisionStockRawSnapshot as Online, OnlineProvisionStockRawStaging as Staging
from app.utils import online_provision_stock_sync as sync
from app.utils import stock_processed_order_sync as orders
from app.utils import export_service, online_provision_stock_export

URI = os.getenv('TEST_POSTGRES_URI')


def normalize(html):
    # Ignore only report-specific identifiers. Numeric values and labels remain exact.
    names = set(re.findall(r'\bfunction\s+(\w+)\s*\(',
        (Path(physical.__file__).resolve().parents[2] / 'static/js/location_physical_stock_status.js').read_text()
        + (Path(physical.__file__).resolve().parents[2] / 'templates/partials/_view_location_physical_stock_status.html').read_text()))
    for name in sorted(names, key=len, reverse=True):
        html = html.replace('online' + name[0].upper() + name[1:], name)
    return html.replace('online-', '').replace('online_provision_stock', 'location_physical_stock')


@unittest.skipUnless(URI, 'Set TEST_POSTGRES_URI to run PostgreSQL parity tests')
class OnlineStockPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = 'test_online_stock_' + uuid.uuid4().hex[:12]
        cls.control = create_engine(URI)
        with cls.control.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.app = Flask(__name__, template_folder=str(Path(physical.__file__).resolve().parents[2] / 'templates'))
        cls.app.config.update(SECRET_KEY='test', SQLALCHEMY_DATABASE_URI=URI)
        db.init_app(cls.app)
        cls.ctx = cls.app.app_context(); cls.ctx.push()
        event.listen(db.engine, 'connect', lambda connection, _: cls.set_path(connection))
        cls.engine = db.engine
        db.metadata.create_all(db.engine, tables=[Physical.__table__, Online.__table__, Staging.__table__,
            BranchAuthoritySnapshot.__table__, SizeLevelNIPBarcodeSnapshot.__table__, orders.TABLE])

    @classmethod
    def set_path(cls, connection):
        with connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{cls.schema}"')

    @classmethod
    def tearDownClass(cls):
        db.session.remove(); cls.ctx.pop(); cls.engine.dispose()
        with cls.control.begin() as c:
            c.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))
        cls.control.dispose()

    def setUp(self):
        for model in (Physical, Online, Staging, SizeLevelNIPBarcodeSnapshot):
            db.session.query(model).delete()
        db.session.execute(orders.TABLE.delete())
        for model in (Physical, Online):
            for i in range(1, 5):
                db.session.add(model(id=i, snapshot_date=datetime(2026, 11, 24),
                    location='Shop A' if i < 3 else 'Shop B', branch_id=1 if i < 3 else 2,
                    branch_type='SHOP' if i < 3 else 'FRANCHISE_SHOP', branch_status='Active',
                    business_head_emp_code='123', state='KERALA', division='Gold', group_name='GOLD',
                    section='BANGLE' if i % 2 else 'CHAIN', section_id=4 if i % 2 else 5,
                    classification='Plain', classification_id=6, type='Regular', type_id=3,
                    division_id=1, group_id=1, sub_classification_id=1, make_id=1, collection_id=1,
                    master_collection_id=1, sub_section_id=1, gender_id=1, size_id=1, screw_type_id=1,
                    make='Machine', collection='Classic', wide_range='Small', wide_range_id=5,
                    purity=22, purity_id=2, range_weight=10, prov_type='Regular',
                    provision_mode=1, provision_mode_filter='Fixed', prov_type_filter=1,
                    prov_pieces=i*2, prov_gr_wt=i*10.125, stock_qty=i*3, stock_gr_wt=i*9.5,
                    in_shop_wt=i*8.25, in_shop_pcs=i*2, in_transit_wt=i*0.75,
                    order_only_wt=i*0.5, short_gr_wt=i*0.125, excess_gr_weight=0,
                    short_percent=1.25, not_in_shop_wt=i, prov_amount=i*2000))
        identity = {name: 1 for name in orders.IDENTITY_FIELDS}
        identity.update(section_id=4, purity_id=2, type_id=3, wide_range_id=5, classification_id=6)
        db.session.add(SizeLevelNIPBarcodeSnapshot(id=1, branch_id=1, **identity,
            location='Shop A', division='Gold', section='BANGLE', classification='Plain',
            make='Machine', collection='Classic', type='Regular', wide_range='Small',
            purity=22, weight=10, pieces=2, gross_wt=12.345, barcode_no='TEST-ONLINE-001',
            design_no='DESIGN-1', branch_type='SHOP', is_nip=True, snapshot_date=datetime(2026,11,24)))
        db.session.execute(orders.TABLE.insert().values(branch_id=1, **identity,
            location='Shop A', order_no='ORDER-1', range_weight=10, quantity=2,
            gross_weight=5.125, date=date(2026,11,24)))
        db.session.commit()

    def render_pair(self, original, clone, args):
        outputs = []
        for module, fn in [(physical, original), (online, clone)]:
            with self.app.test_request_context('/?' + args), patch.object(module, 'redis_client') as redis:
                redis.get.return_value = None
                session.update(roles=['ADMIN'], user_id='123')
                result = inspect.unwrap(fn)()
                if isinstance(result, tuple):
                    self.assertEqual(result[1], 200, result[0]); result = result[0]
                self.assertNotIn('Backend Error', result)
                self.assertNotIn('Error:', result)
                outputs.append(normalize(result))
        self.assertEqual(*outputs)
        return outputs

    def test_main_and_hierarchy_numbers_match(self):
        for args in ['', 'division=Gold&location=Shop+A', 'section=BANGLE&sort_by=prov_gr_wt&sort_order=desc',
                     'branch_type=FRANCHISE_SHOP', 'section=NONE']:
            with self.subTest(args=args):
                self.render_pair(physical.get_location_physical_stock_status_partial,
                                 online.get_online_provision_stock_status_partial, args)
                contexts = []
                for module, fn in [(physical, physical.get_location_physical_stock_status_drilldown),
                                   (online, online.get_online_provision_stock_status_drilldown)]:
                    with self.app.test_request_context('/?' + args + '&section=BANGLE'), patch.object(
                            module, 'render_template', side_effect=lambda template, **context: context):
                        session.update(roles=['ADMIN'], user_id='123')
                        contexts.append(inspect.unwrap(fn)())
                # Additional Design No rows must not change the five existing levels or totals.
                parents = [{k: v for k, v in row.items() if k != 'design_no'}
                           for row in contexts[1]['rows'] if row['level_id'] <= 5]
                self.assertEqual(contexts[0]['rows'], parents)
                self.assertEqual(contexts[0]['modal_totals'], contexts[1]['modal_totals'])

    def test_all_popup_queries_match(self):
        args = 'division=Gold&drill_level=1&drill_section_ids=4'
        identity = {name: 1 for name in orders.IDENTITY_FIELDS}
        identity.update(branch_id=1, section_id=4, purity_id=2, type_id=3,
                        wide_range_id=5, classification_id=6, range_weight=10)
        barcode_args = '&'.join(f'{k}={v}' for k, v in identity.items())
        for name in ['provision_details', 'in_shop_details', 'comparison', 'comparison_barcodes']:
            with self.subTest(popup=name):
                outputs = self.render_pair(getattr(physical, 'get_location_physical_stock_' + name),
                                 getattr(online, 'get_online_provision_stock_' + name),
                                 barcode_args if name == 'comparison_barcodes' else args)
                if name in ('in_shop_details', 'comparison_barcodes'):
                    self.assertIn('TEST-ONLINE-001', outputs[0])
        with self.app.test_request_context('/?' + args):
            session.update(roles=['ADMIN'], user_id='123')
            a = physical._get_location_physical_stock_details(ordered=True, roles=['ADMIN'])
            b = online._get_online_provision_stock_details(ordered=True, roles=['ADMIN'])
            self.assertEqual(normalize(a), normalize(b))

    def test_export_cell_values_and_formats_match(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(export_service, 'EXPORTS_DIR', folder), patch.object(online_provision_stock_export, 'EXPORTS_DIR', folder):
                a = export_service.generate_location_physical_stock_status_export({'division': 'Gold'})
                b = online_provision_stock_export.generate_online_provision_stock_status_export({'division': 'Gold'})
            books = [load_workbook(Path(folder) / file) for file in (a, b)]
            values = []
            for book in books:
                values.append([[(str(cell.value).replace('Online Provision Stock status', 'Location Physical Stock Status'),
                                 cell.number_format, cell.style_id) for cell in row] for row in book.active])
            self.assertEqual(*values)
            for book in books: book.close()

    def test_publish_only_replaces_online_and_failure_preserves_previous(self):
        before = [(s.id, s.prov_gr_wt) for s in Physical.query.order_by(Physical.id)]
        db.session.add(Staging(id=1, location='Online-only', prov_gr_wt=25, snapshot_date=datetime(2026, 11, 24)))
        db.session.commit()
        with self.assertRaises(ValueError): sync.publish_staging(2, 25)
        self.assertEqual(Online.query.count(), 4)
        sync.publish_staging(1, 25)
        self.assertEqual([(r.location, r.prov_gr_wt) for r in Online.query], [('Online-only', 25)])
        self.assertEqual(before, [(s.id, s.prov_gr_wt) for s in Physical.query.order_by(Physical.id)])
        self.assertEqual(Staging.query.count(), 0)

    def test_complete_sync_streams_validates_and_uses_only_online_tables(self):
        original = [(r.id, r.prov_gr_wt) for r in Physical.query.order_by(Physical.id)]
        source = MagicMock()
        metadata = MagicMock()
        metadata.description = [(c,) for c in sync.source_columns()]
        metadata.fetchone.return_value = (1, 25)
        stream = MagicMock()
        row = {c: None for c in sync.source_columns()}
        row.update(location='Online source only', provision_weight=25, ordered_wt=12, req_only=3,
                   branch_id=1, size=Decimal('5.25'))
        stream.fetchmany.side_effect = [[row], []]
        metadata.__enter__.return_value = metadata
        stream.__enter__.return_value = stream
        source.cursor.side_effect = [metadata, stream]
        with patch('app.utils.sync_tasks.get_external_db_connection', return_value=source), patch(
            'app.utils.sync_tasks.emit_sync_update') as emit:
            result = sync.sync_online_provision_stock_status_data_task()
        self.assertEqual(result, {'status':'success','count':1,'validation':{'match':True}})
        published = Online.query.one()
        self.assertEqual(published.location, 'Online source only')
        self.assertEqual(published.prov_gr_wt, 25)
        self.assertEqual(published.order_only_wt + published.req_only, 15)
        self.assertEqual(published.size, '5.25')
        self.assertIsNone(published.stock_qty)
        self.assertIsNotNone(published.snapshot_date)
        self.assertEqual(Staging.query.count(), 0)
        self.assertEqual(original, [(r.id, r.prov_gr_wt) for r in Physical.query.order_by(Physical.id)])
        source.close.assert_called_once()
        self.assertEqual(emit.call_args.args[0], 'success')
        self.assertEqual(emit.call_args.args[3], sync.TASK)
        self.assertTrue(emit.call_args.kwargs['metadata']['validation_passed'])
        self.assertIn(sync.SOURCE, stream.execute.call_args.args[0])
        self.assertIn('SUM(provision_weight)', metadata.execute.call_args.args[0])
        self.assertIn('\"provision_weight\"', stream.execute.call_args.args[0])
        self.assertNotIn('\"prov_gr_wt\"', stream.execute.call_args.args[0])
