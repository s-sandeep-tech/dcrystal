"""Opt-in source-sync tests. Requires a disposable database named sales_test."""
import os
import unittest
from unittest.mock import patch
import psycopg2
from flask import Flask
from sqlalchemy import text
from app.extensions import db
from app.models.sales_prediction import SalesPredictionSyncRun, SalesTurnoverDailySnapshot
from app.utils.sales_prediction_sync import sync_sales_prediction_data_task


@unittest.skipUnless(os.getenv('SALES_PREDICTION_INTEGRATION') == '1', 'Requires isolated sales_test database')
class SalesSyncIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        uri = os.environ['SQLALCHEMY_DATABASE_URI']
        if not uri.endswith('/sales_test'):
            raise RuntimeError('Use a disposable database named sales_test')
        cls.app = Flask(__name__)
        cls.app.config.update(SQLALCHEMY_DATABASE_URI=uri, SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(cls.app)
        cls.ctx = cls.app.app_context(); cls.ctx.push()
        cls.dsn = uri.replace('postgresql+psycopg2://', 'postgresql://')
        with db.engine.begin() as conn:
            conn.execute(text('CREATE SCHEMA IF NOT EXISTS ext_view'))
            conn.execute(text('''CREATE TABLE ext_view.vw_item_wise_tsk_details_data (
                id integer, trans_date timestamp, date date, branch_id integer, location_name text,
                trans_type text, turn_over numeric, last_updated_at timestamp)'''))
            conn.execute(text('''INSERT INTO ext_view.vw_item_wise_tsk_details_data
                SELECT n, DATE '2026-04-01' + (n-1)/2, DATE '2026-04-01' + (n-1)/2,
                    2, 'THRISSUR ROUND', CASE WHEN n % 2 = 1 THEN 'INVOICE' ELSE 'SR' END,
                    CASE WHEN n % 2 = 1 THEN 100000 ELSE -10000 END, CURRENT_TIMESTAMP
                FROM generate_series(1,200) n'''))

    @classmethod
    def tearDownClass(cls):
        db.session.remove(); cls.ctx.pop()

    def sync(self):
        with patch('app.utils.sync_tasks.get_external_db_connection', side_effect=lambda: psycopg2.connect(self.dsn)), \
             patch('app.utils.sync_tasks.emit_sync_update'):
            return sync_sales_prediction_data_task()

    def test_atomic_sync_reconciles_daily_totals(self):
        result = self.sync()
        self.assertEqual(result['status'], 'success', result)
        run = db.session.get(SalesPredictionSyncRun, result['run_id'])
        self.assertEqual(run.source_count, 200)
        self.assertEqual(run.row_count, 100)
        self.assertEqual(float(run.net_turnover), 9000000)
        self.assertEqual(SalesTurnoverDailySnapshot.query.filter_by(run_id=run.id).count(), 100)

    def test_duplicate_source_failure_retains_published_run(self):
        before = SalesPredictionSyncRun.query.count()
        with db.engine.begin() as conn:
            conn.execute(text('INSERT INTO ext_view.vw_item_wise_tsk_details_data SELECT * FROM ext_view.vw_item_wise_tsk_details_data WHERE id = 1'))
        try:
            self.assertEqual(self.sync()['status'], 'error')
            self.assertEqual(SalesPredictionSyncRun.query.count(), before)
        finally:
            with db.engine.begin() as conn:
                conn.execute(text('DELETE FROM ext_view.vw_item_wise_tsk_details_data WHERE ctid IN (SELECT ctid FROM ext_view.vw_item_wise_tsk_details_data WHERE id=1 LIMIT 1)'))

    def test_insert_failure_rolls_back_staging(self):
        before = SalesPredictionSyncRun.query.count()
        original = db.session.execute

        def fail_insert(statement, *args, **kwargs):
            if getattr(getattr(statement, 'table', None), 'name', None) == 'sales_turnover_daily_snapshots':
                raise RuntimeError('Simulated daily insert failure')
            return original(statement, *args, **kwargs)

        with patch.object(db.session, 'execute', side_effect=fail_insert):
            self.assertEqual(self.sync()['status'], 'error')
        self.assertEqual(SalesPredictionSyncRun.query.count(), before)

    def test_z_publish_forecast(self):
        from app.services.sales_prediction import enqueue_sales_forecast
        result = enqueue_sales_forecast(1, branch_id=2)
        self.assertEqual(result['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
