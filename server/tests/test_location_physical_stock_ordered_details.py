import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import text

from app.dashboard.routes import location_physical_stock_status as report
from app.extensions import db
from app.models.snapshots import ProvisionStockRawSnapshot as Stock
from app.utils import stock_processed_order_sync as sync


class ProcessedOrderDetailsTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY='test', SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        Stock.__table__.create(db.engine)
        sync.TABLE.create(db.engine)

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_paged_totals_and_ambiguous_locations(self):
        stock = [
            (1, 'Allowed', 1, 10),
            (2, 'Allowed', 1, 10),  # Multiple stock matches must not duplicate an order.
            (3, 'Denied', 2, 10),
            (4, 'Ambiguous', 1, 10),
            (5, ' ambiguous ', 2, 10),
        ]
        for key, location, branch, weight in stock:
            db.session.add(Stock(id=key, location=location, branch_id=branch,
                                 section_id=4, range_weight=weight))
        rows = [
            ('Allowed', 'A', 10, 4), ('Allowed', 'B', 10, 5),
            ('Allowed', 'Wrong range', 20, 90), ('Denied', 'D', 10, 90),
            ('Ambiguous', 'X', 10, 90),
        ]
        db.session.execute(sync.TABLE.insert(), [
            dict(location=location, order_no=order, range_weight=weight, gross_weight=gross,
                 quantity=1, section_id=4, date=date(2026, 11, 3))
            for location, order, weight, gross in rows
        ])
        db.session.commit()
        matching = 'WITH matching_stock AS (SELECT * FROM provision_stock_raw_snapshot WHERE branch_id = 1)'
        with patch.object(report, 'render_template', side_effect=lambda template, **context: context):
            result = report._render_processed_order_details(matching, {'limit': 1, 'offset': 1}, 2, 1)
        self.assertEqual([row['order_no'] for row in result['rows']], ['B'])
        self.assertEqual(result['totals']['total_records'], 2)
        self.assertEqual(result['totals']['total_gross_weight'], 9)
        self.assertEqual(result['total_pages'], 2)

    def test_ordered_details_reuses_base_and_hierarchy_filters(self):
        args = ('drill_level=5&drill_section_ids=4&drill_purity_ids=2&drill_type_ids=3'
                '&drill_wide_range_ids=5&drill_range_weight=10&location=Allowed'
                '&prov_type=Individual&provision_mode=Fixed&state=KERALA&page=2')
        with self.app.test_request_context('/?' + args), patch.object(
            report, '_render_processed_order_details', return_value='ok'
        ) as render:
            self.assertEqual(report._get_location_physical_stock_details(
                ordered=True, roles=['BUSINESS_HEAD'], user_id='123'), 'ok')
        sql, params, page, _ = render.call_args.args
        self.assertIn('p.business_head_emp_code = :bh_emp_code', sql)
        self.assertIn('p.provision_mode_filter', sql)
        self.assertIn('p.range_weight = CAST(:drill_range_weight AS numeric)', sql)
        self.assertEqual(params['bh_emp_code'], '123')
        self.assertEqual(params['location'], 'Allowed')
        self.assertEqual(params['prov_type'], 'Individual')
        self.assertEqual(params['state'], 'KERALA')
        self.assertEqual((page, params['offset']), (2, 100))

    def test_restricted_role_without_identity_is_denied(self):
        with self.app.test_request_context('/?drill_section_ids=4'):
            response = report._get_location_physical_stock_details(
                ordered=True, roles=['SHOWROOM_MANAGER'])
        self.assertEqual(response[1], 403)

    def test_order_link_is_opt_in_and_requires_nonzero_weight(self):
        env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / 'app/templates'),
                          autoescape=True)
        template = env.get_template('partials/_view_provision_stock_drilldown.html')
        row = dict(level_id=1, section='BANGLE', section_ids='4', purity_ids=None,
                   type_ids=None, wide_range_ids=None, purity=None, type=None,
                   wide_range=None, range_weight=None, ordered_wt=42, percent=0, short_excess_wt=0)
        self.assertNotIn('data-ordered-detail', template.render(rows=[row]))
        html = template.render(rows=[row, {**row, 'ordered_wt': 0}], enable_ordered_details=True)
        self.assertEqual(html.count('data-ordered-detail'), 1)
        self.assertIn('data-section-ids="4"', html)

    def test_failed_transfer_preserves_snapshot(self):
        db.session.execute(sync.TABLE.insert().values(order_no='Previous', date=date(2026, 11, 2)))
        db.session.commit()
        execute = db.session.execute

        def with_lock(statement, *args, **kwargs):
            if str(statement).startswith('SELECT pg_try_advisory_xact_lock'):
                return MagicMock(**{'scalar.return_value': True})
            return execute(statement, *args, **kwargs)

        def connection():
            conn = MagicMock()
            cursor = conn.cursor.return_value.__enter__.return_value
            cursor.fetchmany.side_effect = [
                [dict(order_no='New', date=date(2026, 11, 3))], RuntimeError('Interrupted')
            ]
            return conn

        with patch.object(db.session, 'execute', side_effect=with_lock), \
             patch('app.utils.sync_tasks.get_external_db_connection', side_effect=connection) as source, \
             patch('app.utils.sync_tasks.emit_sync_update'), patch.object(sync.time, 'sleep'), \
             patch.object(sync.logger, 'exception'):
            self.assertEqual(sync.sync_stock_processed_order_details()['status'], 'error')
        self.assertEqual(source.call_count, 3)
        self.assertEqual(db.session.execute(text(
            'SELECT order_no FROM stock_processed_order_details_snapshot')).scalars().all(), ['Previous'])

    def test_combined_sync_reports_failure_after_attempting_both_steps(self):
        with patch('app.utils.sync_tasks.sync_size_level_nip_barcode_task',
                   return_value={'status': 'error', 'message': 'Source unavailable'}) as barcode, \
             patch.object(sync, 'sync_stock_processed_order_details',
                          return_value={'status': 'success', 'count': 5}) as orders, \
             patch('app.utils.sync_tasks.emit_sync_update') as emit:
            result = sync.sync_stock_drilldown_details()
        barcode.assert_called_once()
        orders.assert_called_once()
        self.assertEqual(result['status'], 'error')
        self.assertIn('Size Level NIP Barcode: Source unavailable', result['message'])
        self.assertEqual(emit.call_args.args[-1], sync.COMBINED_TASK)
        self.assertEqual(emit.call_args.args[0], 'error')

    def test_combined_sync_success_counts_both_snapshots(self):
        with patch('app.utils.sync_tasks.sync_size_level_nip_barcode_task',
                   return_value={'status': 'success', 'count': 4}), \
             patch.object(sync, 'sync_stock_processed_order_details',
                          return_value={'status': 'success', 'count': 5}), \
             patch('app.utils.sync_tasks.emit_sync_update') as emit:
            result = sync.sync_stock_drilldown_details()
        self.assertEqual((result['status'], result['count']), ('success', 9))
        self.assertEqual(emit.call_args.args, ('success', result['message'], 100, sync.COMBINED_TASK))

    def test_combined_endpoint_queues_one_task(self):
        with self.app.test_request_context('/api/sync/stock-drilldown-details', method='POST'), \
             patch.object(report, 'get_jwt_identity', return_value='12'), \
             patch('app.utils.sync_manager.enqueue_sync_task', return_value={'status': 'success'}) as enqueue:
            response, status = report.queue_stock_drilldown_details.__wrapped__()
        self.assertEqual(status, 200)
        self.assertEqual(response.get_json()['status'], 'success')
        enqueue.assert_called_once_with(sync.COMBINED_TASK, '12')
