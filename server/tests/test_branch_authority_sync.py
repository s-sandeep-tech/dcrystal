import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class BranchAuthoritySyncTests(unittest.TestCase):
    def run_sync(self, pages):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.side_effect = pages
        session = MagicMock()
        with patch.object(sync, 'get_external_db_connection', return_value=connection), \
             patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'emit_sync_update'):
            result = sync.sync_branch_authority_data_task()
        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        self.assertEqual(connection.cursor.call_args.kwargs['name'], 'branch_authority_sync')
        connection.close.assert_called_once()
        cursor.fetchall.assert_not_called()
        for fetch in cursor.fetchmany.call_args_list:
            self.assertEqual(fetch.args, (30_000,))
        return result, session

    def test_full_and_partial_batches_preserve_source_values(self):
        row = {'branch_id': 20, 'emp_code': 1235}
        result, session = self.run_sync([[row] * 30_000, [row], []])
        self.assertEqual(result, {'status': 'success', 'count': 30_001})
        batches = session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(batch.args[1]) for batch in batches], [30_000, 1])
        self.assertEqual(batches[1].args,
                         (sync.BranchAuthoritySnapshot, [row]))
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.add_all.assert_not_called()

    def test_fetch_failure_rolls_back_loaded_batches(self):
        result, session = self.run_sync([[{'branch_id': 20, 'emp_code': 1235}], RuntimeError('source disconnected')])
        self.assertEqual(result['status'], 'error')
        session.bulk_insert_mappings.assert_called_once()
        session.commit.assert_not_called()
        session.rollback.assert_called_once()

    def test_first_fetch_failure_preserves_snapshot(self):
        result, session = self.run_sync([RuntimeError('first fetch failed')])
        self.assertEqual(result['status'], 'error')
        session.query.assert_not_called()
        session.rollback.assert_called_once()

    def test_empty_source_keeps_existing_authority(self):
        result, session = self.run_sync([[]])
        self.assertEqual(result, {'status': 'success', 'count': 0})
        session.query.assert_not_called()
        session.bulk_insert_mappings.assert_not_called()
        session.commit.assert_not_called()
