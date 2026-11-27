import unittest
from unittest.mock import patch

from flask import Flask
from app.extensions import db
from app.models.snapshots import PartyMakeCapacityDetailsSnapshot as Snapshot
from app.dashboard.routes.party_make_capacity import (
    get_aggregated_capacity_data, api_party_make_capacity_data,
    api_party_make_capacity_drilldown,
)


class BoolOr:
    def __init__(self):
        self.value = False

    def step(self, value):
        self.value = self.value or bool(value)

    def finalize(self):
        return int(self.value)


class CapacityOrderStatusTests(unittest.TestCase):
    def setUp(self):
        visibility = patch('app.dashboard.routes.party_make_capacity.capacity_owner_condition', return_value=None)
        visibility.start()
        self.addCleanup(visibility.stop)
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        Snapshot.__table__.create(db.engine)
        connection = db.engine.raw_connection()
        connection.create_aggregate('bool_or', 1, BoolOr)
        connection.close()
        db.session.add_all([
            Snapshot(supplier='A inactive', make='A', is_orders=False),
            Snapshot(supplier='B mixed', make='A inactive', is_orders=False),
            Snapshot(supplier='B mixed', make='B active', is_orders=True),
            Snapshot(supplier='B mixed', make='C mixed', is_orders=False, location='A'),
            Snapshot(supplier='B mixed', make='C mixed', is_orders=True, location='Z'),
            Snapshot(supplier='C unknown', make='A', is_orders=None),
            Snapshot(supplier='D inactive', make='A', is_orders=False),
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()

    def test_grouping_and_both_sort_directions(self):
        for direction, names in [
            ('asc', ['B mixed', 'C unknown', 'A inactive', 'D inactive']),
            ('desc', ['C unknown', 'B mixed', 'D inactive', 'A inactive']),
        ]:
            with self.app.test_request_context('/?sort_order=' + direction):
                rows, kpis = get_aggregated_capacity_data()
                self.assertEqual([r['supplier'] for r in rows], names)
                self.assertEqual(kpis['total_suppliers_count'], 4)
                mixed = next(r for r in rows if r['supplier'] == 'B mixed')
                self.assertTrue(mixed['is_orders'])
                self.assertEqual([m['make'] for m in mixed['makes']],
                                 ['B active', 'C mixed', 'A inactive'])
                self.assertFalse(mixed['makes'][-1]['is_orders'])

    def test_partition_precedes_pagination(self):
        with self.app.test_request_context('/?per_page=2&page=2'):
            result = api_party_make_capacity_data.__wrapped__().get_json()
            self.assertEqual([r['supplier'] for r in result['data']],
                             ['A inactive', 'D inactive'])

    def test_detail_rows_false_last(self):
        with self.app.test_request_context('/?supplier=B+mixed&make=C+mixed'):
            result = api_party_make_capacity_drilldown.__wrapped__().get_json()
            self.assertEqual([r['is_orders'] for r in result['data']], [True, False])
            self.assertEqual([r['location'] for r in result['data']], ['Z', 'A'])

    def test_filtered_group_status(self):
        with self.app.test_request_context('/?supplier=B+mixed&make=A+inactive'):
            rows, _ = get_aggregated_capacity_data()
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]['is_orders'])

    def test_vendor_type_filters_capacity_not_actual_capacity(self):
        db.session.add_all([
            Snapshot(supplier='Vendors', make='Discount', party_capacity_kg=2,
                     actual_capacity_kg=0),
            Snapshot(supplier='Vendors', make='Negative', party_capacity_kg=-1),
            Snapshot(supplier='Vendors', make='Non Discount', party_capacity_kg=0,
                     actual_capacity_kg=5),
        ])
        db.session.commit()
        for kind, names, capacity in [
            ('discount', ['Discount', 'Negative'], 1),
            ('non_discount', ['Non Discount'], 0),
            ('', ['Discount', 'Negative', 'Non Discount'], 1),
        ]:
            with self.app.test_request_context('/?supplier=Vendors&vendor_type=' + kind):
                rows, kpis = get_aggregated_capacity_data()
                self.assertEqual([m['make'] for m in rows[0]['makes']], names)
                self.assertEqual(kpis['total_capacity_kg'], capacity)
                detail = api_party_make_capacity_drilldown.__wrapped__().get_json()
                self.assertEqual(detail['total'], len(names))

    def test_rework_uses_correction_weight_and_weighted_supplier_total(self):
        db.session.add_all([
            Snapshot(supplier='Rework', make='A', process_pending_wt=80,
                     qc_issue_pending_wt=20, correction_wt=10),
            Snapshot(supplier='Rework', make='B', process_pending_wt=300,
                     correction_wt=90),
            Snapshot(supplier='Rework', make='Empty', correction_wt=None),
        ])
        db.session.commit()
        with self.app.test_request_context('/?supplier=Rework'):
            rows, kpis = get_aggregated_capacity_data()
            supplier = rows[0]
            makes = {m['make']: m for m in supplier['makes']}
            self.assertEqual(makes['A']['qc_rework_pct'], 10.0)
            self.assertEqual(makes['B']['qc_rework_pct'], 30.0)
            self.assertEqual(makes['Empty']['qc_rework_pct'], 0.0)
            self.assertEqual(supplier['qc_rework_pct'], 25.0)
            self.assertEqual(supplier['total_wt'], 400.0)
            self.assertEqual(supplier['qc_issue_pending_wt'], 20.0)
            self.assertEqual(kpis['total_qc_rework_kg'], 0.1)

    def test_actual_capacity_deduplicates_per_make_and_sums_supplier(self):
        db.session.add_all([
            Snapshot(supplier='Capacity', make='A', actual_capacity_kg=2.5),
            Snapshot(supplier='Capacity', make='A', actual_capacity_kg=2.5),
            Snapshot(supplier='Capacity', make='B', actual_capacity_kg=1.25),
            Snapshot(supplier='Capacity', make='Zero', actual_capacity_kg=0),
            Snapshot(supplier='Capacity', make='Missing'),
        ])
        db.session.commit()
        with self.app.test_request_context('/?sort_by=actual_capacity&sort_order=desc'):
            rows, _ = get_aggregated_capacity_data()
            self.assertEqual(rows[0]['supplier'], 'Capacity')
            self.assertEqual(rows[0]['actual_capacity'], 3.75)
            makes = {m['make']: m for m in rows[0]['makes']}
            self.assertEqual(makes['A']['actual_capacity'], 2.5)
            self.assertEqual(makes['Zero']['actual_capacity'], 0)
            self.assertIsNone(makes['Missing']['actual_capacity'])
            self.assertIsNone(rows[1]['actual_capacity'])

    def test_current_capacity_balance_deduplicates_and_uses_actual_capacity(self):
        db.session.add_all([
            Snapshot(supplier='Current', make='A', party_capacity_kg=99, current_capacity=5,
                     actual_capacity_kg=2, total_wt=1000, is_orders=True),
            Snapshot(supplier='Current', make='A', party_capacity_kg=99, current_capacity=5,
                     actual_capacity_kg=2, total_wt=500, is_orders=True),
            Snapshot(supplier='Current', make='B', party_capacity_kg=99, current_capacity=2,
                     actual_capacity_kg=4, total_wt=4000, is_orders=True),
        ])
        db.session.commit()
        with self.app.test_request_context('/?supplier=Current&sort_by=current_capacity&sort_order=desc'):
            rows, kpis = get_aggregated_capacity_data()
        supplier = rows[0]
        makes = {m['make']: m for m in supplier['makes']}
        self.assertEqual(makes['A']['current_capacity'], 5)
        self.assertEqual(makes['A']['diff'], -3)
        self.assertEqual(makes['B']['diff'], 2)
        self.assertEqual(supplier['current_capacity'], 7)
        self.assertEqual(supplier['actual_capacity'], 6)
        self.assertEqual(supplier['total_wt_in_kg'], 5.5)
        self.assertEqual(supplier['diff'], -1)
        self.assertEqual(kpis['net_diff_kg'], -1)
        self.assertEqual(kpis['total_current_capacity_kg'], 7)

    def test_export_places_current_capacity_before_pending_and_exports_new_balance(self):
        from app.dashboard.routes import party_make_capacity as report
        db.session.add(Snapshot(supplier='Export', make='A', current_capacity=6,
                                actual_capacity_kg=2, total_wt=123456, is_orders=True))
        db.session.commit()
        with self.app.test_request_context('/?supplier=Export'), patch.object(
            report, 'ensure_exports_dir'
        ), patch('openpyxl.workbook.workbook.Workbook.save', autospec=True) as save, patch.object(
            report, 'send_file', return_value='exported'
        ), patch.object(db.session, 'add'):
            self.assertEqual(report.api_party_make_capacity_export.__wrapped__(), 'exported')
        sheet = save.call_args.args[0].active
        headers = [c.value for c in sheet[1]]
        self.assertEqual(headers[4:7], ['Current Capacity (kg)', 'Total Pending (kg)', 'Balance (kg)'])
        self.assertEqual([sheet.cell(2, c).value for c in (5, 6, 7)], [6, 123.456, -4])
        self.assertEqual([sheet.cell(3, c).value for c in (5, 6, 7)], [6, 123.456, -4])


if __name__ == '__main__':
    unittest.main()
