import sys
import os

# Add the server directory to the path so we can import app
sys.path.append('/app')

from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Tables in DB: {tables}")
    
    if 'location_wise_stock_snapshot' in tables:
        print("\nColumns in 'location_wise_stock_snapshot':")
        columns = inspector.get_columns('location_wise_stock_snapshot')
        for column in columns:
            print(f"- {column['name']} ({column['type']})")
        
        # Try a raw SQL query to see data
        result = db.session.execute("SELECT * FROM location_wise_stock_snapshot LIMIT 1").fetchone()
        print(f"\nSample Raw row: {result}")
    else:
        print("Table 'location_wise_stock_snapshot' DOES NOT EXIST.")
