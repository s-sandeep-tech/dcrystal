from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE pending_acceptance_feedback_snapshot ADD COLUMN accepted_wt NUMERIC(18, 3)"))
        db.session.commit()
        print("Column accepted_wt added successfully.")
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()
