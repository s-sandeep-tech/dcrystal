
import os
os.environ['SQLALCHEMY_DATABASE_URI'] = "postgresql+psycopg2://meetaccess:meetpass@localhost:5433/dcrystaldb"

from app import create_app
from app.extensions import db
from app.models import User
from sqlalchemy import text

def setup_test_users():
    app = create_app()
    with app.app_context():
        # Sync sequence
        db.session.execute(text("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users) + 1)"))
        db.session.commit()
        
        # Setup Admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(user_id='U001', username='admin', email='admin@example.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            print("Created admin user.")
        else:
            admin.user_id = 'U001'
            admin.is_admin = True
            admin.set_password('admin123')
            print("Updated admin user.")
            
        # Setup Test User (Rama)
        # Note: If 'Rama' exists but with different casing, filter_by might fail or match multiple.
        # Let's check for 'Rama' exactly as in 'Make Owner'
        test_user = User.query.filter_by(username='Rama').first()
        if not test_user:
            test_user = User(user_id='U002', username='Rama', email='rama@example.com', is_admin=False)
            test_user.set_password('user123')
            db.session.add(test_user)
            print("Created test user 'Rama'.")
        else:
            test_user.user_id = 'U002'
            test_user.is_admin = False
            test_user.set_password('user123')
            print("Updated test user 'Rama'.")
            
        db.session.commit()
        print("Test users setup complete.")

if __name__ == "__main__":
    setup_test_users()
