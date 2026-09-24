import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy.dialects import postgresql
from app.models import CollectionWiseAverageDeliveryDaysSnapshot as Snapshot
from app.dashboard.routes import collection_wise_average_delivery_days as report


class CollectionSLAVarianceTests(unittest.TestCase):
    def test_barcode_variance_includes_transit_allowance(self):
        for transit, target, receipt, expected in [
            (3, 10, date(2026, 1, 16), 2),
            (5, 10, date(2026, 1, 16), 0),
            (7, 10, date(2026, 1, 16), -2),
            (None, 10, date(2026, 1, 16), 5),
            (3, None, date(2026, 1, 16), None),
            (3, 10, None, None),
            (3, 10, date(2025, 12, 31), None),
            (3, 10, date(2099, 1, 1), None),
            (3, -1, date(2026, 1, 16), None),
            (-1, 10, date(2026, 1, 16), None),
        ]:
            with self.subTest(transit=transit, target=target, receipt=receipt):
                record = Snapshot(ordered_date=date(2026, 1, 1),
                                  morr_received_date=receipt, delivery_days=target,
                                  in_transit_days=transit)
                with patch.object(report, 'build_process_timeline', return_value=([], [])), \
                     patch.object(report, 'compute_barcode_bayesian_stage_risk', return_value={}):
                    row = report.build_delivery_display_rows([record])[0]
                self.assertEqual(row['variance_days'], expected)
                self.assertEqual(row['modal_data']['variance_days'], expected)
                if expected is not None:
                    self.assertEqual(row['status_label'], 'On Time' if expected <= 0 else 'Delayed')
                if receipt and (receipt < record.ordered_date or receipt.year == 2099):
                    self.assertIsNone(row['tat_days'])
                    self.assertEqual(row['status_label'], 'Invalid Dates')

    def test_summary_uses_transit_in_variance_and_delayed_count(self):
        with patch.object(report, 'build_snapshot_query'):
            _, metrics = report.build_collection_summary_query({})
        for key in ['avg_sla_variance', 'sla_delayed_count', 'compliance_pct', 'delayed_count']:
            sql = str(metrics[key].compile(dialect=postgresql.dialect(),
                                          compile_kwargs={'literal_binds': True}))
            self.assertIn(f'coalesce({Snapshot.__tablename__}.in_transit_days, 0)', sql)


if __name__ == '__main__':
    unittest.main()
