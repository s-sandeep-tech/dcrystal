import sys
from app import create_app
from app.extensions import db
from app.models.snapshots import PendingAcceptanceAction

app = create_app()
with app.app_context():
    try:
        a = PendingAcceptanceAction(collection_owner="test", action_type="CONTINUE", action_data=[{"weight": 1.5, "delivery_date": "2026-03-30"}], username="test")
        db.session.add(a)
        db.session.commit()
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {e}")
        db.session.rollback()
