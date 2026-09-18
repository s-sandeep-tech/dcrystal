import unittest
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks


class CapacitySyncTests(unittest.TestCase):
    def setUp(self):
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
        }]
        result = sync_tasks.sync_party_make_capacity_details_task()
        self.assertEqual(result, {'status': 'success', 'count': 1})
        self.connection.cursor.return_value.execute.assert_any_call(
            'SELECT * FROM ext_view.vw_party_make_capacity_details')
        record = sync_tasks.db.session.bulk_insert_mappings.call_args.args[1][0]
        self.assertEqual(record['supplier'], 'Supplier')
        self.assertEqual(record['group_name'], 'Gold')
        self.assertEqual(record['party_capacity_kg'], 2.5)
        self.assertEqual(record['receipt_pending_wt'], 12.345)
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
        sync_tasks.db.session.rollback.assert_called_once()
        self.connection.close.assert_called_once()

    def test_insert_failure_rolls_back(self):
        self.connection.cursor.return_value.fetchall.return_value = [{'supplier': 'Supplier'}]
        sync_tasks.db.session.bulk_insert_mappings.side_effect = RuntimeError('insert failed')
        result = sync_tasks.sync_party_make_capacity_details_task()
        self.assertEqual(result['status'], 'error')
        sync_tasks.db.session.commit.assert_not_called()
        sync_tasks.db.session.rollback.assert_called_once()
        self.connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
