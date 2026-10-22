"""Opt-in integration tests using a disposable sales_test PostgreSQL database."""
import os
import unittest
from datetime import datetime, timezone, date
from sqlalchemy import select, func
from src.db.connection import engine, SessionLocal
from src.db.models import SalesExternalFeature, SalesExternalFetchLog, SalesForecastFeatureInput
from src.external.sales_features import store_context, load_features, save_inputs
from src.external.sales_audit import audit, fetch_scope


@unittest.skipUnless(os.getenv('SALES_FEATURE_INTEGRATION') == '1', 'Requires isolated sales_test database')
class FeatureStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if engine.url.database != 'sales_test':
            raise RuntimeError('Use a disposable sales_test database')
        for model in (SalesExternalFeature, SalesExternalFetchLog, SalesForecastFeatureInput):
            model.__table__.create(engine, checkfirst=True)

    def test_store_is_idempotent_and_snapshots_inputs(self):
        context = {'retrieved_at': '2026-10-22T08:00:00+00:00', 'parameters': {'weather': {
            'status': 'available', 'provider': 'fixture', 'source': {'url': 'https://example.com'},
            'days': [{'date': '2026-10-23', 'rain_mm': 2, 'max_temp_c': 30}]}}}
        with SessionLocal.begin() as session:
            store_context(session, context, 2)
            store_context(session, context, 2)
            rows = load_features(session, 2, date(2026, 10, 1), date(2026, 10, 25))
            self.assertEqual(len(rows), 1)
            self.assertEqual(load_features(session, 3, date(2026, 10, 1), date(2026, 10, 25)), [])
            save_inputs(session, 'fixture', rows, {'engine': 'weekday_average'})
        with SessionLocal() as session:
            self.assertEqual(len(session.get(SalesForecastFeatureInput, 'fixture').inputs_json['features']), 1)

    def test_audit_survives_forecast_rollback(self):
        token = fetch_scope.set({'task_id': 'rolled-back-fixture'})
        try:
            with SessionLocal() as session:
                audit('request', provider='fixture')
                session.rollback()
            with SessionLocal() as session:
                count = session.scalar(select(func.count()).select_from(SalesExternalFetchLog).where(
                    SalesExternalFetchLog.task_id == 'rolled-back-fixture'))
                self.assertGreaterEqual(count, 1)
        finally:
            fetch_scope.reset(token)


if __name__ == '__main__':
    unittest.main()
