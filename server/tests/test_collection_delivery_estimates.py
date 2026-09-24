import unittest
from types import SimpleNamespace

from flask import Flask
from sqlalchemy import literal, select, union_all
from app.extensions import db
from app.dashboard.routes.collection_wise_average_delivery_days import (
    compute_bayesian_delivery_metrics, collection_delivery_baselines,
)


class DeliveryEstimateTests(unittest.TestCase):
    def row(self, **changes):
        values = dict(valid_tat_count=100, avg_tat_days=20, tat_stddev_days=10,
                      office_pending_count=10, office_assessed_pending_count=8,
                      office_overdue_count=2, compliance_eligible_count=50,
                      compliant_count=20)
        values.update(changes)
        return SimpleNamespace(**values)

    def test_adjustment_and_actual_spread(self):
        result = compute_bayesian_delivery_metrics(self.row(), 10, 80)
        self.assertEqual(result['bayes_adjusted_tat'], 19.5)
        self.assertEqual(result['bayes_credible_min'], 18.4)
        self.assertEqual(result['bayes_credible_max'], 21.6)
        self.assertEqual(result['bayes_smoothed_compliance'], 45.5)
        self.assertEqual(result['bayes_inflight_risk_pct'], 25.0)
        self.assertEqual(result['bayes_orders_at_risk'], 2)
        self.assertEqual(result['confidence_level'], 'Large sample')

    def test_missing_sample_does_not_invent_estimates(self):
        result = compute_bayesian_delivery_metrics(self.row(
            valid_tat_count=0, avg_tat_days=None, tat_stddev_days=None,
            compliance_eligible_count=0, compliant_count=0,
            office_pending_count=0, office_assessed_pending_count=0,
            office_overdue_count=0), 14, 82)
        for key in ['bayes_adjusted_tat', 'bayes_credible_min',
                    'bayes_smoothed_compliance', 'bayes_inflight_risk_pct']:
            self.assertIsNone(result[key])

    def test_small_sample_and_missing_targets(self):
        result = compute_bayesian_delivery_metrics(self.row(
            valid_tat_count=2, office_assessed_pending_count=0,
            office_overdue_count=0))
        self.assertIsNone(result['bayes_credible_min'])
        self.assertIsNone(result['bayes_inflight_risk_pct'])
        self.assertEqual(result['completed_count'], 2)

    def test_no_forced_minimum_interval_width(self):
        result = compute_bayesian_delivery_metrics(self.row(tat_stddev_days=0))
        self.assertEqual(result['bayes_credible_min'], 20)
        self.assertEqual(result['bayes_credible_max'], 20)

    def test_baseline_is_weighted_and_independent_of_sort_order(self):
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        db.init_app(app)
        with app.app_context():
            groups = union_all(
                select(literal(100).label('tat_sum_days'), literal(10).label('valid_tat_count'),
                       literal(5).label('compliant_count'), literal(10).label('compliance_eligible_count')),
                select(literal(900), literal(30), literal(1), literal(2)),
            ).subquery()
            query = db.session.query(*groups.c)
            for order in [groups.c.tat_sum_days.asc(), groups.c.tat_sum_days.desc()]:
                mean, compliance = collection_delivery_baselines(query.order_by(order))
                self.assertEqual(mean, 25)
                self.assertEqual(compliance, 50)
            db.session.remove()
            db.engine.dispose()


if __name__ == '__main__':
    unittest.main()
