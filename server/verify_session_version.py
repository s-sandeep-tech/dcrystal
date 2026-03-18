from app import create_app
from app.extensions import db
from app.models.auth import User
import os

# Set the DB URI for the host if not set
if not os.getenv('SQLALCHEMY_DATABASE_URI'):
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://meetaccess:meetpass@localhost:5433/dcrystaldb'

app = create_app()

def verify():
    with app.app_context():
        # 1. Check if the column exists in the database
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('users')]
        if 'session_version' in columns:
            print("✓ SUCCESS: 'session_version' column found in 'users' table.")
        else:
            print("✗ ERROR: 'session_version' column NOT found in 'users' table.")
            return

        # 2. Check a user's session version
        user = User.query.filter_by(username='admin').first()
        if not user:
            print("✗ ERROR: Admin user not found.")
            return
        
        initial_version = user.session_version
        print(f"Initial session version for admin: {initial_version}")
        
        # 3. Simulate password change
        print("Simulating password change for admin...")
        user.set_password('admin123')
        user.session_version += 1
        db.session.commit()
        
        updated_user = User.query.filter_by(username='admin').first()
        new_version = updated_user.session_version
        print(f"Updated session version for admin: {new_version}")
        
        if new_version == initial_version + 1:
            print("✓ SUCCESS: Session version incremented correctly.")
        else:
            print(f"✗ ERROR: Session version did not increment correctly (expected {initial_version + 1}, got {new_version}).")

if __name__ == "__main__":
    try:
        verify()
    except Exception as e:
        print(f"✗ ERROR: Verification failed with exception: {e}")
