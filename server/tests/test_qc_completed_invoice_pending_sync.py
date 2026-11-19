import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.utils import sync_tasks as sync


class QCCompletedInvoicePendingSyncTests(unittest.TestCase):
    def run_sync(self, pages):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.side_effect = pages
        session = MagicMock()
        with patch.object(sync, 'get_external_db_connection', return_value=connection), \
             patch.object(sync, 'db', SimpleNamespace(session=session)), \
             patch.object(sync, 'emit_sync_update'):
            result = sync.sync_qc_completed_invoice_pending_data_task()
        connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
        self.assertEqual(connection.cursor.call_args.kwargs['name'], 'qc_completed_invoice_pending_sync')
        connection.close.assert_called_once()
        cursor.fetchall.assert_not_called()
        for fetch in cursor.fetchmany.call_args_list:
            self.assertEqual(fetch.args, (30_000,))
        return result, session

    def test_full_and_partial_batches_preserve_tuple_mapping(self):
        row = tuple(range(35))
        result, session = self.run_sync([[row] * 30_000, [row], []])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['count'], 30_001)
        batches = session.bulk_insert_mappings.call_args_list
        self.assertEqual([len(batch.args[1]) for batch in batches], [30_000, 1])
        record = batches[1].args[1][0]
        fields = ('make_owner', 'make', 'collection_owner', 'collection', 'order_branch',
                  'business_head_name', 'party', 'po_date', 'po_number', 'order_type',
                  'order_request_type', 'party_mobile_no', 'barcode_completion_date', 'barcoded_weight',
                  'set_identifier', 'set_design_no', 'target_date', 'qc_issue_receipt_no',
                  'qc_issue_receipt_date', 'qc_ro', 'qc_ro_incharge', 'final_qc_receipt_no',
                  'final_qc_receipt_date', 'net_weight', 'gross_weight', 'stone_weight', 'invoice_ro',
                  'is_qc_completed', 'qc_completed_date', 'is_rate_requisition_completed', 'is_invoiced',
                  'purchase_invoice_rate_requisition_number', 'pieces', 'weight', 'design_no')
        expected = list(range(35))
        for index in (27, 29, 30):
            expected[index] = True
        self.assertEqual([record[field] for field in fields], expected)
        self.assertEqual(record['snapshot_date'], batches[0].args[1][0]['snapshot_date'])
        session.query.return_value.delete.assert_called_once_with(synchronize_session=False)
        session.commit.assert_called_once()
        session.rollback.assert_not_called()
        session.bulk_save_objects.assert_not_called()

    def test_mid_fetch_failure_rolls_back_loaded_batches(self):
        result, session = self.run_sync([[tuple(range(35))], RuntimeError('source disconnected')])
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

    def test_boolean_nulls_and_false_values_preserve_conversion(self):
        row = list(range(35))
        row[27], row[29], row[30] = None, 0, False
        result, session = self.run_sync([[tuple(row)], []])
        self.assertEqual(result['status'], 'success')
        record = session.bulk_insert_mappings.call_args.args[1][0]
        for field in ('is_qc_completed', 'is_rate_requisition_completed', 'is_invoiced'):
            self.assertIs(record[field], False)
