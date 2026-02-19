import psycopg2
from psycopg2.extras import RealDictCursor
from app.extensions import db
from app.models.snapshots import OwnerWiseOrderSummarySnapshot
from flask import current_app
import os
import socket
import time

def get_external_db_connection():
    """Establishes a connection to the external Azure PostgreSQL database."""
    host = "kj-az1-prod1-crystal-psql-db2.postgres.database.azure.com"
    try:
        # Diagnostic: Try to resolve host via socket first
        try:
            ip = socket.gethostbyname(host)
            current_app.logger.info(f"DNS Resolve Success: {host} -> {ip}")
        except Exception as dns_e:
            current_app.logger.error(f"DNS Resolve Failure for {host}: {str(dns_e)}")
            # Even if socket.gethostbyname fails, psycopg2 might have its own resolution path
            # but this gives us a clear indicator in logs.
            
        conn = psycopg2.connect(
            host=host,
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
        query = "SELECT * FROM ext_view.vw_ownership_wise_order_summary"
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
