"""Unit tests for Empirical Bayes delivery metrics in collection wise delivery days report."""
import unittest
from collections import namedtuple
from app.dashboard.routes.collection_wise_average_delivery_days import (
    compute_bayesian_delivery_metrics,
    compute_barcode_bayesian_stage_risk,
)
from datetime import date, timedelta

RowMock = namedtuple('RowMock', [
    'barcode_count',
    'office_pending_count',
    'avg_tat_days',
    'median_tat_days',
    'p90_tat_days',
    'avg_delivery_days',
    'compliance_pct',
    'office_overdue_count',
    'avg_pending_age_days',
], defaults=[0, 0, None, None, None, 15.0, None, 0, None])

BarcodeMock = namedtuple('BarcodeMock', [
    'ordered_date',
    'hm_issue_date',
    'hm_receipt_date',
    'qc_issue_date',
    'qc_receipt_date',
    'crystal_invoice_date',
    'morr_received_date',
    'muziris_inshop_received_date',
], defaults=[None]*8)

class TestBayesianDeliveryMetrics(unittest.TestCase):
    def test_small_sample_shrinkage(self):
        # N=1, raw TAT=5d, global baseline=15d, prior weight=5d
        # w = 1 / (1 + 5) = 1/6; adjusted = (1/6 * 5) + (5/6 * 15) = 0.833 + 12.5 = 13.33d
        row = RowMock(barcode_count=1, office_pending_count=0, avg_tat_days=5.0, compliance_pct=100.0)
        res = compute_bayesian_delivery_metrics(row, global_mu0=15.0, global_comp0=80.0, prior_weight_m=5.0)

        self.assertAlmostEqual(res['bayes_adjusted_tat'], 13.3, places=1)
        self.assertEqual(res['confidence_level'], 'Low Volume (Prior-Guided)')
        self.assertTrue(res['is_low_sample'])
        # Compliance smoothed from 100% towards 80%
        self.assertLess(res['bayes_smoothed_compliance'], 90.0)
        self.assertGreater(res['bayes_smoothed_compliance'], 80.0)

    def test_large_sample_fidelity(self):
        # N=500, raw TAT=18.8d, global baseline=14.0d
        # w = 500 / 505 = 0.990 -> adjusted remains very close to raw
        row = RowMock(
            barcode_count=500,
            office_pending_count=0,
            avg_tat_days=18.8,
            median_tat_days=16.0,
            p90_tat_days=34.0,
            compliance_pct=13.3,
        )
        res = compute_bayesian_delivery_metrics(row, global_mu0=14.0, global_comp0=82.0, prior_weight_m=5.0)

        self.assertAlmostEqual(res['bayes_adjusted_tat'], 18.8, delta=0.2)
        self.assertEqual(res['confidence_level'], 'High Confidence')
        self.assertFalse(res['is_low_sample'])
        self.assertLess(res['bayes_credible_min'], res['bayes_adjusted_tat'])
        self.assertGreater(res['bayes_credible_max'], res['bayes_adjusted_tat'])

    def test_inflight_risk_detection(self):
        # 10 pending orders, 8 already overdue
        row = RowMock(
            barcode_count=20,
            office_pending_count=10,
            avg_tat_days=12.0,
            avg_delivery_days=15.0,
            compliance_pct=80.0,
            office_overdue_count=8,
            avg_pending_age_days=18.0,
        )
        res = compute_bayesian_delivery_metrics(row, global_mu0=14.0, global_comp0=80.0)

        self.assertGreater(res['bayes_inflight_risk_pct'], 70.0)
        self.assertTrue(res['has_high_inflight_risk'])
        self.assertGreaterEqual(res['bayes_orders_at_risk'], 8)

    def test_barcode_completed_state(self):
        today = date.today()
        rec = BarcodeMock(
            ordered_date=today - timedelta(days=14),
            morr_received_date=today - timedelta(days=2),
            muziris_inshop_received_date=today,
        )
        res = compute_barcode_bayesian_stage_risk(rec, delivery_target_days=15, tat_days=12)
        self.assertEqual(res['state'], 'completed')
        self.assertEqual(res['breach_risk_pct'], 0.0)
        self.assertIn('Delivered On-Time', res['risk_level'])

    def test_barcode_overdue_in_production(self):
        today = date.today()
        rec = BarcodeMock(
            ordered_date=today - timedelta(days=20),
            hm_issue_date=today - timedelta(days=16),
            hm_receipt_date=today - timedelta(days=10),
            morr_received_date=None,
        )
        res = compute_barcode_bayesian_stage_risk(rec, delivery_target_days=15, tat_days=None)
        self.assertEqual(res['state'], 'workshop_pending')
        self.assertGreaterEqual(res['breach_risk_pct'], 90.0)
        self.assertEqual(res['risk_level'], 'SLA Overdue')
        self.assertEqual(res['active_stage'], 'HM Received')

if __name__ == '__main__':
    unittest.main()
