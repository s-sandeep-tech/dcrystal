from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    columns = inspector.get_columns('allocated_barcodes_snapshot')
    for col in columns:
        print(f"Column: {col['name']}, Type: {col['type']}")
