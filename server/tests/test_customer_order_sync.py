import unittest
from unittest.mock import Mock, patch

from app.utils import sync_tasks


class CustomerOrderSyncTests(unittest.TestCase):
    def test_combined_status_is_copied_from_source(self):
        from app.models.customer_order_analysis import CustomerOrderAnalysisSnapshot
        connection = Mock()
        connection.cursor.return_value.fetchall.return_value = [{
            'request_no': 'REQ-1', 'order_status': 'Delivered to office',
            'combine_order_status': 'Customer delivery pending',
        }]
        with patch.object(sync_tasks, 'emit_sync_update'), \
                patch.object(sync_tasks, 'get_external_db_connection', return_value=connection), \
                patch.object(sync_tasks, 'db') as database, \
                patch.object(CustomerOrderAnalysisSnapshot.__table__, 'create'):
            result = sync_tasks.sync_customer_order_analysis_task()
        self.assertEqual(result['status'], 'success')
        records = database.session.bulk_insert_mappings.call_args.args[1]
        self.assertEqual(records[0]['combine_order_status'], 'Customer delivery pending')
        self.assertEqual(records[0]['order_status'], 'Delivered to office')

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
