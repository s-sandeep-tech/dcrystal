import psycopg2
from psycopg2.extras import RealDictCursor
from app.extensions import db
from app.models.snapshots import OwnerWiseOrderSummarySnapshot, PartyProcessAgeingSnapshot
from flask import current_app
import os
import socket
import time

def get_external_db_connection():
    """Establishes a connection to the external Azure PostgreSQL database."""
    host = "kj-az1-prod1-crystal-psql-db2.postgres.database.azure.com"
    ip_fallback = "10.150.76.133" # IP from user's successful manual test
    
    try:
        # Diagnostic: Log env vars (filtered for security)
        env_info = {k: v for k, v in os.environ.items() if "PROXY" in k.upper() or "HOST" in k.upper() or "ADDR" in k.upper()}
        current_app.logger.info(f"Environment Info (Partial): {env_info}")

        # Diagnostic: Try to resolve host via socket first
        target_host = host
        try:
            ip = socket.gethostbyname(host)
            current_app.logger.info(f"DNS Resolve Success: {host} -> {ip}")
        except Exception as dns_e:
            current_app.logger.error(f"DNS Resolve Failure for {host}: {str(dns_e)}")
            current_app.logger.info(f"Falling back to IP: {ip_fallback} for host {host}")
            target_host = ip_fallback
            
        conn = psycopg2.connect(
            host=target_host,
            database="crystal",
            user="repo_user_ext",
            password="KjPGReportUserAz@26",
            port=5432,
            sslmode="require",
            connect_timeout=10
        )
        return conn
    except Exception as e:
        current_app.logger.error(f"Failed to connect to external DB ({host}): {str(e)}")
        raise e

def sync_owner_wise_data():
    """
    Syncs data from ext_view.vw_ownership_wise_order_summary 
     to owner_wise_order_summary_snapshot table.
    Performs a full replacement (Delete & Insert).
    """
    conn = None
    try:
        current_app.logger.info("Starting external data sync for OwnerWiseOrderSummary...")
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Fetch data from external view
        query = "SELECT * FROM ext_view.vw_ownership_wise_order_summary_with_order_type"
        cur.execute(query)
        external_data = cur.fetchall()
        
        if not external_data:
            current_app.logger.warning("No data found in external view.")
            return {"status": "success", "count": 0, "message": "No data found to sync."}

        # Use a transaction for the local update
        try:
            # Clear local table
            db.session.query(OwnerWiseOrderSummarySnapshot).delete()
            
            # Map and insert new records
            new_records = []
            for row in external_data:
                # Mapping dictionary based on model definition
                # db.Column('Supplier', db.Text, primary_key=True) -> mapped to property 'supplier'
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
            
            current_app.logger.info(f"Sync complete. {len(new_records)} records synced.")
            return {"status": "success", "count": len(new_records)}
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Local database error during sync: {str(e)}")
            raise e
            
    except Exception as e:
        current_app.logger.error(f"Sync failed: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        if conn:
            conn.close()

def sync_process_level_delay_data():
    """
    Syncs data from external Azure PostgreSQL using the provided query
    to party_process_ageing_snapshot table.
    """
    conn = None
    try:
        current_app.logger.info("Starting external data sync for PartyProcessAgeingSnapshot...")
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
          WITH qc_agg AS (
            SELECT
              order_id,
              MAX(qc_completed_at)::date AS qc_date
            FROM ext_view.vw_order_qc_details
            GROUP BY order_id
          ),
          hm_agg AS (
            SELECT
              order_id,
              MAX(hm_out_date)::date AS hallmark_date,
              -- If any record is Passed, treat as Passed (adjust if your logic differs)
              CASE WHEN BOOL_OR(hm_status = 'Passed') THEN 'Passed' ELSE 'Not Passed' END AS hallmark_status
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
              q.qc_date
            FROM ext_view.vw_order_details od
            LEFT JOIN qc_agg q ON q.order_id = od.order_id
            LEFT JOIN hm_agg h ON h.order_id = od.order_id
          ),
          status_rows AS (
            SELECT DISTINCT order_id, party_name,
              'Order Accepted' AS completed_process_level,
              accepted_date    AS last_completed_date
            FROM base
            WHERE accepted_date IS NOT NULL

            UNION ALL
            SELECT DISTINCT order_id, party_name,
              'Barcoded', barcoded_date
            FROM base
            WHERE barcoded_date IS NOT NULL

            UNION ALL
            SELECT DISTINCT order_id, party_name,
              'Hallmark Completed', hallmark_date
            FROM base
            WHERE hallmark_date IS NOT NULL
              AND hallmark_status = 'Passed'

            UNION ALL
            SELECT DISTINCT order_id, party_name,
              'QC Completed', qc_date
            FROM base
            WHERE qc_date IS NOT NULL

            UNION ALL
            SELECT DISTINCT order_id, party_name,
              'Invoiced',
              COALESCE(qc_date, hallmark_date, barcoded_date, accepted_date, order_date)
            FROM base
            WHERE order_status ILIKE '%invoice%'

            UNION ALL
            SELECT DISTINCT order_id, party_name,
              'Delivered',
              COALESCE(qc_date, hallmark_date, barcoded_date, accepted_date, order_date)
            FROM base
            WHERE order_status ILIKE '%deliver%'
          ),
          stage_flow AS (
            SELECT * FROM (VALUES
              ('Order Accepted',     'Barcoding', 1),
              ('Barcoded',           'Hallmark',  2),
              ('Hallmark Completed', 'QC',        3),
              ('QC Completed',       'Invoice',   4),
              ('Invoiced',           'Delivery',  5),
              ('Delivered',          'Completed', 6)
            ) AS t(completed_process_level, next_process_level, seq)
          )
          SELECT
            s.party_name,
            s.completed_process_level,
            COUNT(*) AS completed_quantity,
            f.next_process_level,

            COUNT(*) FILTER (
              WHERE s.last_completed_date IS NOT NULL
                AND (CURRENT_DATE - s.last_completed_date) BETWEEN 1 AND 2
            ) AS "Time Window 1-2days",

            COUNT(*) FILTER (
              WHERE s.last_completed_date IS NOT NULL
                AND (CURRENT_DATE - s.last_completed_date) BETWEEN 3 AND 4
            ) AS "Time Window 2-4days",

            COUNT(*) FILTER (
              WHERE s.last_completed_date IS NOT NULL
                AND (CURRENT_DATE - s.last_completed_date) > 4
            ) AS "Time Window-morethan 4 days"

          FROM status_rows s
          JOIN stage_flow f
            ON f.completed_process_level = s.completed_process_level
          GROUP BY s.party_name, s.completed_process_level, f.next_process_level, f.seq
          ORDER BY s.party_name, f.seq;
        """
        
        cur.execute(query)
        external_data = cur.fetchall()
        
        if not external_data:
            current_app.logger.warning("No data found for Process Level Delay.")
            return {"status": "success", "count": 0, "message": "No data found to sync."}

        try:
            # Clear local table
            db.session.query(PartyProcessAgeingSnapshot).delete()
            
            new_records = []
            for row in external_data:
                record = PartyProcessAgeingSnapshot(
                    party_name=row.get('party_name'),
                    completed_process_level=row.get('completed_process_level'),
                    completed_quantity=row.get('completed_quantity'),
                    next_process_level=row.get('next_process_level'),
                    time_window_1_2_days=row.get('Time Window 1-2days'),
                    time_window_2_4_days=row.get('Time Window 2-4days'),
                    time_window_more_than_4_days=row.get('Time Window-morethan 4 days'),
                    report_date=db.func.current_date()
                )
                new_records.append(record)
            
            db.session.add_all(new_records)
            db.session.commit()
            
            current_app.logger.info(f"Process Level Delay Sync complete. {len(new_records)} records synced.")
            return {"status": "success", "count": len(new_records)}
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Local database error during process delay sync: {str(e)}")
            raise e
            
    except Exception as e:
        current_app.logger.error(f"Process Level Delay Sync failed: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        if conn:
            conn.close()

def sync_outstanding_purchase_order_data():
    """
    Syncs data for the Outstanding Purchase Order Status Report
    to outstanding_purchase_order_status_snapshot table.
    Performs a full replacement (Delete & Insert).
    """
    from app.models.snapshots import OutstandingPurchaseOrderStatusSnapshot
    
    conn = None
    try:
        current_app.logger.info("Starting external data sync for OutstandingPurchaseOrderStatusSnapshot...")
        conn = get_external_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT
    od.supplier              AS party,
    od.order_no              AS order_number,
    od.order_date            AS order_date,

    opd.classification       AS classification,
    opd.classification_owner AS classification_owner,

    opd.make                 AS make,
    opd.make_owner           AS make_owner,

    opd.collection           AS collection,
    opd.collection_owner     AS collection_owner,

    opd.section              AS section,

    -- Optional fields (include only if present in view)
    opd.division             AS division,
    opd."group"              AS "group",
    opd.purity               AS purity,

    od.order_ro              AS purchase_ro,

    CASE
        WHEN inv.order_receipt_created_at IS NOT NULL THEN 'Y'
        ELSE 'N'
    END                      AS receipt_present,

    COUNT(*)                 AS order_pieces,
    SUM(od.required_weight)  AS order_weight,

    COUNT(*) FILTER (
        WHERE od.accepted_on IS NOT NULL
          AND od.rejected_on IS NULL
    )                         AS accepted_pieces,

    SUM(od.required_weight) FILTER (
        WHERE od.accepted_on IS NOT NULL
          AND od.rejected_on IS NULL
    )                         AS accepted_weight

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
    CASE WHEN inv.order_receipt_created_at IS NOT NULL THEN 'Y' ELSE 'N' END;
        """
        
        cur.execute(query)
        external_data = cur.fetchall()
        
        if not external_data:
            current_app.logger.warning("No data found for Outstanding Purchase Order sync.")
            return {"status": "success", "count": 0, "message": "No data found to sync."}

        try:
            # Clear local table
            db.session.query(OutstandingPurchaseOrderStatusSnapshot).delete()
            
            new_records = []
            for row in external_data:
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
            
            current_app.logger.info(f"Outstanding Purchase Order Sync complete. {len(new_records)} records synced.")
            return {"status": "success", "count": len(new_records)}
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Local database error during outstanding PO sync: {str(e)}")
            raise e
            
    except Exception as e:
        current_app.logger.error(f"Outstanding PO Sync failed: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        if conn:
            conn.close()
