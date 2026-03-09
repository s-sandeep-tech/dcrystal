from datetime import datetime, timedelta
from app.extensions import db
from app.models import User, LoginAttemptLog
from flask import request

class AuthService:
    def __init__(self, max_attempts=5, lockout_minutes=15):
        self.max_attempts = max_attempts
        self.lockout_minutes = lockout_minutes

    def log_attempt(self, username, user_id=None, status='failure', failure_reason=None):
        # Capture full IP chain if behind proxy
        ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        log = LoginAttemptLog(
            user_id=user_id,
            username_submitted=username,
            ip_address=ip_addr,
            user_agent=request.headers.get('User-Agent'),
            status=status,
            failure_reason=failure_reason
        )
        db.session.add(log)
        db.session.commit()

    def handle_failed_login(self, user, username):
        if user:
            user.failed_attempt_count += 1
            user.last_failed_at = datetime.utcnow()
            
            if user.failed_attempt_count >= self.max_attempts:
                user.lockout_until = datetime.utcnow() + timedelta(minutes=self.lockout_minutes)
            
            db.session.commit()
            self.log_attempt(username, user_id=user.user_id, status='failure', failure_reason='invalid_credentials')
        else:
            # Safe handle: log but don't leak existence
            self.log_attempt(username, status='failure', failure_reason='invalid_credentials')

    def handle_successful_login(self, user, ip):
        user.failed_attempt_count = 0
        user.lockout_until = None
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip
        db.session.commit()
        self.log_attempt(user.user_id, user_id=user.user_id, status='success')

    def is_locked_out(self, user):
        if user and user.lockout_until:
            if user.lockout_until > datetime.utcnow():
                return True
            else:
                # Lockout expired, clear it
                user.lockout_until = None
                db.session.commit()
        return False

auth_service = AuthService()
