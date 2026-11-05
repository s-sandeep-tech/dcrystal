import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from contextlib import ExitStack

from app.utils import sync_tasks as sync


class OwnerShowroomRetryTests(unittest.TestCase):
    def run_sync(self, results):
        names = ['sync_pending_order_details_task', 'sync_active_order_details_task',
                 'sync_owner_wise_data_task', 'sync_showroom_wise_order_summary_task']
        with ExitStack() as stack:
            tasks = [stack.enter_context(patch.object(sync, name, side_effect=result))
                     for name, result in zip(names, results)]
            emit = stack.enter_context(patch.object(sync, 'emit_sync_update'))
            sleep = stack.enter_context(patch.object(sync.time, 'sleep'))
            redis = stack.enter_context(patch.object(sync, 'redis_client'))
            session = MagicMock()
            stack.enter_context(patch.object(sync, 'db', SimpleNamespace(session=session)))
            result = sync.sync_owner_and_showroom_wise_task()
            return result, tasks, sleep, emit, redis, session

    def test_failed_segment_only_retried(self):
        ok = {'status': 'success', 'count': 5}
        result, tasks, sleep, emit, redis, session = self.run_sync(
            [[ok], [{'status': 'error', 'message': 'SSL closed'}, ok], [ok], [ok]])
        self.assertEqual(result['status'], 'success')
        self.assertEqual([task.call_count for task in tasks], [1, 2, 1, 1])
        sleep.assert_called_once_with(5)
        self.assertEqual(result['active_count'], 5)
        tasks[1].assert_called_with(task_type_override='owner_showroom_combined',
                                    progress_range=(25, 45), is_subtask=True)
        redis.flushdb.assert_called_once()

    def test_exhausted_segment_stops_without_restarting_previous(self):
        result, tasks, sleep, emit, redis, session = self.run_sync([
            [{'status': 'success'}], [None, None, None], [], []])
        self.assertEqual(result['status'], 'error')
        self.assertIn('Active Orders failed after 3 attempts', result['message'])
        self.assertEqual([task.call_count for task in tasks], [1, 3, 0, 0])
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(emit.call_args.args[0], 'error')

    def test_every_segment_gets_its_own_attempts(self):
        results = [[{'status': 'error'}, RuntimeError('disconnected'),
                    {'status': 'success', 'count': index}] for index in range(4)]
        result, tasks, sleep, emit, redis, session = self.run_sync(results)
        self.assertEqual(result['status'], 'success')
        self.assertEqual([task.call_count for task in tasks], [3, 3, 3, 3])
        self.assertEqual(sleep.call_count, 8)
        self.assertEqual(session.rollback.call_count, 4)
