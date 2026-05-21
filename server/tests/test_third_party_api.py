import unittest
import json
import os
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db, redis_client
from app.models.auth import ThirdPartyApiClient

class ThirdPartyApiTestCase(unittest.TestCase):
    def setUp(self):
        # Configure env variables for testing before creating app
        os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        os.environ['ALLOWED_THIRD_PARTY_IPS'] = '127.0.0.1,192.168.1.100'
        
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
        self.client = self.app.test_client()

        
        with self.app.app_context():
            db.create_all()
            
            # Setup active test API client
            self.test_client_id = 'test_client'
            self.test_raw_token = 'secure_test_token_2026'
            
            self.api_client = ThirdPartyApiClient(
                client_id=self.test_client_id,
                client_name='Test Client Description'
            )
            self.api_client.set_token(self.test_raw_token)
            db.session.add(self.api_client)
            db.session.commit()
            
            # Mock Redis client in-memory to prevent connection errors and support cache testing
            self.redis_store = {}
            def fake_get(key):
                val = self.redis_store.get(key)
                return val.encode('utf-8') if isinstance(val, str) else val
            def fake_setex(key, time, value):
                self.redis_store[key] = value
                return True
            redis_client.get = fake_get
            redis_client.setex = fake_setex
            redis_client.rpush = lambda queue, data: 1
            redis_client.flushdb = lambda: self.redis_store.clear()
            
            redis_client.flushdb()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        # Clean up env
        if 'ALLOWED_THIRD_PARTY_IPS' in os.environ:
            del os.environ['ALLOWED_THIRD_PARTY_IPS']

    def test_unauthorized_missing_token(self):
        response = self.client.post('/api/sync/provision-stock-status')
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('Authorization header is missing', data['message'])

    def test_unauthorized_malformed_token(self):
        headers = {'Authorization': 'Bearer only_token_without_client_id'}
        response = self.client.post('/api/sync/provision-stock-status', headers=headers)
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertIn('Invalid token format', data['message'])

    def test_forbidden_invalid_token(self):
        headers = {'Authorization': f'Bearer {self.test_client_id}.wrong_secret_123'}
        response = self.client.post('/api/sync/provision-stock-status', headers=headers)
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertIn('Invalid credentials', data['message'])

    def test_forbidden_inactive_client(self):
        with self.app.app_context():
            client = ThirdPartyApiClient.query.filter_by(client_id=self.test_client_id).first()
            client.is_active = False
            db.session.commit()
            
        headers = {'Authorization': f'Bearer {self.test_client_id}.{self.test_raw_token}'}
        response = self.client.post('/api/sync/provision-stock-status', headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertIn('Invalid credentials', response.get_json()['message'])

    def test_forbidden_expired_client(self):
        with self.app.app_context():
            client = ThirdPartyApiClient.query.filter_by(client_id=self.test_client_id).first()
            client.expires_at = datetime.utcnow() - timedelta(hours=1)
            db.session.commit()
            
        headers = {'Authorization': f'Bearer {self.test_client_id}.{self.test_raw_token}'}
        response = self.client.post('/api/sync/provision-stock-status', headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertIn('Credentials have expired', response.get_json()['message'])

    def test_success_valid_token(self):
        # We also mock the sync enqueuing call in the worker if necessary, 
        # but in this mock DB/redis in-memory setup, sync_provision_stock_status_data will push to the in-memory redis.
        headers = {
            'Authorization': f'Bearer {self.test_client_id}.{self.test_raw_token}',
            'X-Forwarded-For': '192.168.1.100'
        }
        
        # Enqueue success trigger
        response = self.client.post('/api/sync/provision-stock-status', headers=headers)
        self.assertEqual(response.status_code, 202)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('successfully enqueued', data['message'])

    def test_payload_validation_invalid_json(self):
        headers = {
            'Authorization': f'Bearer {self.test_client_id}.{self.test_raw_token}',
            'X-Forwarded-For': '192.168.1.100',
            'Content-Type': 'application/json'
        }
        response = self.client.post('/api/sync/provision-stock-status', headers=headers, data="{invalid_json_body}")
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid JSON format', response.get_json()['message'])

    def test_payload_validation_failure_status(self):
        headers = {
            'Authorization': f'Bearer {self.test_client_id}.{self.test_raw_token}',
            'X-Forwarded-For': '192.168.1.100'
        }
        payload = {'status': 'failed', 'error': 'External API failure'}
        response = self.client.post('/api/sync/provision-stock-status', headers=headers, json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('aborted because external status is', response.get_json()['message'])

    def test_payload_validation_success_status(self):
        headers = {
            'Authorization': f'Bearer {self.test_client_id}.{self.test_raw_token}',
            'X-Forwarded-For': '192.168.1.100'
        }
        payload = {'status': 'success', 'external_batch_id': 'batch_999'}
        response = self.client.post('/api/sync/provision-stock-status', headers=headers, json=payload)
        self.assertEqual(response.status_code, 202)

    def test_ip_whitelisting_denied(self):
        headers = {
            'Authorization': f'Bearer {self.test_client_id}.{self.test_raw_token}',
            'X-Forwarded-For': '198.51.100.42' # Non-whitelisted IP
        }
        response = self.client.post('/api/sync/provision-stock-status', headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertIn('Access denied from IP address', response.get_json()['message'])

if __name__ == '__main__':
    unittest.main()
