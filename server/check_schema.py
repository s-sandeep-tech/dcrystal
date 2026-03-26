from app import create_app
from app.extensions import db
from app.models import ShowroomWiseOrderSummarySnapshot
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('showroom_wise_order_summary_snapshot')]
    print(f"Columns: {columns}")
    if 'branch_type' in columns:
        print("branch_type column EXISTS")
    else:
        print("branch_type column MISSING")
