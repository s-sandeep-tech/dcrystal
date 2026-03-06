from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        # Check if the column already exists
        result = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='pending_acceptance_feedback' AND column_name='feedback_category'
        """)).fetchone()
        
        if not result:
            db.session.execute(text("ALTER TABLE pending_acceptance_feedback ADD COLUMN feedback_category VARCHAR(100)"))
            db.session.commit()
            print("Column 'feedback_category' added successfully to 'pending_acceptance_feedback'.")
        else:
            print("Column 'feedback_category' already exists.")
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()
