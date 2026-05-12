import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any
from sqlalchemy import text
from ..extensions import db, socketio, redis_client
from ..models.snapshots import (
    OwnerWiseOrderSummarySnapshot, 
    PartyProcessAgeingSnapshot,
    OutstandingPurchaseOrderStatusSnapshot,
    StageLevelDelaySnapshot,
    OrderDelayTrackingSnapshot,
    PendingAcceptanceSnapshot,
    RejectedWeightSnapshot,
    ShowroomWiseOrderSummarySnapshot,
    ProvisionStockRawSnapshot,
    ProvisionStockRawStaging,
    HallmarkingDelayedSnapshot,
    QCDelayedSnapshot,
    OrderProcessingPendingSnapshot,
    HMCompletedReturnSnapshot,
    SupplierHMIssueSnapshot,
    HMReturnQCIssueSnapshot,
    SupplierQCIssueReceiptPendingSnapshot,
    QCCompletedInvoicePendingSnapshot,
    QCCompletedInvoiceRequestPendingSnapshot,
    InvoiceCompletedPendingDeliverSnapshot,
    BranchAuthoritySnapshot,
    HMReceiptCompletedHMPendingSnapshot,
    HMCompletedReturnPendingSnapshot,
    PartyDelayManagementSnapshot,
    PartyDelayManagementFeedback,
    PartyAcceptPendingSnapshot,
    PartyProcessPendingSnapshot,
    PartyBarcodePendingSnapshot,
    PartyHMIssuePendingSnapshot,
    PartyHMReceiptCompletedQCIssuePendingSnapshot,
    PartyInvoiceRequestCompletedInvoicePendingSnapshot
)
from flask import current_app
import os
import time
from datetime import date, datetime
import json
import logging
import socket
import threading
import queue
import traceback

logger = logging.getLogger(__name__)

def emit_sync_update(status, message, progress=0, data_type=None):
    """Utility to emit real-time updates via SocketIO and Redis bridge."""
    payload = {
        'status': status,
        'message': message,
        'progress': progress,
        'type': data_type
    }
    # 1. Emit via Flask-SocketIO (for consistency)
    socketio.emit('sync_update', payload)
    
    # 2. Publish to Redis for Node.js socket server
    try:
        redis_client.publish('sync_updates', json.dumps(payload))
        
        # 3. Global notification for all users on success
        if status == 'success':
            sync_name = data_type.replace('_', ' ').capitalize() if data_type else "Data"
            global_payload = {
                "title": f"Sync Successful: {sync_name}",
                "message": f"The {sync_name} synchronization has completed successfully.",
                "type": "success",
                "icon": "sync"
            }
            redis_client.publish('global_notifications', json.dumps(global_payload))
    except Exception as e:
        logger.error(f"Failed to publish sync update to Redis: {e}")

def emit_combined_sync_update(status, message, progress, task_type, progress_range=(0, 100), is_subtask=False):
    """
    Helper to emit updates for sub-tasks within a combined task.
    If is_subtask is True, it converts 'success' status to 'processing' and scales progress.
    """
    # Scale progress
    scaled_progress = progress_range[0] + (progress * (progress_range[1] - progress_range[0]) / 100)
    
    # Override status if it's a sub-task and it's 'success'
    effective_status = status
    if is_subtask and status == 'success':
        effective_status = 'processing'
        
    emit_sync_update(effective_status, message, int(scaled_progress), task_type)

def get_external_db_connection():
    """Establishes a connection to the external Azure PostgreSQL database."""
    host = "kj-az1-prod1-crystal-psql-db2.postgres.database.azure.com"
    ip_fallback = "10.150.76.133"
    
    try:
        target_host = host
        try:
            socket.gethostbyname(host)
        except Exception:
            target_host = ip_fallback
            
        conn = psycopg2.connect(
            host=target_host,
            database="crystal",
            user="repo_user_ext",
            password="KjPGReportUserAz@26",
            port=5432,
            sslmode="require",
            connect_timeout=60, # Increased from 10
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to external DB: {str(e)}")
        raise e

def sync_owner_wise_data_task(task_type_override=None, progress_range=(0, 100), is_subtask=False) -> Dict[str, Any]:
    conn = None
    TASK_TYPE = task_type_override or 'owner_wise'
    
    def emit(status, message, progress):
        emit_combined_sync_update(status, message, progress, TASK_TYPE, progress_range, is_subtask)

    try:
        emit('processing', 'Starting Owner Wise Order Summary Sync...', 5)
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit('processing', 'Fetching data from Azure PostgreSQL...', 20)
        query = "SELECT * FROM ext_view.vw_ownership_wise_order_summary_with_order_type_provision_type"
        
        start_time = time.time()
        # Ensure session doesn't time out for this specific slow query
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"OwnerWise query took {duration:.2f} seconds.")
        emit('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local database...', 50)
        
        # Clear existing
        db.session.query(OwnerWiseOrderSummarySnapshot).delete()
        
        # Insert new using high-performance bulk mappings
        new_records = []
        for row in rows:
            new_records.append({
                'supplier': row.get('supplier'),
                'batch': row.get('batch'),
                'division': row.get('division'),
                'group_name': row.get('group'),
                'purity': row.get('purity'),
                'classification': row.get('classification'),
                'make': row.get('make'),
                'collection': row.get('collection'),
                'order_request_type': row.get('order_request_type'),
                'order_type': row.get('order_type'),
                'order_date': row.get('order_date'),
                'order_ro': row.get('order_ro'),
                'provision_type': row.get('provision_type'),
                'branch_provision_type': row.get('branch_provision_type'),
                'classification_owner': row.get('classification_owner'),
                'collection_owner': row.get('collection_owner'),
                'make_owner': row.get('make_owner'),
                'ordered_pcs': row.get('order_qty'),
                'ordered_wt': row.get('order_wt'),
                'accepted_pcs': row.get('accepted_pcs'),
                'accepted_wt': row.get('accepted_wt'),
                'rejected_pcs': row.get('rejected_pcs'),
                'rejected_wt': row.get('rejected_wt'),
                'cancelled_pcs': row.get('cancelled_pcs'),
                'cancelled_wt': row.get('cancelled_wt'),
                'barcoded_pcs': row.get('barcoded_pcs'),
                'barcoded_wt': row.get('barcoded_wt'),
                'not_barcoded_pcs': row.get('not_barcoded_pcs'),
                'not_barcoded_wt': row.get('not_barcoded_wt'),
                'hm_processed_pcs': row.get('hm_processed_pcs'),
                'hm_testcut_pcs': row.get('hm_testcut_pcs'),
                'hm_testcut_wt': row.get('hm_testcut_wt'),
                'hm_passed_pcs': row.get('hm_passed_pcs'),
                'hm_passed_wt': row.get('hm_passed_wt'),
                'hm_failed_pcs': row.get('hm_failed_pcs'),
                'hm_failed_wt': row.get('hm_failed_wt'),
                'qc_processed_pcs': row.get('qc_processed_pcs'),
                'qc_pending_pcs': row.get('qc_pending_pcs'),
                'qc_pending_wt': row.get('qc_pending_wt'),
                'qc_rejected_pcs': row.get('qc_reject_pcs'),
                'qc_rejected_wt': row.get('qc_reject_wt'),
                'qc_passed_pcs': row.get('qc_passed_pcs'),
                'qc_passed_wt': row.get('qc_passed_wt'),
                'invoiced_pcs': row.get('invoice_pcs'),
                'invoiced_wt': row.get('invoiced_wt'),
                'delivered_pcs': row.get('delivered_pcs'),
                'delivered_wt': row.get('delivered_wt'),
                'pending_to_be_delv_pcs': row.get('pending_to_deliver_pcs'),
                'pending_to_be_delv_wt': row.get('pending_to_deliver_wt'),
                'pending_to_accepted_pcs': row.get('pending_to_accepted_pcs'),
                'pending_to_accepted_wt': row.get('pending_to_accepted_wt')
            })
        
        db.session.bulk_insert_mappings(OwnerWiseOrderSummarySnapshot, new_records)
        db.session.commit()
        
        emit('success', f'Sync completed! {len(rows)} records updated.', 100)
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"OwnerWise Sync error: {error_msg}")
        emit('error', f'Sync failed: {error_msg}', 0)
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_process_level_delay_data_task() -> Dict[str, Any]:
    conn = None
    try:
        emit_sync_update('processing', 'Starting Process Level Delay Sync...', 5, 'process_delay')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching analytical data from Azure...', 20, 'process_delay')
        query = """
                    WITH
            qc_agg AS (
                SELECT
                order_id,
                MAX(qc_completed_at)::date AS qc_date,
                MAX(qc_completed_at) FILTER (WHERE qc_status_name <> 'Passed')::date AS qc_rejected_date,
                CASE
                    WHEN BOOL_OR(qc_status_name = 'Reject') THEN 'Rejected'
                    WHEN BOOL_OR(qc_status_name = 'Passed')
                    OR BOOL_OR(qc_status_name = 'Accepted with issue') THEN 'Passed'
                ELSE 'Not Passed'
                END AS qc_status
                FROM ext_view.vw_order_qc_details
                GROUP BY order_id
            ),

            hm_agg AS (
                SELECT
                order_id,
                MAX(hm_issued_delivery_challan_date)::date AS hallmark_date,
                CASE
                    WHEN BOOL_OR(hm_status = 'Passed') THEN 'Passed'
                    ELSE 'Not Passed'
                END AS hallmark_status
                FROM ext_view.vw_order_hallmark_details
                GROUP BY order_id
            ),

            base AS (
                SELECT
                od.order_id,
                od.supplier AS party_name,
                od.order_status,
                od.order_date::date  AS order_date,
                od.accepted_on::date AS accepted_date,
                od.barcoded_at::date AS barcoded_date,
                h.hallmark_date,
                h.hallmark_status,
                q.qc_date,
                q.qc_status,
                q.qc_rejected_date
                FROM ext_view.vw_order_details od
                LEFT JOIN qc_agg q ON q.order_id = od.order_id
                LEFT JOIN hm_agg h ON h.order_id = od.order_id
            ),

            status_rows AS (
                SELECT
                    order_id,
                    party_name,
                    'Order Accepted' AS completed_process_level,
                    accepted_date    AS last_completed_date
                FROM base
                WHERE accepted_date IS NOT NULL

                UNION ALL
                SELECT order_id, party_name, 'Barcoded', barcoded_date
                FROM base
                WHERE barcoded_date IS NOT NULL

                UNION ALL
                SELECT order_id, party_name, 'Hallmark Completed', hallmark_date
                FROM base
                WHERE hallmark_date IS NOT NULL
                    AND hallmark_status = 'Passed'

                UNION ALL
                SELECT order_id, party_name, 'QC Completed', COALESCE(qc_date, CURRENT_DATE) AS  qc_date
                FROM base
                WHERE   qc_status = 'Passed'

                UNION ALL
                SELECT order_id, party_name, 'QC Rejected', qc_rejected_date
                FROM base
                WHERE  qc_status = 'Rejected'

                UNION ALL
                SELECT
                    order_id,
                    party_name,
                    'Invoiced',
                    COALESCE(qc_date, hallmark_date, barcoded_date, accepted_date, order_date)
                FROM base
                WHERE order_status ILIKE '%Invoice Approved%'
                    OR order_status ILIKE '%RO Received%'

                UNION ALL
                SELECT
                    order_id,
                    party_name,
                    'Delivered',
                    COALESCE(qc_date, hallmark_date, barcoded_date, accepted_date, order_date)
                FROM base
                WHERE order_status ILIKE '%RO Received%'
            ),

            stage_flow AS (
                SELECT *
                FROM (VALUES
                ('Order Accepted',     'Barcoded',           'Barcoding', 1),
                ('Barcoded',           'Hallmark Completed', 'Hallmark',  2),
                ('Hallmark Completed', 'QC Completed',       'QC',        3),
                ('QC Completed',       'Invoiced',           'Invoice',   4),
                ('Invoiced',           'Delivered',          'Delivery',  5),
                ('Delivered',          NULL,                'Completed', 6),
                ('QC Rejected',        NULL,                'Rejected',  35)
                ) AS t(curr_stage, next_stage, next_process_level, seq)
            ),

            joined AS (
                SELECT
                c.order_id,
                c.party_name,
                c.completed_process_level AS completed_process,
                c.last_completed_date     AS completed_date,
                f.next_stage,
                f.next_process_level      AS next_process,
                f.seq,
                n.last_completed_date     AS next_completed_date,
                (CURRENT_DATE - c.last_completed_date) AS days_waiting
                FROM status_rows c
                JOIN stage_flow f
                ON f.curr_stage = c.completed_process_level
                LEFT JOIN status_rows n
                ON n.order_id = c.order_id
                AND (
                    (f.next_stage <> 'QC Completed' AND n.completed_process_level = f.next_stage)
                OR (f.next_stage = 'QC Completed' AND n.completed_process_level IN ('QC Completed', 'QC Rejected'))
                )
                WHERE c.last_completed_date IS NOT NULL
            )

            SELECT
            party_name,
            completed_process AS completed_process_level,
            COUNT(DISTINCT order_id) AS completed_quantity,
            next_process AS next_process_level,

            COUNT(DISTINCT order_id) FILTER (
                WHERE next_stage IS NOT NULL
                AND next_completed_date IS NULL
            ) AS "Pending Qty",

            COUNT(DISTINCT order_id) FILTER (
                WHERE next_stage IS NOT NULL
                AND next_completed_date IS NULL
                AND days_waiting BETWEEN 1 AND 2
            ) AS "Window 1-2",

            COUNT(DISTINCT order_id) FILTER (
                WHERE next_stage IS NOT NULL
                AND next_completed_date IS NULL
                AND days_waiting BETWEEN 3 AND 4
            ) AS "Window 3-4",

            COUNT(DISTINCT order_id) FILTER (
                WHERE next_stage IS NOT NULL
                AND next_completed_date IS NULL
                AND days_waiting BETWEEN 5 AND 10
            ) AS "Window 5-10",

            COUNT(DISTINCT order_id) FILTER (
                WHERE next_stage IS NOT NULL
                AND next_completed_date IS NULL
                AND days_waiting > 10
            ) AS "Window 10+",
            seq AS sort_order

            FROM joined
            GROUP BY
            party_name,
            completed_process,
            next_process,
            seq
            ORDER BY
            party_name,
            seq;
        """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"ProcessDelay query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} analytical rows in {int(duration)}s. Updating local snapshot...', 60, 'process_delay')
        
        db.session.query(PartyProcessAgeingSnapshot).delete()
        new_records = []
        for row in rows:
            record = PartyProcessAgeingSnapshot(
                party_name=row.get('party_name'),
                completed_process_level=row.get('completed_process_level'),
                completed_quantity=row.get('completed_quantity'),
                next_process_level=row.get('next_process_level'),
                time_window_1_2_days=row.get('Window 1-2'),
                time_window_2_4_days=row.get('Window 3-4'),
                time_window_5_10_days=row.get('Window 5-10'),
                time_window_more_than_10_days=row.get('Window 10+'),
                sort_order=row.get('sort_order') or 0,
                report_date=db.func.current_date()
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        
        emit_sync_update('success', f'Process Delay Sync completed! {len(rows)} records updated.', 100, 'process_delay')
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"ProcessDelay Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, 'process_delay')
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_outstanding_purchase_order_data_task() -> Dict[str, Any]:
    conn = None
    try:
        emit_sync_update('processing', 'Starting Outstanding PO Sync...', 5, 'outstanding_po')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching PO data from Azure...', 20, 'outstanding_po')
        query = """
          SELECT
                od.supplier AS party,
                od.order_no AS order_number,
                od.order_date AS order_date,
                opd.classification,
                opd.classification_owner,
                opd.make,
                opd.make_owner,
                opd.collection,
                opd.collection_owner,
                opd.section,
                opd.division,
                opd."group",
                opd.purity,
                od.order_ro AS purchase_ro,
                CASE WHEN inv.order_receipt_created_at IS NOT NULL THEN 'Y' ELSE 'N' END AS receipt_present,
                COUNT(*) AS order_pieces,
                SUM(od.required_weight) AS order_weight,
                COUNT(*) FILTER (WHERE od.accepted_on IS NOT NULL AND od.rejected_on IS NULL) AS accepted_pieces,
                SUM(od.required_weight) FILTER (WHERE od.accepted_on IS NOT NULL AND od.rejected_on IS NULL) AS accepted_weight
                FROM ext_view.vw_order_details od
                JOIN ext_view.vw_order_product_details opd
                ON opd.order_id = od.order_id
                LEFT JOIN ext_view.vw_order_supplier_invoice_summary inv
                ON inv.order_id = od.order_id
                GROUP BY
                od.supplier,
                od.order_no,
                od.order_date,
                opd.classification,
                opd.classification_owner,
                opd.make,
                opd.make_owner,
                opd.collection,
                opd.collection_owner,
                opd.section,
                opd.division,
                opd."group",
                opd.purity,
                od.order_ro,
                (inv.order_receipt_created_at IS NOT NULL);
    """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"OutstandingPO query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} PO records in {int(duration)}s. Updating local snapshot...', 60, 'outstanding_po')
        
        db.session.query(OutstandingPurchaseOrderStatusSnapshot).delete()
        new_records = []
        for row in rows:
            record = OutstandingPurchaseOrderStatusSnapshot(
                party=row.get('party'),
                order_number=row.get('order_number'),
                order_date=row.get('order_date'),
                classification=row.get('classification'),
                classification_owner=row.get('classification_owner'),
                make=row.get('make'),
                make_owner=row.get('make_owner'),
                collection=row.get('collection'),
                collection_owner=row.get('collection_owner'),
                section=row.get('section'),
                division=row.get('division'),
                group=row.get('group'),
                purity=row.get('purity'),
                purchase_ro=row.get('purchase_ro'),
                receipt_present=row.get('receipt_present'),
                order_pieces=row.get('order_pieces'),
                order_weight=row.get('order_weight'),
                accepted_pieces=row.get('accepted_pieces'),
                accepted_weight=row.get('accepted_weight')
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        
        emit_sync_update('success', f'Outstanding PO Sync completed! {len(rows)} records updated.', 100, 'outstanding_po')
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"OutstandingPO Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, 'outstanding_po')
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_stage_level_delay_data_task() -> Dict[str, Any]:
    """Sync StageLevel Delay data using the provided analytical query."""
    conn = None
    try:
        emit_sync_update('processing', 'Starting StageLevel Delay Sync...', 5, 'stage_delay')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching data from Azure...', 20, 'stage_delay')
        query = """
WITH
qc_agg AS (
  SELECT
    order_id,
    MAX(qc_completed_at)::date AS qc_date,
    MAX(qc_completed_at) FILTER (WHERE qc_status_name <> 'Passed')::date AS qc_rejected_date,
    CASE
      WHEN BOOL_OR(qc_status_name = 'Reject') THEN 'Rejected'
      WHEN BOOL_OR(qc_status_name = 'Passed')
        OR BOOL_OR(qc_status_name = 'Accepted with issue') THEN 'Passed'
      ELSE 'Not Passed'
    END AS qc_status
  FROM ext_view.vw_order_qc_details
  GROUP BY order_id
),

hm_agg AS (
  SELECT
    order_id,
    MAX(hm_issued_delivery_challan_date)::date AS hallmark_date,
    CASE
      WHEN BOOL_OR(hm_status = 'Passed') THEN 'Passed'
      ELSE 'Not Passed'
    END AS hallmark_status
  FROM ext_view.vw_order_hallmark_details
  GROUP BY order_id
),

/* Direct fetch (not MAX). Keeps 1 row per order_id to prevent join duplicates */
prod_one AS (
  SELECT DISTINCT ON (order_id)
    order_id,
    classification_owner,
    make_owner,
    collection_owner,
    division,
    "group",
    purity
  FROM ext_view.vw_order_product_details
  ORDER BY order_id
),

base AS (
  SELECT
    od.order_id,
    od.supplier AS party_name,
    od.order_ro,
    od.order_no,
    od.order_status,
    od.order_date::date  AS order_date,
    od.accepted_on::date AS accepted_date,
    od.barcoded_at::date AS barcoded_date,
    od.barcode,

    p.classification_owner,
    p.make_owner,
    p.collection_owner,
    p.division,
    p."group",
    p.purity,

    h.hallmark_date,
    h.hallmark_status,
    q.qc_date,
    q.qc_status,
    q.qc_rejected_date
  FROM ext_view.vw_order_details od
  LEFT JOIN prod_one p ON p.order_id = od.order_id
  LEFT JOIN qc_agg  q  ON q.order_id = od.order_id
  LEFT JOIN hm_agg  h  ON h.order_id = od.order_id
),

status_rows AS (
  SELECT
    order_id, party_name, order_ro, order_no,
    classification_owner, make_owner, collection_owner, division, "group", purity,
    order_date, barcode,
    'Order Accepted' AS completed_process_level,
    accepted_date    AS last_completed_date
  FROM base
  WHERE accepted_date IS NOT NULL

  UNION ALL
  SELECT
    order_id, party_name, order_ro, order_no,
    classification_owner, make_owner, collection_owner, division, "group", purity,
    order_date, barcode,
    'Barcoded', barcoded_date
  FROM base
  WHERE barcoded_date IS NOT NULL

  UNION ALL
  SELECT
    order_id, party_name, order_ro, order_no,
    classification_owner, make_owner, collection_owner, division, "group", purity,
    order_date, barcode,
    'Hallmark Completed', hallmark_date
  FROM base
  WHERE hallmark_date IS NOT NULL
    AND hallmark_status = 'Passed'

  UNION ALL
  SELECT
    order_id, party_name, order_ro, order_no,
    classification_owner, make_owner, collection_owner, division, "group", purity,
    order_date, barcode,
    'QC Completed', COALESCE(qc_date, CURRENT_DATE)
  FROM base
  WHERE qc_status = 'Passed'

  UNION ALL
  SELECT
    order_id, party_name, order_ro, order_no,
    classification_owner, make_owner, collection_owner, division, "group", purity,
    order_date, barcode,
    'QC Rejected', qc_rejected_date
  FROM base
  WHERE qc_status = 'Rejected'

  UNION ALL
  SELECT
    order_id, party_name, order_ro, order_no,
    classification_owner, make_owner, collection_owner, division, "group", purity,
    order_date, barcode,
    'Invoiced',
    COALESCE(qc_date, hallmark_date, barcoded_date, accepted_date, order_date)
  FROM base
  WHERE order_status ILIKE '%Invoice Approved%'
     OR order_status ILIKE '%RO Received%'

  UNION ALL
  SELECT
    order_id, party_name, order_ro, order_no,
    classification_owner, make_owner, collection_owner, division, "group", purity,
    order_date, barcode,
    'Delivered',
    COALESCE(qc_date, hallmark_date, barcoded_date, accepted_date, order_date)
  FROM base
  WHERE order_status ILIKE '%RO Received%'
),

/* keep only the latest date per (order_id, stage) */
status_rows_dedup AS (
  SELECT DISTINCT ON (order_id, completed_process_level)
    *
  FROM status_rows
  WHERE last_completed_date IS NOT NULL
  ORDER BY order_id, completed_process_level, last_completed_date DESC
),

stage_flow AS (
  SELECT *
  FROM (VALUES
    ('Order Accepted',     'Barcoded',           'Barcoding', 1),
    ('Barcoded',           'Hallmark Completed', 'Hallmark',  2),
    ('Hallmark Completed', 'QC Completed',       'QC',        3),
    ('QC Completed',       'Invoiced',           'Invoice',   4),
    ('Invoiced',           'Delivered',          'Delivery',  5),
    ('Delivered',          NULL,                'Completed', 6),
    ('QC Rejected',        NULL,                'Rejected',  35)
  ) AS t(curr_stage, next_stage, next_process_level, seq)
),

joined AS (
  SELECT
    c.*,
    f.next_stage,
    f.next_process_level AS next_process_level,
    f.seq,
    n.last_completed_date AS next_completed_date,
    (CURRENT_DATE - c.last_completed_date) AS days_waiting
  FROM status_rows_dedup c
  JOIN stage_flow f
    ON f.curr_stage = c.completed_process_level
  LEFT JOIN status_rows_dedup n
    ON n.order_id = c.order_id
   AND (
        (f.next_stage <> 'QC Completed' AND n.completed_process_level = f.next_stage)
     OR (f.next_stage = 'QC Completed' AND n.completed_process_level IN ('QC Completed', 'QC Rejected'))
   )
),

/* optional: only latest stage per item (recommended) */
current_stage AS (
  SELECT DISTINCT ON (order_id)
    *
  FROM joined
  ORDER BY order_id, seq DESC, last_completed_date DESC
)

SELECT
  order_id,
  party_name,
  order_ro,
  order_no,

  classification_owner,
  make_owner,
  collection_owner,
  division,
  "group",
  purity,
  order_date,
  barcode,

  completed_process_level,
  last_completed_date AS completed_date,

  next_process_level,
  days_waiting,
  seq,

  CASE
    WHEN next_stage IS NOT NULL AND next_completed_date IS NULL AND days_waiting BETWEEN 1 AND 2 THEN '1-2'
    WHEN next_stage IS NOT NULL AND next_completed_date IS NULL AND days_waiting BETWEEN 3 AND 4 THEN '3-4'
    WHEN next_stage IS NOT NULL AND next_completed_date IS NULL AND days_waiting BETWEEN 5 AND 10 THEN '5-10'
    WHEN next_stage IS NOT NULL AND next_completed_date IS NULL AND days_waiting > 10 THEN '10+'
    WHEN next_stage IS NOT NULL AND next_completed_date IS NULL THEN '0'
    ELSE NULL
  END AS pending_window

FROM current_stage;
        """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"StageLevelDelay query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local snapshot...', 60, 'stage_delay')
        
        # Clear existing
        db.session.query(StageLevelDelaySnapshot).delete()
        
        new_records = []
        for row in rows:
            # parsing window count
            w1 = 1 if row.get('pending_window') == '1-2' else 0
            w2 = 1 if row.get('pending_window') == '3-4' else 0
            w3 = 1 if row.get('pending_window') == '5-10' else 0
            w4 = 1 if row.get('pending_window') == '10+' else 0
            
            record = StageLevelDelaySnapshot(
                classification_owner=row.get('classification_owner'),
                make_owner=row.get('make_owner'),
                collection_owner=row.get('collection_owner'),
                division=row.get('division'),
                group=row.get('group'),
                purity=row.get('purity'),
                purchase_ro=row.get('order_ro'),
                order_number=row.get('order_no'),
                order_date=row.get('order_date'),
                barcode_number=row.get('barcode'),
                barcode_last_step_date=row.get('completed_date'),
                party=row.get('party_name'),
                completed_process_level=row.get('completed_process_level'),
                next_process_level=row.get('next_process_level'),
                seq=row.get('seq'),
                time_window_1_2_days=w1,
                time_window_3_4_days=w2,
                time_window_5_10_days=w3,
                time_window_more_than_10_days=w4,
                snapshot_date=db.func.current_date()
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        
        emit_sync_update('success', f'StageLevel Delay Sync completed! {len(rows)} records updated.', 100, 'stage_delay')
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"StageLevelDelay Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, 'stage_delay')
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()


def sync_order_delay_tracking_data_task() -> Dict[str, Any]:
    """Sync Order Delay Tracking data using the provided analytical query."""
    conn = None
    try:
        emit_sync_update('processing', 'Starting Order Delay Tracking Sync...', 5, 'order_delay_tracking')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching data from Azure...', 20, 'order_delay_tracking')
        query = """
            WITH production_orders AS MATERIALIZED (
                SELECT DISTINCT order_id
                FROM ext_view.vw_order_status_process
                WHERE status IN ('Process Pending', 'Barcode Pending')
            ),
            qc_orders AS MATERIALIZED (
                SELECT DISTINCT order_id
                FROM ext_view.vw_order_status_process
                WHERE process = 'Final QC'
            ),
            base_orders AS MATERIALIZED (
                SELECT
                    od.order_id,
                    od.po_id, 
                    od.cancelled_on 
                FROM ext_view.vw_order_details od
            ),

            prod_bucket AS (
                SELECT
                    bo.order_id,
                    CASE
                        WHEN po.delivery_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.delivery_target_date
                            THEN CURRENT_DATE - po.delivery_target_date
                        ELSE 0
                    END AS production_delay_days,

                    CASE
                        WHEN po.delivery_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.delivery_target_date
                            AND (CURRENT_DATE - po.delivery_target_date) BETWEEN 1 AND 2
                        THEN 1 ELSE 0
                    END AS production_1_2_delay,

                    CASE
                        WHEN po.delivery_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.delivery_target_date
                            AND (CURRENT_DATE - po.delivery_target_date) BETWEEN 3 AND 4
                        THEN 1 ELSE 0
                    END AS production_3_4_delay,

                    CASE
                        WHEN po.delivery_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.delivery_target_date
                            AND (CURRENT_DATE - po.delivery_target_date) BETWEEN 5 AND 10
                        THEN 1 ELSE 0
                    END AS production_5_10_delay,

                    CASE
                        WHEN po.delivery_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.delivery_target_date
                            AND (CURRENT_DATE - po.delivery_target_date) > 10
                        THEN 1 ELSE 0
                    END AS production_gt_10_delay
                FROM base_orders bo
                INNER JOIN production_orders pr
                    ON pr.order_id = bo.order_id
                INNER JOIN ext_view.vw_purchase_order po
                    ON po.po_id = bo.po_id
                WHERE bo.cancelled_on is null
            ),

            qc_bucket AS (
                SELECT
                    bo.order_id,
                    CASE
                        WHEN po.qc_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.qc_target_date
                            THEN CURRENT_DATE - po.qc_target_date
                        ELSE 0
                    END AS qc_delay_days,

                    CASE
                        WHEN po.qc_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.qc_target_date
                            AND (CURRENT_DATE - po.qc_target_date) BETWEEN 1 AND 2
                        THEN 1 ELSE 0
                    END AS qc_1_2_delay,

                    CASE
                        WHEN po.qc_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.qc_target_date
                            AND (CURRENT_DATE - po.qc_target_date) BETWEEN 3 AND 4
                        THEN 1 ELSE 0
                    END AS qc_3_4_delay,

                    CASE
                        WHEN po.qc_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.qc_target_date
                            AND (CURRENT_DATE - po.qc_target_date) BETWEEN 5 AND 10
                        THEN 1 ELSE 0
                    END AS qc_5_10_delay,

                    CASE
                        WHEN po.qc_target_date IS NULL THEN NULL
                        WHEN CURRENT_DATE > po.qc_target_date
                            AND (CURRENT_DATE - po.qc_target_date) > 10
                        THEN 1 ELSE 0
                    END AS qc_gt_10_delay
                FROM base_orders bo
                INNER JOIN qc_orders q
                    ON q.order_id = bo.order_id
                INNER JOIN ext_view.vw_purchase_order po
                    ON po.po_id = bo.po_id
            )

            SELECT
                po.po_id,
                bo.order_id,
                p.classification_owner,
                p.make_owner,
                p.collection_owner,
                p.make,
                p.collection,
                po.supplier,
                po.po_number,
                po.po_date,
                po.delivery_target_date,
                po.qc_target_date,

                pb.production_delay_days,
                pb.production_1_2_delay,
                pb.production_3_4_delay,
                pb.production_5_10_delay,
                pb.production_gt_10_delay,

                qb.qc_delay_days,
                qb.qc_1_2_delay,
                qb.qc_3_4_delay,
                qb.qc_5_10_delay,
                qb.qc_gt_10_delay

            FROM base_orders bo
            INNER JOIN ext_view.vw_purchase_order po
                ON po.po_id = bo.po_id
            INNER JOIN ext_view.vw_order_product_details p
                ON p.order_id = bo.order_id
            LEFT JOIN prod_bucket pb
                ON pb.order_id = bo.order_id
            LEFT JOIN qc_bucket qb
                ON qb.order_id = bo.order_id
            WHERE pb.order_id IS NOT NULL
            OR qb.order_id IS NOT NULL;
        """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"OrderDelayTracking query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local snapshot...', 60, 'order_delay_tracking')
        
        # Clear existing
        db.session.query(OrderDelayTrackingSnapshot).delete()
        
        new_records = []
        for row in rows:
            record = OrderDelayTrackingSnapshot(
                classification_owner=row.get('classification_owner'),
                make_owner=row.get('make_owner'),
                collection_owner=row.get('collection_owner'),
                delay_1_2_days=row.get('production_1_2_delay'),
                delay_3_4_days=row.get('production_3_4_delay'),
                delay_5_10_days=row.get('production_5_10_delay'),
                delay_more_than_10_days=row.get('production_gt_10_delay'),
                delay_days=row.get('production_delay_days'),
                qc_delay_1_2_days=row.get('qc_1_2_delay'),
                qc_delay_3_4_days=row.get('qc_3_4_delay'),
                qc_delay_5_10_days=row.get('qc_5_10_delay'),
                qc_delay_more_than_10_days=row.get('qc_gt_10_delay'),
                qc_delay_days=row.get('qc_delay_days'),
                supplier=row.get('supplier'),
                po_id=row.get('po_id'),
                order_id=row.get('order_id'),
                po_number=row.get('po_number'),
                po_date=row.get('po_date'),
                delivery_target_date=row.get('delivery_target_date'),
                qc_target_date=row.get('qc_target_date'),
                make=row.get('make'),
                collection=row.get('collection'),
                snapshot_date=db.func.current_date()
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        
        emit_sync_update('success', f'Order Delay Tracking Sync completed! {len(rows)} records updated.', 100, 'order_delay_tracking')
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"OrderDelayTracking Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, 'order_delay_tracking')
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_pending_acceptance_data_task() -> Dict[str, Any]:
    """Sync Pending Acceptance data using the provided analytical query."""
    conn = None
    try:
        emit_sync_update('processing', 'Starting Pending Acceptance Sync...', 5, 'pending_acceptance')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching data from Azure...', 20, 'pending_acceptance')
        query = """
            SELECT 
                a.collection_owner,
                a.make_owner,
                po.supplier,
                a.collection,
                a.classification,
                po.po_number,
                po.po_date,
                po.total_weight,
                po.total_quantity AS order_piece,
                a.order_wt,
                a.accepted_wt,
                a.pending_to_accepted_wt,
                a.pending_to_deliver_pcs,
                a.pending_to_deliver_wt,
                a.not_barcoded_pcs,
                a.not_barcoded_wt,
                a.order_type,
                a.order_request_type,
                a.order_date,
                po.delivery_target_date,
                a.branch_type AS branch_type
            FROM ext_view.vw_ownership_wise_order_summary_with_order_type_and_po_number_b a
            LEFT JOIN ext_view.vw_purchase_order po
                ON po.po_number = a.po_number
            WHERE (a.pending_to_accepted_wt > 0 OR a.pending_to_deliver_pcs > 0 OR a.not_barcoded_pcs > 0) 
            AND a.order_qty <> a.cancelled_pcs
            ORDER BY 
                a.accepted_wt DESC,
                a.pending_to_accepted_wt DESC;
        """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"PendingAcceptance query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local snapshot...', 60, 'pending_acceptance')
        
        # Clear existing
        db.session.query(PendingAcceptanceSnapshot).delete()
        
        new_records = []
        for row in rows:
            record = PendingAcceptanceSnapshot(
                collection_owner=row.get('collection_owner'),
                make_owner=row.get('make_owner'),
                supplier=row.get('supplier'),
                collection=row.get('collection'),
                classification=row.get('classification'),
                po_number=row.get('po_number'),
                po_date=row.get('po_date'),
                total_weight=row.get('total_weight'),
                order_piece=row.get('order_piece'),
                order_wt=row.get('order_wt'),
                accepted_wt=row.get('accepted_wt'),
                pending_to_accepted_wt=row.get('pending_to_accepted_wt'),
                pending_to_deliver_pcs=row.get('pending_to_deliver_pcs'),
                pending_to_deliver_wt=row.get('pending_to_deliver_wt'),
                not_barcoded_pcs=row.get('not_barcoded_pcs'),
                not_barcoded_wt=row.get('not_barcoded_wt'),
                order_type=row.get('order_type'),
                order_request_type=row.get('order_request_type'),
                order_date=row.get('order_date'),
                delivery_target_date=row.get('delivery_target_date'),
                branch_type=row.get('branch_type'),
                snapshot_date=db.func.current_date()
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        
        emit_sync_update('success', f'Pending Acceptance Sync completed! {len(rows)} records updated.', 100, 'pending_acceptance')
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"PendingAcceptance Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, 'pending_acceptance')
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_rejected_weight_data_task() -> Dict[str, Any]:
    """Sync Rejected Weight data using the provided analytical query."""
    conn = None
    try:
        emit_sync_update('processing', 'Starting Rejected Weight Sync...', 5, 'rejected_weight')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching data from Azure...', 20, 'rejected_weight')
        query = """
        SELECT 
            a.collection_owner,
            a.make_owner,
            po.supplier,
            a.collection,
            po.po_number,
            po.po_date,
            po.total_weight,
            po.total_quantity AS order_piece,
            a.order_wt,
            a.accepted_wt,
            a.rejected_wt,
            a.order_type,
            a.order_request_type,
            a.order_date
        FROM ext_view.vw_ownership_wise_order_summary_with_order_type_and_po_number a
        LEFT JOIN ext_view.vw_purchase_order po
            ON po.po_number = a.po_number
        WHERE a.rejected_wt > 0 and  a.order_qty <> a.cancelled_pcs
        ORDER BY 
            a.rejected_wt DESC;
        """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"RejectedWeight query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local snapshot...', 60, 'rejected_weight')
        
        # Clear existing
        db.session.query(RejectedWeightSnapshot).delete()
        
        new_records = []
        for row in rows:
            record = RejectedWeightSnapshot(
                collection_owner=row.get('collection_owner'),
                make_owner=row.get('make_owner'),
                supplier=row.get('supplier'),
                collection=row.get('collection'),
                po_number=row.get('po_number'),
                po_date=row.get('po_date'),
                total_weight=row.get('total_weight'),
                order_piece=row.get('order_piece'),
                order_wt=row.get('order_wt'),
                accepted_wt=row.get('accepted_wt'),
                rejected_wt=row.get('rejected_wt'),
                order_type=row.get('order_type'),
                order_request_type=row.get('order_request_type'),
                order_date=row.get('order_date'),
                snapshot_date=db.func.current_date()
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        
        emit_sync_update('success', f'Rejected Weight Sync completed! {len(rows)} records updated.', 100, 'rejected_weight')
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"RejectedWeight Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, 'rejected_weight')
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_hallmarking_delayed_data_task() -> Dict[str, Any]:
    """Sync Hallmarking Delayed data using the provided analytical query."""
    conn = None
    try:
        emit_sync_update('processing', 'Starting Hallmarking Delayed Sync...', 5, 'hallmarking_delayed')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching data from Azure...', 20, 'hallmarking_delayed')
        query = """
           WITH base AS MATERIALIZED (
    SELECT
        hm.hm_ro,
        vopd.make_owner,
        vopd.collection_owner,
        vopd.collection,
        hm.hm_agent,
        vod.supplier AS supplier,
        hm.challan_date,
        hm.requested_delivery_challan AS challan_no,
        1 AS pieces,
        COALESCE(vod.barcoded_weight, vod.required_weight) AS weight,
        hm.agent_received_on AS receipt_date,
        hm.receipt_no,
        hm.hm_status,
        vod.cancelled_on
    FROM ext_view.vw_order_hallmark_details hm
    INNER JOIN ext_view.vw_order_details vod
        ON vod.order_id = hm.order_id
    INNER JOIN ext_view.vw_order_product_details vopd
        ON vopd.order_id = hm.order_id
    WHERE hm.hm_status = 'Pending'
      AND hm.agent_received_on IS NOT NULL
      AND CURRENT_DATE - hm.agent_received_on > 2
)
        SELECT
            hm_ro,
            make_owner,
            collection_owner,
            collection,
            hm_agent,
            supplier,
            challan_date,
            challan_no,
            pieces,
            weight,
            receipt_date,
            receipt_no,
            hm_status
        FROM base
        WHERE cancelled_on IS  NULL;
        """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"HallmarkingDelayed query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local snapshot...', 60, 'hallmarking_delayed')
        
        # Clear existing
        db.session.execute(text("TRUNCATE hallmarking_delayed_snapshot"))
        
        new_records = []
        for row in rows:
            record = HallmarkingDelayedSnapshot(
                office=row.get('hm_ro'),
                make_owner=row.get('make_owner'),
                collection_owner=row.get('collection_owner'),
                collection=row.get('collection'),
                hm_agent=row.get('hm_agent'),
                supplier=row.get('supplier'),
                challan_date=row.get('challan_date'),
                challan_no=row.get('challan_no'),
                pieces=row.get('pieces'),
                weight=row.get('weight'),
                receipt_date=row.get('receipt_date'),
                receipt_no=row.get('receipt_no'),
                hm_status=row.get('hm_status'),
                snapshot_date=db.func.current_date()
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        
        emit_sync_update('success', f'Hallmarking Delayed Sync completed! {len(rows)} records updated.', 100, 'hallmarking_delayed')
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"HallmarkingDelayed Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, 'hallmarking_delayed')
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_showroom_wise_order_summary_task(task_type_override=None, progress_range=(0, 100), is_subtask=False) -> Dict[str, Any]:
    conn = None
    TASK_TYPE = task_type_override or 'showroom_wise_order'
    
    def emit(status, message, progress):
        emit_combined_sync_update(status, message, progress, TASK_TYPE, progress_range, is_subtask)

    try:
        emit('processing', 'Starting Showroom Wise Order Summary Sync...', 5)
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching data from Azure...', 15, 'showroom_wise_order')
        query = """
SELECT
    business_head_name as business_head,
    ownershippo.supplier AS party,
    ownershippo.order_branch AS location,
    ownershippo.order_ro AS purchase_ro,
    ownershippo.order_type,
    ownershippo.order_request_type,
    ownershippo.batch AS provision_type,
    ownershippo.batch AS branch_provision_type,
    ownershippo.branch_type AS branch_type,
    ownershippo.bh_emp_code,

    ownershippo.classification_owner,
    ownershippo.make_owner,
    ownershippo.collection_owner,

    ownershippo.supplier,
    ownershippo.po_number,
    ownershippo.po_id,
    ownershippo.order_date,
    ownershippo.order_ro,
    ownershippo.batch,
    ownershippo.bh_emp_code,
    ownershippo.division,
    ownershippo."group",
    ownershippo.purity,
    ownershippo.classification,
    ownershippo.make,
    ownershippo.collection,

    ownershippo.order_qty,
    ownershippo.order_wt,

    ownershippo.cancelled_pcs,
    ownershippo.cancelled_wt,

    ownershippo.accepted_pcs,
    ownershippo.accepted_wt,

    ownershippo.pending_to_accepted_pcs,
    ownershippo.pending_to_accepted_wt,

    ownershippo.rejected_pcs,
    ownershippo.rejected_wt,

    ownershippo.barcoded_pcs,
    ownershippo.barcoded_wt,

    ownershippo.not_barcoded_pcs,
    ownershippo.not_barcoded_wt,

    ownershippo.hm_processed_pcs,
    ownershippo.hm_passed_pcs,
    ownershippo.hm_passed_wt,
    ownershippo.hm_failed_pcs,
    ownershippo.hm_failed_wt,
    ownershippo.hm_testcut_pcs,
    ownershippo.hm_testcut_wt,

    ownershippo.qc_processed_pcs,
    ownershippo.qc_pending_pcs,
    ownershippo.qc_pending_wt,
    ownershippo.qc_reject_pcs,
    ownershippo.qc_reject_wt,
    ownershippo.qc_passed_pcs,
    ownershippo.qc_passed_wt,

    ownershippo.invoice_pcs,
    ownershippo.invoiced_wt,

    ownershippo.delivered_pcs,
    ownershippo.delivered_wt,

    ownershippo.pending_to_deliver_pcs,
    ownershippo.pending_to_deliver_wt

FROM ext_view.vw_ownership_wise_order_summary_with_order_type_and_po_number_b AS ownershippo;
        """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"ShowroomWiseOrderSummary query took {duration:.2f} seconds. Rows: {len(rows)}")
        emit_sync_update('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local snapshot...', 60, 'showroom_wise_order')
        
        # Clear existing
        db.session.execute(text("TRUNCATE showroom_wise_order_summary_snapshot"))
        
        # Insert new using high-performance bulk mappings
        new_records = []
        today = date.today()
        for row in rows:
            bh = row.get('business_head')
            if bh == 'NULL':
                bh = None
            new_records.append({
                'business_head': bh,
                'party': row.get('party'),
                'location': row.get('location'),
                'purchase_ro': row.get('purchase_ro'),
                'order_type': row.get('order_type'),
                'order_request_type': row.get('order_request_type'),
                'provision_type': row.get('provision_type'),
                'branch_provision_type': row.get('branch_provision_type'),
                'classification_owner': row.get('classification_owner'),
                'make_owner': row.get('make_owner'),
                'collection_owner': row.get('collection_owner'),
                'supplier': row.get('supplier'),
                'po_number': row.get('po_number'),
                'po_id': row.get('po_id'),
                'order_date': row.get('order_date'),
                'order_ro': row.get('order_ro'),
                'batch': row.get('batch'),
                'branch_type': row.get('branch_type'),
                'bh_emp_code': row.get('bh_emp_code'),
                'division': row.get('division'),
                'group_name': row.get('group'),
                'purity': row.get('purity'),
                'classification': row.get('classification'),
                'make': row.get('make'),
                'collection': row.get('collection'),
                'order_qty': row.get('order_qty'),
                'order_wt': row.get('order_wt'),
                'cancelled_pcs': row.get('cancelled_pcs'),
                'cancelled_wt': row.get('cancelled_wt'),
                'accepted_pcs': row.get('accepted_pcs'),
                'accepted_wt': row.get('accepted_wt'),
                'pending_to_accepted_pcs': row.get('pending_to_accepted_pcs'),
                'pending_to_accepted_wt': row.get('pending_to_accepted_wt'),
                'rejected_pcs': row.get('rejected_pcs'),
                'rejected_wt': row.get('rejected_wt'),
                'barcoded_pcs': row.get('barcoded_pcs'),
                'barcoded_wt': row.get('barcoded_wt'),
                'not_barcoded_pcs': row.get('not_barcoded_pcs'),
                'not_barcoded_wt': row.get('not_barcoded_wt'),
                'hm_processed_pcs': row.get('hm_processed_pcs'),
                'hm_passed_pcs': row.get('hm_passed_pcs'),
                'hm_passed_wt': row.get('hm_passed_wt'),
                'hm_failed_pcs': row.get('hm_failed_pcs'),
                'hm_failed_wt': row.get('hm_failed_wt'),
                'hm_testcut_pcs': row.get('hm_testcut_pcs'),
                'hm_testcut_wt': row.get('hm_testcut_wt'),
                'qc_processed_pcs': row.get('qc_processed_pcs'),
                'qc_pending_pcs': row.get('qc_pending_pcs'),
                'qc_pending_wt': row.get('qc_pending_wt'),
                'qc_reject_pcs': row.get('qc_reject_pcs'),
                'qc_reject_wt': row.get('qc_reject_wt'),
                'qc_passed_pcs': row.get('qc_passed_pcs'),
                'qc_passed_wt': row.get('qc_passed_wt'),
                'invoice_pcs': row.get('invoice_pcs'),
                'invoiced_wt': row.get('invoiced_wt'),
                'delivered_pcs': row.get('delivered_pcs'),
                'delivered_wt': row.get('delivered_wt'),
                'pending_to_deliver_pcs': row.get('pending_to_deliver_pcs'),
                'pending_to_deliver_wt': row.get('pending_to_deliver_wt'),
                'snapshot_date': today
            })
        
        db.session.bulk_insert_mappings(ShowroomWiseOrderSummarySnapshot, new_records)
        db.session.commit()
        
        emit('success', f'Showroom Wise Order Summary Sync completed! {len(rows)} records updated.', 100)
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"ShowroomWiseOrderSummary Sync error: {error_msg}")
        emit('error', f'Sync failed: {error_msg}', 0)
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_owner_and_showroom_wise_task() -> Dict[str, Any]:
    """Combined sync: runs Owner Wise Order Summary then Showroom Wise Order Summary in sequence."""
    TASK_TYPE = 'owner_showroom_combined'
    result_owner: Dict[str, Any] = {}
    result_showroom: Dict[str, Any] = {}
    
    try:
        emit_sync_update('processing', 'Starting combined Owner Wise & Showroom Wise Order Summary Sync...', 2, TASK_TYPE)

        # ── Step 1: Owner Wise ────────────────────────────────────────────
        emit_sync_update('processing', '[1/2] Syncing Owner Wise Order Summary...', 5, TASK_TYPE)
        result_owner = sync_owner_wise_data_task(task_type_override=TASK_TYPE, progress_range=(5, 45), is_subtask=True)
        if not result_owner or result_owner.get('status') == 'error':
            error_msg = result_owner.get('message') if result_owner else "Unknown error (result is None)"
            raise Exception(f"Owner Wise sync failed: {error_msg}")

        # ── Step 2: Showroom Wise ─────────────────────────────────────────
        emit_sync_update('processing', '[2/2] Syncing Showroom Wise Order Summary...', 45, TASK_TYPE)
        result_showroom = sync_showroom_wise_order_summary_task(task_type_override=TASK_TYPE, progress_range=(45, 90), is_subtask=True)
        if not result_showroom or result_showroom.get('status') == 'error':
            error_msg = result_showroom.get('message') if result_showroom else "Unknown error (result is None)"
            raise Exception(f"Showroom Wise sync failed: {error_msg}")

        # ── Step 3: Clear Cache ───────────────────────────────────────────
        emit_sync_update('processing', 'Clearing application cache...', 95, TASK_TYPE)
        try:
            redis_client.flushdb()
            cache_msg = "Application cache cleared."
        except Exception as ce:
            logger.error(f"Failed to clear cache during combined sync: {ce}")
            cache_msg = "Cache clear failed (sync succeeded)."

        owner_count = result_owner.get('count', 0)
        showroom_count = result_showroom.get('count', 0)
        emit_sync_update(
            'success',
            f'Combined sync completed! {cache_msg} (Owner: {owner_count}, Showroom: {showroom_count})',
            100, TASK_TYPE
        )
        return {"status": "success", "owner_count": owner_count, "showroom_count": showroom_count}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Combined OwnerWise+ShowroomWise Sync error: {error_msg}")
        emit_sync_update('error', f'Combined sync failed: {error_msg}', 0, TASK_TYPE)
        return {"status": "error", "message": error_msg}

def _provision_sync_producer(conn_params, data_queue, stop_event, batch_size, total_to_sync, shared_state):
    """Producer thread: Fetches data batches from Azure, with auto-resume support (duplication-safe)."""
    conn = None
    max_retries = 25
    retry_count = 0
    producer_offset = 0 # Track records successfully put into the queue
    query_template = """
        SELECT "division","group","location","branch_id","provision_mode","provision_mode_filter",
               "purity","classification","sub_classification","section","type","make","collection",
               "master_collection","sub_section","gender","wide_range","range_weight","size",
               "screw_type","prov_pieces","prov_gr_wt","prov_amount","stock_qty","stock_gr_wt",
               "stock_amount","in_shop_pcs","in_shop_wt","in_shop_amt","not_in_shop","in_transit",
               "order_only","req_only","in_transit_wt","order_only_wt","not_in_shop_wt","refill_from_qty",
               "refill_to_qty","refill_from_wt","refill_to_wt","prov_type_filter","short_pcs",
               "short_gr_wt","short_amt","short_percent","excess_pcs","excess_gr_weight","excess_amt",
               "not_in_prov_pcs","not_in_prov_gr_weight","not_in_prov_amt","prov_type",
               "branch_type","branch_status","business_head_name","business_head_emp_code",
               "state",
               "last_updated_at"
        FROM  ext_view.vw_prov_and_stock_size_level
        ORDER BY location, division, "group", purity, classification, sub_classification, 
                 section, type, make, collection, master_collection, sub_section, gender, 
                 wide_range, range_weight, size, screw_type, provision_mode, prov_type, 
                 last_updated_at
        LIMIT %s OFFSET %s;
    """

    while retry_count < max_retries and not stop_event.is_set():
        try:
            if retry_count > 0:
                logger.info(f"Retrying Provision Sync (Attempt {retry_count})... Resuming from PRODUCER offset {producer_offset}")
                time.sleep(5)  # Wait for connection to stabilize
            
            # 2. Chunked fetching loop: Continues until all records are fetched
            while producer_offset < total_to_sync and not stop_event.is_set():
                # Establish a FRESH connection for EVERY batch to prevent SSL/Duration timeouts
                conn = None
                try:
                    conn = get_external_db_connection()
                    with conn.cursor() as s_cur:
                        s_cur.execute("SET statement_timeout = 0")
                    
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    
                    # Fetch a specific block of data
                    cur.execute(query_template, (batch_size, producer_offset))
                    rows = cur.fetchall()
                    
                    if not rows:
                        break # End of data
                    
                    # Signal progress and move to next block
                    put_success = False
                    while not put_success and not stop_event.is_set():
                        try:
                            data_queue.put(rows, timeout=1)
                            producer_offset += len(rows) # Correctly update after successful put
                            put_success = True
                        except queue.Full:
                            continue
                finally:
                    if conn:
                        try: conn.close()
                        except: pass

            # If we reached the end, signal completion and exit producer
            # If we reached the end, signal completion and exit producer
            if producer_offset >= total_to_sync:
                # Block until there is space to signal EOF (up to 10 mins)
                data_queue.put(None, timeout=600)
                return # SUCCESSFUL PRODUCER EXIT
            
        except Exception as e:
            retry_count += 1
            error_trace = traceback.format_exc()
            logger.error(f"Provision Sync Error (Attempt {retry_count}): {e}\n{error_trace}")
            
            if retry_count >= max_retries:
                logger.error("Provision Sync: Max retries exceeded.")
                stop_event.set()
                try: data_queue.put(None, timeout=1)
                except: pass
                raise e

def _provision_sync_consumer(app, data_queue, stop_event, total_to_sync, data_type, shared_state, target_model=None):
    """Consumer thread: Processes rows and updates shared progress for resume capability."""
    try:
        with app.app_context():
            current_time = datetime.utcnow()
            while True:
                try:
                    rows = data_queue.get(timeout=1)
                except queue.Empty:
                    if stop_event.is_set():
                        break
                    continue
                
                if rows is None:
                    break # EOF
                
                if stop_event.is_set():
                    break
                
                batch_data = []
                for row in rows:
                    batch_data.append({
                        'division': row.get('division'),
                        'group_name': row.get('group'),
                        'location': row.get('location'),
                        'branch_id': row.get('branch_id'),
                        'branch_type': row.get('branch_type'),
                        'branch_status': row.get('branch_status'),
                        'business_head_name': row.get('business_head_name'),
                        'business_head_emp_code': row.get('business_head_emp_code'),
                        'provision_mode': row.get('provision_mode'),
                        'provision_mode_filter': row.get('provision_mode_filter'),
                        'purity': row.get('purity'),
                        'classification': row.get('classification'),
                        'sub_classification': row.get('sub_classification'),
                        'section': row.get('section'),
                        'type': row.get('type'),
                        'make': row.get('make'),
                        'collection': row.get('collection'),
                        'master_collection': row.get('master_collection'),
                        'sub_section': row.get('sub_section'),
                        'gender': row.get('gender'),
                        'wide_range': row.get('wide_range'),
                        'range_weight': row.get('range_weight'),
                        'size': row.get('size'),
                        'screw_type': row.get('screw_type'),
                        'prov_pieces': row.get('prov_pieces'),
                        'prov_gr_wt': row.get('prov_gr_wt'),
                        'prov_amount': row.get('prov_amount'),
                        'stock_qty': row.get('stock_qty'),
                        'stock_gr_wt': row.get('stock_gr_wt'),
                        'stock_amount': row.get('stock_amount'),
                        'in_shop_pcs': row.get('in_shop_pcs'),
                        'in_shop_wt': row.get('in_shop_wt'),
                        'in_shop_amt': row.get('in_shop_amt'),
                        'not_in_shop': row.get('not_in_shop'),
                        'in_transit': row.get('in_transit'),
                        'order_only': row.get('order_only'),
                        'req_only': row.get('req_only'),
                        'in_transit_wt': row.get('in_transit_wt'),
                        'order_only_wt': row.get('order_only_wt'),
                        'not_in_shop_wt': row.get('not_in_shop_wt'),
                        'refill_from_qty': row.get('refill_from_qty'),
                        'refill_to_qty': row.get('refill_to_qty'),
                        'refill_from_wt': row.get('refill_from_wt'),
                        'refill_to_wt': row.get('refill_to_wt'),
                        'prov_type_filter': row.get('prov_type_filter'),
                        'short_pcs': row.get('short_pcs'),
                        'short_gr_wt': row.get('short_gr_wt'),
                        'short_amt': row.get('short_amt'),
                        'short_percent': row.get('short_percent'),
                        'excess_pcs': row.get('excess_pcs'),
                        'excess_gr_weight': row.get('excess_gr_weight'),
                        'excess_amt': row.get('excess_amt'),
                        'not_in_prov_pcs': row.get('not_in_prov_pcs'),
                        'not_in_prov_gr_weight': row.get('not_in_prov_gr_weight'),
                        'not_in_prov_amt': row.get('not_in_prov_amt'),
                        'prov_type': row.get('prov_type'),
                        'state': row.get('state'),
                        'snapshot_date': row.get('last_updated_at') or current_time
                    })
                
                if target_model:
                    db.session.bulk_insert_mappings(target_model, batch_data)
                else:
                    db.session.bulk_insert_mappings(ProvisionStockRawSnapshot, batch_data)
                db.session.commit()
                
                shared_state['records_committed'] += len(rows)
                progress = 15 + int((shared_state['records_committed'] / total_to_sync) * 80)
                emit_sync_update('processing', f'Syncing... {shared_state["records_committed"]:,} / {total_to_sync:,} records...', progress, data_type)
            
            return shared_state['records_committed']
    except Exception as e:
        logger.error(f"Provision Sync Consumer Error: {e}")
        stop_event.set()
        raise e

def sync_provision_stock_status_data_task() -> Dict[str, Any]:
    """
    Synchronizes Provision & Stock Status data using a parallelized Producer-Consumer model.
    This avoids SSL connection timeouts by keeping the connection active during inserts.
    """
    conn = None
    BATCH_SIZE = 20000  # Reduced batch size for more consistent performance
    DATA_TYPE = 'provision_stock_status'
    
    try:
        emit_sync_update('processing', 'Starting Async Provision & Stock Status Sync...', 5, DATA_TYPE)

        conn = get_external_db_connection()
        
        # 1. Clear existing STAGING data (ensure clean slate)
        emit_sync_update('processing', 'Preparing staging area...', 10, DATA_TYPE)
        db.session.execute(text("TRUNCATE provision_stock_raw_staging"))
        db.session.commit()

        # 2. Get total count and sum for validation
        count_cur = conn.cursor()
        count_cur.execute('SELECT COUNT(*), SUM(prov_gr_wt) FROM ext_view.vw_prov_and_stock_size_level')
        source_stats = count_cur.fetchone()
        total_to_sync = source_stats[0]
        source_sum_wt = source_stats[1] or 0
        count_cur.close()
        
        logger.info(f"Provision Stock Sync: Source Total Count: {total_to_sync}, Source Sum Weight: {source_sum_wt}")
        
        # 3. Setup Named Cursor
        cur = conn.cursor(name='provision_stock_sync_cursor', cursor_factory=RealDictCursor)
        cur.itersize = 2000  # Optimal itersize for SSL stability and streaming
        
        # Set timeout on session before main query
        with conn.cursor() as s_cur:
            s_cur.execute("SET statement_timeout = 0")
        
        query = """
            SELECT "division","group","location","branch_id","provision_mode","provision_mode_filter",
                   "purity","classification","sub_classification","section","type","make","collection",
                   "master_collection","sub_section","gender","wide_range","range_weight","size",
                   "screw_type","prov_pieces","prov_gr_wt","prov_amount","stock_qty","stock_gr_wt",
                   "stock_amount","in_shop_pcs","in_shop_wt","in_shop_amt","not_in_shop","in_transit",
                   "order_only","req_only","in_transit_wt","order_only_wt","not_in_shop_wt","refill_from_qty",
                   "refill_to_qty","refill_from_wt","refill_to_wt","prov_type_filter","short_pcs",
                   "short_gr_wt","short_amt","short_percent","excess_pcs","excess_gr_weight","excess_amt",
                   "not_in_prov_pcs","not_in_prov_gr_weight","not_in_prov_amt","prov_type",
                   "branch_type","branch_status","business_head_name","business_head_emp_code",
                   "state",
                   "last_updated_at"
            FROM  ext_view.vw_prov_and_stock_size_level;
        """
        
        start_time = time.time()
        # Initial query call moved inside producer for resumability
        
        # 4. Initialize Threads and Queue
        data_queue = queue.Queue(maxsize=5) # Pre-load 5 batches ahead for zero-wait inserting
        stop_event = threading.Event()
        shared_state = {'records_committed': 0}
        app = current_app._get_current_object()
        
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Note: Producer now handles its own connection and cursor for resumability
            producer_future = executor.submit(_provision_sync_producer, None, data_queue, stop_event, BATCH_SIZE, total_to_sync, shared_state)
            consumer_future = executor.submit(_provision_sync_consumer, app, data_queue, stop_event, total_to_sync, DATA_TYPE, shared_state, ProvisionStockRawStaging)
            
            total_records = consumer_future.result()
            producer_future.result()

        # 5. ATOMIC SWAP: Move from staging to main
        emit_sync_update('processing', 'Finalizing sync (Atomic swap)...', 95, DATA_TYPE)
        try:
            # We use raw SQL for the fastest possible copy operation
            # TRUNCATE is faster than DELETE for large tables and resists locking issues
            db.session.execute(text("TRUNCATE provision_stock_raw_snapshot"))
            
            # Copy all columns from staging to main. 
            # We explicitly exclude the 'id' column if it's serial to avoid sequence issues, 
            # but here both have the same structure. In PG, 'autoincrement' means serial.
            # It's safer to specify columns or use SELECT * EXCLUDING if both are identical.
            # Since they are IDENTICAL, SELECT * is fine as long as we don't mind IDs changing.
            copy_query = """
                INSERT INTO provision_stock_raw_snapshot 
                (division, "group", location, branch_id, branch_type, branch_status, business_head_name, 
                business_head_emp_code, state, provision_mode, provision_mode_filter, classification, 
                sub_classification, section, type, make, collection, master_collection, sub_section, 
                gender, wide_range, size, screw_type, prov_type, purity, range_weight, prov_pieces, 
                prov_gr_wt, prov_amount, stock_qty, stock_gr_wt, stock_amount, in_shop_pcs, in_shop_wt, 
                in_shop_amt, not_in_shop, in_transit, order_only, req_only, in_transit_wt, order_only_wt, 
                not_in_shop_wt, refill_from_qty, refill_to_qty, refill_from_wt, refill_to_wt, 
                short_pcs, short_gr_wt, short_amt, short_percent, excess_pcs, excess_gr_weight, 
                excess_amt, not_in_prov_pcs, not_in_prov_gr_weight, not_in_prov_amt, prov_type_filter, 
                snapshot_date)
                SELECT 
                division, "group", location, branch_id, branch_type, branch_status, business_head_name, 
                business_head_emp_code, state, provision_mode, provision_mode_filter, classification, 
                sub_classification, section, type, make, collection, master_collection, sub_section, 
                gender, wide_range, size, screw_type, prov_type, purity, range_weight, prov_pieces, 
                prov_gr_wt, prov_amount, stock_qty, stock_gr_wt, stock_amount, in_shop_pcs, in_shop_wt, 
                in_shop_amt, not_in_shop, in_transit, order_only, req_only, in_transit_wt, order_only_wt, 
                not_in_shop_wt, refill_from_qty, refill_to_qty, refill_from_wt, refill_to_wt, 
                short_pcs, short_gr_wt, short_amt, short_percent, excess_pcs, excess_gr_weight, 
                excess_amt, not_in_prov_pcs, not_in_prov_gr_weight, not_in_prov_amt, prov_type_filter, 
                snapshot_date
                FROM provision_stock_raw_staging;
            """
            db.session.execute(text(copy_query))
            
            # Clean up staging table to save space
            db.session.execute(text("TRUNCATE provision_stock_raw_staging"))
            db.session.commit()
            
            logger.info("Atomic swap completed successfully.")
        except Exception as swap_error:
            db.session.rollback()
            logger.error(f"Atomic swap failed: {swap_error}")
            raise Exception(f"Finalizing sync failed: {swap_error}")

        # 6. Post-Sync Validation
        local_stats = db.session.query(
            db.func.count(ProvisionStockRawSnapshot.id),
            db.func.sum(ProvisionStockRawSnapshot.prov_gr_wt)
        ).first()
        
        local_count = local_stats[0] or 0
        local_sum_wt = float(local_stats[1] or 0)
        
        # Determine success vs discrepancy
        count_matched = (local_count == total_to_sync)
        # Using a small epsilon for float/decimal comparison if necessary, but here we expect exact match or identifiable loss
        sum_matched = (abs(float(local_sum_wt) - float(source_sum_wt)) < 0.001)

        if count_matched and sum_matched:
            emit_sync_update('success', f'Sync completed & validated! {total_records:,} records updated.', 100, DATA_TYPE)
        else:
            warn_msg = f"Sync finished with DISCREPANCY! Source: {total_to_sync} rows / {source_sum_wt} wt. Local: {local_count} rows / {local_sum_wt} wt."
            logger.warning(warn_msg)
            emit_sync_update('success', f'Sync finished with validation warnings. Please check logs.', 100, DATA_TYPE)

        return {"status": "success", "count": total_records, "validation": {"match": count_matched and sum_matched}}

    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"ProvisionStockStatus Async Sync Error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    finally:
        if conn: conn.close()

def sync_qc_delayed_data_task() -> Dict[str, Any]:
    """Sync QC Delayed data using the provided materialized CTE query."""
    conn = None
    DATA_TYPE = 'qc_delayed'
    try:
        emit_sync_update('processing', 'Starting QC Delayed Sync...', 5, DATA_TYPE)
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching QC data from Azure...', 20, DATA_TYPE)
        query = """
            WITH qc_base AS MATERIALIZED (
                SELECT
                    vod.order_id,
                    vqd.qc_ro_name AS Office,
                    vopd.make_owner,
                    vopd.collection_owner,
                    vopd.collection,
                    vod.supplier AS supplier,
                    1 AS pieces,
                    COALESCE(vod.barcoded_weight, vod.required_weight) AS weight,
                    COALESCE(vqd.qc_status_name, 'Pending') AS qc_completion_status,
                    vqd.qc_request_no,
                    vqd.qc_date,
                    vqd.qc_received_delivery_challan,
                    vqd.receipt_no,
                    vqd.qc_received_on,
                    vod.cancelled_on
                FROM ext_view.vw_order_details vod
                INNER JOIN ext_view.vw_order_product_details vopd
                    ON vopd.order_id = vod.order_id
                LEFT JOIN ext_view.vw_order_qc_details vqd
                    ON vqd.order_id = vod.order_id
                LEFT JOIN ext_view.vw_order_supplier_invoice_summary vosis
                    ON vosis.order_id = vod.order_id
                WHERE vqd.qc_received_on IS NOT NULL
                  AND vqd.qc_received_on < CURRENT_DATE - INTERVAL '3 days'
                  AND COALESCE(vqd.qc_status_name, 'Pending') = 'Pending'
            )
            SELECT
                order_id,
                Office,
                make_owner,
                collection_owner,
                collection,
                supplier,
                pieces,
                weight,
                qc_completion_status,
                qc_request_no,
                qc_date,
                qc_received_delivery_challan,
                receipt_no,
                qc_received_on,
                cancelled_on
            FROM qc_base
            WHERE cancelled_on IS NULL;
        """
        
        start_time = time.time()
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"QCDelayed query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local snapshot...', 60, DATA_TYPE)
        
        # Clear existing
        db.session.execute(text("TRUNCATE qc_delayed_snapshot"))
        
        new_records = []
        for row in rows:
            record = {
                'order_id': row.get('order_id'),
                'office': row.get('office'),
                'make_owner': row.get('make_owner'),
                'collection_owner': row.get('collection_owner'),
                'collection': row.get('collection'),
                'supplier': row.get('supplier'),
                'pieces': row.get('pieces'),
                'weight': row.get('weight'),
                'qc_completion_status': row.get('qc_completion_status'),
                'qc_request_no': row.get('qc_request_no'),
                'qc_date': row.get('qc_date'),
                'qc_received_delivery_challan': row.get('qc_received_delivery_challan'),
                'receipt_no': row.get('receipt_no'),
                'qc_received_on': row.get('qc_received_on'),
                'snapshot_date': date.today()
            }
            new_records.append(record)
        
        db.session.bulk_insert_mappings(QCDelayedSnapshot, new_records)
        db.session.commit()
        
        emit_sync_update('success', f'QC Delayed Sync completed! {len(rows)} records updated.', 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"QCDelayed Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_order_processing_pending_data_task():
    """Sync Order Processing Pending Report data from External Azure DB"""
    DATA_TYPE = 'order_processing_pending'
    
    emit_sync_update('processing', 'Fetching data from external source...', 10, DATA_TYPE)
    start_time = time.time()
    logger.info("Starting Order Processing Pending Data sync...")

    conn = get_external_db_connection()
    if not conn:
        error_msg = "Could not establish connection to external database"
        logger.error(f"OrderProcessingPending sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT 
            make_owner, collection_owner, collection, order_branch, party, po_date, po_number, 
            party, party_mobile_no, barcode_completion_date, barcoded_weight, 
            set_identifier, set_design_no, order_type, order_request_type, target_date, 
            pending_to_hallmark_issue_piece, pending_to_hallmark_issue_wt 
        FROM ext_view.vw_order_barcoding_completed_hm_issue_pending
        WHERE CURRENT_DATE - DATE(barcode_completion_date) > 1;
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            # Clear existing data
            db.session.execute(text("TRUNCATE TABLE order_processing_pending_snapshots"))
            db.session.commit()

            # Insert all records at once
            snapshot_date = datetime.now()
            objects = [
                OrderProcessingPendingSnapshot(
                    snapshot_date=snapshot_date,
                    make_owner=row[0],
                    collection_owner=row[1],
                    collection=row[2],
                    branch=row[3],
                    supplier=row[4],
                    po_date=row[5],
                    po_number=row[6],
                    # party (repeat) is row[7]
                    party_mobile_no=row[8],
                    barcode_completion_date=row[9],
                    barcoded_weight=row[10],
                    set_identifier=row[11],
                    set_design_no=row[12],
                    order_type=row[13],
                    order_request_type=row[14],
                    target_date=row[15],
                    pieces=row[16], # pending_to_hallmark_issue_piece
                    weight=row[17]  # pending_to_hallmark_issue_wt
                )
                for row in rows
            ]
            db.session.bulk_save_objects(objects)
            db.session.commit()
            emit_sync_update('processing', 'Local snapshot updated successfully.', 90, DATA_TYPE)

            duration = time.time() - start_time
            msg = f"Successfully synced {len(rows)} records in {duration:.2f}s"
            logger.info(msg)
            emit_sync_update('success', msg, 100, DATA_TYPE)
            return {"status": "success", "message": msg, "count": len(rows)}
        else:
            msg = "No data found for Order Processing Pending Report"
            logger.warning(msg)
            emit_sync_update('success', msg, 100, DATA_TYPE)
            return {"status": "success", "message": msg, "count": 0}

    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"OrderProcessingPending sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}
    finally:
        if cur: cur.close()
        if conn: conn.close()

def sync_hm_completed_return_data_task():
    DATA_TYPE = 'hm_return_pending'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"HMCompletedReturn sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT
            make_owner, collection_owner, collection, order_branch, party, po_date, po_number,
            order_type, order_request_type, party_mobile_no, barcode_completion_date,
            barcoded_weight, set_identifier, set_design_no, hm_request_no, hm_ro,
            hallmark_agent, hm_agent_email, hm_agent_pnone_no, hm_completed_at,
            hm_agent_invoice_receipt_no, hm_agent_invoice_receipt_date, net_weight,
            gross_weight, stone_weight, pending_to_hm_recipt_return_piece,
            pending_to_hm_recipt_return_wt, logistic_mobile_no, logistic_date, vehicle_no
        FROM ext_view.vw_hm_completed_return_pending
        WHERE CURRENT_DATE - DATE(hm_completed_at) > 1;
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE hm_completed_return_snapshots"))
            db.session.commit()

            snapshot_date = datetime.now()
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                objects = [
                    HMCompletedReturnSnapshot(
                        snapshot_date=snapshot_date,
                        make_owner=row[0],
                        collection_owner=row[1],
                        collection=row[2],
                        order_branch=row[3],
                        supplier=row[4],
                        po_date=row[5],
                        po_number=row[6],
                        order_type=row[7],
                        order_request_type=row[8],
                        party_mobile_no=row[9],
                        set_identifier=row[12],
                        set_design_no=row[13],
                        hm_ro=row[15],
                        hallmark_agent=row[16],
                        hm_agent_email=row[17],
                        hm_agent_pnone_no=row[18],
                        hm_completed_date=row[19],
                        hm_agent_invoice_receipt_no=row[20],
                        hm_agent_invoice_receipt_date=row[21],
                        net_weight=row[22],
                        gross_weight=row[23],
                        stone_weight=row[24],
                        pieces=row[25],
                        weight=row[26],
                        logistic_mobile_no=row[27],
                        logistic_date=row[28],
                        vehicle_no=row[29]
                    )
                    for row in batch
                ]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                
                progress = 40 + int(((i + len(batch)) / len(rows)) * 50)
                emit_sync_update('processing', f'Saving batch {i//batch_size + 1}...', progress, DATA_TYPE)

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_supplier_hm_issue_data_task():
    DATA_TYPE = 'supplier_hm_issue'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"SupplierHMIssue sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        # Query based on user provided view and columns
        query = """
        SELECT 
            make_owner, collection_owner, collection, order_branch, party, po_date, po_number, 
            order_type, order_request_type, party_mobile_no, 
            barcode_completion_date, barcoded_weight, set_identifier, set_design_no, 
            target_date, hm_ro, hallmark_agent, hm_agent_email, hm_agent_pnone_no, 
            hm_issue_receipt_no, hm_issue_receipt_date, net_weight, gross_weight, 
            stone_weight, business_head_name, hm_receipt_pending_pcs, hm_receipt_pending_wt
        FROM ext_view.vw_supplier_hm_issue_completed_hm_receipt_pending
        WHERE CURRENT_DATE - DATE(hm_issue_receipt_date) > 1
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            # Clear existing data
            db.session.execute(text("TRUNCATE TABLE supplier_hm_issue_snapshots"))
            db.session.commit()

            # Insert all records at once
            snapshot_date = datetime.now()
            objects = [
                SupplierHMIssueSnapshot(
                    snapshot_date=snapshot_date,
                    make_owner=row[0],
                    collection_owner=row[1],
                    collection=row[2],
                    order_branch=row[3],
                    supplier=row[4],
                    po_date=row[5],
                    po_number=row[6],
                    order_type=row[7],
                    order_request_type=row[8],
                    party_mobile_no=row[9],
                    barcode_completion_date=row[10],
                    barcoded_weight=row[11],
                    set_identifier=row[12],
                    set_design_no=row[13],
                    target_date=row[14],
                    hm_ro=row[15],
                    hallmark_agent=row[16],
                    hm_agent_email=row[17],
                    hm_agent_pnone_no=row[18],
                    hm_issue_receipt_no=row[19],
                    hm_issue_receipt_date=row[20],
                    net_weight=row[21],
                    gross_weight=row[22],
                    stone_weight=row[23],
                    business_head_name=row[24],
                    pieces=row[25] # hm_receipt_pending_pcs
                )
                for row in rows
            ]
            db.session.bulk_save_objects(objects)
            db.session.commit()
            emit_sync_update('processing', 'Local snapshot updated successfully.', 90, DATA_TYPE)

        duration = time.time() - start_time
        msg = f"Successfully synced {len(rows)} records in {duration:.2f}s"
        logger.info(msg)
        emit_sync_update('success', msg, 100, DATA_TYPE)
        return {"status": "success", "count": len(rows), "duration": duration}

    except Exception as e:
        db.session.rollback()
        error_msg = f"Sync failed: {str(e)}"
        logger.error(error_msg)
        emit_sync_update('error', error_msg, 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}
    finally:
        if conn:
            conn.close()

def sync_hm_return_qc_issue_data_task():
    DATA_TYPE = 'hm_qc_issue_pending'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"HMReturnQCIssue sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT 
            make_owner, collection_owner, collection, order_branch, party, po_date, po_number, 
            order_type, order_request_type, party_mobile_no, barcode_completion_date, 
            barcoded_weight, set_identifier, set_design_no, target_date, 
            hm_request_no, hm_ro, hallmark_agent, hm_agent_email, hm_agent_pnone_no, 
            hm_completed_at, hm_agent_invoice_receipt_no, hm_agent_invoice_receipt_date, 
            net_weight, gross_weight, stone_weight, pending_to_final_qc_issue_pcs, 
            pending_to_final_qc_issue_weight 
        FROM ext_view.vw_hm_return_received_qc_issue_pending
        WHERE CURRENT_DATE - DATE(hm_agent_invoice_receipt_date) > 1
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE hm_return_qc_issue_snapshots"))
            db.session.commit()

            snapshot_date = datetime.now()
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                objects = [
                    HMReturnQCIssueSnapshot(
                        snapshot_date=snapshot_date,
                        make_owner=row[0],
                        collection_owner=row[1],
                        collection=row[2],
                        order_branch=row[3],
                        party=row[4],
                        po_date=row[5],
                        po_number=row[6],
                        order_type=row[7],
                        order_request_type=row[8],
                        party_mobile_no=row[9],
                        barcode_completion_date=row[10],
                        barcoded_weight=row[11],
                        set_identifier=row[12],
                        set_design_no=row[13],
                        target_date=row[14],
                        hm_request_no=row[15],
                        hm_ro=row[16],
                        hallmark_agent=row[17],
                        hm_agent_email=row[18],
                        hm_agent_pnone_no=row[19],
                        hm_completed_at=row[20],
                        hm_agent_invoice_receipt_no=row[21],
                        hm_agent_invoice_receipt_date=row[22],
                        net_weight=row[23],
                        gross_weight=row[24],
                        stone_weight=row[25],
                        pieces=row[26], # pending_to_final_qc_issue_pcs
                        weight=row[27]   # pending_to_final_qc_issue_weight
                    )
                    for row in batch
                ]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                
                progress = 40 + int(((i + len(batch)) / len(rows)) * 50)
                emit_sync_update('processing', f'Saving batch {i//batch_size + 1}...', progress, DATA_TYPE)

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_supplier_qc_issue_receipt_pending_data_task():
    DATA_TYPE = 'supplier_qc_issue_receipt_pending'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"SupplierQCIssueReceiptPending sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT 
            make_owner, collection_owner, collection, order_branch, business_head_name, 
            party, po_date, po_number, order_type, order_request_type, 
            party_mobile_no, barcode_completion_date, barcoded_weight, 
            set_identifier, set_design_no, target_date, hm_request_no, 
            hm_ro, hallmark_agent, hm_agent_email, hm_agent_pnone_no, 
            hm_completed_at, qc_issue_receipt_no, qc_issue_receipt_date, 
            qc_ro, qc_ro_incharge, net_weight, gross_weight, stone_weight, 
            qc_pending_to_receipt_pcs, qc_pending_to_receipt_wt, po_number as order_no, set_design_no as design_no
        FROM ext_view.vw_supplier_qc_issue_completed_receipt_pending
        WHERE CURRENT_DATE - DATE(qc_issue_receipt_date) > 1;
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE supplier_qc_issue_receipt_pending_snapshots"))
            db.session.commit()

            snapshot_date = datetime.now()
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                objects = [
                    SupplierQCIssueReceiptPendingSnapshot(
                        snapshot_date=snapshot_date,
                        make_owner=row[0],
                        collection_owner=row[1],
                        collection=row[2],
                        order_branch=row[3],
                        business_head_name=row[4],
                        party=row[5],
                        po_date=row[6],
                        po_number=row[7],
                        order_type=row[8],
                        order_request_type=row[9],
                        party_mobile_no=row[10],
                        barcode_completion_date=row[11],
                        barcoded_weight=row[12],
                        set_identifier=row[13],
                        set_design_no=row[14],
                        target_date=row[15],
                        hm_request_no=row[16],
                        hm_ro=row[17],
                        hallmark_agent=row[18],
                        hm_agent_email=row[19],
                        hm_agent_pnone_no=row[20],
                        hm_completed_at=row[21],
                        qc_issue_receipt_no=row[22],
                        qc_issue_receipt_date=row[23],
                        qc_ro=row[24],
                        qc_ro_incharge=row[25],
                        net_weight=row[26],
                        gross_weight=row[27],
                        stone_weight=row[28],
                        pieces=row[29], # qc_pending_to_receipt_pcs
                        weight=row[30],  # qc_pending_to_receipt_wt
                        order_no=row[31],
                        design_no=row[32]
                    )
                    for row in batch
                ]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                
                progress = 40 + int(((i + len(batch)) / len(rows)) * 50)
                emit_sync_update('processing', f'Saving batch {i//batch_size + 1}...', progress, DATA_TYPE)

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_qc_completed_invoice_pending_data_task():
    DATA_TYPE = 'qc_completed_invoice_pending'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"QCCompletedInvoicePending sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT 
            make_owner, make, collection_owner, collection, order_branch, business_head_name, 
            party, po_date, po_number, order_type, order_request_type, 
            party_mobile_no, barcode_completion_date, barcoded_weight, 
            set_identifier, set_design_no, target_date, qc_issue_receipt_no, 
            qc_issue_receipt_date, qc_ro, qc_ro_incharge, final_qc_receipt_no, 
            final_qc_receipt_date, net_weight, gross_weight, stone_weight, 
            invoice_ro, is_qc_completed, qc_completed_date, 
            is_rate_requisition_completed, is_invoiced, 
            purchase_invoice_rate_requisition_number, 
            pending_to_invoice_pcs, pending_to_invoice_wt, design_no
        FROM ext_view.vw_qc_completed_invoice_pending
        WHERE CURRENT_DATE - DATE(qc_completed_date) > 1
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE qc_completed_invoice_pending_snapshots"))
            db.session.commit()

            snapshot_date = datetime.now()
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                objects = [
                    QCCompletedInvoicePendingSnapshot(
                        snapshot_date=snapshot_date,
                        make_owner=row[0],
                        make=row[1],
                        collection_owner=row[2],
                        collection=row[3],
                        order_branch=row[4],
                        business_head_name=row[5],
                        party=row[6],
                        po_date=row[7],
                        po_number=row[8],
                        order_type=row[9],
                        order_request_type=row[10],
                        party_mobile_no=row[11],
                        barcode_completion_date=row[12],
                        barcoded_weight=row[13],
                        set_identifier=row[14],
                        set_design_no=row[15],
                        target_date=row[16],
                        qc_issue_receipt_no=row[17],
                        qc_issue_receipt_date=row[18],
                        qc_ro=row[19],
                        qc_ro_incharge=row[20],
                        final_qc_receipt_no=row[21],
                        final_qc_receipt_date=row[22],
                        net_weight=row[23],
                        gross_weight=row[24],
                        stone_weight=row[25],
                        invoice_ro=row[26],
                        is_qc_completed=bool(row[27]) if row[27] is not None else False,
                        qc_completed_date=row[28],
                        is_rate_requisition_completed=bool(row[29]) if row[29] is not None else False,
                        is_invoiced=bool(row[30]) if row[30] is not None else False,
                        purchase_invoice_rate_requisition_number=row[31],
                        pieces=row[32], # pending_to_invoice_pcs
                        weight=row[33],  # pending_to_invoice_wt
                        design_no=row[34]
                    )
                    for row in batch
                ]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                
                progress = 40 + int(((i + len(batch)) / len(rows)) * 50)
                emit_sync_update('processing', f'Saving batch {i//batch_size + 1}...', progress, DATA_TYPE)

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_qc_completed_invoice_request_pending_data_task():
    DATA_TYPE = 'qc_completed_invoice_request_pending'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"QCCompletedInvoiceRequestPending sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT 
            order_id, order_no, qc_ro_id, qc_ro, qc_ro_incharge, qc_ro_incharge_email, 
            qc_ro_incharge_phone_no, make_owner, make, collection_owner, collection, 
            party, party_mobile_no, po_date, delivery_target_date, po_number, 
            order_type, order_request_type, design_no, set_identifier, set_design_no, 
            order_ro, order_branch, business_head_name, order_incharge_email, 
            order_incharge_phone_no, barcoded_weight, barcode_completion_date, 
            hm_completed_date, final_qc_receipt_no, final_qc_receipt_date, 
            qc_number, qc_completed_date, net_weight, gross_weight, stone_weight
        FROM ext_view.vw_qc_completed_invoice_request_pending
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE qc_completed_invoice_request_pending_snapshots"))
            db.session.commit()

            snapshot_date = datetime.now()
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                objects = [
                    QCCompletedInvoiceRequestPendingSnapshot(
                        snapshot_date=snapshot_date,
                        order_id=row[0],
                        order_no=row[1],
                        qc_ro_id=row[2],
                        qc_ro=row[3],
                        qc_ro_incharge=row[4],
                        qc_ro_incharge_email=row[5],
                        qc_ro_incharge_phone_no=row[6],
                        make_owner=row[7],
                        make=row[8],
                        collection_owner=row[9],
                        collection=row[10],
                        party=row[11],
                        party_mobile_no=row[12],
                        po_date=row[13],
                        delivery_target_date=row[14],
                        po_number=row[15],
                        order_type=row[16],
                        order_request_type=row[17],
                        design_no=row[18],
                        set_identifier=row[19],
                        set_design_no=row[20],
                        order_ro=row[21],
                        order_branch=row[22],
                        business_head_name=row[23],
                        order_incharge_email=row[24],
                        order_incharge_phone_no=row[25],
                        barcoded_weight=row[26],
                        barcode_completion_date=row[27],
                        hm_completed_date=row[28],
                        final_qc_receipt_no=row[29],
                        final_qc_receipt_date=row[30],
                        qc_number=row[31],
                        qc_completed_date=row[32],
                        net_weight=row[33],
                        gross_weight=row[34],
                        stone_weight=row[35]
                    )
                    for row in batch
                ]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                
                progress = 40 + int(((i + len(batch)) / len(rows)) * 50)
                emit_sync_update('processing', f'Saving batch {i//batch_size + 1}...', progress, DATA_TYPE)

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_invoice_completed_pending_deliver_data_task():
    DATA_TYPE = 'invoice_completed_pending_deliver'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"InvoiceCompletedPendingDeliver sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT 
            make_owner, make, collection_owner, collection, order_branch, business_head_name, 
            party, po_date, po_number, order_type, order_request_type, 
            party, party_mobile_no, barcode_completion_date, barcoded_weight, 
            set_identifier, set_design_no, order_type, order_request_type, target_date, 
            net_weight, gross_weight, stone_weight, is_invoiced, 
            purchase_invoice_rate_requisition_number, invoice_ro, invoice_no, 
            invoice_date, invoice_amount, pending_to_deliver_pcs, pending_to_deliver_wt
        FROM ext_view.vw_invoice_completed_pending_to_deliver
        WHERE invoice_date IS NOT NULL AND CURRENT_DATE - DATE(invoice_date) >= 1
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE invoice_completed_pending_deliver_snapshots"))
            db.session.commit()

            snapshot_date = datetime.now()
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                objects = [
                    InvoiceCompletedPendingDeliverSnapshot(
                        snapshot_date=snapshot_date,
                        make_owner=row[0],
                        make=row[1],
                        collection_owner=row[2],
                        collection=row[3],
                        order_branch=row[4],
                        business_head_name=row[5],
                        party=row[6],
                        po_date=row[7],
                        po_number=row[8],
                        order_type=row[9],
                        order_request_type=row[10],
                        # party (repeat) is row[11]
                        party_mobile_no=row[12],
                        barcode_completion_date=row[13],
                        barcoded_weight=row[14],
                        set_identifier=row[15],
                        set_design_no=row[16],
                        # order_type (repeat) is row[17]
                        # order_request_type (repeat) is row[18]
                        target_date=row[19],
                        net_weight=row[20],
                        gross_weight=row[21],
                        stone_weight=row[22],
                        is_invoiced=bool(row[23]) if row[23] is not None else False,
                        purchase_invoice_rate_requisition_number=row[24],
                        invoice_ro=row[25],
                        invoice_no=row[26],
                        invoice_date=row[27],
                        invoice_amount=row[28],
                        pieces=row[29], # pending_to_deliver_pcs
                        weight=row[30]   # pending_to_deliver_wt
                    )
                    for row in batch
                ]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                
                progress = 40 + int(((i + len(batch)) / len(rows)) * 50)
                emit_sync_update('processing', f'Saving batch {i//batch_size + 1}...', progress, DATA_TYPE)

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_branch_authority_data_task():
    DATA_TYPE = 'branch_authority'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"BranchAuthority sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT branch_id, emp_code FROM ext_view.vw_branch_authority_data"
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE branch_authority_snapshot"))
            db.session.commit()

            new_records = []
            for row in rows:
                new_records.append({
                    'branch_id': row.get('branch_id'),
                    'emp_code': row.get('emp_code')
                })
            
            db.session.bulk_insert_mappings(BranchAuthoritySnapshot, new_records)
            db.session.commit()

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_qc_delay_management_data_task():
    DATA_TYPE = 'qc_delay_management'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"QCDelayManagement sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT 
            qc_ro_id, qc_ro, qc_ro_code, 
            qc_issue_completed_receipt_pending_piece, qc_issue_completed_receipt_pending_weight, 
            delayed_qc_issue_completed_receipt_pending_piece, delayed_qc_issue_completed_receipt_pending_weight,
            qc_receipt_completed_qc_pending_piece, qc_receipt_completed_qc_pending_weight, 
            delayed_qc_receipt_completed_qc_pending_piece, delayed_qc_receipt_completed_qc_pending_weight,
            qc_completed_invoice_request_pending_piece, qc_completed_invoice_request_pending_weight,
            delayed_qc_completed_invoice_request_pending_piece, delayed_qc_completed_invoice_request_pending_weight,
            qc_ro_incharge, qc_ro_incharge_email, qc_ro_incharge_phone_number, qc_ro_address
        FROM ext_view.qc_summary_data
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE qc_delay_management_snapshots"))
            db.session.commit()

            snapshot_date = datetime.now()
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                objects = [
                    QCDelayManagementSnapshot(
                        snapshot_date=snapshot_date,
                        qc_ro_id=row[0],
                        qc_ro=row[1],
                        qc_ro_code=row[2],
                        qc_issue_completed_receipt_pending_piece=row[3],
                        qc_issue_completed_receipt_pending_weight=row[4],
                        delayed_qc_issue_completed_receipt_pending_piece=row[5],
                        delayed_qc_issue_completed_receipt_pending_weight=row[6],
                        qc_receipt_completed_qc_pending_piece=row[7],
                        qc_receipt_completed_qc_pending_weight=row[8],
                        delayed_qc_receipt_completed_qc_pending_piece=row[9],
                        delayed_qc_receipt_completed_qc_pending_weight=row[10],
                        qc_completed_invoice_request_pending_piece=row[11],
                        qc_completed_invoice_request_pending_weight=row[12],
                        delayed_qc_completed_invoice_request_pending_piece=row[13],
                        delayed_qc_completed_invoice_request_pending_weight=row[14],
                        qc_ro_incharge=row[15],
                        qc_ro_incharge_email=row[16],
                        qc_ro_incharge_phone_number=row[17],
                        qc_ro_address=row[18]
                    )
                    for row in batch
                ]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                
                progress = 40 + int(((i + len(batch)) / len(rows)) * 50)
                emit_sync_update('processing', f'Saving batch {i//batch_size + 1}...', progress, DATA_TYPE)

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_qc_receipt_completed_pending_data_task():
    DATA_TYPE = 'qc_receipt_completed_pending'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 10, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"QCReceiptCompletedQCPending sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        query = """
        SELECT 
            order_id, order_no, qc_ro_id, qc_ro, qc_ro_incharge, qc_ro_incharge_email, qc_ro_incharge_phone_no,
            make_owner, make, collection_owner, collection, party, party_mobile_no, po_date,
            delivery_target_date, po_number, order_type, order_request_type, design_no,
            set_identifier, set_design_no, order_ro, order_branch, business_head_name,
            order_incharge_email, order_incharge_phone_no, barcoded_weight, barcode_completion_date,
            hm_completed_date, qc_issue_challan_no, qc_issue_challan_date, receipt_no, receipt_date,
            net_weight, gross_weight, stone_weight
        FROM ext_view.vw_qc_receipt_completed_qc_pending
        """
        
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        logger.info(f"Fetched {len(rows)} rows from external DB in {time.time() - start_time:.2f}s")
        emit_sync_update('processing', f'Processing {len(rows)} records...', 40, DATA_TYPE)

        if rows:
            db.session.execute(text("TRUNCATE TABLE qc_receipt_completed_qc_pending_snapshots"))
            db.session.commit()

            snapshot_date = datetime.now()
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                objects = [
                    QCReceiptCompletedQCPendingSnapshot(
                        snapshot_date=snapshot_date,
                        order_id=row[0],
                        order_no=row[1],
                        qc_ro_id=row[2],
                        qc_ro=row[3],
                        qc_ro_incharge=row[4],
                        qc_ro_incharge_email=row[5],
                        qc_ro_incharge_phone_no=row[6],
                        make_owner=row[7],
                        make=row[8],
                        collection_owner=row[9],
                        collection=row[10],
                        party=row[11],
                        party_mobile_no=row[12],
                        po_date=row[13],
                        delivery_target_date=row[14],
                        po_number=row[15],
                        order_type=row[16],
                        order_request_type=row[17],
                        design_no=row[18],
                        set_identifier=row[19],
                        set_design_no=row[20],
                        order_ro=row[21],
                        order_branch=row[22],
                        business_head_name=row[23],
                        order_incharge_email=row[24],
                        order_incharge_phone_no=row[25],
                        barcoded_weight=row[26],
                        barcode_completion_date=row[27],
                        hm_completed_date=row[28],
                        qc_issue_challan_no=row[29],
                        qc_issue_challan_date=row[30],
                        receipt_no=row[31],
                        receipt_date=row[32],
                        net_weight=row[33],
                        gross_weight=row[34],
                        stone_weight=row[35],
                        weight=row[34], # Standard weight field (using gross_weight)
                        piece=1         # Standard piece field (default to 1 per row for this view)
                    )
                    for row in batch
                ]
                db.session.bulk_save_objects(objects)
                db.session.commit()
                
                progress = 40 + int(((i + len(batch)) / len(rows)) * 50)
                emit_sync_update('processing', f'Saving batch {i//batch_size + 1}...', progress, DATA_TYPE)

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced {len(rows)} records", 100, DATA_TYPE)
        return {"status": "success", "count": len(rows)}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()

def sync_hm_delay_management_data_task():
    DATA_TYPE = 'hm_delay_management'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 5, DATA_TYPE)
        conn = get_external_db_connection()
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        logger.error(f"HMDelayManagement sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, DATA_TYPE)
        return {"status": "error", "message": error_msg}

    try:
        cur = conn.cursor()
        
        # 1. Sync Summary Data
        emit_sync_update('processing', 'Fetching HM Summary data...', 10, DATA_TYPE)
        summary_query = """
        SELECT 
            hallmarking_center_id, hallmarking_center, hallmarking_center_code, 
            hm_issue_completed_receipt_pending_piece, hm_issue_completed_receipt_pending_weight, 
            hm_receipt_completed_hm_pending_piece, hm_receipt_completed_hm_pending_weight, 
            hm_completed_return_pending_piece, hm_completed_return_pending_weight
        FROM ext_view.hm_summary_data
        """
        cur.execute(summary_query)
        summary_rows = cur.fetchall()
        
        db.session.execute(text("TRUNCATE TABLE hm_delay_management_snapshots"))
        snapshot_date = datetime.now()
        summary_objects = [
            HallmarkingDelayManagementSnapshot(
                snapshot_date=snapshot_date,
                hallmarking_center_id=row[0],
                hallmarking_center=row[1],
                hallmarking_center_code=row[2],
                hm_issue_completed_receipt_pending_piece=row[3],
                hm_issue_completed_receipt_pending_weight=row[4],
                hm_receipt_completed_hm_pending_piece=row[5],
                hm_receipt_completed_hm_pending_weight=row[6],
                hm_completed_return_pending_piece=row[7],
                hm_completed_return_pending_weight=row[8]
            ) for row in summary_rows
        ]
        db.session.bulk_save_objects(summary_objects)
        db.session.commit()
        emit_sync_update('processing', 'Summary synced. Syncing Segment 1 details...', 30, DATA_TYPE)

        # 2. Segment 1 Details
        s1_query = """
        SELECT 
            orderid, make_owner, collection_owner, collection, order_ro, 
            order_branch, party, party_mobile_no, po_date, target_date, 
            po_number, order_type, order_request_type, order_no, required_weight, 
            design_no, set_identifier, set_design_no, barcode, is_barcoded, 
            is_supplier_hm_issue_challan_created, is_supplier_hm_issue_completed, 
            is_hm_agent_received, barcoded_weight, barcode_completion_date, 
            order_status, current_stage, hm_req_id, hm_issue_receipt_no, 
            hm_issue_receipt_date, hallmark_agent, hm_ro, hm_agent_email, 
            hm_agent_pnone_no, net_weight, gross_weight, stone_weight, 
            business_head_name, hm_receipt_pending_pcs, hm_receipt_pending_wt
        FROM ext_view.vw_supplier_hm_issue_completed_hm_receipt_pending
        """
        cur.execute(s1_query)
        s1_rows = cur.fetchall()
        db.session.execute(text("TRUNCATE TABLE supplier_hm_issue_receipt_pending_snapshots"))
        s1_objects = [
            SupplierHMIssueReceiptPendingSnapshot(
                snapshot_date=snapshot_date,
                orderid=row[0], make_owner=row[1], collection_owner=row[2], collection=row[3], order_ro=row[4],
                order_branch=row[5], party=row[6], party_mobile_no=row[7], po_date=row[8], target_date=row[9],
                po_number=row[10], order_type=row[11], order_request_type=row[12], order_no=row[13], required_weight=row[14],
                design_no=row[15], set_identifier=row[16], set_design_no=row[17], barcode=row[18], is_barcoded=row[19],
                is_supplier_hm_issue_challan_created=row[20], is_supplier_hm_issue_completed=row[21],
                is_hm_agent_received=row[22], barcoded_weight=row[23], barcode_completion_date=row[24],
                order_status=row[25], current_stage=row[26], hm_req_id=row[27], hm_issue_receipt_no=row[28],
                hm_issue_receipt_date=row[29], hallmarking_center=row[30], hm_ro=row[31], hm_agent_email=row[32],
                hm_agent_pnone_no=row[33], net_weight=row[34], gross_weight=row[35], stone_weight=row[36],
                business_head_name=row[37], hm_receipt_pending_pcs=row[38], hm_receipt_pending_wt=row[39]
            ) for row in s1_rows
        ]
        db.session.bulk_save_objects(s1_objects)
        db.session.commit()
        emit_sync_update('processing', 'Segment 1 details synced. Syncing Segment 2...', 60, DATA_TYPE)

        # 3. Segment 2 Details
        s2_query = """
        SELECT 
            order_id, order_no, hm_request_number, hm_request_date, hm_ro_id, 
            hm_ro, hm_ro_incharge, hm_ro_incharge_email, hm_ro_incharge_phone_no, 
            agent_name, hm_agent_phone_no, hm_agent_email, make_owner, make, 
            collection_owner, collection, party, party_mobile_no, po_date, 
            delivery_target_date, po_number, order_type, order_request_type, 
            design_no, set_identifier, set_design_no, order_ro, order_branch, 
            business_head_name, order_incharge_email, order_incharge_phone_no, 
            barcoded_weight, barcode_completion_date, supplier_issue_challan_no, 
            supplier_issue_challan_date, agent_received_receipt_no, 
            agent_received_receipt_date, net_weight, gross_weight, stone_weight
        FROM ext_view.vw_hm_receipt_completed_hm_pending
        """
        cur.execute(s2_query)
        s2_rows = cur.fetchall()
        db.session.execute(text("TRUNCATE TABLE hm_receipt_completed_hm_pending_snapshots"))
        s2_objects = [
            HMReceiptCompletedHMPendingSnapshot(
                snapshot_date=snapshot_date,
                order_id=row[0], order_no=row[1], hm_request_number=row[2], hm_request_date=row[3], hm_ro_id=row[4],
                hm_ro=row[5], hm_ro_incharge=row[6], hm_ro_incharge_email=row[7], hm_ro_incharge_phone_no=row[8],
                hallmarking_center=row[9], hm_agent_phone_no=row[10], hm_agent_email=row[11], make_owner=row[12], make=row[13],
                collection_owner=row[14], collection=row[15], party=row[16], party_mobile_no=row[17], po_date=row[18],
                delivery_target_date=row[19], po_number=row[20], order_type=row[21], order_request_type=row[22],
                design_no=row[23], set_identifier=row[24], set_design_no=row[25], order_ro=row[26], order_branch=row[27],
                business_head_name=row[28], order_incharge_email=row[29], order_incharge_phone_no=row[30],
                barcoded_weight=row[31], barcode_completion_date=row[32], supplier_issue_challan_no=row[33],
                supplier_issue_challan_date=row[34], agent_received_receipt_no=row[35],
                agent_received_receipt_date=row[36], net_weight=row[37], gross_weight=row[38], stone_weight=row[39]
            ) for row in s2_rows
        ]
        db.session.bulk_save_objects(s2_objects)
        db.session.commit()
        emit_sync_update('processing', 'Segment 2 details synced. Syncing Segment 3...', 80, DATA_TYPE)

        # 4. Segment 3 Details
        s3_query = """
        SELECT 
            order_id, make_owner, collection_owner, collection, order_ro, 
            order_branch, party, party_mobile_no, po_date, target_date, 
            po_number, order_type, order_request_type, order_no, required_weight, 
            design_no, set_identifier, set_design_no, barcode, is_hm_agent_received, 
            is_hallmark_completed, barcoded_weight, barcode_completion_date, 
            order_status, current_stage, hallmar_req_id, hm_request_no, 
            hallmark_agent, hallmark_status, hm_agent_invoice_receipt_no, 
            hm_agent_invoice_receipt_date, hm_ro, hm_agent_email, hm_agent_pnone_no, 
            hm_completed_at, hallmark_info_id, net_weight, gross_weight, 
            stone_weight, vehicle_no, logistic_mobile_no, logistic_date, 
            by_hand_name, pending_to_hm_recipt_return_piece, pending_to_hm_recipt_return_wt
        FROM ext_view.vw_hm_completed_return_pending
        """
        cur.execute(s3_query)
        s3_rows = cur.fetchall()
        db.session.execute(text("TRUNCATE TABLE hm_completed_return_pending_snapshots"))
        s3_objects = [
            HMCompletedReturnPendingSnapshot(
                snapshot_date=snapshot_date,
                order_id=row[0], make_owner=row[1], collection_owner=row[2], collection=row[3], order_ro=row[4],
                order_branch=row[5], party=row[6], party_mobile_no=row[7], po_date=row[8], target_date=row[9],
                po_number=row[10], order_type=row[11], order_request_type=row[12], order_no=row[13], required_weight=row[14],
                design_no=row[15], set_identifier=row[16], set_design_no=row[17], barcode=row[18], 
                is_hm_agent_received=row[19], is_hallmark_completed=row[20], 
                barcoded_weight=row[21], barcode_completion_date=row[22],
                order_status=row[23], current_stage=row[24], hallmar_req_id=row[25], hm_request_no=row[26],
                hallmarking_center=row[27], hallmark_status=row[28], hm_agent_invoice_receipt_no=row[29],
                hm_agent_invoice_receipt_date=row[30], hm_ro=row[31], hm_agent_email=row[32], hm_agent_pnone_no=row[33],
                hm_completed_at=row[34], hallmark_info_id=row[35], net_weight=row[36], gross_weight=row[37],
                stone_weight=row[38], vehicle_no=row[39], logistic_mobile_no=row[40], logistic_date=row[41],
                by_hand_name=row[42], pending_to_hm_recipt_return_piece=row[43], pending_to_hm_recipt_return_wt=row[44]
            ) for row in s3_rows
        ]
        db.session.bulk_save_objects(s3_objects)
        db.session.commit()

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced HM Delay Management data in {duration:.2f}s", 100, DATA_TYPE)
        return {"status": "success", "duration": duration}

    except Exception as e:
        db.session.rollback()
        logger.error(f"HMDelayManagement sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()
def sync_party_delay_management_data_task():
    DATA_TYPE = 'party_delay_management'
    start_time = time.time()
    conn = None
    try:
        emit_sync_update('processing', 'Connecting to external database...', 5, DATA_TYPE)
        conn = get_external_db_connection()
        cur = conn.cursor()
        
        # 1. Sync Summary Data
        emit_sync_update('processing', 'Fetching Party Summary data...', 10, DATA_TYPE)
        summary_query = """
        SELECT vod.supplier AS party,s.code AS party_code,'' AS address,
        COUNT(vod.order_id) FILTER (WHERE vod.order_status = 'Invited') AS pending_to_accept_pcs,
        COALESCE(SUM(vod.required_weight) FILTER (WHERE vod.order_status = 'Invited'),0) AS pending_to_accept_wt,
        COUNT(vod.order_id) FILTER (WHERE vod.order_status = 'Process Pending') AS process_pending_pieces,
        COALESCE(SUM(vod.required_weight) FILTER (WHERE vod.order_status = 'Process Pending'),0) AS process_pending_weight,
        COUNT(vod.order_id) FILTER (WHERE vod.order_status = 'Barcode Pending') AS accepted_and_barcode_pending_piece,
        COALESCE(SUM(vod.required_weight) FILTER (WHERE vod.order_status = 'Barcode Pending'),0) AS accepted_and_barcode_pending_weight,
        COUNT(vod.order_id) FILTER (WHERE vod.order_status in ('Packing Pending','Bundle Pending',
        'Initial QC Challan Pending','Initial QC Issue Pending',
        'Initial QC Receipt Pending','Initial QC Pending','Initial QC Correction Pending','Initial QC Failed',
        'Initial QC Test Cut Completed','HM Packing Pending','HM Request Pending','HM Request Initiated',
        'Initial QC Receipt Return Challan Pending','Initial QC Receipt Return Pending',
        'Initial QC Issue Return Pending','HM Challan Pending','HM Issue Pending')) AS barcoded_and_hm_issue_pending_piece,
        COALESCE(SUM(vod.required_weight) FILTER (WHERE vod.order_status in ('Packing Pending','Bundle Pending',
        'Initial QC Challan Pending','Initial QC Issue Pending',
        'Initial QC Receipt Pending','Initial QC Pending','Initial QC Correction Pending','Initial QC Failed',
        'Initial QC Test Cut Completed','HM Packing Pending','HM Request Pending','HM Request Initiated',
        'Initial QC Receipt Return Challan Pending','Initial QC Receipt Return Pending',
        'Initial QC Issue Return Pending','HM Challan Pending','HM Issue Pending')),0) AS barcoded_and_hm_issue_pending_weight,
        COUNT(vod.order_id) FILTER (WHERE vod.order_status in ('Final QC Packing Pending','QC Issue Pending')) AS hm_receipt_completed_and_qc_issue_pending_piece,
        COALESCE(SUM(vod.required_weight) FILTER (WHERE vod.order_status in ('Final QC Packing Pending','QC Issue Pending')),0) AS hm_receipt_completed_and_qc_issue_pending_weight,
        COUNT(vod.order_id) FILTER (WHERE vod.order_status = 'Invoice Approval Pending') AS invoice_request_completed_and_invoice_pending_piece,
        COALESCE(SUM(vod.required_weight) FILTER (WHERE vod.order_status = 'Invoice Approval Pending'),0) AS invoice_request_completed_and_invoice_pending_weight
        FROM ext_view.vw_order_details vod
        INNER JOIN ext_view.vw_supplier s ON s.supplier_id = vod.supplier_id
        GROUP BY vod.supplier,s.code;
        """
        cur.execute(summary_query)
        summary_rows = cur.fetchall()
        
        db.session.execute(text("TRUNCATE TABLE party_delay_management_snapshots"))
        snapshot_date = datetime.now()
        summary_objects = [
            PartyDelayManagementSnapshot(
                snapshot_date=snapshot_date,
                party=row[0],
                party_code=row[1],
                address=row[2],
                pending_to_accept_pcs=row[3],
                pending_to_accept_wt=row[4],
                process_pending_pieces=row[5],
                process_pending_weight=row[6],
                accepted_and_barcode_pending_piece=row[7],
                accepted_and_barcode_pending_weight=row[8],
                barcoded_and_hm_issue_pending_piece=row[9],
                barcoded_and_hm_issue_pending_weight=row[10],
                hm_receipt_completed_and_qc_issue_pending_piece=row[11],
                hm_receipt_completed_and_qc_issue_pending_weight=row[12],
                invoice_request_completed_and_invoice_pending_piece=row[13],
                invoice_request_completed_and_invoice_pending_weight=row[14]
            ) for row in summary_rows
        ]
        db.session.bulk_save_objects(summary_objects)
        db.session.commit()
        emit_sync_update('processing', 'Summary synced. Syncing Segment 1 details...', 20, DATA_TYPE)

        # 2. Segment 1 Details (Accept Pending)
        s1_query = "SELECT make_owner, collection_owner, collection, order_branch, po_date, po_number, party, party_mobile_no, set_identifier, set_design_no, order_type, order_request_type, target_date, business_head_name, business_head_phone_number, barcoded_weight, required_weight, order_status, stone_weight, net_weight, order_no FROM ext_view.vw_invited_order_details"
        try:
            cur.execute(s1_query)
            s1_rows = cur.fetchall()
            db.session.execute(text("TRUNCATE TABLE party_accept_pending_snapshots"))
            s1_objects = [PartyAcceptPendingSnapshot(snapshot_date=snapshot_date, **dict(zip([c.name for c in PartyAcceptPendingSnapshot.__table__.columns if c.name not in ['id', 'snapshot_date', 'updated_at']], row))) for row in s1_rows]
            db.session.bulk_save_objects(s1_objects)
            db.session.commit()
        except Exception as e:
            raise Exception(f"Segment 1 (vw_invited_order_details) failed: {str(e)}")
        emit_sync_update('processing', 'Segment 1 synced. Syncing Segment 2...', 35, DATA_TYPE)

        # 3. Segment 2 Details (Process Pending)
        s2_query = "SELECT make_owner, collection_owner, collection, order_branch, po_date, po_number, party, party_mobile_no, set_identifier, set_design_no, order_type, order_request_type, target_date, business_head_name, business_head_phone_number, barcoded_weight, required_weight, order_status, stone_weight, net_weight, order_no FROM ext_view.vw_process_pending_order_details"
        try:
            cur.execute(s2_query)
            s2_rows = cur.fetchall()
            db.session.execute(text("TRUNCATE TABLE party_process_pending_snapshots"))
            s2_objects = [PartyProcessPendingSnapshot(snapshot_date=snapshot_date, **dict(zip([c.name for c in PartyProcessPendingSnapshot.__table__.columns if c.name not in ['id', 'snapshot_date', 'updated_at']], row))) for row in s2_rows]
            db.session.bulk_save_objects(s2_objects)
            db.session.commit()
        except Exception as e:
            raise Exception(f"Segment 2 (vw_process_pending_order_details) failed: {str(e)}")
        emit_sync_update('processing', 'Segment 2 synced. Syncing Segment 3...', 50, DATA_TYPE)

        # 4. Segment 3 Details (Barcode Pending)
        s3_query = "SELECT make_owner, collection_owner, collection, order_branch, po_date, po_number, party, party_mobile_no, set_identifier, set_design_no, order_type, order_request_type, target_date, business_head_name, business_head_phone_number, barcoded_weight, required_weight, order_status, stone_weight, net_weight, order_no FROM ext_view.vw_barcode_pending_order_details"
        try:
            cur.execute(s3_query)
            s3_rows = cur.fetchall()
            db.session.execute(text("TRUNCATE TABLE party_barcode_pending_snapshots"))
            s3_objects = [PartyBarcodePendingSnapshot(snapshot_date=snapshot_date, **dict(zip([c.name for c in PartyBarcodePendingSnapshot.__table__.columns if c.name not in ['id', 'snapshot_date', 'updated_at']], row))) for row in s3_rows]
            db.session.bulk_save_objects(s3_objects)
            db.session.commit()
        except Exception as e:
            raise Exception(f"Segment 3 (vw_barcode_pending_order_details) failed: {str(e)}")
        emit_sync_update('processing', 'Segment 3 synced. Syncing Segment 4...', 65, DATA_TYPE)

        # 5. Segment 4 Details (HM Issue Pending)
        s4_query = "SELECT make_owner, collection_owner, collection, order_branch, po_date, po_number, party, party_mobile_no, set_identifier, set_design_no, order_type, order_request_type, target_date, barcoded_weight, required_weight, order_status, stone_weight, net_weight, order_no FROM ext_view.vw_order_barcoding_completed_hm_issue_pending"
        try:
            cur.execute(s4_query)
            s4_rows = cur.fetchall()
            db.session.execute(text("TRUNCATE TABLE party_hm_issue_pending_snapshots"))
            s4_objects = [PartyHMIssuePendingSnapshot(snapshot_date=snapshot_date, **dict(zip([c.name for c in PartyHMIssuePendingSnapshot.__table__.columns if c.name not in ['id', 'snapshot_date', 'updated_at']], row))) for row in s4_rows]
            db.session.bulk_save_objects(s4_objects)
            db.session.commit()
        except Exception as e:
            raise Exception(f"Segment 4 (vw_order_barcoding_completed_hm_issue_pending) failed: {str(e)}")
        emit_sync_update('processing', 'Segment 4 synced. Syncing Segment 5...', 80, DATA_TYPE)

        # 6. Segment 5 Details (QC Issue Pending)
        s5_query = "SELECT order_id, make_owner, collection_owner, collection, order_ro, order_branch, party, party_mobile_no, po_date, target_date, po_number, order_type, order_request_type, order_no, required_weight, design_no, set_identifier, set_design_no, barcode, is_hm_agent_received, barcoded_weight, barcode_completion_date, order_status, current_stage, hallmar_req_id, hm_request_no, hallmark_agent, hallmark_status, hm_ro, hm_agent_email, hm_agent_pnone_no, hm_completed_at, hallmark_info_id, net_weight, gross_weight, stone_weight, business_head_name, hm_agent_invoice_receipt_no, hm_agent_invoice_receipt_date, pending_to_final_qc_issue_pcs, pending_to_final_qc_issue_weight FROM ext_view.vw_hm_return_received_qc_issue_pending"
        try:
            cur.execute(s5_query)
            s5_rows = cur.fetchall()
            db.session.execute(text("TRUNCATE TABLE party_qc_issue_pending_snapshots"))
            s5_objects = [PartyHMReceiptCompletedQCIssuePendingSnapshot(snapshot_date=snapshot_date, **dict(zip([c.name for c in PartyHMReceiptCompletedQCIssuePendingSnapshot.__table__.columns if c.name not in ['id', 'snapshot_date', 'updated_at']], row))) for row in s5_rows]
            db.session.bulk_save_objects(s5_objects)
            db.session.commit()
        except Exception as e:
            raise Exception(f"Segment 5 (vw_hm_return_received_qc_issue_pending) failed: {str(e)}")
        emit_sync_update('processing', 'Segment 5 synced. Syncing Segment 6...', 90, DATA_TYPE)

        # 7. Segment 6 Details (Invoice Pending)
        s6_query = "SELECT order_id, order_no, qc_ro_id, qc_ro, qc_ro_incharge, qc_ro_incharge_email, qc_ro_incharge_phone_no, make_owner, make, collection_owner, collection, party, party_mobile_no, po_date, delivery_target_date, po_number, order_type, order_request_type, design_no, set_identifier, set_design_no, order_ro, order_branch, business_head_name, order_incharge_email, order_incharge_phone_no, barcoded_weight, barcode_completion_date, hm_completed_date, final_qc_receipt_no, final_qc_receipt_date, net_weight, gross_weight, stone_weight, invoice_request_number, invoice_request_date FROM ext_view.vw_invoice_request_completed_invoice_pending"
        try:
            cur.execute(s6_query)
            s6_rows = cur.fetchall()
            db.session.execute(text("TRUNCATE TABLE party_invoice_pending_snapshots"))
            s6_objects = [PartyInvoiceRequestCompletedInvoicePendingSnapshot(snapshot_date=snapshot_date, **dict(zip([c.name for c in PartyInvoiceRequestCompletedInvoicePendingSnapshot.__table__.columns if c.name not in ['id', 'snapshot_date', 'updated_at']], row))) for row in s6_rows]
            db.session.bulk_save_objects(s6_objects)
            db.session.commit()
        except Exception as e:
            raise Exception(f"Segment 6 (vw_invoice_request_completed_invoice_pending) failed: {str(e)}")

        duration = time.time() - start_time
        emit_sync_update('success', f"Successfully synced Party Delay Management data in {duration:.2f}s", 100, DATA_TYPE)
        return {"status": "success", "duration": duration}

    except Exception as e:
        db.session.rollback()
        logger.error(f"PartyDelayManagement sync failed: {str(e)}")
        emit_sync_update('error', str(e), 0, DATA_TYPE)
        return {"status": "error", "message": str(e)}
    finally:
        if conn: conn.close()
