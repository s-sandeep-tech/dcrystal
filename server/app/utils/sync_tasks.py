import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any
from app.extensions import db, socketio, redis_client
from app.models.snapshots import (
    OwnerWiseOrderSummarySnapshot, 
    PartyProcessAgeingSnapshot,
    OutstandingPurchaseOrderStatusSnapshot,
    StageLevelDelaySnapshot,
    OrderDelayTrackingSnapshot,
    PendingAcceptanceSnapshot,
    RejectedWeightSnapshot,
    ShowroomWiseOrderSummarySnapshot,
    ProvisionStockRawSnapshot,
    HallmarkingDelayedSnapshot,
    QCDelayedSnapshot
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
        db.session.query(HallmarkingDelayedSnapshot).delete()
        
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
        db.session.query(ShowroomWiseOrderSummarySnapshot).delete()
        
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
    max_retries = 5
    retry_count = 0
    producer_offset = 0 # Track records successfully put into the queue
    
    query_template = """
        SELECT "division","group","location","provision_mode","provision_mode_filter",
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
        ORDER BY location, division, "group", purity, classification, make, collection, size, last_updated_at
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

def _provision_sync_consumer(app, data_queue, stop_event, total_to_sync, data_type, shared_state):
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
    BATCH_SIZE = 25000  # Reduced batch size for more consistent performance
    DATA_TYPE = 'provision_stock_status'
    
    try:
        emit_sync_update('processing', 'Starting Async Provision & Stock Status Sync...', 5, DATA_TYPE)
        conn = get_external_db_connection()
        
        # 1. Clear existing data
        emit_sync_update('processing', 'Clearing existing local snapshots...', 10, DATA_TYPE)
        db.session.query(ProvisionStockRawSnapshot).delete()
        db.session.commit()

        # 2. Get total count
        count_cur = conn.cursor()
        count_cur.execute('SELECT COUNT(*) FROM ext_view.vw_prov_and_stock_size_level')
        total_to_sync = count_cur.fetchone()[0]
        count_cur.close()
        
        # 3. Setup Named Cursor
        cur = conn.cursor(name='provision_stock_sync_cursor', cursor_factory=RealDictCursor)
        cur.itersize = 2000  # Optimal itersize for SSL stability and streaming
        
        # Set timeout on session before main query
        with conn.cursor() as s_cur:
            s_cur.execute("SET statement_timeout = 0")
        
        query = """
            SELECT "division","group","location","provision_mode","provision_mode_filter",
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
            consumer_future = executor.submit(_provision_sync_consumer, app, data_queue, stop_event, total_to_sync, DATA_TYPE, shared_state)
            
            total_records = consumer_future.result()
            producer_future.result()

        duration = time.time() - start_time
        logger.info(f"ProvisionStockStatus Async Sync (Resumable) took {duration:.2f} seconds for {total_records} records.")
        emit_sync_update('success', f'Sync completed! {total_records:,} records updated in {int(duration)}s.', 100, DATA_TYPE)
        
        return {"status": "success", "count": total_records}

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
        db.session.query(QCDelayedSnapshot).delete()
        
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
