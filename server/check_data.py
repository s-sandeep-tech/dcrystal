from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    result = db.session.execute(text("SELECT source_location, target_location FROM allocated_barcodes_snapshot LIMIT 5"))
    for row in result:
        print(f"Source: {row[0]}, Target: {row[1]}")
