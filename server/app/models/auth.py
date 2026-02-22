from app.extensions import db
from datetime import datetime
from passlib.hash import bcrypt

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationships
    roles = db.relationship('Role', secondary='user_role', backref=db.backref('users', lazy='dynamic'))

    def set_password(self, password):
        self.password_hash = bcrypt.hash(password)

    def check_password(self, password):
        return bcrypt.verify(password, self.password_hash)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'is_admin': self.is_admin,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'roles': [r.name for r in self.roles]
        }
