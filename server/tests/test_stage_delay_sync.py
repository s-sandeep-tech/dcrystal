import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class StageDelaySyncTests(unittest.TestCase):
    def run_sync(self, pages):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.side_effect = pages
        session = MagicMock()
        session.execute.return_value.scalar_one.return_value = date(2026, 11, 19)
        with patch.object(sync, 'get_external_db_connection', return_value=connection), \
             patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'emit_sync_update'):
            result = sync.sync_stage_level_delay_data_task()
        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        self.assertEqual(connection.cursor.call_args.kwargs['name'], 'stage_delay_sync')
        connection.close.assert_called_once()
        cursor.fetchall.assert_not_called()
        for fetch in cursor.fetchmany.call_args_list:
            self.assertEqual(fetch.args, (30_000,))
        return result, session

    def test_batched_mapping_preserves_stage_windows_and_date(self):
        first = {'order_ro': 'RO1', 'order_no': 'PO1', 'barcode': 'BC1', 'party_name': 'Supplier',
                 'completed_date': date(2026, 11, 1), 'pending_window': '1-2'}
        windows = ['1-2', '3-4', '5-10', '10+', '0', None]
        result, session = self.run_sync([[first] * 30_000,
                                        [{**first, 'pending_window': window} for window in windows], []])
        self.assertEqual(result, {'status': 'success', 'count': 30_006})
        batches = session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(batch.args[1]) for batch in batches], [30_000, 6])
        for index, record in enumerate(batches[1].args[1]):
            self.assertEqual(record['purchase_ro'], 'RO1')
            self.assertEqual(record['order_number'], 'PO1')
            self.assertEqual(record['barcode_number'], 'BC1')
            self.assertEqual(record['party'], 'Supplier')
            self.assertEqual(record['snapshot_date'], date(2026, 11, 19))
            self.assertEqual([record[name] for name in ('time_window_1_2_days', 'time_window_3_4_days',
                                                       'time_window_5_10_days', 'time_window_more_than_10_days')],
                             [int(index == window) for window in range(4)])
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.add_all.assert_not_called()

    def test_failure_after_first_batch_rolls_back(self):
        result, session = self.run_sync([[{'pending_window': '10+'}], RuntimeError('connection lost')])
        self.assertEqual(result['status'], 'error')
        session.bulk_insert_mappings.assert_called_once()
        session.commit.assert_not_called()
        session.rollback.assert_called_once()

    def test_first_fetch_failure_keeps_snapshot(self):
        result, session = self.run_sync([RuntimeError('query failed')])
        self.assertEqual(result['status'], 'error')
        session.query.assert_not_called()
        session.rollback.assert_called_once()

    def test_empty_result_commits_empty_snapshot(self):
        result, session = self.run_sync([[]])
        self.assertEqual(result, {'status': 'success', 'count': 0})
        session.query.return_value.delete.assert_called_once_with(synchronize_session=False)
        session.bulk_insert_mappings.assert_not_called()
        session.commit.assert_called_once()
