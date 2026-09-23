import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, session
from app.extensions import db
from app.models.snapshots import PartyMakeCapacityDetailsSnapshot as Snapshot
from app.dashboard.routes import party_make_capacity as report
from tests.test_capacity_order_status import BoolOr


class CapacityOwnerVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SECRET_KEY='test')
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        Snapshot.__table__.create(db.engine)
        connection = db.engine.raw_connection()
        connection.create_aggregate('bool_or', 1, BoolOr)
        connection.close()
        db.session.add_all([
            Snapshot(supplier='Make owned', make='A', location='L1',
                     make_owner_emp_code=' 00123 ', party_capacity_kg=1),
            Snapshot(supplier='Collection owned', make='B', location='L2',
                     collection_owner_emp_code='00123', party_capacity_kg=2),
            Snapshot(supplier='Other', make='KMU - KERALA', location='Secret',
                     make_owner_emp_code='999', party_capacity_kg=10),
            Snapshot(supplier='Unassigned', make='C', party_capacity_kg=20),
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()

    def actor(self, role='READER', code='00123', active=True):
        return SimpleNamespace(user_id=code, is_active=active, is_admin=False,
                               username='reader', roles=[SimpleNamespace(name=role)])

    def test_owner_rows_kpis_options_and_direct_drilldown(self):
        with self.app.test_request_context('/?supplier=Other'), \
                patch.object(report, 'get_jwt_identity', return_value='42'), \
                patch.object(db.session, 'get', return_value=self.actor()):
            session['roles'] = ['ADMIN']  # Session values cannot override verified identity.
            response = report.api_party_make_capacity_drilldown.__wrapped__().get_json()
            self.assertEqual(response['total'], 0)
            self.assertEqual(report.fetch_all_filter_options()['locations'], ['L1', 'L2'])
        with self.app.test_request_context('/'), \
                patch.object(report, 'get_jwt_identity', return_value='42'), \
                patch.object(db.session, 'get', return_value=self.actor()):
            rows, kpis = report.get_aggregated_capacity_data()
            self.assertEqual({r['supplier'] for r in rows}, {'Make owned', 'Collection owned'})
            self.assertEqual(kpis['total_capacity_kg'], 3)

    def test_requested_bypasses_and_kmu_scope(self):
        for role in ['ADMIN', 'SUPER_ADMIN', 'BIC_MANAGER', 'MANAGER_2', 'MANAGER_KMU']:
            with self.subTest(role=role), self.app.test_request_context('/'), \
                    patch.object(report, 'get_jwt_identity', return_value='42'), \
                    patch.object(db.session, 'get', return_value=self.actor(role)):
                rows, _ = report.get_aggregated_capacity_data()
                self.assertEqual(len(rows), 1 if role == 'MANAGER_KMU' else 4)
                if role == 'MANAGER_KMU':
                    self.assertEqual(rows[0]['supplier'], 'Other')

    def test_missing_identity_inactive_or_missing_code_fail_closed(self):
        for actor in [None, self.actor(active=False), self.actor(code='')]:
            with self.app.test_request_context('/'), \
                    patch.object(report, 'get_jwt_identity', return_value='42'), \
                    patch.object(db.session, 'get', return_value=actor):
                self.assertEqual(report.get_aggregated_capacity_data()[0], [])
                self.assertEqual(report.fetch_all_filter_options()['parties'], [])
        with self.app.test_request_context('/'):
            self.assertEqual(report.get_aggregated_capacity_data()[0], [])


if __name__ == '__main__':
    unittest.main()
