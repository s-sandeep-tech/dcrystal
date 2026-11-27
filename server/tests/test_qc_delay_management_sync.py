import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class QCDelayManagementSyncTests(unittest.TestCase):
    def connection(self, pages):
        connection = MagicMock()
        cursors = []

        def cursor(**kwargs):
            context = MagicMock()
            current = context.__enter__.return_value
            if 'name' in kwargs:
                current.fetchmany.side_effect = pages[len(cursors)]
                cursors.append(current)
            return context

        connection.cursor.side_effect = cursor
        return connection, cursors

    def run_sync(self, connections):
        session = MagicMock()
        with patch.object(sync, 'get_external_db_connection', side_effect=connections), \
             patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'emit_sync_update'), patch.object(sync.time, 'sleep') as sleep:
            result = sync.sync_qc_delay_management_data_task()
        for connection in connections:
            connection.close.assert_called_once()
            connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        return result, session, sleep

    def test_all_four_views_use_bounded_batches_and_commit_each_stage(self):
        rows = [tuple(range(size)) for size in (28, 34, 37, 37)]
        connection, cursors = self.connection([[[row] * 30_000, [row], []] for row in rows])
        result, session, _ = self.run_sync([connection])
        self.assertEqual(result['status'], 'success')
        batches = session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(batch.args[1]) for batch in batches], [30_000, 1] * 4)
        models = [sync.QCDelayManagementSnapshot, sync.SupplierQCIssueReceiptPendingSnapshot,
                  sync.QCReceiptCompletedQCPendingSnapshot, sync.QCCompletedInvoiceRequestPendingSnapshot]
        for index, model in enumerate(models):
            self.assertIs(batches[index * 2].args[0], model)
        self.assertEqual(batches[0].args[1][0]['qc_completed_date'], 27)
        self.assertEqual(batches[2].args[1][0]['make_owner_emp_code'], 1)
        self.assertEqual(batches[4].args[1][0]['weight'], 35)
        self.assertEqual(batches[4].args[1][0]['piece'], 1)
        self.assertEqual(batches[6].args[1][0]['qc_completed_date'], 33)
        dates = {batch.args[1][0]['snapshot_date'] for batch in batches}
        self.assertEqual(len(dates), 1)
        for cursor in cursors:
            cursor.fetchall.assert_not_called()
            self.assertTrue(all(call.args == (30_000,) for call in cursor.fetchmany.call_args_list))
        self.assertEqual(session.commit.call_count, 4)
        session.rollback.assert_not_called()
        session.bulk_save_objects.assert_not_called()

    def test_last_segment_failure_rolls_back_and_retries_only_that_segment(self):
        first, _ = self.connection([[[tuple(range(size))], []] for size in (28, 34, 37)]
                                   + [[RuntimeError('source disconnected')]])
        second, cursors = self.connection([[[]]])
        result, session, sleep = self.run_sync([first, second])
        self.assertEqual(result['status'], 'success')
        session.rollback.assert_called_once()
        self.assertEqual(session.commit.call_count, 4)
        sleep.assert_called_once_with(5)
        self.assertEqual(session.query.return_value.delete.call_count, 4)
        self.assertEqual(len(cursors), 1)
        self.assertIn('FROM ext_view.vw_qc_completed_invoice_request_pending', cursors[0].execute.call_args.args[0])

    def test_exhausted_retries_never_commit(self):
        connections = [self.connection([[RuntimeError('source unavailable')]])[0] for _ in range(5)]
        result, session, sleep = self.run_sync(connections)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(session.rollback.call_count, 5)
        session.commit.assert_not_called()
        session.bulk_insert_mappings.assert_not_called()
        self.assertEqual(sleep.call_count, 4)
