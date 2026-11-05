import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class PartyPerformanceSegmentRetryTests(unittest.TestCase):
    def run_sync(self, fetch, fail_commit=False):
        session = MagicMock()
        if fail_commit:
            session.commit.side_effect = RuntimeError('local write failed')
        with patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'get_external_db_connection') as connect, \
             patch.object(sync, '_fetch_party_performance_source', side_effect=fetch), \
             patch.object(sync, 'emit_combined_sync_update') as emit, \
             patch.object(sync, 'redis_client') as redis, \
             patch.object(sync.time, 'sleep') as sleep:
            connections = []
            def fresh_connection():
                connection = MagicMock()
                connections.append(connection)
                return connection
            connect.side_effect = fresh_connection
            result = sync.sync_party_performance_matrix_task()
            for connection in connections:
                connection.close.assert_called_once()
            return result, session, sleep, emit, redis, len(connections)

    def test_only_failed_segment_retried_with_new_connection(self):
        calls = []
        def fetch(cursor, spec):
            calls.append(spec['view'])
            if spec == sync.PARTY_PERFORMANCE_SYNC_SPECS[4] and calls.count(spec['view']) == 1:
                raise RuntimeError('SSL connection closed')
            return []
        result, session, sleep, emit, redis, connections = self.run_sync(fetch)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(connections, 10)
        self.assertEqual(calls.count(sync.PARTY_PERFORMANCE_SYNC_SPECS[0]['view']), 1)
        self.assertEqual(calls.count(sync.PARTY_PERFORMANCE_SYNC_SPECS[4]['view']), 2)
        sleep.assert_called_once_with(5)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()

    def test_exhaustion_preserves_snapshots_and_does_not_restart(self):
        calls = []
        def fetch(cursor, spec):
            calls.append(spec['view'])
            if spec == sync.PARTY_PERFORMANCE_SYNC_SPECS[1]:
                raise RuntimeError('source unavailable')
            return []
        result, session, sleep, emit, redis, connections = self.run_sync(fetch)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(connections, 4)
        self.assertEqual(calls.count(sync.PARTY_PERFORMANCE_SYNC_SPECS[0]['view']), 1)
        self.assertEqual(sleep.call_count, 2)
        session.query.assert_not_called()
        session.commit.assert_not_called()
        session.rollback.assert_called_once()
        redis.flushdb.assert_not_called()
        self.assertEqual(emit.call_args.args[0], 'error')

    def test_each_failed_segment_has_its_own_retry_budget(self):
        calls = {}
        def fetch(cursor, spec):
            key = spec['view']
            calls[key] = calls.get(key, 0) + 1
            if calls[key] < 3:
                raise RuntimeError('temporary disconnect')
            return []
        result, session, sleep, emit, redis, connections = self.run_sync(fetch)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(connections, 27)
        self.assertEqual(sleep.call_count, 18)

    def test_local_write_failure_rolls_back_without_refetch(self):
        result, session, sleep, emit, redis, connections = self.run_sync(
            lambda cursor, spec: [], fail_commit=True)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(connections, 9)
        session.rollback.assert_called_once()
        sleep.assert_not_called()
        redis.flushdb.assert_not_called()
