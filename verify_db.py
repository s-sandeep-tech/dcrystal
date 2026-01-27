import sys
import os

# Add the server directory to the path so we can import app
sys.path.append('/Users/sandeeps/Documents/DCrystal/server')

from app import create_app
from app.extensions import db
from app.models import LocationWiseStockSnapshot
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Tables in DB: {tables}")
    
    if 'location_wise_stock_snapshot' in tables:
        print("Table 'location_wise_stock_snapshot' EXISTS.")
        count = db.session.query(LocationWiseStockSnapshot).count()
        print(f"Row count: {count}")
    else:
        print("Table 'location_wise_stock_snapshot' DOES NOT EXIST.")
