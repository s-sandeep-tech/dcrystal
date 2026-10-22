import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
from app.extensions import db
from app.models.sales_prediction import SalesPredictionSyncRun, SalesTurnoverDailySnapshot, SalesTurnoverForecastRun
from app.models.auth import User
from app.models.rbac import Role, Menu, Permission, UserRole, RoleMenu, RolePermission
from app.utils.sales_prediction_sync import validate_diagnostics
from app.dashboard.routes.sales_prediction import start_sales_turnover_forecast, sales_turnover_forecast_data
from app.services.sales_prediction import enqueue_sales_forecast, report_data


class SalesPredictionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False,
                               JWT_SECRET_KEY='test-key-for-sales-prediction-123456', JWT_TOKEN_LOCATION=['headers'])
        db.init_app(self.app)
        JWTManager(self.app)
        self.ctx = self.app.app_context(); self.ctx.push()
        db.metadata.create_all(db.engine, tables=[m.__table__ for m in [User, Role, Menu, Permission, UserRole,
            RoleMenu, RolePermission, SalesPredictionSyncRun, SalesTurnoverDailySnapshot, SalesTurnoverForecastRun]])
        self.run = SalesPredictionSyncRun(id='run-one', cutoff_date=date(2026, 10, 20), first_date=date(2026, 4, 1),
            row_count=1, source_count=2, net_turnover=Decimal('90'), diagnostics={})
        db.session.add(self.run)
        db.session.add(SalesTurnoverDailySnapshot(run_id='run-one', sales_date=date(2026, 10, 20), branch_id=2,
            location_name='THRISSUR ROUND', invoice_turnover=100, return_turnover=-10, net_turnover=90, source_count=2))
        self.user = User(user_id='test-sales', username='test-sales', email='test-sales@example.com', password_hash='unused', is_active=True)
        db.session.add(self.user); db.session.commit()
        self.app.add_url_rule('/api/sales-turnover-forecast/run', view_func=start_sales_turnover_forecast, methods=['POST'])
        self.app.add_url_rule('/api/sales-turnover-forecast/data', view_func=sales_turnover_forecast_data)

    def tearDown(self):
        db.session.remove(); self.ctx.pop()

    def test_data_totals_and_scope(self):
        self.assertEqual(report_data(2)['history'][0]['y'], 90)
        self.assertEqual(report_data(3)['history'], [])

    def test_new_snapshot_and_pending_task_keep_last_completed_forecast(self):
        saved = {'forecast': [{'ds': '2026-10-21', 'baseline_yhat': 123}], 'snapshot_run_id': 'run-one'}
        db.session.add(SalesTurnoverForecastRun(task_id='completed', snapshot_run_id='run-one',
            branch_id=2, requested_by=self.user.id, result_json=saved, created_at=datetime(2026, 10, 20)))
        db.session.add(SalesPredictionSyncRun(id='run-two', cutoff_date=date(2026, 10, 21),
            first_date=date(2026, 4, 1), row_count=1, source_count=1, net_turnover=150,
            diagnostics={}, created_at=datetime(2030, 1, 1)))
        db.session.add(SalesTurnoverDailySnapshot(run_id='run-two', sales_date=date(2026, 10, 21),
            branch_id=2, location_name='THRISSUR ROUND', invoice_turnover=150, return_turnover=0,
            net_turnover=150, source_count=1))
        db.session.add(SalesTurnoverForecastRun(task_id='pending', snapshot_run_id='run-two',
            branch_id=2, requested_by=self.user.id, created_at=datetime(2026, 10, 22)))
        db.session.commit()
        result = report_data(2)
        self.assertEqual(result['history'], [{'ds': '2026-10-21', 'y': 150}])
        self.assertEqual(result['forecast_run']['result'], saved)
        self.assertEqual(result['pending_task_id'], 'pending')

    def test_producer_uses_stream_and_pins_snapshot(self):
        with patch('app.services.sales_prediction.redis_client') as redis:
            result = enqueue_sales_forecast(self.user.id, 2, True)
        record = db.session.get(SalesTurnoverForecastRun, result['task_id'])
        self.assertEqual(record.snapshot_run_id, 'run-one')
        self.assertTrue(record.include_external)
        self.assertTrue(redis.xadd.call_args.args[0].endswith(':stream'))

    def test_gemini_fallback_is_persisted_and_requires_external_data(self):
        with patch('app.services.sales_prediction.redis_client'):
            result = enqueue_sales_forecast(self.user.id, 2, True, allow_gemini_fallback=True)
        record = db.session.get(SalesTurnoverForecastRun, result['task_id'])
        self.assertTrue(record.allow_gemini_fallback)
        with self.assertRaises(ValueError):
            enqueue_sales_forecast(self.user.id, 2, False, allow_gemini_fallback=True)

    def test_ungranted_user_cannot_view_or_run_forecast(self):
        token = create_access_token(identity=str(self.user.id))
        headers = {'Authorization': 'Bearer ' + token}
        client = self.app.test_client()
        self.assertEqual(client.get('/api/sales-turnover-forecast/data', headers=headers).status_code, 403)
        self.assertEqual(client.post('/api/sales-turnover-forecast/run', headers=headers).status_code, 403)

    def test_redis_failure_preserves_request_for_outbox_recovery(self):
        with patch('app.services.sales_prediction.redis_client') as redis:
            redis.xadd.side_effect = ConnectionError('unavailable')
            result = enqueue_sales_forecast(self.user.id, 2)
        record = db.session.get(SalesTurnoverForecastRun, result['task_id'])
        self.assertIsNotNone(record)
        self.assertIsNone(record.queued_at)
        self.assertEqual(record.snapshot_run_id, 'run-one')

    def test_source_validation_rejects_duplicates_and_wrong_sign(self):
        valid = dict(source_count=2, invalid_rows=0, date_mismatches=0, duplicate_ids=0, positive_returns=0, negative_returns=1)
        validate_diagnostics(valid, 'signed')
        # date_mismatches should be tolerated using COALESCE(trans_date::date, date)
        validate_diagnostics({**valid, 'date_mismatches': 5}, 'signed')
        for column in ['invalid_rows', 'duplicate_ids', 'positive_returns']:
            with self.assertRaises(ValueError):
                validate_diagnostics({**valid, column: 1}, 'signed')
        with self.assertRaises(ValueError):
            validate_diagnostics(valid, 'positive')


if __name__ == '__main__':
    unittest.main()
