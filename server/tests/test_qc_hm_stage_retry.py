from collections import Counter
import re
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


SPECS = (
    ('sync_qc_delay_management_data_task', (
        'vw_qc_summary_data', 'vw_supplier_qc_issue_completed_receipt_pending',
        'vw_qc_receipt_completed_qc_pending', 'vw_qc_completed_invoice_request_pending',
    )),
    ('sync_hm_delay_management_data_task', (
        'vw_hm_summary_data', 'vw_supplier_hm_issue_completed_hm_receipt_pending',
        'vw_hm_receipt_completed_hm_pending', 'vw_hm_completed_return_pending',
    )),
)


class QCHMStageRetryTests(unittest.TestCase):
    def run_sync(self, function, failures=None, fail_commit=False):
        counts = Counter()
        connections = []
        session = MagicMock()
        if fail_commit:
            # Summary commits; Segment 1 fails its first local commit.
            session.commit.side_effect = [None, RuntimeError('local commit failed'), None, None, None]

        def connect():
            connection = MagicMock()
            connections.append(connection)

            def cursor(*args, **kwargs):
                cur = MagicMock()
                cur.__enter__.return_value = cur
                cur.fetchall.return_value = []
                cur.fetchmany.return_value = []

                def execute(sql):
                    match = re.search(r'FROM ext_view\.(\w+)', str(sql))
                    if not match:
                        return
                    view = match.group(1)
                    counts[view] += 1
                    if counts[view] <= (failures or {}).get(view, 0):
                        raise RuntimeError('source connection closed')

                cur.execute.side_effect = execute
                return cur

            connection.cursor.side_effect = cursor
            return connection

        with patch.object(sync, 'get_external_db_connection', side_effect=connect), patch.object(
            sync, 'db', SimpleNamespace(session=session)
        ), patch.object(sync, 'emit_sync_update') as emit, patch.object(sync.time, 'sleep') as sleep:
            result = getattr(sync, function)()
        for connection in connections:
            connection.close.assert_called_once()
        return result, counts, session, emit, sleep

    def test_middle_stage_retries_without_repeating_completed_stages(self):
        for function, views in SPECS:
            with self.subTest(function=function):
                result, counts, session, emit, sleep = self.run_sync(function, {views[2]: 2})
                self.assertEqual(result['status'], 'success')
                self.assertEqual(counts, Counter({v: 3 if v == views[2] else 1 for v in views}))
                self.assertEqual(session.commit.call_count, 4)
                self.assertEqual(session.rollback.call_count, 2)
                self.assertEqual(sleep.call_count, 2)
                self.assertFalse(any(c.args[0] == 'error' for c in emit.call_args_list))

    def test_every_stage_has_its_own_five_attempt_budget(self):
        for function, views in SPECS:
            with self.subTest(function=function):
                result, counts, session, _, sleep = self.run_sync(function, {v: 4 for v in views})
                self.assertEqual(result['status'], 'success')
                self.assertEqual(counts, Counter({v: 5 for v in views}))
                self.assertEqual(session.commit.call_count, 4)
                self.assertEqual(session.rollback.call_count, 16)
                self.assertEqual(sleep.call_count, 16)

    def test_exhaustion_preserves_completed_stages_and_stops_later_stages(self):
        for function, views in SPECS:
            with self.subTest(function=function):
                result, counts, session, emit, sleep = self.run_sync(function, {views[2]: 5})
                self.assertEqual(result['status'], 'error')
                self.assertIn('Segment 2', result['message'])
                self.assertIn('Attempt 5/5', result['message'])
                self.assertEqual(counts, Counter({views[0]: 1, views[1]: 1, views[2]: 5}))
                self.assertEqual(session.commit.call_count, 2)
                self.assertEqual(session.rollback.call_count, 5)
                self.assertEqual(sleep.call_count, 4)
                self.assertEqual(sum(c.args[0] == 'error' for c in emit.call_args_list), 1)

    def test_failed_local_commit_retries_that_stage_after_rollback(self):
        for function, views in SPECS:
            with self.subTest(function=function):
                result, counts, session, _, _ = self.run_sync(function, fail_commit=True)
                self.assertEqual(result['status'], 'success')
                self.assertEqual(counts, Counter({v: 2 if v == views[1] else 1 for v in views}))
                self.assertEqual(session.rollback.call_count, 1)
                self.assertEqual(session.commit.call_count, 5)


if __name__ == '__main__':
    unittest.main()
