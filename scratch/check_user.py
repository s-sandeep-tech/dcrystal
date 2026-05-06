
import sys
import os
sys.path.append('/Users/sandeeps/Documents/DCrystal/server')

from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    user = User.query.filter_by(user_id='U001').first()
    if user:
        print(f"User U001 found. Username: {user.username}")
    else:
        print("User U001 not found.")
