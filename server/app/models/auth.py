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
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Security fields
    failed_attempt_count = db.Column(db.Integer, default=0)
    last_failed_at = db.Column(db.DateTime, nullable=True)
    lockout_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True) # 45 for IPv6 support
    session_version = db.Column(db.Integer, default=0, nullable=False)
    
    # Password reset fields
    must_reset_password = db.Column(db.Boolean, default=False)
    last_reset_initiated_at = db.Column(db.DateTime, nullable=True)
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
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'roles': [r.name for r in self.roles],
            'failed_attempt_count': self.failed_attempt_count,
            'lockout_until': self.lockout_until.isoformat() if self.lockout_until else None,
            'must_reset_password': self.must_reset_password,
            'last_reset_initiated_at': self.last_reset_initiated_at.isoformat() if self.last_reset_initiated_at else None
        }

class LoginAttemptLog(db.Model):
    __tablename__ = 'login_attempt_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=True) # user_id from User model
    username_submitted = db.Column(db.String(80), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False) # 'success', 'failure'
    failure_reason = db.Column(db.String(50), nullable=True) # 'invalid_credentials', 'locked_out', 'rate_limited', etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username_submitted': self.username_submitted,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'status': self.status,
            'failure_reason': self.failure_reason,
            'timestamp': self.timestamp.isoformat()
        }
