import ast
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.utils import sync_manager as manager

WORKER = Path(__file__).resolve().parents[2] / 'sync-consumer/main.py'


class StopWorker(BaseException):
    pass


class ScheduledSyncBatchTests(unittest.TestCase):
    def test_early_batch_enqueues_one_task_at_a_time_in_order(self):
        expected = ['owner_showroom_combined', 'party_make_capacity_details',
                    'party_performance_matrix', 'sales_stock_composition_analysis']
        with patch.object(manager, 'redis_client') as redis:
            self.assertEqual(manager.enqueue_scheduled_early_sync()['status'], 'success')
            for index, task in enumerate(expected):
                self.assertEqual(redis.rpush.call_count, index + 1)
                key, raw = redis.rpush.call_args.args
                data = json.loads(raw)
                self.assertEqual(key, 'sync_queue')
                self.assertEqual(data['type'], task)
                self.assertEqual(data['batch_index'], index)
                self.assertEqual(data['batch_total'], 4)
                self.assertEqual(data['batch_tasks'], expected)
                self.assertEqual(data['batch_schedule'], '03:00')
                self.assertEqual(data['user_id'], 'SCHEDULER')
                self.assertTrue(data['scheduled_all_batch'])
                manager.enqueue_next_scheduled_all_task(data)
            self.assertEqual(redis.rpush.call_count, 4)

    def test_morning_batch_excludes_heavy_and_combined_subtasks(self):
        self.assertEqual(len(manager.SCHEDULED_ALL_SYNC_TASKS), 25)
        excluded = set(manager.SCHEDULED_EARLY_SYNC_TASKS) | {
            'party_design_average_delivery_days', 'party_order_accept_cancel_delivery'}
        self.assertFalse(set(manager.SCHEDULED_ALL_SYNC_TASKS) & excluded)
        self.assertTrue(set(manager.SCHEDULED_EARLY_SYNC_TASKS) <= manager.ALLOWED_SYNC_TASKS)
        with patch.object(manager, 'redis_client') as redis:
            manager.enqueue_scheduled_all_sync()
            data = json.loads(redis.rpush.call_args.args[1])
            self.assertEqual(data['type'], 'process_delay')
            self.assertEqual(data['batch_total'], 25)
            self.assertEqual(data['batch_schedule'], '07:30')

    def test_pending_legacy_batch_preserves_original_sequence(self):
        old = dict(type='owner_showroom_combined', batch_id='legacy', batch_index=0,
                   batch_total=28, scheduled_all_batch=True)
        with patch.object(manager, 'redis_client') as redis:
            manager.enqueue_next_scheduled_all_task(old)
            data = json.loads(redis.rpush.call_args.args[1])
        self.assertEqual(data['type'], 'process_delay')
        self.assertEqual(data['batch_total'], 28)
        self.assertEqual(data['batch_tasks'], list(manager.LEGACY_SCHEDULED_ALL_SYNC_TASKS))

    def test_queued_task_list_survives_later_configuration_changes(self):
        with patch.object(manager, 'redis_client') as redis:
            manager.enqueue_scheduled_early_sync()
            data = json.loads(redis.rpush.call_args.args[1])
            with patch.object(manager, 'SCHEDULED_EARLY_SYNC_TASKS', ('different',)):
                manager.enqueue_next_scheduled_all_task(data)
            next_data = json.loads(redis.rpush.call_args.args[1])
        self.assertEqual(next_data['type'], 'party_make_capacity_details')

    def test_schedule_has_3am_batch_and_only_customer_jobs_at_530(self):
        tree = ast.parse(WORKER.read_text())
        setup = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'setup_scheduler')
        scheduler = MagicMock()
        scope = dict(BackgroundScheduler=MagicMock(return_value=scheduler),
                     enqueue_sync_task=MagicMock(), enqueue_scheduled_all_sync=MagicMock(),
                     enqueue_scheduled_early_sync=MagicMock(), logger=MagicMock())
        exec(compile(ast.Module(body=[setup], type_ignores=[]), str(WORKER), 'exec'), scope)
        scope['setup_scheduler']()
        jobs = [c.kwargs for c in scheduler.add_job.call_args_list]
        early = [j for j in jobs if j['hour'] == 3]
        self.assertEqual(len(early), 1)
        self.assertEqual(early[0]['minute'], 0)
        self.assertIs(early[0]['func'], scope['enqueue_scheduled_early_sync'])
        self.assertFalse(any(j['hour'] == 4 for j in jobs))
        customers = [j for j in jobs if j['hour'] == 5 and j['minute'] == 30]
        self.assertEqual({j['args'][0] for j in customers},
                         {'customer_order_analysis', 'customer_order_approval_pending'})
        self.assertEqual(len(customers), 2)
        direct = {j['args'][0] for j in jobs if j.get('args')}
        self.assertFalse(direct & set(manager.SCHEDULED_EARLY_SYNC_TASKS))
        self.assertFalse(direct & {'party_design_average_delivery_days', 'party_order_accept_cancel_delivery'})
        self.assertTrue(any(j['hour'] == 7 and j['minute'] == 30 for j in jobs))
        scheduler.start.assert_called_once()

    def test_worker_advances_early_batch_after_success_returned_error_and_exception(self):
        tree = ast.parse(WORKER.read_text())
        worker = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'process_sync_queue')
        for outcome in ({'status': 'success'}, {'status': 'error'}, RuntimeError('failed')):
            data = dict(type='party_make_capacity_details', scheduled_all_batch=True,
                        batch_id='early', batch_index=1, batch_schedule='03:00',
                        batch_tasks=list(manager.SCHEDULED_EARLY_SYNC_TASKS))
            queue = MagicMock()
            queue.blpop.side_effect = [('sync_queue', json.dumps(data)), StopWorker()]
            task = MagicMock()
            if isinstance(outcome, Exception):
                task.side_effect = outcome
            else:
                task.return_value = outcome
            advance = MagicMock()
            scope = dict(logger=MagicMock(), queue_redis_client=queue, json=json,
                         flask_app=SimpleNamespace(app_context=nullcontext),
                         time=SimpleNamespace(time=lambda: 0, sleep=lambda _: None),
                         sync_party_make_capacity_details_task=task,
                         enqueue_next_scheduled_all_task=advance)
            exec(compile(ast.Module(body=[worker], type_ignores=[]), str(WORKER), 'exec'), scope)
            with patch('app.models.core.SyncLog', return_value=SimpleNamespace()), patch(
                'app.extensions.db', SimpleNamespace(session=MagicMock())
            ):
                with self.assertRaises(StopWorker):
                    scope['process_sync_queue']()
            advance.assert_called_once_with(data)


if __name__ == '__main__':
    unittest.main()
