import unittest
from test_super_admin import SuperAdminTests
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role


class RoleUsersTests(unittest.TestCase):
    setUp = SuperAdminTests.setUp
    tearDown = SuperAdminTests.tearDown
    call = SuperAdminTests.call

    def test_counts_include_inactive_and_empty_roles(self):
        role = self.roles['READER']
        db.session.add(User(user_id='inactive', username='inactive', email='inactive@example.com',
                            password_hash='secret', is_active=False, roles=[role]))
        db.session.add(Role(name='EMPTY'))
        db.session.commit()
        response = self.call('ADMIN', 'GET', '/api/admin/roles')
        counts = {r['name']: r['user_count'] for r in response.json}
        self.assertEqual(counts['READER'], 2)
        self.assertEqual(counts['EMPTY'], 0)
        data = self.call('ADMIN', 'GET', f'/api/admin/roles/{role.id}/users').json
        self.assertEqual(data['total'], 2)
        self.assertEqual(set(data['users'][0]), {'user_id', 'username', 'email', 'is_active', 'last_login_at'})
        self.assertNotIn('secret', str(data))

    def test_access_and_missing_role(self):
        url = f'/api/admin/roles/{self.roles["READER"].id}/users'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.call('READER', 'GET', url).status_code, 403)
        self.assertEqual(self.call('ADMIN', 'GET', '/api/admin/roles/99999/users').status_code, 404)
        self.assertEqual(self.call('SUPER_ADMIN', 'GET', url).status_code, 200)

    def test_pagination_and_role_isolation(self):
        role = Role(name='MANY')
        for i in range(51):
            db.session.add(User(user_id=f'u{i}', username=f'u{i:03}', email=f'u{i}@example.com',
                                password_hash='unused', roles=[role]))
        db.session.commit()
        url = f'/api/admin/roles/{role.id}/users'
        first = self.call('ADMIN', 'GET', url).json
        second = self.call('ADMIN', 'GET', url+'?page=2').json
        self.assertEqual((first['total'], first['pages'], len(first['users'])), (51, 2, 50))
        self.assertEqual(len(second['users']), 1)
        self.assertEqual(second['users'][0]['username'], 'u050')
        self.assertEqual(self.call('ADMIN', 'GET', url+'?page=invalid').json['page'], 1)
