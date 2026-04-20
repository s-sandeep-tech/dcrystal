from app import create_app
from app.extensions import db
from app.models.snapshots import ProvisionStockRawSnapshot, ProvisionStockRawStaging
from app.utils.sync_tasks import sync_provision_stock_status_data_task

app = create_app()
with app.app_context():
    print("Checking models...")
    print(f"ProvisionStockRawSnapshot table: {ProvisionStockRawSnapshot.__tablename__}")
    print(f"ProvisionStockRawStaging table: {ProvisionStockRawStaging.__tablename__}")
    
    # Check if we can access the columns
    print(f"Snapshot columns: {len(ProvisionStockRawSnapshot.__table__.columns)}")
    print(f"Staging columns: {len(ProvisionStockRawStaging.__table__.columns)}")
    
    if len(ProvisionStockRawSnapshot.__table__.columns) == len(ProvisionStockRawStaging.__table__.columns):
        print("Column counts match!")
    else:
        print(f"WARNING: Column counts mismatch! Snapshot: {len(ProvisionStockRawSnapshot.__table__.columns)}, Staging: {len(ProvisionStockRawStaging.__table__.columns)}")

    print("Success: Models and sync task imported correctly.")
