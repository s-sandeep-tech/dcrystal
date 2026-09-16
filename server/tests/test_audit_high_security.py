"""Security regressions, using SQLite and isolated request middleware only."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import Flask, session, request, g, jsonify, redirect, url_for
from flask_jwt_extended import JWTManager, create_access_token
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role, Menu, Permission, UserRole, RoleMenu, RolePermission
from app.utils.decorators import require_report_access
from app.utils.security_config import signing_key, session_is_current


class HighSecurityTests(unittest.TestCase):
    def test_signing_keys_fail_closed(self):
        for name in ['SECRET_KEY', 'JWT_SECRET_KEY']:
            for value in ['', 'short', 'super-secret-key-change-me', 'dev-secret-key-123']:
                with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}):
                    with self.assertRaises(RuntimeError):
                        signing_key(name)
            with patch.dict(os.environ, {name: 'test-only-random-secret-with-32-characters'}):
                self.assertEqual(signing_key(name), os.environ[name])

    def test_session_middleware_rejects_revoked_and_legacy_sessions(self):
        # Execute the real registered middleware without application startup/Redis.
        path = Path(__file__).parents[1] / 'app/__init__.py'
        tree = ast.parse(path.read_text())
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                    and n.name == 'refresh_effective_session_roles')
        node.decorator_list = []
        user = SimpleNamespace(is_active=True, session_version=2, user_id='employee',
                               username='reader', is_admin=False, roles=[])
        model = SimpleNamespace(query=SimpleNamespace(filter_by=lambda **kw:
                                SimpleNamespace(first=lambda: user)))
        scope = dict(session=session, request=request, g=g, jsonify=jsonify,
                     redirect=redirect, url_for=url_for, User=model,
                     session_is_current=session_is_current)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
        app = Flask(__name__)
        app.secret_key = 'test-only-session-secret-with-32-characters'
        app.before_request(scope['refresh_effective_session_roles'])
        app.add_url_rule('/api/protected', 'protected', lambda: jsonify(ok=True))
        for version in [None, 1, 2]:
            client = app.test_client()
            with client.session_transaction() as saved:
                saved['user_id'] = 'employee'
                if version is not None:
                    saved['session_version'] = version
            response = client.get('/api/protected')
            self.assertEqual(response.status_code, 200 if version == 2 else 401)
        user.is_active = False
        self.assertEqual(client.get('/api/protected').status_code, 401)

    def test_all_capacity_routes_have_access_gate(self):
        path = Path(__file__).parents[1] / 'app/dashboard/routes/party_make_capacity.py'
        functions = [n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)]
        routes = [n for n in functions if any(isinstance(d, ast.Call)
                  and isinstance(d.func, ast.Attribute) and d.func.attr == 'route'
                  for d in n.decorator_list)]
        self.assertEqual(len(routes), 5)
        for node in routes:
            self.assertTrue(any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                                and d.func.id == 'require_report_access' for d in node.decorator_list), node.name)


class ReportAccessTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                               JWT_SECRET_KEY='test-only-signing-secret-with-32-characters')
        db.init_app(self.app)
        JWTManager(self.app)
        self.app.add_url_rule('/api/report', 'report',
                             require_report_access('/party-make-capacity-report')(lambda: jsonify(ok=True)))
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.metadata.create_all(db.engine, tables=[m.__table__ for m in
                              [User, Role, Menu, Permission, UserRole, RoleMenu, RolePermission]])
        self.role = Role(name='READER')
        self.user = User(user_id='employee', username='reader', email='reader@example.com', password_hash='unused',
                         is_active=True, roles=[self.role])
        db.session.add(self.user)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def call(self):
        token = create_access_token(identity=str(self.user.id))
        return self.client.get('/api/report', headers={'Authorization': f'Bearer {token}'})

    def test_anonymous_and_invalid_tokens(self):
        self.assertEqual(self.client.get('/api/report').status_code, 401)
        self.assertEqual(self.client.get('/api/report', headers={'Authorization': 'Bearer invalid'}).status_code, 401)

    def test_menu_and_permission_required(self):
        self.assertEqual(self.call().status_code, 403)
        self.role.menus.append(Menu(title='Capacity', url='/party-make-capacity-report',
                                    permission_required='CAPACITY_READ'))
        db.session.commit()
        self.assertEqual(self.call().status_code, 403)
        self.role.permissions.append(Permission(name='CAPACITY_READ'))
        db.session.commit()
        self.assertEqual(self.call().status_code, 200)

    def test_admin_bypass_and_disabled_account(self):
        self.role.name = 'ADMIN'
        db.session.commit()
        self.assertEqual(self.call().status_code, 200)
        self.user.is_active = False
        db.session.commit()
        self.assertEqual(self.call().status_code, 401)


if __name__ == '__main__':
    unittest.main()
