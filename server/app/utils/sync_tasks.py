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
        # ... (query omitted for space, assuming it's identified by the next line)
        
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
        # ... (query omitted)
        
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
