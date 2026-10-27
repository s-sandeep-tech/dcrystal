import unittest
from html.parser import HTMLParser
from pathlib import Path
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

    def test_weight_heading_information_icons_have_exact_tooltips(self):
        class InfoParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.icons = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'fulfilment-metric-info' in attrs.get('class', '').split():
                    self.icons.append(attrs)

        folder = Path(__file__).resolve().parents[1] / 'app/templates'
        expected = ['PO Generated Weight', 'Rejected Weight', 'Cancelled Weight',
                    'Collection Owner Approved \u2013 Order Not Generated weight',
                    'Party Accepted Weight', 'Barcoded Weight', 'Hallmarked Weight',
                    'Quality Control Passed Weight', 'Invoiced Weight',
                    'Delivered to Customer Weight', 'Pending to be Delivered Weight']
        for filename in ['customer_order_fulfilment_summary.html',
                         'partials/_view_customer_order_fulfilment_summary.html']:
            parser = InfoParser()
            parser.feed((folder / filename).read_text())
            self.assertEqual([icon['title'] for icon in parser.icons], expected)
            for icon in parser.icons:
                self.assertEqual(icon['aria-label'], icon['title'])
                self.assertEqual(icon['tabindex'], '0')
