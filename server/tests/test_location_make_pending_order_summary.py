import unittest
from flask import Flask, session
from app.extensions import db
from app.models.snapshots import PendingOrderDetailsSnapshot
from app.dashboard.routes.location_make_pending_order_summary import build_filter_query


class LocationMakePendingOrderTypeFilterTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SECRET_KEY='test-key')
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        PendingOrderDetailsSnapshot.__table__.create(db.engine)

        db.session.add_all([
            PendingOrderDetailsSnapshot(id=1, supplier='AACHAL JEWELLERS', location='MUMBAI', make='MAKE_A', order_type='STOCK'),
            PendingOrderDetailsSnapshot(id=2, supplier='AACHAL JEWELLERS', location='DELHI', make='MAKE_B', order_type='CUSTOM'),
            PendingOrderDetailsSnapshot(id=3, supplier='AACHAL JEWELLERS', location='CHENNAI', make='MAKE_C', order_type='REPAIR'),
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()

    def test_single_order_type_filter(self):
        with self.app.test_request_context('/?order_type=STOCK'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(db.session.query(PendingOrderDetailsSnapshot))
            results = q.all()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].order_type, 'STOCK')

    def test_multi_select_order_type_filter(self):
        with self.app.test_request_context('/?order_type=STOCK,REPAIR'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(db.session.query(PendingOrderDetailsSnapshot))
            results = q.all()
            self.assertEqual(len(results), 2)
            types = sorted([r.order_type for r in results])
            self.assertEqual(types, ['REPAIR', 'STOCK'])

    def test_multi_select_order_type_filter_with_whitespace(self):
        with self.app.test_request_context('/?order_type=STOCK%2C%20REPAIR'):
            session['roles'] = ['ADMIN']
            q = build_filter_query(db.session.query(PendingOrderDetailsSnapshot))
            results = q.all()
            self.assertEqual(len(results), 2)
            types = sorted([r.order_type for r in results])
            self.assertEqual(types, ['REPAIR', 'STOCK'])

    def test_empty_order_type_filter(self):
        with self.app.test_request_context('/?order_type='):
            session['roles'] = ['ADMIN']
            q = build_filter_query(db.session.query(PendingOrderDetailsSnapshot))
            results = q.all()
            self.assertEqual(len(results), 3)
