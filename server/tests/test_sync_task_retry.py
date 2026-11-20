import ast
import json
from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch, call

from app.utils import sync_tasks as sync

TASKS = {
    'process_delay': 'process_level_delay',
    'outstanding_po': 'outstanding_purchase_order',
    'stage_delay': 'stage_level_delay',
    'order_delay_tracking': 'order_delay_tracking',
    'pending_acceptance': 'pending_acceptance',
    'rejected_weight': 'rejected_weight',
    'hallmarking_delayed': 'hallmarking_delayed',
}

class StopWorker(BaseException):
    pass

class SyncTaskRetryTests(unittest.TestCase):
    def test_retries_returned_and_raised_failures_then_stops_on_success(self):
        session = MagicMock()
        task = MagicMock(side_effect=[{'status': 'error', 'message': 'failed'}, RuntimeError('disconnected'), {'status': 'success', 'count': 4}])
        with patch.object(sync, 'db', SimpleNamespace(session=session)), patch.object(sync, 'emit_sync_update') as emit, patch.object(sync.time, 'sleep') as sleep:
            result = sync.run_sync_with_retry(task, 'stage_delay')
        self.assertEqual(result, {'status': 'success', 'count': 4})
        self.assertEqual(task.call_count, 3)
        self.assertEqual(session.rollback.call_count, 2)
        self.assertEqual(sleep.call_args_list, [call(5)] * 2)
        self.assertTrue(all(c.args[0] == 'processing' for c in emit.call_args_list))
        self.assertIsNone(sync._retrying_sync_type.get())

    def test_only_exhaustion_publishes_terminal_failure(self):
        session = MagicMock()
        def fail():
            sync.emit_sync_update('error', 'source unavailable', 0, 'pending_acceptance')
            return {'status': 'error', 'message': 'source unavailable'}
        with patch.object(sync, 'db', SimpleNamespace(session=session)), patch.object(sync, 'socketio') as socket, patch.object(sync, 'redis_client') as redis, patch.object(sync.time, 'sleep') as sleep:
            result = sync.run_sync_with_retry(fail, 'pending_acceptance')
        self.assertEqual(result['status'], 'error')
        self.assertIn('3 attempts', result['message'])
        statuses = [c.args[1]['status'] for c in socket.emit.call_args_list]
        self.assertEqual(statuses.count('error'), 1)
        self.assertEqual(statuses[-1], 'error')
        notifications = [json.loads(c.args[1]) for c in redis.publish.call_args_list if c.args[0] == 'global_notifications']
        self.assertEqual(len(notifications), 1)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(session.rollback.call_count, 3)
        self.assertIsNone(sync._retrying_sync_type.get())

    def test_success_never_retries(self):
        task = MagicMock(return_value={'status': 'success'})
        with patch.object(sync.time, 'sleep') as sleep:
            self.assertEqual(sync.run_sync_with_retry(task, 'process_delay'), {'status': 'success'})
        task.assert_called_once()
        sleep.assert_not_called()

    def test_worker_uses_retries_and_advances_batch_once_for_each_task(self):
        worker = Path(__file__).resolve().parents[2] / 'sync-consumer/main.py'
        tree = ast.parse(worker.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'process_sync_queue')
        for task_type, name in TASKS.items():
            with self.subTest(task_type=task_type):
                task = MagicMock()
                retry = MagicMock(return_value={'status': 'success', 'count': 1})
                advance = MagicMock()
                queue = MagicMock()
                data = {'type': task_type, 'scheduled_all_batch': True, 'user_id': 'SCHEDULER'}
                queue.blpop.side_effect = [('sync_queue', json.dumps(data)), StopWorker()]
                scope = dict(logger=MagicMock(), queue_redis_client=queue, json=json,
                             flask_app=SimpleNamespace(app_context=nullcontext), time=SimpleNamespace(time=lambda: 0, sleep=lambda _: None),
                             run_sync_with_retry=retry, enqueue_next_scheduled_all_task=advance)
                scope[f'sync_{name}_data_task'] = task
                exec(compile(ast.Module(body=[function], type_ignores=[]), str(worker), 'exec'), scope)
                with patch('app.models.core.SyncLog', return_value=SimpleNamespace()), patch('app.extensions.db', SimpleNamespace(session=MagicMock())):
                    with self.assertRaises(StopWorker): scope['process_sync_queue']()
                retry.assert_called_once_with(task, task_type)
                advance.assert_called_once_with(data)
