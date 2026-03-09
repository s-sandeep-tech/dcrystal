import unittest
import json
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, LoginAttemptLog
from app.services.auth_service import auth_service

class AuthSecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        # Clear pooling options that are incompatible with SQLite
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            self.test_user = User(user_id='testuser', username='testuser', email='test@example.com')
            self.test_user.set_password('password123')
            db.session.add(self.test_user)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_failed_login_increments_counter(self):
        with self.app.app_context():
            user = User.query.filter_by(user_id='testuser').first()
            self.assertEqual(user.failed_attempt_count, 0)
            
            # Post failed login
            self.client.post('/api/auth/login', json={'user_id': 'testuser', 'password': 'wrongpassword'})
            
            user = User.query.filter_by(user_id='testuser').first()
            self.assertEqual(user.failed_attempt_count, 1)

    def test_lockout_after_max_attempts(self):
        with self.app.app_context():
            # max_attempts is 5 by default
            for _ in range(5):
                self.client.post('/api/auth/login', json={'user_id': 'testuser', 'password': 'wrongpassword'})
            
            user = User.query.filter_by(user_id='testuser').first()
            self.assertEqual(user.failed_attempt_count, 5)
            self.assertIsNotNone(user.lockout_until)
            self.assertTrue(user.lockout_until > datetime.utcnow())
            
            # Submitting correct password while locked out
            response = self.client.post('/api/auth/login', json={'user_id': 'testuser', 'password': 'password123'})
            self.assertEqual(response.status_code, 423)
            self.assertIn("Account is temporarily locked", response.get_json()['msg'])

    def test_successful_login_resets_counter(self):
        with self.app.app_context():
            # Fail a few times
            for _ in range(3):
                self.client.post('/api/auth/login', json={'user_id': 'testuser', 'password': 'wrongpassword'})
            
            user = User.query.filter_by(user_id='testuser').first()
            self.assertEqual(user.failed_attempt_count, 3)
            
            # Succeed
            self.client.post('/api/auth/login', json={'user_id': 'testuser', 'password': 'password123'})
            
            user = User.query.filter_by(user_id='testuser').first()
            self.assertEqual(user.failed_attempt_count, 0)
            self.assertIsNone(user.lockout_until)

    def test_nonexistent_user_safe_handling(self):
        response = self.client.post('/api/auth/login', json={'user_id': 'nonexistent', 'password': 'any'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['msg'], "Bad user id or password")
        
        with self.app.app_context():
            log = LoginAttemptLog.query.filter_by(username_submitted='nonexistent').first()
            self.assertIsNotNone(log)
            self.assertEqual(log.status, 'failure')

if __name__ == '__main__':
    unittest.main()
