"""Optional real-PostgreSQL checks, isolated in a disposable schema."""
import os
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask
from sqlalchemy import Column, MetaData, Table, create_engine, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import make_url

from app.extensions import db
from app.models.nip_stock_trend import NIPStockTrendSnapshot as S, SOURCE_COLUMNS
from app.utils import nip_stock_trend_sync as sync


@unittest.skipUnless(os.getenv('NIP_SYNC_TEST_DATABASE_URL'), 'Requires disposable PostgreSQL schema access')
class PostgresNIPSyncTests(unittest.TestCase):
    def setUp(self):
        self.url = os.environ['NIP_SYNC_TEST_DATABASE_URL']
        self.schema = 'nip_sync_test_' + uuid4().hex
        self.admin = create_engine(self.url)
        with self.admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {self.schema}'))
        app = Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI=self.url,
            SQLALCHEMY_ENGINE_OPTIONS={'connect_args': {'options': f'-csearch_path={self.schema}'}})
        db.init_app(app)
        self.context = app.app_context()
        self.context.push()
        S.__table__.create(db.engine)
        self.source = Table('fixture_nip_source', MetaData(),
            *(Column(name, UUID() if name == 'uid' else S.__table__.c[name].type)
              for name in SOURCE_COLUMNS))
        self.source.create(db.engine)
        self.ids = [str(uuid4()) for _ in range(3)]
        with db.engine.begin() as conn:
            conn.execute(self.source.insert(), [dict(uid=uid, date=date(2026,10,29),
                gross_wt=Decimal('1.123456789') + i, pieces=i + 1,
                classification='Before', is_nip=True) for i, uid in enumerate(self.ids)])
        db.session.add(S(uid='old-history',date=date(2026,10,28),gross_wt=10,pieces=1))
        db.session.add(S(uid='old-current',date=date(2026,10,29),gross_wt=20,pieces=2))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()
        with self.admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {self.schema} CASCADE'))
        self.admin.dispose()

    def connect_source(self):
        return psycopg2.connect(**make_url(self.url).translate_connect_args(username='user'),
                               options=f'-csearch_path={self.schema}')

    def run_attempt(self):
        test = self
        class ShortTransactionCursor(RealDictCursor):
            def fetchall(self):
                rows = super().fetchall()
                test.assertTrue(self.connection.autocommit)
                test.assertEqual(self.connection.get_transaction_status(),psycopg2.extensions.TRANSACTION_STATUS_IDLE)
                return rows
        with patch.object(sync, 'SOURCE', f'{self.schema}.fixture_nip_source'), \
             patch.object(sync, 'BATCH_SIZE', 1), \
             patch.object(sync, 'RealDictCursor', ShortTransactionCursor), \
             patch('app.utils.sync_tasks.get_external_db_connection', side_effect=self.connect_source), \
             patch('app.utils.sync_tasks.emit_sync_update'):
            return sync._sync_nip_stock_trend_attempt()

    def test_real_keyset_checksum_and_atomic_publish(self):
        self.assertEqual(self.run_attempt(), {'status':'success','count':3})
        self.assertEqual(S.query.count(),4)
        self.assertIsNotNone(S.query.filter_by(uid='old-history').first())
        self.assertIsNone(S.query.filter_by(uid='old-current').first())
        self.assertEqual(S.query.filter_by(uid=self.ids[0]).one().gross_wt,Decimal('1.123456789'))
        with db.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM pg_class WHERE relname LIKE 'nip_trend_stage_%' AND relnamespace = pg_my_temp_schema()")).scalar(),0)

    def test_metadata_change_rejects_publish_even_with_unchanged_weight(self):
        manifest = sync._source_manifest
        calls = 0
        def changing_manifest(conn):
            nonlocal calls
            calls += 1
            if calls == 2:
                with self.admin.begin() as writer:
                    writer.execute(text(f"UPDATE {self.schema}.fixture_nip_source SET classification='Changed'"))
            return manifest(conn)
        with patch.object(sync, '_source_manifest', side_effect=changing_manifest):
            result = self.run_attempt()
        self.assertEqual(result['status'],'error')
        self.assertTrue(result['retryable'])
        self.assertIn('checksum validation failed',result['message'])
        self.assertEqual(S.query.count(),2)
        self.assertEqual(S.query.filter_by(uid='old-current').one().gross_wt,20)

    def test_publish_failure_rolls_back_live_date_replacement(self):
        execute = db.session.execute
        def failing_publish(statement,*args,**kwargs):
            if getattr(statement,'is_insert',False) and statement.table is S.__table__:
                raise RuntimeError('simulated publish failure')
            return execute(statement,*args,**kwargs)
        with patch.object(db.session,'execute',side_effect=failing_publish):
            result = self.run_attempt()
        self.assertEqual(result['status'],'error')
        self.assertIn('simulated publish failure',result['message'])
        self.assertEqual(S.query.count(),2)
        self.assertEqual(S.query.filter_by(uid='old-current').one().gross_wt,20)


if __name__ == '__main__':
    unittest.main()
