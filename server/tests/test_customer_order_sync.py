import unittest
from unittest.mock import patch

from app.utils import sync_tasks


class CustomerOrderSyncTests(unittest.TestCase):
    def test_progress_uses_supported_keyword_and_handles_source_failure(self):
        with patch.object(sync_tasks, 'emit_sync_update', autospec=True) as emit, \
                patch.object(sync_tasks, 'get_external_db_connection', side_effect=RuntimeError('Source unavailable')), \
                patch.object(sync_tasks, 'db') as database, \
                patch.object(sync_tasks.logger, 'exception'):
            result = sync_tasks.sync_customer_order_analysis_task()
            self.assertEqual(result['status'], 'error')
            emit.assert_any_call('processing', 'Starting Customer Order Analysis sync...', 5,
                                 data_type='customer_order_analysis')
            emit.assert_any_call('error', 'Sync failed: Source unavailable', 0,
                                 data_type='customer_order_analysis')
            database.session.query.assert_not_called()
            database.session.rollback.assert_called_once()

    def test_override_and_progress_range(self):
        with patch.object(sync_tasks, 'emit_sync_update', autospec=True) as emit, \
                patch.object(sync_tasks, 'get_external_db_connection', side_effect=RuntimeError('Source unavailable')), \
                patch.object(sync_tasks, 'db'), patch.object(sync_tasks.logger, 'exception'):
            sync_tasks.sync_customer_order_analysis_task(task_type_override='combined', progress_range=(20, 80))
            emit.assert_any_call('processing', 'Starting Customer Order Analysis sync...', 23,
                                 data_type='combined')
