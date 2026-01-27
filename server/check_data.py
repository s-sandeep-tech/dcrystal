from app import create_app
from app.extensions import db
from app.models import LocationWiseStockSnapshot
from sqlalchemy import func

app = create_app()

with app.app_context():
    count = db.session.query(LocationWiseStockSnapshot).count()
    print(f"Total Rows in LocationWiseStockSnapshot: {count}")
    
    if count > 0:
        latest_date = db.session.query(func.max(LocationWiseStockSnapshot.snapshot_date)).scalar()
        print(f"Latest Snapshot Date: {latest_date}")
        
        sample = db.session.query(LocationWiseStockSnapshot).first()
        print(f"Sample Row: {sample.to_dict() if sample else 'None'}")
    else:
        print("NO DATA IN TABLE")
