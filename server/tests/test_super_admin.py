"""Isolated API tests: in-memory SQLite only, no application startup or Redis."""
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager, create_access_token
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role, UserRole, Permission, RolePermission, Menu, RoleMenu, AuditLog, UserPasswordHistory
from app.api.admin_rbac import admin_rbac_bp
from app.utils.access_policy import effective_roles
from app.utils.decorators import require_role


class SuperAdminTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                               JWT_SECRET_KEY='test-only-key-with-at-least-32-characters')
        db.init_app(self.app)
        JWTManager(self.app)
        self.app.register_blueprint(admin_rbac_bp, url_prefix='/api/admin')

        @self.app.route('/api/strict')
        @require_role('SUPER_ADMIN')
        def strict():
            return jsonify(ok=True)

        self.ctx = self.app.app_context()
        self.ctx.push()
        tables = [m.__table__ for m in [User, Role, UserRole, Permission, RolePermission, Menu, RoleMenu, AuditLog, UserPasswordHistory]]
        db.metadata.create_all(db.engine, tables=tables)
        self.roles = {name: Role(name=name) for name in ['ADMIN', 'SUPER_ADMIN', 'READER']}
        self.users = {}
        for i, name in enumerate(['ADMIN', 'SUPER_ADMIN', 'READER'], 1):
            user = User(user_id=str(i), username=name.lower(), email=f'{i}@example.com',
                        password_hash='unused', is_active=True, roles=[self.roles[name]])
            db.session.add(user)
            self.users[name] = user
        db.session.commit()
        fake_redis = MagicMock()
        fake_redis.get.return_value = '1'
        fake_redis.exists.return_value = False
        self.cache = patch('app.utils.rbac_cache.redis_client', fake_redis)
        self.cache.start()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.cache.stop()
        self.ctx.pop()

    def call(self, actor, method, path, data=None):
        token = create_access_token(identity=str(self.users[actor].id))
        response = self.client.open(path, method=method, json=data,
                                   headers={'Authorization': f'Bearer {token}'})
        if response.status_code >= 400:
            db.session.rollback()
        return response

    def test_inheritance_and_strict_gate(self):
        self.assertIn('ADMIN', effective_roles(self.users['SUPER_ADMIN']))
        self.assertEqual(self.call('ADMIN', 'GET', '/api/strict').status_code, 403)
        self.assertEqual(self.call('SUPER_ADMIN', 'GET', '/api/strict').status_code, 200)

    def test_admin_keeps_ordinary_role_management(self):
        response = self.call('ADMIN', 'POST', '/api/admin/roles', {'name': 'REPORT_READER'})
        self.assertEqual(response.status_code, 201)
        reader = self.users['READER']
        response = self.call('ADMIN', 'PUT', f'/api/admin/users/{reader.id}/roles', {'role_ids': [self.roles['READER'].id]})
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_assign_or_rename_super_role(self):
        response = self.call('ADMIN', 'PUT', f"/api/admin/users/{self.users['ADMIN'].id}/roles",
                             {'role_ids': [self.roles['ADMIN'].id, self.roles['SUPER_ADMIN'].id]})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.call('ADMIN', 'POST', '/api/admin/roles', {'name': 'super_admin'}).status_code, 403)
        response = self.call('ADMIN', 'PUT', f"/api/admin/roles/{self.roles['READER'].id}", {'name': 'SUPER_ADMIN'})
        self.assertEqual(response.status_code, 403)

    def test_protected_user_mutations(self):
        target = self.users['SUPER_ADMIN'].id
        for method, suffix, data in [
            ('PUT', '', {'username': 'changed'}), ('DELETE', '', {}),
            ('PUT', '/password', {'password': 'NewPassword@123'}),
            ('POST', '/toggle-status', {}), ('POST', '/clear-lockout', {}),
            ('POST', '/force-password-reset', {}), ('POST', '/resend-verification', {}),
            ('PUT', '/roles', {'role_ids': []}),
        ]:
            with self.subTest(suffix=suffix, method=method):
                self.assertEqual(self.call('ADMIN', method, f'/api/admin/users/{target}{suffix}', data).status_code, 403)

    def test_last_super_admin_and_system_role(self):
        target = self.users['SUPER_ADMIN'].id
        self.assertEqual(self.call('SUPER_ADMIN', 'DELETE', f'/api/admin/users/{target}').status_code, 400)
        self.assertEqual(self.call('SUPER_ADMIN', 'PUT', f'/api/admin/users/{target}/roles', {'role_ids': []}).status_code, 400)
        self.assertEqual(self.call('SUPER_ADMIN', 'DELETE', f"/api/admin/roles/{self.roles['SUPER_ADMIN'].id}").status_code, 400)

    def test_super_admin_can_promote_and_demote_with_successor(self):
        reader = self.users['READER'].id
        self.assertEqual(self.call('SUPER_ADMIN', 'PUT', f'/api/admin/users/{reader}/roles',
                                  {'role_ids': [self.roles['SUPER_ADMIN'].id]}).status_code, 200)
        target = self.users['SUPER_ADMIN'].id
        self.assertEqual(self.call('SUPER_ADMIN', 'PUT', f'/api/admin/users/{target}/roles',
                                  {'role_ids': [self.roles['ADMIN'].id]}).status_code, 200)

    def test_role_permissions_do_not_grant_super_role(self):
        fake = Permission(name='SUPER_ADMIN')
        self.roles['ADMIN'].permissions.append(fake)
        db.session.commit()
        self.assertEqual(self.call('ADMIN', 'GET', '/api/strict').status_code, 403)

    def test_protected_role_mappings(self):
        role = self.roles['SUPER_ADMIN'].id
        for suffix, data in [('/menus', {'menu_ids': []}), ('/permissions', {'permission_ids': []}), ('', {'description': 'changed'})]:
            self.assertEqual(self.call('ADMIN', 'PUT', f'/api/admin/roles/{role}{suffix}', data).status_code, 403)

    def test_ordinary_user_cannot_administer(self):
        self.assertEqual(self.call('READER', 'POST', '/api/admin/roles', {'name': 'OTHER'}).status_code, 403)

    def test_reserved_permission_cannot_be_created(self):
        self.assertEqual(self.call('ADMIN', 'POST', '/api/admin/permissions', {'name': 'SUPER_ADMIN'}).status_code, 400)

    def test_disabled_super_admin_has_no_authority(self):
        self.users['SUPER_ADMIN'].is_active = False
        db.session.commit()
        self.assertEqual(self.call('SUPER_ADMIN', 'POST', '/api/admin/roles', {'name': 'OTHER'}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
