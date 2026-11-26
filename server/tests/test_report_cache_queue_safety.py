import unittest
from unittest.mock import MagicMock

from app.utils.cache_utils import clear_report_cache


class ReportCacheQueueSafetyTests(unittest.TestCase):
    def test_cache_clear_preserves_waiting_jobs_and_operational_state(self):
        pending = [
            'party_order_accept_cancel_delivery',
            'sales_stock_composition_analysis',
            'owner_showroom_combined:scheduled_all_batch',
        ]
        store = {
            'sync_queue': pending.copy(),
            'export_queue': ['waiting export'],
            'lock:akt_perf_cache_v10:report': 'owner token',
            'purchase-plan:report:v6:version:digest:lock': 'owner token',
            'session:admin': 'session data',
            'rbac:version': '4',
            'akt_sync_metadata': 'generation data',
            'opo_main:latest:': 'old cache',
            'purchase-plan:report:v6:version:digest': 'old cache',
            b'prov_stock_status_options_v2:latest': 'old cache',
        }
        preserved = {k: v for k, v in store.items() if 'old cache' != v}
        client = MagicMock()
        client.scan_iter.return_value = iter(list(store))

        def delete(*keys):
            for key in keys:
                del store[key]
            return len(keys)

        client.delete.side_effect = delete
        self.assertEqual(clear_report_cache(client), 3)
        self.assertEqual(store, preserved)
        self.assertEqual(store['sync_queue'], pending)
        client.flushdb.assert_not_called()

    def test_deletes_in_bounded_batches(self):
        client = MagicMock()
        client.scan_iter.return_value = iter(f'opo_main:{i}' for i in range(1001))
        client.delete.side_effect = lambda *keys: len(keys)
        self.assertEqual(clear_report_cache(client), 1001)
        self.assertEqual([len(c.args) for c in client.delete.call_args_list], [500, 500, 1])


if __name__ == '__main__':
    unittest.main()
