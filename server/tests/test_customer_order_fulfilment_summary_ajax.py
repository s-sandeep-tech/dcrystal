import unittest
from flask import Flask
from app.extensions import db
from app.models import Notification, CustomerOrderFulfilmentSummarySnapshot
from app.dashboard.routes.customer_order_fulfilment_summary import (
    customer_order_fulfilment_summary,
    customer_order_fulfilment_summary_partial,
    build_filter_query,
    get_filter_options,
    HIERARCHIES
)
from unittest.mock import patch, MagicMock

class CustomerOrderFulfilmentSummaryAjaxTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder='../app/templates')
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY='test-key'
        )
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        Notification.__table__.create(db.engine, checkfirst=True)
        CustomerOrderFulfilmentSummarySnapshot.__table__.create(db.engine, checkfirst=True)

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()

    @patch('app.dashboard.routes.customer_order_fulfilment_summary.render_template')
    def test_main_route_does_not_compute_stats_synchronously(self, mock_render):
        mock_render.return_value = 'mock_html'
        with self.app.test_request_context('/customerorderfulfilmentsummary'):
            res = customer_order_fulfilment_summary()
            self.assertEqual(res, 'mock_html')
            kwargs = mock_render.call_args.kwargs
            self.assertIsNone(kwargs['stats'])
            self.assertEqual(kwargs['rows'], [])
            self.assertIsNone(kwargs['pagination'])

    @patch('app.dashboard.routes.customer_order_fulfilment_summary.render_template')
    def test_partial_route_computes_stats_and_rows_for_ajax(self, mock_render):
        mock_render.return_value = '<div>partial_html</div>'
        with self.app.test_request_context('/partial/customerorderfulfilmentsummary'):
            res = customer_order_fulfilment_summary_partial()
            self.assertEqual(res, '<div>partial_html</div>')
            kwargs = mock_render.call_args.kwargs
            self.assertIsNotNone(kwargs['stats'])
            self.assertIn('ordered_wt', kwargs['stats'])
            self.assertIsNotNone(kwargs['pagination'])

    def test_location_options_and_shared_query_filter(self):
        M = CustomerOrderFulfilmentSummarySnapshot
        db.session.add_all([M(id=1, location='ERNAKULAM'), M(id=2, location='THRISSUR ROUND'),
                            M(id=3, location='ERNAKULAM')])
        db.session.commit()
        with self.app.test_request_context('/customerorderfulfilmentsummary?location=ERNAKULAM'):
            self.assertEqual(get_filter_options()['locations'], ['ERNAKULAM', 'THRISSUR ROUND'])
            self.assertEqual([r.id for r in build_filter_query(M.query).order_by(M.id)], [1, 3])
        with self.app.test_request_context('/customerorderfulfilmentsummary'):
            self.assertEqual(build_filter_query(M.query).count(), 3)
