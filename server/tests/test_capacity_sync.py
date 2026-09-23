import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks


class CapacitySyncTests(unittest.TestCase):
    def setUp(self):
        sleeper = patch.object(sync_tasks.time, 'sleep')
        sleeper.start()
        self.addCleanup(sleeper.stop)
        self.connection = MagicMock()
        model = MagicMock()
        model.__table__ = MagicMock()
        for name, value in [
            ('get_external_db_connection', MagicMock(return_value=self.connection)),
            ('db', MagicMock()),
            ('PartyMakeCapacityDetailsSnapshot', model),
            ('emit_combined_sync_update', MagicMock()),
        ]:
            patcher = patch.object(sync_tasks, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_fetches_maps_and_commits_actual_rows(self):
        self.connection.cursor.return_value.fetchall.return_value = [{
            'supplier': ' Supplier ', 'make': 'Make', 'group': 'Gold',
            'party_capacity_kg': '2.5', 'receipt_pending_wt': '12.345',
            'process_pending_pcs': '4', 'is_msme': False,
            'actual_capacity_kg': Decimal('123456789012.345'),
            'correction_pcs': 9223372036854775807,
            'make_owner': ' Owner A ', 'collection_owner': 'Owner B',
            'make_owner_emp_code': ' 00123 ', 'collection_owner_emp_code': '00456',
            'correction_wt': Decimal('123456789012345.123456'),
            'is_orders': True,
            'order_type': 'x' * 250, 'order_request_type': 'y' * 250,
        }]
        result = sync_tasks.sync_party_make_capacity_details_task()
        self.assertEqual(result, {'status': 'success', 'count': 1})
        self.connection.cursor.return_value.execute.assert_any_call(
            'SELECT * FROM ext_view.vw_party_make_capacity_details')
        record = sync_tasks.db.session.bulk_insert_mappings.call_args.args[1][0]
        self.assertEqual(record['supplier'], 'Supplier')
        self.assertEqual(record['group_name'], 'Gold')
        self.assertEqual(record['party_capacity_kg'], 2.5)
        self.assertEqual(record['receipt_pending_wt'], Decimal('12.345'))
        self.assertEqual(record['actual_capacity_kg'], Decimal('123456789012.345'))
        self.assertEqual(record['correction_pcs'], 9223372036854775807)
        self.assertIsInstance(record['correction_pcs'], int)
        self.assertEqual(record['make_owner'], 'Owner A')
        self.assertEqual(record['collection_owner'], 'Owner B')
        self.assertEqual(record['make_owner_emp_code'], '00123')
        self.assertEqual(record['collection_owner_emp_code'], '00456')
        self.assertEqual(record['correction_wt'], Decimal('123456789012345.123456'))
        self.assertIs(record['is_orders'], True)
        self.assertEqual(record['order_type'], 'x' * 250)
        self.assertEqual(record['order_request_type'], 'y' * 250)
        self.assertEqual(record['process_pending_pcs'], 4)
        sync_tasks.db.session.commit.assert_called_once()
        sync_tasks.db.session.rollback.assert_not_called()
        self.connection.close.assert_called_once()

    def test_source_failure_does_not_delete_snapshot(self):
        self.connection.cursor.return_value.execute.side_effect = RuntimeError('source unavailable')
        result = sync_tasks.sync_party_make_capacity_details_task()
        self.assertEqual(result['status'], 'error')
        sync_tasks.db.session.query.assert_not_called()
        sync_tasks.db.session.commit.assert_not_called()
        self.assertEqual(sync_tasks.db.session.rollback.call_count, 6)
        self.assertEqual(self.connection.close.call_count, 6)

    def test_new_fields_preserve_nulls_and_false(self):
        self.connection.cursor.return_value.fetchall.return_value = [
            {'supplier': 'A'}, {'supplier': 'B', 'is_orders': False}]
        result = sync_tasks.sync_party_make_capacity_details_task()
        self.assertEqual(result['status'], 'success')
        records = sync_tasks.db.session.bulk_insert_mappings.call_args.args[1]
        for field in ('actual_capacity_kg', 'correction_pcs', 'correction_wt', 'is_orders',
                      'make_owner', 'collection_owner', 'make_owner_emp_code', 'collection_owner_emp_code'):
            self.assertIsNone(records[0][field])
        self.assertIs(records[1]['is_orders'], False)

    def test_model_matches_source_numeric_and_text_types(self):
        from app.models.snapshots import PartyMakeCapacityDetailsSnapshot
        columns = PartyMakeCapacityDetailsSnapshot.__table__.c
        for name in ('party_capacity_kg', 'actual_capacity_kg'):
            self.assertEqual(columns[name].type.precision, 15)
            self.assertEqual(columns[name].type.scale, 3)
        for name in ('order_type', 'order_request_type'):
            self.assertEqual(columns[name].type.length, 250)
        from sqlalchemy import BigInteger
        self.assertIsInstance(columns['correction_pcs'].type, BigInteger)
        for name in ('make_owner', 'collection_owner'):
            self.assertEqual(columns[name].type.length, 250)
        for name in ('make_owner_emp_code', 'collection_owner_emp_code'):
            self.assertEqual(columns[name].type.length, 256)
        for name in ('correction_wt', 'total_wt',
                     'process_pending_wt', 'barcode_pending_wt', 'hallmark_pending_wt',
                     'qc_issue_pending_wt', 'qc_complete_pending_wt',
                     'invoice_pending_wt', 'receipt_pending_wt'):
            self.assertIsNone(columns[name].type.precision)
            self.assertIsNone(columns[name].type.scale)

    def test_insert_failure_rolls_back(self):
        self.connection.cursor.return_value.fetchall.return_value = [{'supplier': 'Supplier'}]
        sync_tasks.db.session.bulk_insert_mappings.side_effect = RuntimeError('insert failed')
        result = sync_tasks.sync_party_make_capacity_details_task()
        self.assertEqual(result['status'], 'error')
        sync_tasks.db.session.commit.assert_not_called()
        self.assertEqual(sync_tasks.db.session.rollback.call_count, 6)
        self.assertEqual(self.connection.close.call_count, 6)


if __name__ == '__main__':
    unittest.main()
