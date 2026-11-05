import os
import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from werkzeug.datastructures import MultiDict
from app.services import sales_tsk_performance as report
from app.dashboard.routes import sales_tsk_performance as routes


class FilterTests(unittest.TestCase):
    def test_default_financial_year(self):
        for today, expected in [(datetime(2026, 11, 5), date(2026, 4, 1)),
                                (datetime(2027, 3, 31), date(2026, 4, 1)),
                                (datetime(2027, 4, 1), date(2027, 4, 1))]:
            with patch.object(report, 'datetime') as clock:
                clock.now.return_value = today
                self.assertEqual(report.defaults(), (expected, today.date()))

    def test_bounds_and_leap_year(self):
        with self.assertRaises(ValueError):
            report.parse_filters(MultiDict(dict(start='2026-02-01', end='2026-01-01')))
        with self.assertRaises(ValueError):
            report.parse_filters(MultiDict(dict(start='2025-01-01', end='2026-01-01')))
        self.assertEqual(report.previous_year(date(2024, 2, 29)), date(2023, 2, 28))

    def test_values_are_bound_and_dates_are_exclusive(self):
        attack = "1' OR TRUE --"
        filters = report.parse_filters(MultiDict([('start', '2026-01-01'), ('end', '2026-01-31'), ('section_id', attack)]))
        sql, params = report.where_clause(filters)
        self.assertNotIn(attack, sql)
        self.assertEqual(params, [date(2026, 1, 1), date(2026, 2, 1), [attack]])

    def test_invalid_transaction_type(self):
        with self.assertRaises(ValueError):
            report.parse_filters(MultiDict(dict(trans_type='OTHER')))


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.add_url_rule('/api/sales-tsk-performance/<segment>', view_func=routes.sales_tsk_performance_segment)
        self.client = self.app.test_client()

    def test_anonymous_cannot_access_any_segment(self):
        for segment in routes.SEGMENTS:
            self.assertEqual(self.client.get('/api/sales-tsk-performance/' + segment).status_code, 401)

    def test_report_grant_required_for_every_segment(self):
        user = SimpleNamespace(is_active=True, roles=[], username='reader', is_admin=False)
        with patch('app.utils.decorators.verify_jwt_in_request'), patch('app.utils.decorators.get_jwt_identity', return_value='1'), patch('app.extensions.db.session.get', return_value=user), patch.object(report, 'load_segment') as loader:
            for segment in routes.SEGMENTS:
                self.assertEqual(self.client.get('/api/sales-tsk-performance/' + segment).status_code, 403)
            loader.assert_not_called()

    def test_granted_api_decimal_and_no_store(self):
        menu = SimpleNamespace(url=routes.REPORT, permission_required=None)
        user = SimpleNamespace(is_active=True, roles=[SimpleNamespace(name='REPORT_READER', permissions=[], menus=[menu])], username='reader', is_admin=False)
        with patch('app.utils.decorators.verify_jwt_in_request'), patch('app.utils.decorators.get_jwt_identity', return_value='1'), patch('app.extensions.db.session.get', return_value=user), patch.object(report, 'load_segment', return_value={'net_turnover': Decimal('12.25')}):
            response = self.client.get('/api/sales-tsk-performance/kpis')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['data']['net_turnover'], 12.25)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_export_escapes_source_labels(self):
        with self.app.test_request_context('/?start=2026-01-01&end=2026-01-31'), patch.object(report, 'load_segment', return_value=[{'month': '2026-01-01', 'net_turnover': Decimal('-12'), 'leading_branch': '=HYPERLINK("bad")'}]):
            response = routes.sales_tsk_performance_segment.__wrapped__('export')
            self.assertIn("'=HYPERLINK", response.get_data(as_text=True))
            self.assertIn('-12', response.get_data(as_text=True))

    def test_failure_is_sanitized_and_invalid_filters_do_not_query(self):
        with self.app.test_request_context('/?start=bad'), patch.object(report, 'load_segment') as loader:
            _, status = routes.sales_tsk_performance_segment.__wrapped__('ledger')
            self.assertEqual(status, 400); loader.assert_not_called()
        with self.app.test_request_context('/'), patch.object(report, 'load_segment', side_effect=RuntimeError('sensitive connection detail')):
            response, status = routes.sales_tsk_performance_segment.__wrapped__('ledger')
            self.assertEqual(status, 503)
            self.assertNotIn('sensitive', response.get_data(as_text=True))


@unittest.skipUnless(os.getenv('SALES_TSK_SQL_TEST') == '1', 'Opt-in PostgreSQL temporary-table tests')
class PostgreSQLTests(unittest.TestCase):
    """Only a connection-local TEMP table is written; application tables are untouched."""
    def setUp(self):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        uri = os.environ['SQLALCHEMY_DATABASE_URI'].replace('postgresql+psycopg2://', 'postgresql://')
        self.conn = psycopg2.connect(uri)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.cur.execute('''CREATE TEMP TABLE sales_tsk_fixture (
            date date, trans_date timestamp, trans_type text, turn_over numeric, net_weight numeric, total_tsk numeric,
            section_id int, section text, branch_id int, location_name text, last_updated_at timestamp,
            state_name text, location_group text, make_id int, make text, master_collection_id int, master_collection text,
            collection_id int, collection text, classification_id int, classification text, purity_id int, purity text,
            gender_id int, gender text, invoice_type text)''')
        self.cur.execute('''INSERT INTO sales_tsk_fixture(date, trans_date, trans_type, turn_over, net_weight, total_tsk, section_id, section, branch_id, location_name)
            VALUES ('2026-01-01', '2026-01-02', 'INVOICE', 100, 10, 5, 1, 'Rings', 1, 'A'),
                   ('2026-01-03', NULL, 'SR', -20, -2, -1, 1, 'Rings', 1, 'A'),
                   ('2026-01-31', '2026-01-31 23:59:59', 'INVOICE', 60, 6, 3, 2, 'Rings', 2, 'B'),
                   ('2026-02-01', NULL, 'INVOICE', 200, 20, 10, NULL, NULL, 2, 'B'),
                   ('2025-01-01', NULL, 'INVOICE', 70, 7, 3, 1, 'Rings', 1, 'A'),
                   ('2026-01-04', NULL, 'OTHER', 9999, 0, 0, 1, 'Rings', 1, 'A')''')
        self.source_patch = patch.object(report, 'SOURCE', 'pg_temp.sales_tsk_fixture'); self.source_patch.start()
        self.sign_patch = patch.dict(os.environ, SALES_PREDICTION_RETURN_SIGN='signed'); self.sign_patch.start()
        self.filters = report.parse_filters(MultiDict(dict(start='2026-01-01', end='2026-01-31')))

    def tearDown(self):
        self.source_patch.stop(); self.sign_patch.stop(); self.conn.rollback(); self.conn.close()

    def test_reconciliation_section_ids_and_prior_year(self):
        totals = report.totals(self.cur, self.filters)
        self.assertEqual(totals['net_turnover'], Decimal(140))
        self.assertEqual(totals['net_weight'], Decimal('0.014'))
        self.assertEqual(totals['total_tsk'], Decimal(7))
        sections = report.breakdown(self.cur, self.filters, 'sections')
        self.assertEqual(len(sections), 2)  # Same name, distinct section IDs.
        self.assertEqual(sum(r['net_turnover'] for r in sections), totals['net_turnover'])
        self.assertAlmostEqual(sum(r['share'] for r in sections), Decimal(100))
        months = report.monthly(self.cur, self.filters)
        self.assertEqual(months[0]['net_turnover'], totals['net_turnover'])
        self.assertEqual(months[0]['yoy'], Decimal(100))
        self.assertEqual(months[0]['leading_branch'], 'A')
        self.assertEqual(report.options(self.cur, self.filters)['section_id'], [{'value': '1', 'label': 'Rings'}, {'value': '2', 'label': 'Rings'}])

    def test_filters_dates_unknown_sections_and_missing_months(self):
        filters = report.parse_filters(MultiDict(dict(start='2026-01-01', end='2026-03-31', section_id='1')))
        months = report.monthly(self.cur, filters)
        self.assertEqual([r['net_turnover'] for r in months], [80, 0, 0])
        self.assertIsNone(months[-1]['yoy'])
        filters['selections'] = {}
        sections = report.breakdown(self.cur, filters, 'sections')
        self.assertIn('Unspecified', [r['label'] for r in sections])
        filters = report.parse_filters(MultiDict(dict(start='2026-01-01', end='2026-01-01')))
        self.assertEqual(report.totals(self.cur, filters)['row_count'], 0)  # trans_date takes precedence.

    def test_kpi_year_over_year_and_filtered_baseline(self):
        totals = report.totals(self.cur, self.filters)
        self.assertEqual(totals['yoy']['net_turnover'], Decimal(100))
        self.assertEqual(totals['yoy']['net_weight'], Decimal(100))
        self.assertAlmostEqual(totals['yoy']['total_tsk'], Decimal(400) / 3)
        self.assertIsNone(totals['yoy']['return_turnover'])  # Zero prior returns.
        self.assertEqual(totals['prior_period'], {'start': '2025-01-01', 'end': '2025-01-31'})
        self.filters['selections'] = {'branch_id': ['2']}
        totals = report.totals(self.cur, self.filters)
        self.assertTrue(all(value is None for value in totals['yoy'].values()))
        self.filters['selections'] = {}
        self.filters['start'] = date(2026, 1, 2)  # Prior Jan 1 must not be included.
        self.assertIsNone(report.totals(self.cur, self.filters)['yoy']['net_turnover'])

    def test_ledger_contribution_and_complete_month_movement(self):
        filters = report.parse_filters(MultiDict(dict(start='2026-01-01', end='2026-03-31')))
        rows = report.monthly(self.cur, filters)
        self.assertAlmostEqual(sum(row['period_share'] for row in rows), Decimal(100))
        self.assertIsNone(rows[0]['mom'])
        self.assertAlmostEqual(rows[1]['mom'], Decimal(60) / Decimal(140) * 100)
        self.assertIsNone(rows[2]['mom'])  # No transactions, not a real decline.
        filters['end'] = date(2026, 2, 5)
        rows = report.monthly(self.cur, filters)
        self.assertTrue(rows[1]['is_partial'])
        self.assertIsNone(rows[1]['mom'])
        self.cur.execute("UPDATE sales_tsk_fixture SET turn_over=-1000 WHERE trans_type='SR'")
        self.assertTrue(all(row['period_share'] is None for row in report.monthly(self.cur, filters)))

    def test_kpi_negative_baseline_and_unchanged_values(self):
        self.cur.execute("INSERT INTO sales_tsk_fixture(date, trans_type, turn_over, net_weight, total_tsk) VALUES ('2025-01-03', 'SR', -40, 7, 4)")
        totals = report.totals(self.cur, self.filters)
        self.assertEqual(totals['yoy']['return_turnover'], Decimal(50))
        self.assertEqual(totals['yoy']['net_weight'], Decimal(0))
        self.assertEqual(totals['yoy']['total_tsk'], Decimal(0))
        self.cur.execute("UPDATE sales_tsk_fixture SET turn_over=-10 WHERE trans_type='SR' AND date='2025-01-03'")
        self.assertEqual(report.totals(self.cur, self.filters)['yoy']['return_turnover'], Decimal(-100))

    def test_return_sign_validation(self):
        self.cur.execute("UPDATE sales_tsk_fixture SET turn_over=20 WHERE trans_type='SR'")
        with self.assertRaises(report.SourceDataError): report.totals(self.cur, self.filters)
        with patch.dict(os.environ, SALES_PREDICTION_RETURN_SIGN='positive'):
            self.assertEqual(report.totals(self.cur, self.filters)['net_turnover'], Decimal(140))


if __name__ == '__main__':
    unittest.main()
