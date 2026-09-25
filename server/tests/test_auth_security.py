import unittest
import json
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, LoginAttemptLog
from app.services.auth_service import auth_service
from app.api.auth import validate_company_email
from app.services.email_verification_service import issue_verification_token

class AuthSecurityTestCase(unittest.TestCase):
    def setUp(self):
        import os
        from unittest.mock import patch
        keys = patch.dict(os.environ, {
            'SECRET_KEY': 'test-only-session-key-with-at-least-32-characters',
            'JWT_SECRET_KEY': 'test-only-jwt-key-with-at-least-32-characters',
        })
        keys.start()
        self.addCleanup(keys.stop)
        os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = create_app()
        self.app.config['TESTING'] = True
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
        import os
        if 'SQLALCHEMY_DATABASE_URI' in os.environ:
            del os.environ['SQLALCHEMY_DATABASE_URI']

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

    def test_company_email_validation(self):
        valid, normalized = validate_company_email(' SandeepS@KalyanJewellers.Tech ')
        self.assertTrue(valid)
        self.assertEqual(normalized, 'sandeeps@kalyanjewellers.tech')
        valid, normalized = validate_company_email(' SandeepS@KalyanJewellers.Net ')
        self.assertTrue(valid)
        self.assertEqual(normalized, 'sandeeps@kalyanjewellers.net')
        valid, normalized = validate_company_email(' VaishaliNagar@KalyanJewellers.Store ')
        self.assertTrue(valid)
        self.assertEqual(normalized, 'vaishalinagar@kalyanjewellers.store')

        for email in (
            'sandeeps@example.com',
            'sandeeps@sub.kalyanjewellers.tech',
            '@kalyanjewellers.tech',
            'sandeeps@kalyanjewellers.tech.example.com',
            'sandeeps@sub.kalyanjewellers.net',
            'sandeeps@kalyanjewellers.net.example.com',
            '@kalyanjewellers.net',
            'sandeep s@kalyanjewellers.net',
            'sandeeps@sub.kalyanjewellers.store',
            'sandeeps@kalyanjewellers.store.example.com',
            '@kalyanjewellers.store',
        ):
            valid, error = validate_company_email(email)
            self.assertFalse(valid)
            self.assertIn('@kalyanjewellers.tech', error)

    def test_email_verification_activates_pending_user_once(self):
        with self.app.app_context():
            user = User(
                user_id='pendinguser',
                username='pendinguser',
                email='pendinguser@kalyanjewellers.tech',
                is_active=False,
            )
            user.set_password('Password1!')
            token = issue_verification_token(user)
            db.session.add(user)
            db.session.commit()

            response = self.client.get(f'/api/auth/verify-email?token={token}')
            self.assertEqual(response.status_code, 200)
            db.session.refresh(user)
            self.assertTrue(user.is_active)
            self.assertIsNotNone(user.email_verified_at)
            self.assertIsNone(user.email_verification_token_hash)

            # Verify audit log entry was created for successful verification
            from app.models import AuditLog
            audit = AuditLog.query.filter_by(user_id=user.id, action="EMAIL_VERIFIED").first()
            self.assertIsNotNone(audit)
            self.assertEqual(audit.target_type, "USER")
            self.assertEqual(audit.details.get("email"), user.email)

            reused = self.client.get(f'/api/auth/verify-email?token={token}')
            self.assertEqual(reused.status_code, 400)

    def test_toggle_user_status_strict_email_verification_no_admin_override(self):
        with self.app.app_context():
            from flask_jwt_extended import create_access_token
            admin_user = User(user_id='admin_test', username='admin_test', email='admin_test@example.com', is_admin=True, is_active=True)
            admin_user.set_password('admin123!')
            db.session.add(admin_user)

            # Create an unverified disabled user
            unverified_user = User(user_id='unverified', username='unverified', email='unverified@example.com', is_active=False, email_verified_at=None)
            unverified_user.set_password('pass123!')
            db.session.add(unverified_user)
            db.session.commit()

            access_token = create_access_token(
                identity=str(admin_user.id),
                additional_claims={'session_version': admin_user.session_version}
            )
            headers = {'Authorization': f'Bearer {access_token}'}

            # Admin attempts to toggle/enable unverified user - must fail with 400 (strict email verification, no admin override)
            response = self.client.post(f'/api/admin/users/{unverified_user.id}/toggle-status', headers=headers)
            self.assertEqual(response.status_code, 400)
            self.assertIn("must verify their email", response.get_json().get("msg", ""))
            db.session.refresh(unverified_user)
            self.assertFalse(unverified_user.is_active)

    def test_toggle_user_status_re_enabling_clears_lockout_for_verified_user(self):
        with self.app.app_context():
            from flask_jwt_extended import create_access_token
            admin_user = User(user_id='admin_test2', username='admin_test2', email='admin_test2@example.com', is_admin=True, is_active=True)
            admin_user.set_password('admin123!')
            db.session.add(admin_user)

            # Verified user that got disabled and locked out
            verified_user = User(
                user_id='verified_locked',
                username='verified_locked',
                email='verified_locked@example.com',
                is_active=False,
                email_verified_at=datetime.utcnow(),
                failed_attempt_count=5,
                lockout_until=datetime.utcnow() + timedelta(minutes=15)
            )
            verified_user.set_password('pass123!')
            db.session.add(verified_user)
            db.session.commit()

            access_token = create_access_token(
                identity=str(admin_user.id),
                additional_claims={'session_version': admin_user.session_version}
            )
            headers = {'Authorization': f'Bearer {access_token}'}

            # Admin re-enables the account
            response = self.client.post(f'/api/admin/users/{verified_user.id}/toggle-status', headers=headers)
            self.assertEqual(response.status_code, 200)
            db.session.refresh(verified_user)
            self.assertTrue(verified_user.is_active)
            self.assertEqual(verified_user.failed_attempt_count, 0)
            self.assertIsNone(verified_user.lockout_until)

    def test_clear_lockout_endpoint(self):
        # 1. Login as Admin to get token (simplifying by mocking or using a real user if needed)
        # However, the test environment doesn't have roles/RBAC fully setup in memory unless we do it.
        # Let's just test the logic directly if possible or mock the decorator.
        # Since this is a unit test for security logic, I'll test the model reset.
        
        with self.app.app_context():
            # Setup a locked user
            user = User.query.filter_by(user_id='testuser').first()
            user.failed_attempt_count = 5
            user.lockout_until = datetime.utcnow() + timedelta(minutes=15)
            db.session.commit()
            
            # Verify they are locked
            self.assertEqual(user.failed_attempt_count, 5)
            self.assertIsNotNone(user.lockout_until)
            
            # Call the clear lockout logic (mocking the admin check if necessary, or just testing the model method if I add one)
            # Since I put the logic in the route, I'll call the route. 
            # I need to mock 'require_role' or setup an admin. 
            
            # For simplicity in this test environment, let's just test that we can clear it.
            # I will manually call the logic that the route would execute for now, 
            # or better, setup the test client with an admin session if I can.
            
            from flask_jwt_extended import create_access_token
            admin_user = User(user_id='admin', username='admin', email='admin@example.com', is_admin=True)
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            
            access_token = create_access_token(
                identity=str(admin_user.id),
                additional_claims={'session_version': admin_user.session_version}
            )
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = self.client.post(f'/api/admin/users/{user.id}/clear-lockout', headers=headers)
            self.assertEqual(response.status_code, 200)
            
            # Re-fetch user and verify
            db.session.refresh(user)
            self.assertEqual(user.failed_attempt_count, 0)
            self.assertIsNone(user.lockout_until)
            self.assertIsNone(user.last_failed_at)

if __name__ == '__main__':
    unittest.main()
