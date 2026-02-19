import psycopg2
from psycopg2.extras import RealDictCursor
from app.extensions import db
from app.models.snapshots import OwnerWiseOrderSummarySnapshot
from flask import current_app
import os

def get_external_db_connection():
    """Establishes a connection to the external Azure PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host="kj-az1-prod1-crystal-psql-db2.postgres.database.azure.com",
            database="crystal",
            user="repo_user_ext",
            password="KjPGReportUserAz@26",
            port=5432,
            sslmode="require"
        )
        return conn
    except Exception as e:
        current_app.logger.error(f"Failed to connect to external DB: {str(e)}")
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
                    supplier=row.get('Supplier'),
                    batch=row.get('Batch'),
                    division=row.get('Division'),
                    group_name=row.get('Group'),
                    purity=row.get('Purity'),
                    classification=row.get('Classification'),
                    make=row.get('Make'),
                    collection=row.get('Collection'),
                    classification_owner=row.get('Classification Owner'),
                    collection_owner=row.get('Collection Owner'),
                    make_owner=row.get('Make Owner'),
                    ordered_pcs=row.get('Ordered Pcs'),
                    ordered_wt=row.get('Ordered Wt'),
                    accepted_pcs=row.get('Accepted Pcs'),
                    accepted_wt=row.get('Accepted Wt'),
                    rejected_pcs=row.get('Rejected Pcs'),
                    rejected_wt=row.get('Rejected Wt'),
                    barcoded_pcs=row.get('Barcoded Pcs'),
                    barcoded_wt=row.get('Barcoded Wt'),
                    not_barcoded_pcs=row.get('Not Barcod Pcs'),
                    not_barcoded_wt=row.get('Not Barcode Wt'),
                    hm_processed_pcs=row.get('Hm Processed Pcs'),
                    hm_passed_pcs=row.get('Hm Passed Pcs'),
                    hm_passed_wt=row.get('Hm Passed Wt'),
                    hm_failed_pcs=row.get('Hm Failed Pcs'),
                    hm_failed_wt=row.get('Hm Failed Wt'),
                    qc_processed_pcs=row.get('Qc Processed Pcs'),
                    qc_pending_pcs=row.get('Qc Pending Pcs'),
                    qc_pending_wt=row.get('Qc Pending Wt'),
                    qc_rejected_pcs=row.get('Qc Rejected Pcs'),
                    qc_rejected_wt=row.get('Qc Rejected Wt'),
                    qc_passed_pcs=row.get('Qc Passed Pcs'),
                    qc_passed_wt=row.get('Qc Passed Wt'),
                    invoiced_pcs=row.get('Invoiced Pcs'),
                    invoiced_wt=row.get('Invoiced Wt'),
                    delivered_pcs=row.get('Delivered Pcs'),
                    delivered_wt=row.get('Delivered Wt'),
                    pending_to_be_delv_pcs=row.get('Pending To Be Delv. Pcs'),
                    pending_to_be_delv_wt=row.get('Pending To Be Delv. Wt')
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
