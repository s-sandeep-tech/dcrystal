import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class InvoiceCompletedPendingDeliverSyncTests(unittest.TestCase):
    def run_sync(self, pages):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.side_effect = pages
        session = MagicMock()
        with patch.object(sync, 'get_external_db_connection', return_value=connection), \
             patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'emit_sync_update'):
            result = sync.sync_invoice_completed_pending_deliver_data_task()
        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        self.assertEqual(connection.cursor.call_args.kwargs['name'], 'invoice_completed_pending_deliver_sync')
        connection.close.assert_called_once()
        cursor.fetchall.assert_not_called()
        for fetch in cursor.fetchmany.call_args_list:
            self.assertEqual(fetch.args, (30_000,))
        return result, session

    def test_full_and_partial_batches_preserve_tuple_mapping(self):
        row = tuple(range(31))
        result, session = self.run_sync([[row] * 30_000, [row], []])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['count'], 30_001)
        batches = session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(batch.args[1]) for batch in batches], [30_000, 1])
        record = batches[1].args[1][0]
        fields = ('make_owner', 'make', 'collection_owner', 'collection', 'order_branch',
                  'business_head_name', 'party', 'po_date', 'po_number', 'order_type', 'order_request_type',
                  'party_mobile_no', 'barcode_completion_date', 'barcoded_weight', 'set_identifier',
                  'set_design_no', 'target_date', 'net_weight', 'gross_weight', 'stone_weight',
                  'is_invoiced', 'purchase_invoice_rate_requisition_number', 'invoice_ro', 'invoice_no',
                  'invoice_date', 'invoice_amount', 'pieces', 'weight')
        expected = [*range(11), *range(12, 17), *range(19, 31)]
        expected[fields.index('is_invoiced')] = True
        self.assertEqual([record[field] for field in fields], expected)
        self.assertEqual(record['snapshot_date'], batches[0].args[1][0]['snapshot_date'])
        session.query.return_value.delete.assert_called_once_with(synchronize_session=False)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.bulk_save_objects.assert_not_called()

    def test_mid_fetch_failure_rolls_back_loaded_batches(self):
        result, session = self.run_sync([[tuple(range(31))], RuntimeError('source disconnected')])
        self.assertEqual(result['status'], 'error')
        session.bulk_insert_mappings.assert_called_once()
        session.commit.assert_not_called()
        session.rollback.assert_called_once()

    def test_first_fetch_failure_preserves_snapshot(self):
        result, session = self.run_sync([RuntimeError('first fetch failed')])
        self.assertEqual(result['status'], 'error')
        session.query.assert_not_called()
        session.rollback.assert_called_once()

    def test_empty_source_keeps_existing_behavior(self):
        result, session = self.run_sync([[]])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['count'], 0)
        session.query.assert_not_called()
        session.bulk_insert_mappings.assert_not_called()
        session.commit.assert_not_called()

    def test_null_and_zero_invoice_flags_remain_false(self):
        for flag in (None, 0, False):
            row = list(range(31))
            row[23] = flag
            result, session = self.run_sync([[tuple(row)], []])
            self.assertEqual(result['status'], 'success')
            self.assertIs(session.bulk_insert_mappings.call_args.args[1][0]['is_invoiced'], False)
