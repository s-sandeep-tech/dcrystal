import unittest
from unittest.mock import patch
from flask import Flask, session
from app.utils import sync_tasks, sync_manager
from app.dashboard.routes.main import settings_sync_party_order_accept_cancel_delivery


class PartyOrderSingleSyncTests(unittest.TestCase):
    def test_only_requested_view_and_progress_key(self):
        with patch.object(sync_tasks, '_sync_party_performance_specs', return_value={'status': 'success'}) as sync:
            result = sync_tasks.sync_party_order_accept_cancel_delivery_task()
            specs, key, progress, subtask = sync.call_args.args
            self.assertEqual([s['view'] for s in specs], ['vw_party_order_accept_cancel_and_delivered_frequency'])
            self.assertEqual(key, 'party_order_accept_cancel_delivery')
            self.assertEqual(result['status'], 'success')
            self.assertEqual(progress, (0, 100))
            self.assertFalse(subtask)

    def test_enqueue_and_no_duplicate_scheduled_sync(self):
        key = 'party_order_accept_cancel_delivery'
        self.assertIn(key, sync_manager.ALLOWED_SYNC_TASKS)
        self.assertNotIn(key, sync_manager.SCHEDULED_ALL_SYNC_TASKS)
        with patch.object(sync_manager, 'enqueue_sync_task') as enqueue:
            sync_manager.sync_party_order_accept_cancel_delivery_data('123')
            enqueue.assert_called_once_with(key, '123')

    def test_route_permissions(self):
        app = Flask(__name__)
        app.secret_key = 'test-secret'
        for roles, expected in [([], 401), (['SHOWROOM_MANAGER'], 401), (['ADMIN'], 200), (['DATA_SYNC_USER'], 200)]:
            with app.test_request_context('/settings/sync-party-order-accept-cancel-delivery', method='POST'):
                session['user_id'] = '123'
                session['roles'] = roles
                with patch.object(sync_manager, 'sync_party_order_accept_cancel_delivery_data', return_value={'status': 'success'}) as enqueue:
                    _, status = settings_sync_party_order_accept_cancel_delivery()
                    self.assertEqual(status, expected)
                    self.assertEqual(enqueue.called, expected == 200)
