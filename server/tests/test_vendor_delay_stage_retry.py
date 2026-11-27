from collections import Counter
import re
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


VIEWS = (
    'vw_party_summary', 'vw_invited_order_details', 'vw_process_pending_order_details',
    'vw_barcode_pending_order_details', 'vw_barcode_completed_bis_request_delay',
    'vw_bis_request_completed_hm_issue_delay', 'vw_hm_return_received_qc_issue_pending',
    'vw_invoice_generated_invoice_approve_delay', 'vw_invoice_approved_not_synched_delay',
)


class VendorDelayStageRetryTests(unittest.TestCase):
    def run_sync(self, failures=None, fail_write=False):
        counts = Counter()
        connections = []
        session = MagicMock()

        def connect():
            connection = MagicMock()
            connections.append(connection)
            cursor = connection.cursor.return_value
            cursor.fetchall.return_value = []

            def execute(sql):
                view = re.search(r'FROM ext_view\.(\w+)', sql).group(1)
                counts[view] += 1
                if counts[view] <= (failures or {}).get(view, 0):
                    raise RuntimeError('source connection closed')

            cursor.execute.side_effect = execute
            return connection

        if fail_write:
            attempts = Counter()

            def write(sql):
                table = str(sql).split()[-1]
                attempts[table] += 1
                if table == 'party_barcode_pending_snapshots' and attempts[table] == 1:
                    raise RuntimeError('local database write failed')

            session.execute.side_effect = write

        with patch.object(sync, 'get_external_db_connection', side_effect=connect), patch.object(
            sync, 'db', SimpleNamespace(session=session)
        ), patch.object(sync, 'emit_sync_update') as emit, patch.object(sync.time, 'sleep') as sleep:
            result = sync.sync_party_delay_management_data_task()
        for connection in connections:
            connection.close.assert_called_once()
        return result, counts, session, emit, sleep, connections

    def test_midstage_source_failure_retries_only_failed_stage(self):
        result, counts, session, emit, sleep, connections = self.run_sync({VIEWS[3]: 2})
        self.assertEqual(result['status'], 'success')
        self.assertEqual(counts, Counter({v: 3 if v == VIEWS[3] else 1 for v in VIEWS}))
        self.assertEqual(session.commit.call_count, 9)
        self.assertEqual(session.rollback.call_count, 2)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(len(connections), 3)
        messages = [c.args for c in emit.call_args_list]
        self.assertEqual(sum(args[0] == 'success' for args in messages), 1)
        self.assertFalse(any(args[0] == 'error' for args in messages))
        self.assertTrue(any('Segment 3 failed; retrying this stage' in args[1] for args in messages))

    def test_each_stage_has_five_attempts_not_one_shared_retry_budget(self):
        result, counts, session, _, sleep, _ = self.run_sync({v: 4 for v in VIEWS})
        self.assertEqual(result['status'], 'success')
        self.assertEqual(counts, Counter({v: 5 for v in VIEWS}))
        self.assertEqual(session.commit.call_count, 9)
        self.assertEqual(session.rollback.call_count, 36)
        self.assertEqual(sleep.call_count, 36)

    def test_exhaustion_keeps_completed_stages_and_stops_following_stages(self):
        result, counts, session, emit, sleep, _ = self.run_sync({VIEWS[4]: 5})
        self.assertEqual(result['status'], 'error')
        self.assertIn('Segment 4', result['message'])
        self.assertIn('Attempt 5/5', result['message'])
        self.assertEqual(counts, Counter({**{v: 1 for v in VIEWS[:4]}, VIEWS[4]: 5}))
        self.assertEqual(session.commit.call_count, 4)
        self.assertEqual(session.rollback.call_count, 5)
        self.assertEqual(sleep.call_count, 4)
        self.assertEqual(sum(c.args[0] == 'error' for c in emit.call_args_list), 1)

    def test_local_write_failure_rolls_back_and_resumes_same_stage(self):
        result, counts, session, _, _, _ = self.run_sync(fail_write=True)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(counts[VIEWS[3]], 2)
        self.assertTrue(all(counts[v] == 1 for v in VIEWS if v != VIEWS[3]))
        self.assertEqual(session.rollback.call_count, 1)
        self.assertEqual(session.commit.call_count, 9)

    def test_connection_failure_does_not_restart_committed_stages(self):
        # A reconnect can fail before the resumed stage gets a new cursor.
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchall.return_value = []
        counts = Counter()

        def execute(sql):
            view = re.search(r'FROM ext_view\.(\w+)', sql).group(1)
            counts[view] += 1
            if view == VIEWS[2] and counts[view] == 1:
                raise RuntimeError('disconnected')

        cursor.execute.side_effect = execute
        with patch.object(sync, 'get_external_db_connection', side_effect=[connection, RuntimeError('reconnect failed'), connection]), patch.object(
            sync, 'db', SimpleNamespace(session=MagicMock())
        ), patch.object(sync, 'emit_sync_update'), patch.object(sync.time, 'sleep'):
            result = sync.sync_party_delay_management_data_task()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(counts[VIEWS[0]], 1)
        self.assertEqual(counts[VIEWS[1]], 1)
        self.assertEqual(counts[VIEWS[2]], 2)


if __name__ == '__main__':
    unittest.main()
