import unittest
from datetime import date, datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from app.utils.customer_order_monitoring import prepare, summarize, filter_rows, STAGES, sort_rows


class MonitoringTests(unittest.TestCase):
    def row(self, **changes):
        row = dict(id=1, sooc='S1', request_no='R1', branch_id=2, location='Kochi',
                   order_status='Delivered to shop', expected_delivery_date=datetime(2026, 10, 1),
                   total_pending_pcs=0, total_pending_wt=0)
        row.update(changes)
        return row

    def prepare(self, rows):
        return prepare(rows, date(2026, 10, 1))

    def test_separate_measures_and_no_stage_total(self):
        rows, _ = self.prepare([self.row(customer_delivery_pending_pcs=2, customer_delivery_pending_wt=12,
                                        customer_order_approval_pending_pcs=1)])
        stats, charts = summarize(rows)
        self.assertEqual(stats['pieces'], 0)
        self.assertEqual(stats['approval'], 1)
        self.assertEqual(charts['stages'][-1]['pcs'], 2)
        self.assertEqual(len(filter_rows(rows, {})), 1)

    def test_terminal_statuses_never_outstanding_even_with_stale_quantities(self):
        for status in ['Delivered to customer', 'Cancelled/rejected by party',
                       'Cancelled/rejected by verifying team', 'Cancelled/rejected by customer']:
            rows, _ = self.prepare([self.row(order_status=status, total_pending_pcs=5)])
            self.assertFalse(rows[0]['_active'])
            self.assertEqual(filter_rows(rows, {}), [])

    def test_risks_distinct_request_earliest_active_date(self):
        rows, _ = self.prepare([
            self.row(expected_delivery_date=datetime(2026, 10, 8)),
            self.row(id=2, sooc='S2', expected_delivery_date=datetime(2026, 9, 30)),
            self.row(id=3, sooc='S3', request_no='R2', expected_delivery_date=None),
            self.row(id=4, sooc='S4', order_status='Delivered to customer', expected_delivery_date=datetime(2026, 8, 1)),
        ])
        stats, charts = summarize(rows)
        self.assertEqual(stats['overdue'], 1)
        self.assertEqual(rows[0]['_risk'], 'critical')
        self.assertEqual(rows[0]['_request_due'], date(2026, 9, 30))
        self.assertEqual(sum(r['count'] for r in charts['risks']), 2)
        self.assertEqual(charts['risks'][-1]['count'], 1)

    def test_risk_boundaries(self):
        for day, expected in [(0, 'critical'), (1, 'high'), (3, 'high'), (4, 'medium'), (8, 'medium'), (9, 'normal')]:
            due = datetime(2026, 10, day) if day else datetime(2026, 9, 30)
            rows, _ = self.prepare([self.row(expected_delivery_date=due)])
            self.assertEqual(rows[0]['_risk'], expected)

    def test_request_in_multiple_branches_is_counted_once(self):
        rows, _ = self.prepare([self.row(), self.row(id=2, sooc='S2', branch_id=3,
            expected_delivery_date=datetime(2026, 9, 30))])
        stats, charts = summarize(rows)
        self.assertEqual(stats['orders'], 1)
        self.assertEqual(stats['overdue'], 1)
        self.assertEqual(sum(r['count'] for r in charts['risks']), 1)

    def test_duplicates_and_conflicts(self):
        rows, count = self.prepare([self.row(), self.row(id=2)])
        self.assertEqual((len(rows), count), (1, 1))
        with self.assertRaises(ValueError):
            self.prepare([self.row(), self.row(id=2, total_pending_pcs=2)])
        with self.assertRaises(ValueError):
            self.prepare([self.row(), self.row(id=2, branch_id=3)])

    def test_filters_and_masked_search(self):
        rows, _ = self.prepare([self.row(party_name='Secret', process_pending_pcs=1)])
        self.assertEqual(len(filter_rows(rows, {'stage': 'processing', 'branch': '2'})), 1)
        self.assertEqual(len(filter_rows(rows, {'stage': 'approval'})), 0)
        self.assertEqual(len(filter_rows(rows, {'search': 'Secret'}, masked=True)), 0)
        self.assertEqual(len(filter_rows(rows, {'search': 'Secret'}, masked=False)), 1)

    def test_unknown_and_missing_dates(self):
        rows, _ = self.prepare([self.row(order_status='new status', expected_delivery_date=datetime(1, 1, 1))])
        self.assertFalse(rows[0]['_active'])
        self.assertIsNone(rows[0]['_due'])
        rows, _ = self.prepare([self.row(order_status=None, process_pending_pcs=1)])
        self.assertTrue(rows[0]['_active'])
        self.assertEqual(rows[0]['_classification'], 'Unclassified')

    def test_table_has_14_columns_and_escaped_supplier(self):
        from app.models.customer_order_analysis import CustomerOrderAnalysisSnapshot
        row = {c.name: None for c in CustomerOrderAnalysisSnapshot.__table__.columns}
        row.update(self.row(party_name='<script>bad()</script>'))
        rows, _ = self.prepare([row])
        folder = Path(__file__).resolve().parents[1] / 'app/templates'
        template = Environment(loader=FileSystemLoader(folder), autoescape=True).get_template('partials/_customer_order_monitoring_table.html')
        html = template.render(rows=rows, stages=STAGES)
        self.assertIn('colspan="14"', html)
        self.assertNotIn('<script>bad()', html)
        self.assertIn('&lt;script&gt;', html)


if __name__ == '__main__':
    unittest.main()
