import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class QCDelayedSyncTests(unittest.TestCase):
    def run_sync(self, pages):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.side_effect = pages
        session = MagicMock()
        session.execute.return_value.scalar_one.return_value = date(2026, 11, 19)
        with patch.object(sync, 'get_external_db_connection', return_value=connection), \
             patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'emit_sync_update'):
            result = sync.sync_qc_delayed_data_task()
        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        self.assertEqual(connection.cursor.call_args.kwargs['name'], 'qc_delayed_sync')
        connection.close.assert_called_once()
        cursor.fetchall.assert_not_called()
        for fetch in cursor.fetchmany.call_args_list:
            self.assertEqual(fetch.args, (30_000,))
        return result, session

    def test_full_and_partial_batches_preserve_source_values(self):
        row = {'order_id': 42, 'office': 'RO1', 'make_owner': None,
               'collection_owner': 'Owner', 'collection': 'Collection', 'supplier': 'Supplier',
               'pieces': 1, 'weight': None, 'qc_completion_status': 'Pending', 'qc_request_no': 'QC1',
               'qc_date': date(2026, 11, 1), 'qc_received_delivery_challan': 'DC1',
               'receipt_no': 'Receipt1', 'qc_received_on': date(2026, 11, 2), 'cancelled_on': None}
        result, session = self.run_sync([[row] * 30_000, [row], []])
        self.assertEqual(result, {'status': 'success', 'count': 30_001})
        batches = session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(batch.args[1]) for batch in batches], [30_000, 1])
        expected = dict(row, snapshot_date=date.today())
        expected.pop('cancelled_on')
        self.assertEqual(batches[1].args, (sync.QCDelayedSnapshot, [expected]))
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.add_all.assert_not_called()

    def test_fetch_failure_rolls_back_loaded_batches(self):
        result, session = self.run_sync([[{'order_id': 42}], RuntimeError('source disconnected')])
        self.assertEqual(result['status'], 'error')
        session.bulk_insert_mappings.assert_called_once()
        session.commit.assert_not_called()
        session.rollback.assert_called_once()

    def test_first_fetch_failure_preserves_snapshot(self):
        result, session = self.run_sync([RuntimeError('first fetch failed')])
        self.assertEqual(result['status'], 'error')
        session.query.assert_not_called()
        session.rollback.assert_called_once()

    def test_empty_source_replaces_snapshot(self):
        result, session = self.run_sync([[]])
        self.assertEqual(result, {'status': 'success', 'count': 0})
        session.query.return_value.delete.assert_called_once_with(synchronize_session=False)
        session.bulk_insert_mappings.assert_not_called()
        session.commit.assert_called_once()
