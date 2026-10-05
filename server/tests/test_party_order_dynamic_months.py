import unittest
from flask import Flask
from app.extensions import db
from app.models import PartyOrderAcceptCancelDeliverySnapshot as Snapshot
from app.dashboard.routes.party_order_accept_cancel_delivery_performance import (
    get_options, report_filters, report_sort, build_matrix, build_month_totals, aggregate_stats,
)


class DynamicMonthsTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        Snapshot.__table__.create(db.engine)
        for i, month in enumerate(['January 2027', 'October 2026', 'September 2026'], 1):
            db.session.add(Snapshot(id=i, month=month, supplier='Supplier A', make='Make A',
                                   party_type='Smith', order_type='Customer', provision_type='Regular',
                                   order_wt=10 * i, order_pcs=i))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_options_and_totals_include_new_months(self):
        months = get_options(Snapshot.month, calendar_order=True)
        self.assertEqual(months, ['September 2026', 'October 2026', 'January 2027'])
        for field, value in [('supplier', 'Supplier A'), ('make', 'Make A'), ('party_type', 'Smith'),
                             ('order_type', 'Customer'), ('provision_type', 'Regular')]:
            self.assertEqual(get_options(getattr(Snapshot, field)), [value])
        with self.app.test_request_context('/?sort_by=month_october%202026'):
            filters = report_filters()
            self.assertEqual(report_sort(months), ('month_october 2026', 'asc'))
            rows, _ = build_matrix(filters, 'party', 1, 50, months=months)
            self.assertEqual(rows[0]['total']['ordered']['wt'], 60)
            self.assertEqual(rows[0]['months']['October 2026']['ordered']['wt'], 20)
            _, total = build_month_totals(filters, months)
            self.assertEqual(total['ordered']['wt'], 60)

    def test_month_filter_and_child_rows(self):
        with self.app.test_request_context('/?month=September%202026'):
            filters = report_filters()
            rows, _ = build_matrix(filters, 'make', 1, 50, parent_party='Supplier A', paginate=False)
            self.assertEqual(rows[0]['total']['ordered']['wt'], 30)
            _, total = build_month_totals(filters)
            self.assertEqual(total['ordered']['wt'], 30)

    def test_every_filter_matches_stats_matrix_and_totals(self):
        db.session.add(Snapshot(id=4, month='February 2027', supplier='Supplier B', make='Make B',
            party_type='Supplier', order_type='Refill', provision_type='Special', order_wt=99, order_pcs=9))
        db.session.commit()
        from urllib.parse import urlencode
        for key, value in [('party', 'Supplier B'), ('party_type', 'Supplier'), ('make', 'Make B'),
                           ('month', 'February 2027'), ('order_type', 'Refill'), ('provision_type', 'Special')]:
            with self.subTest(filter=key), self.app.test_request_context('/?' + urlencode({key: value})):
                filters = report_filters()
                rows, _ = build_matrix(filters, 'party', 1, 50)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['party'], 'Supplier B')
                self.assertEqual(rows[0]['total']['ordered']['wt'], 99)
                self.assertEqual(aggregate_stats(filters)['ordered_wt'], '99.000')
                self.assertEqual(build_month_totals(filters)[1]['ordered']['wt'], 99)
                child_rows, _ = build_matrix(filters, 'make', 1, 50, parent_party='Supplier B', paginate=False)
                self.assertEqual(child_rows[0]['make'], 'Make B')

    def test_grand_total_hidden_when_one_row(self):
        import os
        from flask import render_template
        self.app.template_folder = os.path.abspath('server/app/templates')

        # 1 row in report: Grand Total footer must be hidden
        html_one_row = render_template(
            'partials/_view_party_order_accept_cancel_delivery_performance.html',
            is_child_rows=False,
            rows=[{'level': 'party', 'party': 'P1', 'months': {}, 'total': {'ordered': {'wt': 10, 'pcs': 1}, 'accepted': {'wt': 0, 'pcs': 0}, 'cancelled': {'wt': 0, 'pcs': 0}, 'delivered': {'wt': 0, 'pcs': 0}}}],
            months=[], month_totals={},
            grand_total={'ordered': {'wt': 10, 'pcs': 1}, 'accepted': {'wt': 0, 'pcs': 0}, 'cancelled': {'wt': 0, 'pcs': 0}, 'delivered': {'wt': 0, 'pcs': 0}},
            pagination=type('P', (), {'total': 1, 'page': 1, 'pages': 1, 'per_page': 50})(),
            current_level='party', sort_by='party', sort_dir='asc', stats={},
        )
        self.assertNotIn('Grand Total</td>', html_one_row)

        # 2 rows in report: Grand Total footer must be displayed
        html_two_rows = render_template(
            'partials/_view_party_order_accept_cancel_delivery_performance.html',
            is_child_rows=False,
            rows=[
                {'level': 'party', 'party': 'P1', 'months': {}, 'total': {'ordered': {'wt': 10, 'pcs': 1}, 'accepted': {'wt': 0, 'pcs': 0}, 'cancelled': {'wt': 0, 'pcs': 0}, 'delivered': {'wt': 0, 'pcs': 0}}},
                {'level': 'party', 'party': 'P2', 'months': {}, 'total': {'ordered': {'wt': 20, 'pcs': 2}, 'accepted': {'wt': 0, 'pcs': 0}, 'cancelled': {'wt': 0, 'pcs': 0}, 'delivered': {'wt': 0, 'pcs': 0}}},
            ],
            months=[], month_totals={},
            grand_total={'ordered': {'wt': 30, 'pcs': 3}, 'accepted': {'wt': 0, 'pcs': 0}, 'cancelled': {'wt': 0, 'pcs': 0}, 'delivered': {'wt': 0, 'pcs': 0}},
            pagination=type('P', (), {'total': 2, 'page': 1, 'pages': 1, 'per_page': 50})(),
            current_level='party', sort_by='party', sort_dir='asc', stats={},
        )
        self.assertIn('Grand Total</td>', html_two_rows)
