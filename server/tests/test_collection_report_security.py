"""Collection endpoint authorization using isolated SQLite, no report data services."""
import unittest
from unittest.mock import patch

from flask import Flask, session
from flask_jwt_extended import JWTManager, create_access_token
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role, Menu, Permission, UserRole, RoleMenu, RolePermission
from app.models import CollectionWiseAverageDeliveryDaysSnapshot as Snapshot
from app.dashboard import dashboard_bp
from app.dashboard.routes.collection_wise_average_delivery_days import apply_owner_visibility_filter


class CollectionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                               SECRET_KEY='test-only-session-key-with-32-characters',
                               JWT_SECRET_KEY='test-only-jwt-key-with-32-characters')
        db.init_app(self.app)
        JWTManager(self.app)
        self.app.register_blueprint(dashboard_bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.metadata.create_all(db.engine, tables=[m.__table__ for m in
                              [User, Role, Menu, Permission, UserRole, RoleMenu, RolePermission, Snapshot]])
        self.role = Role(name='READER')
        self.user = User(user_id='EMP001', username='reader', email='reader@example.com',
                         password_hash='unused', is_active=True, roles=[self.role])
        db.session.add(self.user)
        db.session.add_all([Snapshot(id=1, make_user_code='EMP001'),
                            Snapshot(id=2, make_user_code='EMP002')])
        db.session.commit()
        self.client = self.app.test_client()
        self.paths = [
            ('GET', '/partial/collection-wise-average-delivery-days'),
            ('GET', '/partial/collection-wise-average-delivery-days/collection-rows'),
            ('GET', '/api/collection-wise-average-delivery-days/options'),
            ('GET', '/api/collection-wise-average-delivery-days/supplier-delivery-times'),
            ('POST', '/api/collection-wise-average-delivery-days/export'),
            ('POST', '/api/sync/collection-wise-average-delivery-days'),
        ]

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def headers(self):
        return {'Authorization': 'Bearer ' + create_access_token(identity=str(self.user.id))}

    def test_anonymous_cannot_read_or_sync(self):
        for method, path in self.paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.open(path, method=method).status_code, 401)
        response = self.client.get('/collection-wise-average-delivery-days')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/login'))

    def test_unassigned_user_denied(self):
        for method, path in self.paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.open(path, method=method, headers=self.headers()).status_code, 403)

    def test_assigned_reader_options_and_sync_denial(self):
        self.role.menus.append(Menu(title='Collection', url='/collection-wise-average-delivery-days'))
        db.session.commit()
        with patch('app.dashboard.routes.collection_wise_average_delivery_days.get_distinct', return_value=[]):
            self.assertEqual(self.client.get('/api/collection-wise-average-delivery-days/options',
                                            headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.post('/api/sync/collection-wise-average-delivery-days',
                                         headers=self.headers()).status_code, 403)

    def test_admin_and_sync_role(self):
        for role in ['ADMIN', 'DATA_SYNC_USER']:
            self.role.name = role
            db.session.commit()
            with patch('app.utils.sync_manager.sync_collection_wise_average_delivery_days_data',
                       return_value={'status': 'queued'}) as enqueue:
                response = self.client.post('/api/sync/collection-wise-average-delivery-days', headers=self.headers())
                self.assertEqual(response.status_code, 200)
                enqueue.assert_called_once_with('EMP001')

    def test_owner_filter_fails_closed(self):
        with self.app.test_request_context('/'):
            session['roles'] = ['ADMIN']
            self.assertEqual(apply_owner_visibility_filter(Snapshot.query).count(), 0)
            session['user_id'] = 'EMP001'
            session['roles'] = ['READER']
            self.assertEqual([r.id for r in apply_owner_visibility_filter(Snapshot.query).all()], [1])
            session['roles'] = ['ADMIN']
            self.assertEqual(apply_owner_visibility_filter(Snapshot.query).count(), 2)


if __name__ == '__main__':
    unittest.main()
