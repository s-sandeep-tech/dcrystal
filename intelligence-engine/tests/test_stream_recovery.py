"""Integration tests: opt in using isolated PostgreSQL/Redis test services."""
import os
import time
import unittest
from unittest.mock import patch
from uuid import uuid4


@unittest.skipUnless(os.getenv('INTELLIGENCE_INTEGRATION_TESTS') == '1', 'Requires isolated test services')
class StreamRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.connection import init_db
        init_db()

    def setUp(self):
        from src.task_queue.redis_manager import RedisManager
        from src.task_queue.protocol import TaskRequest, TaskType
        self.queue = RedisManager()
        prefix = 'test:' + uuid4().hex
        self.queue.queue_name = prefix
        self.queue.stream = prefix + ':stream'
        self.queue.dead_letter = prefix + ':dead'
        self.queue.result_prefix = prefix + ':result:'
        self.queue.lease_ms = 300
        self.task = TaskRequest(task_id=uuid4().hex, task_type=TaskType.PREDICT)
        self.calls = 0

    def tearDown(self):
        keys = list(self.queue.client.scan_iter(self.queue.queue_name + '*'))
        if keys:
            self.queue.client.delete(*keys)

    def execute(self, task):
        from src.db.writer import DatabaseWriter
        from src.task_queue.protocol import TaskResult, TaskStatus
        self.calls += 1
        DatabaseWriter.save_predictions(task.task_id, [{'entity_id': 'sample', 'predicted_value': 5}])
        return TaskResult(task_id=task.task_id, task_type=task.task_type,
                          status=TaskStatus.COMPLETED, result={'count': 1})

    def rows(self):
        from src.db.connection import get_db_session
        from src.db.models import IntelligencePrediction
        with get_db_session() as session:
            return session.query(IntelligencePrediction).filter_by(task_id=self.task.task_id).count()

    def submit(self):
        self.queue.push_task(self.task)
        return self.queue.pop_task(timeout=1)

    def runner(self, execute=None):
        from src.task_queue.runner import TaskRunner
        return TaskRunner(self.queue, execute or self.execute)

    def reclaim(self, delivery):
        # Simulate a worker dying without heartbeat/acknowledgement.
        self.queue.client.xclaim(self.queue.stream, self.queue.group, 'dead-worker', 0,
                                 [delivery.message_id], idle=1000, justid=True)
        return self.queue.pop_task(timeout=1)

    def test_commit_then_ack_and_duplicate_task_id(self):
        self.runner().process(self.submit())
        self.runner().process(self.submit())
        self.assertEqual(self.rows(), 1)
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.queue.client.xpending(self.queue.stream, self.queue.group)['pending'], 0)

    def test_crash_before_processing_is_recovered(self):
        original = self.submit()
        recovered = self.reclaim(original)
        self.assertEqual(recovered.message_id, original.message_id)
        self.assertEqual(recovered.attempts, 2)
        self.runner().process(recovered)
        self.assertEqual(self.rows(), 1)

    def test_crash_after_commit_replays_without_writing_again(self):
        delivery = self.submit()
        with patch.object(self.queue, 'save_task_result', side_effect=ConnectionError('Redis unavailable')):
            with self.assertRaises(ConnectionError):
                self.runner().process(delivery)
        self.assertEqual(self.rows(), 1)
        self.runner().process(self.reclaim(delivery))
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.rows(), 1)

    def test_failed_output_rolls_back_retries_then_dead_letters(self):
        def fail(task):
            self.execute(task)
            raise RuntimeError('output failed')

        delivery = self.submit()
        for attempt in range(1, self.queue.max_attempts + 1):
            self.runner(fail).process(delivery)
            self.assertEqual(self.rows(), 0)
            status = self.queue.get_task_result(self.task.task_id)['status']
            self.assertEqual(status, 'failed' if attempt == self.queue.max_attempts else 'retrying')
            if attempt < self.queue.max_attempts:
                delivery = self.reclaim(delivery)
        self.assertEqual(self.queue.client.xlen(self.queue.dead_letter), 1)
        self.assertEqual(self.queue.client.xpending(self.queue.stream, self.queue.group)['pending'], 0)

    def test_heartbeat_prevents_reclaim_and_does_not_increment_attempts(self):
        from copy import copy
        delivery = self.submit()
        second = copy(self.queue)
        second.consumer = 'second-worker'
        with self.queue.heartbeat(delivery):
            time.sleep(0.7)
            self.assertIsNone(second.pop_task(timeout=0))
        entry = self.queue.client.xpending_range(self.queue.stream, self.queue.group, '-', '+', 1)[0]
        self.assertEqual(entry['times_delivered'], 1)
        self.queue.acknowledge(delivery)

    def test_stale_worker_cannot_ack_or_renew(self):
        delivery = self.submit()
        self.queue.client.xclaim(self.queue.stream, self.queue.group, 'other', 0,
                                 [delivery.message_id], justid=True)
        self.assertFalse(self.queue.renew(delivery))
        with self.assertRaises(RuntimeError):
            self.queue.acknowledge(delivery)

    def test_legacy_and_invalid_payload_migration(self):
        self.queue.client.rpush(self.queue.queue_name, self.task.model_dump_json(), 'broken json')
        self.runner().process(self.queue.pop_task(timeout=1))
        self.runner().process(self.queue.pop_task(timeout=1))
        self.assertEqual(self.rows(), 1)
        self.assertEqual(self.queue.client.llen(self.queue.queue_name), 0)
        self.assertEqual(self.queue.client.xlen(self.queue.dead_letter), 1)

    def test_writer_exception_is_not_swallowed(self):
        from src.db.writer import DatabaseWriter
        with patch('src.db.writer.get_db_session', side_effect=RuntimeError('DB unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'DB unavailable'):
                DatabaseWriter.save_predictions(self.task.task_id, [{'entity_id': 'sample'}])

    def test_database_outage_leaves_task_pending_and_reports_retrying(self):
        delivery = self.submit()
        with patch('src.task_queue.runner.task_transaction', side_effect=RuntimeError('database offline')):
            with self.assertRaisesRegex(RuntimeError, 'database offline'):
                self.runner().process(delivery)
        self.assertEqual(self.queue.get_task_result(self.task.task_id)['status'], 'retrying')
        self.assertEqual(self.queue.client.xpending(self.queue.stream, self.queue.group)['pending'], 1)
        self.runner().process(self.reclaim(delivery))
        self.assertEqual(self.rows(), 1)

    def test_failed_task_result_never_marks_completed(self):
        from src.task_queue.protocol import TaskResult, TaskStatus

        def failed(task):
            return TaskResult(task_id=task.task_id, task_type=task.task_type,
                              status=TaskStatus.FAILED, error='training failed')

        self.queue.max_attempts = 1
        self.runner(failed).process(self.submit())
        self.assertEqual(self.queue.get_task_result(self.task.task_id)['status'], 'failed')
        self.assertEqual(self.rows(), 0)

    def test_commit_error_rolls_back_output_and_receipt(self):
        from sqlalchemy.orm import Session
        original = Session.commit
        commits = []

        def fail_first_commit(session):
            commits.append(1)
            if len(commits) == 1:
                raise RuntimeError('commit failed')
            return original(session)

        with patch.object(Session, 'commit', fail_first_commit):
            self.runner().process(self.submit())
        self.assertEqual(self.rows(), 0)
        self.assertEqual(self.queue.get_task_result(self.task.task_id)['status'], 'retrying')

    def test_lost_lease_rolls_back_output(self):
        def lose_lease(task):
            result = self.execute(task)
            self.queue.client.xclaim(self.queue.stream, self.queue.group, 'other-worker', 0,
                                     [delivery.message_id], justid=True)
            return result

        delivery = self.submit()
        with self.assertRaisesRegex(RuntimeError, 'lease lost'):
            self.runner(lose_lease).process(delivery)
        self.assertEqual(self.rows(), 0)

    def test_database_lock_prevents_overlapping_duplicate(self):
        from src.db.connection import get_db_session
        from src.task_queue.runner import lock_task
        delivery = self.submit()
        with get_db_session() as session:
            lock_task(session, self.task.task_id)
            self.runner().process(delivery)
            self.assertEqual(self.calls, 0)
        self.runner().process(self.reclaim(delivery))
        self.assertEqual(self.calls, 1)


if __name__ == '__main__':
    unittest.main()
