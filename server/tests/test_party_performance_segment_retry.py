import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg2

from app.utils import sync_tasks as sync


class PartyPerformanceBatchRetryTests(unittest.TestCase):
    def run_sync(self, fetch, fail_commit=False):
        session = MagicMock()
        if fail_commit:
            session.commit.side_effect = RuntimeError('local write failed')
        with patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'get_external_db_connection') as connect, \
             patch.object(sync, '_map_party_performance_rows', side_effect=lambda spec, rows, *args: rows), \
             patch.object(sync, 'emit_combined_sync_update') as emit, \
             patch.object(sync, 'redis_client') as redis, \
             patch.object(sync.time, 'sleep') as sleep:
            connections = []
            offsets = []

            def fresh_connection():
                connection = MagicMock()
                connections.append(connection)
                cursor = connection.cursor.return_value.__enter__.return_value

                def read():
                    query, (limit, offset) = cursor.execute.call_args.args
                    self.assertIn('LIMIT %s OFFSET %s', repr(query))
                    self.assertEqual(limit, 2000)
                    offsets.append(offset)
                    return fetch(offset, len(connections))

                cursor.fetchall.side_effect = read
                return connection

            connect.side_effect = fresh_connection
            result = sync.sync_party_performance_matrix_task()
            for connection in connections:
                connection.close.assert_called_once()
            return result, session, sleep, emit, redis, offsets

    def test_reconnect_retries_failed_offset_and_commits_all_snapshots_once(self):
        def fetch(offset, connection_number):
            if connection_number == 1:
                return [{'party': 'First page'}] * 2000
            if connection_number == 2:
                raise psycopg2.OperationalError('SSL connection closed')
            return [{'party': 'Last page'}] if offset else []

        result, session, sleep, _, _, offsets = self.run_sync(fetch)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['count'], 2001)
        self.assertEqual(len(result['counts']), 9)
        self.assertEqual(offsets, [0, 2000, 2000] + [0] * 8)
        self.assertEqual(session.bulk_insert_mappings.call_count, 2)
        self.assertEqual(session.query.call_count, 9)
        sleep.assert_called_once_with(5)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()

    def test_exhaustion_rolls_back_previously_loaded_batches(self):
        def fetch(offset, connection_number):
            if connection_number == 1:
                return [{'party': 'First page'}] * 2000
            raise psycopg2.OperationalError('source unavailable')

        result, session, sleep, emit, redis, offsets = self.run_sync(fetch)
        self.assertEqual(result['status'], 'error')
        self.assertIn('offset 2000', result['message'])
        self.assertEqual(offsets, [0, 2000, 2000, 2000])
        self.assertEqual(sleep.call_count, 2)
        session.bulk_insert_mappings.assert_called_once()
        session.commit.assert_not_called()
        session.rollback.assert_called_once()
        redis.flushdb.assert_not_called()
        self.assertEqual(emit.call_args.args[0], 'error')

    def test_each_batch_has_its_own_retry_budget(self):
        def fetch(offset, connection_number):
            if connection_number % 3:
                raise psycopg2.OperationalError('temporary disconnect')
            return []

        result, session, sleep, _, _, offsets = self.run_sync(fetch)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(offsets, [0] * 27)
        self.assertEqual(sleep.call_count, 18)

    def test_local_write_failure_rolls_back_without_refetch(self):
        result, session, sleep, _, redis, offsets = self.run_sync(
            lambda offset, connection_number: [], fail_commit=True)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(offsets, [0] * 9)
        session.rollback.assert_called_once()
        sleep.assert_not_called()
        redis.flushdb.assert_not_called()
