from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    if 'location_wise_order_snapshot' not in inspector.get_table_names():
        print("Creating tables...")
        db.create_all()
        print("Table 'location_wise_order_snapshot' created.")
    else:
        print("Table 'location_wise_order_snapshot' already exists.")
    
    columns = [c['name'] for c in inspector.get_columns('location_wise_order_snapshot')]
    print(f"Columns: {columns}")
