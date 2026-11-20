import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class ProvisionStockStartupRetryTests(unittest.TestCase):
    def run_startup(self, stage=None, exhausted=False):
        session = MagicMock()
        connections = []
        attempts = 0

        def connect():
            nonlocal attempts
            attempts += 1
            fails = stage and (exhausted or attempts == 1)
            if fails and stage == 'connection':
                raise RuntimeError('source unavailable')
            connection = MagicMock()
            connections.append(connection)
            cursor = connection.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (42, 123.5)
            if fails and stage == 'count':
                cursor.fetchone.side_effect = RuntimeError('count failed')
            return connection

        if stage == 'staging':
            session.commit.side_effect = RuntimeError('staging failed') if exhausted else [RuntimeError('staging failed'), None]
        with patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'get_external_db_connection', side_effect=connect), \
             patch.object(sync, 'emit_sync_update') as emit, \
             patch.object(sync.time, 'sleep') as sleep:
            if exhausted:
                with self.assertRaisesRegex(RuntimeError, 'startup failed after 3 attempts'):
                    sync._prepare_provision_stock_sync()
            else:
                self.assertEqual(sync._prepare_provision_stock_sync(), (42, 123.5))
        for connection in connections:
            connection.close.assert_called_once()
        self.assertTrue(all(call.args[0] == 'processing' for call in emit.call_args_list))
        return attempts, session, emit, sleep

    def test_success_does_not_retry(self):
        attempts, session, _, sleep = self.run_startup()
        self.assertEqual(attempts, 1)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        sleep.assert_not_called()

    def test_startup_failures_reconnect_and_show_retry(self):
        for stage in ['connection', 'count', 'staging']:
            with self.subTest(stage=stage):
                attempts, session, emit, sleep = self.run_startup(stage)
                self.assertEqual(attempts, 2)
                session.rollback.assert_called_once()
                sleep.assert_called_once_with(5)
                self.assertTrue(any('retrying in 5s (Attempt 2/3)' in call.args[1] for call in emit.call_args_list))

    def test_exhaustion_is_bounded(self):
        for stage in ['connection', 'count', 'staging']:
            with self.subTest(stage=stage):
                attempts, session, _, sleep = self.run_startup(stage, exhausted=True)
                self.assertEqual(attempts, 3)
                self.assertEqual(session.rollback.call_count, 3)
                self.assertEqual(sleep.call_count, 2)
                session.bulk_insert_mappings.assert_not_called()

    def test_task_reports_final_error_without_starting_workers(self):
        session = MagicMock()
        with patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, '_prepare_provision_stock_sync', side_effect=RuntimeError('startup failed after 3 attempts')), \
             patch.object(sync, 'emit_sync_update') as emit, \
             patch('concurrent.futures.ThreadPoolExecutor') as executor:
            result = sync.sync_provision_stock_status_data_task()
        self.assertEqual(result['status'], 'error')
        self.assertIn('3 attempts', result['message'])
        self.assertEqual(emit.call_args.args[0], 'error')
        executor.assert_not_called()
