import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class OrderDelayTrackingSyncTests(unittest.TestCase):
    def run_sync(self, pages):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.side_effect = pages
        session = MagicMock()
        session.execute.return_value.scalar_one.return_value = date(2026, 11, 19)
        with patch.object(sync, 'get_external_db_connection', return_value=connection), \
             patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'emit_sync_update'):
            result = sync.sync_order_delay_tracking_data_task()
        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        self.assertEqual(connection.cursor.call_args.kwargs['name'], 'order_delay_tracking_sync')
        connection.close.assert_called_once()
        cursor.fetchall.assert_not_called()
        for fetch in cursor.fetchmany.call_args_list:
            self.assertEqual(fetch.args, (30_000,))
        return result, session

    def test_full_and_partial_batches_preserve_delay_mapping(self):
        row = {'production_1_2_delay': 1, 'production_3_4_delay': 0, 'production_5_10_delay': 0,
               'production_gt_10_delay': 0, 'production_delay_days': 2, 'qc_1_2_delay': None,
               'qc_3_4_delay': 0, 'qc_5_10_delay': 1, 'qc_gt_10_delay': 0, 'qc_delay_days': 5,
               'order_id': 12, 'po_id': 34, 'po_number': 'PO34', 'supplier': 'Supplier'}
        result, session = self.run_sync([[row] * 30_000, [row], []])
        self.assertEqual(result, {'status': 'success', 'count': 30_001})
        batches = session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(batch.args[1]) for batch in batches], [30_000, 1])
        record = batches[1].args[1][0]
        self.assertEqual([record[name] for name in ('delay_1_2_days', 'delay_3_4_days',
                         'delay_5_10_days', 'delay_more_than_10_days', 'delay_days')], [1, 0, 0, 0, 2])
        self.assertEqual([record[name] for name in ('qc_delay_1_2_days', 'qc_delay_3_4_days',
                         'qc_delay_5_10_days', 'qc_delay_more_than_10_days', 'qc_delay_days')], [None, 0, 1, 0, 5])
        self.assertEqual(record['order_id'], 12)
        self.assertEqual(record['snapshot_date'], date(2026, 11, 19))
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.add_all.assert_not_called()

    def test_fetch_failure_rolls_back_loaded_batches(self):
        result, session = self.run_sync([[{'order_id': 1}], RuntimeError('source disconnected')])
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
