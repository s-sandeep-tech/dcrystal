import psycopg2
from psycopg2.extras import RealDictCursor
from app.extensions import db, socketio, redis_client
from app.models.snapshots import (
    OwnerWiseOrderSummarySnapshot, 
    PartyProcessAgeingSnapshot,
    OutstandingPurchaseOrderStatusSnapshot
)
from flask import current_app
import os
import time
import json
import logging
import socket

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
    except Exception as e:
        logger.error(f"Failed to publish sync update to Redis: {e}")

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

def sync_owner_wise_data_task():
    conn = None
    try:
        emit_sync_update('processing', 'Starting Owner Wise Order Summary Sync...', 5, 'owner_wise')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching data from Azure PostgreSQL...', 20, 'owner_wise')
        query = "SELECT * FROM ext_view.vw_ownership_wise_order_summary_with_order_type"
        
        start_time = time.time()
        # Ensure session doesn't time out for this specific slow query
        cur.execute("SET statement_timeout = 0")
        cur.execute(query)
        rows = cur.fetchall()
        duration = time.time() - start_time
        
        logger.info(f"OwnerWise query took {duration:.2f} seconds.")
        emit_sync_update('processing', f'Fetched {len(rows)} records in {int(duration)}s. Updating local database...', 50, 'owner_wise')
        
        # Clear existing
        db.session.query(OwnerWiseOrderSummarySnapshot).delete()
        
        # Insert new
        new_records = []
        for row in rows:
            record = OwnerWiseOrderSummarySnapshot(
                supplier=row.get('supplier'),
                batch=row.get('batch'),
                division=row.get('division'),
                group_name=row.get('group'),
                purity=row.get('purity'),
                classification=row.get('classification'),
                make=row.get('make'),
                collection=row.get('collection'),
                order_request_type=row.get('order_request_type'),
                order_type=row.get('order_type'),
                order_date=row.get('order_date'),
                order_ro=row.get('order_ro'),
                classification_owner=row.get('classification_owner'),
                collection_owner=row.get('collection_owner'),
                make_owner=row.get('make_owner'),
                ordered_pcs=row.get('order_qty'),
                ordered_wt=row.get('order_wt'),
                accepted_pcs=row.get('accepted_pcs'),
                accepted_wt=row.get('accepted_wt'),
                rejected_pcs=row.get('rejected_pcs'),
                rejected_wt=row.get('rejected_wt'),
                barcoded_pcs=row.get('barcoded_pcs'),
                barcoded_wt=row.get('barcoded_wt'),
                not_barcoded_pcs=row.get('not_barcoded_pcs'),
                not_barcoded_wt=row.get('not_barcoded_wt'),
                hm_processed_pcs=row.get('hm_processed_pcs'),
                hm_passed_pcs=row.get('hm_passed_pcs'),
                hm_passed_wt=row.get('hm_passed_wt'),
                hm_failed_pcs=row.get('hm_failed_pcs'),
                hm_failed_wt=row.get('hm_failed_wt'),
                qc_processed_pcs=row.get('qc_processed_pcs'),
                qc_pending_pcs=row.get('qc_pending_pcs'),
                qc_pending_wt=row.get('qc_pending_wt'),
                qc_rejected_pcs=row.get('qc_reject_pcs'),
                qc_rejected_wt=row.get('qc_reject_wt'),
                qc_passed_pcs=row.get('qc_passed_pcs'),
                qc_passed_wt=row.get('qc_passed_wt'),
                invoiced_pcs=row.get('invoice_pcs'),
                invoiced_wt=row.get('invoiced_wt'),
                delivered_pcs=row.get('delivered_pcs'),
                delivered_wt=row.get('delivered_wt'),
                pending_to_be_delv_pcs=row.get('pending_to_deliver_pcs'),
                pending_to_be_delv_wt=row.get('pending_to_deliver_wt')
            )
            new_records.append(record)
        
        db.session.add_all(new_records)
        db.session.commit()
        
        emit_sync_update('success', f'Sync completed! {len(rows)} records updated.', 100, 'owner_wise')
        return {"status": "success", "count": len(rows)}
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        logger.error(f"OwnerWise Sync error: {error_msg}")
        emit_sync_update('error', f'Sync failed: {error_msg}', 0, 'owner_wise')
        return {"status": "error", "message": error_msg}
    finally:
        if conn: conn.close()

def sync_process_level_delay_data_task():
    conn = None
    try:
        emit_sync_update('processing', 'Starting Process Level Delay Sync...', 5, 'process_delay')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching analytical data from Azure...', 20, 'process_delay')
        query = """
          WITH
            qc_agg AS (
              SELECT order_id, MAX(qc_completed_at)::date AS qc_date, 
              CASE WHEN BOOL_OR(qc_status_name = 'Passed') THEN 'Passed' ELSE 'Not Passed' END AS qc_status
              FROM ext_view.vw_order_qc_details GROUP BY order_id
            ),
            hm_agg AS (
              SELECT order_id, MAX(hm_out_date)::date AS hallmark_date,
              CASE WHEN BOOL_OR(hm_status = 'Passed') THEN 'Passed' ELSE 'Not Passed' END AS hallmark_status
              FROM ext_view.vw_order_hallmark_details GROUP BY order_id
            ),
            base AS (
              SELECT od.order_id, od.supplier AS party_name, od.order_status,
                od.order_date::date AS order_date, od.accepted_on::date AS accepted_date,
                od.barcoded_at::date AS barcoded_date, h.hallmark_date, h.hallmark_status,
                q.qc_date, q.qc_status
              FROM ext_view.vw_order_details od
              LEFT JOIN qc_agg q ON q.order_id = od.order_id
              LEFT JOIN hm_agg h ON h.order_id = od.order_id
            ),
            status_rows AS (
              SELECT order_id, party_name, 'Order Accepted' AS completed_process_level, accepted_date AS last_completed_date FROM base WHERE accepted_date IS NOT NULL
              UNION ALL SELECT order_id, party_name, 'Barcoded', barcoded_date FROM base WHERE barcoded_date IS NOT NULL
              UNION ALL SELECT order_id, party_name, 'Hallmark Completed', hallmark_date FROM base WHERE hallmark_date IS NOT NULL AND hallmark_status = 'Passed'
              UNION ALL SELECT order_id, party_name, 'QC Completed', qc_date FROM base WHERE qc_date IS NOT NULL AND qc_status = 'Passed'
              UNION ALL SELECT order_id, party_name, 'Invoiced', COALESCE(qc_date, hallmark_date, barcoded_date, accepted_date, order_date) FROM base WHERE order_status ILIKE '%Invoice Approved%' OR order_status ILIKE '%RO Received%'
              UNION ALL SELECT order_id, party_name, 'Delivered', COALESCE(qc_date, hallmark_date, barcoded_date, accepted_date, order_date) FROM base WHERE order_status ILIKE '%RO Received%'
            ),
            stage_flow AS (
              SELECT * FROM (VALUES
                ('Order Accepted',     'Barcoded',           'Barcoding', 1),
                ('Barcoded',           'Hallmark Completed', 'Hallmark',  2),
                ('Hallmark Completed', 'QC Completed',       'QC',        3),
                ('QC Completed',       'Invoiced',           'Invoice',   4),
                ('Invoiced',           'Delivered',          'Delivery',  5),
                ('Delivered',          NULL,                'Completed', 6)
              ) AS t(curr_stage, next_stage, next_process_level, seq)
            ),
            joined AS (
              SELECT c.order_id, c.party_name, c.completed_process_level AS completed_process, c.last_completed_date AS completed_date,
                f.next_stage, f.next_process_level AS next_process, f.seq, n.last_completed_date AS next_completed_date,
                (CURRENT_DATE - c.last_completed_date) AS days_waiting
              FROM status_rows c JOIN stage_flow f ON f.curr_stage = c.completed_process_level
              LEFT JOIN status_rows n ON n.order_id = c.order_id AND n.completed_process_level = f.next_stage WHERE c.last_completed_date IS NOT NULL
            )
            SELECT party_name, completed_process AS completed_process_level, COUNT(DISTINCT order_id) AS completed_quantity, next_process AS next_process_level,
              COUNT(DISTINCT order_id) FILTER (WHERE next_stage IS NOT NULL AND next_completed_date IS NULL) AS "Pending Qty",
              COUNT(DISTINCT order_id) FILTER (WHERE next_stage IS NOT NULL AND next_completed_date IS NULL AND days_waiting BETWEEN 1 AND 2) AS "Window 1-2",
              COUNT(DISTINCT order_id) FILTER (WHERE next_stage IS NOT NULL AND next_completed_date IS NULL AND days_waiting BETWEEN 3 AND 4) AS "Window 3-4",
              COUNT(DISTINCT order_id) FILTER (WHERE next_stage IS NOT NULL AND next_completed_date IS NULL AND days_waiting > 4) AS "Window 4+"
            FROM joined GROUP BY party_name, completed_process, next_process, seq ORDER BY party_name, seq
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
                time_window_more_than_4_days=row.get('Window 4+'),
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

def sync_outstanding_purchase_order_data_task():
    conn = None
    try:
        emit_sync_update('processing', 'Starting Outstanding PO Sync...', 5, 'outstanding_po')
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        emit_sync_update('processing', 'Fetching PO data from Azure...', 20, 'outstanding_po')
        query = """
          SELECT od.supplier AS party, od.order_no AS order_number, od.order_date AS order_date,
            opd.classification, opd.classification_owner, opd.make, opd.make_owner, opd.collection, opd.collection_owner, opd.section,
            od.division, opd."group", opd.purity, od.order_ro AS purchase_ro,
            CASE WHEN inv.order_receipt_created_at IS NOT NULL THEN 'Y' ELSE 'N' END AS receipt_present,
            COUNT(*) AS order_pieces, SUM(od.required_weight) AS order_weight,
            COUNT(*) FILTER (WHERE od.accepted_on IS NOT NULL AND od.rejected_on IS NULL) AS accepted_pieces,
            SUM(od.required_weight) FILTER (WHERE od.accepted_on IS NOT NULL AND od.rejected_on IS NULL) AS accepted_weight
          FROM ext_view.vw_order_details od JOIN ext_view.vw_order_product_details opd ON opd.order_id = od.order_id
          LEFT JOIN ext_view.vw_order_supplier_invoice_summary inv ON inv.order_id = od.order_id
          GROUP BY od.supplier, od.order_no, od.order_date, opd.classification, opd.classification_owner, opd.make, opd.make_owner, opd.collection, opd.collection_owner, opd.section, od.division, opd."group", opd.purity, od.order_ro, receipt_present
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
