import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class OutstandingPOSyncTests(unittest.TestCase):
    def run_sync(self, pages):
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchmany.side_effect = pages
        session = MagicMock()
        with patch.object(sync, 'get_external_db_connection', return_value=connection), \
             patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'emit_sync_update'):
            result = sync.sync_outstanding_purchase_order_data_task()
        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        connection.close.assert_called_once()
        self.assertEqual(connection.cursor.call_args.kwargs['name'], 'outstanding_po_sync')
        cursor.fetchall.assert_not_called()
        for fetch in cursor.fetchmany.call_args_list:
            self.assertEqual(fetch.args, (30_000,))
        return result, session

    def test_full_and_partial_batches_commit_once(self):
        row = {'party': 'Supplier', 'order_number': 'PO1', 'order_pieces': 2, 'order_weight': None}
        result, session = self.run_sync([[row] * 30_000, [row], []])
        self.assertEqual(result, {'status': 'success', 'count': 30_001})
        batches = session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(batch.args[1]) for batch in batches], [30_000, 1])
        self.assertEqual(batches[1].args, (sync.OutstandingPurchaseOrderStatusSnapshot, [row]))
        session.query.return_value.delete.assert_called_once_with(synchronize_session=False)
        session.add_all.assert_not_called()
        session.commit.assert_called_once()
        session.rollback.assert_not_called()

    def test_mid_fetch_failure_rolls_back_loaded_batches(self):
        result, session = self.run_sync([[{'party': 'Supplier'}], RuntimeError('source disconnected')])
        self.assertEqual(result['status'], 'error')
        self.assertIn('source disconnected', result['message'])
        session.bulk_insert_mappings.assert_called_once()
        session.commit.assert_not_called()
        session.rollback.assert_called_once()

    def test_first_fetch_failure_preserves_existing_snapshot(self):
        result, session = self.run_sync([RuntimeError('first fetch failed')])
        self.assertEqual(result['status'], 'error')
        session.query.assert_not_called()
        session.bulk_insert_mappings.assert_not_called()
        session.commit.assert_not_called()
        session.rollback.assert_called_once()

    def test_empty_source_replaces_snapshot_with_zero_rows(self):
        result, session = self.run_sync([[]])
        self.assertEqual(result, {'status': 'success', 'count': 0})
        session.query.return_value.delete.assert_called_once_with(synchronize_session=False)
        session.bulk_insert_mappings.assert_not_called()
        session.commit.assert_called_once()
