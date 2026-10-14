import unittest
from unittest.mock import patch

from flask import Flask, session
from app.extensions import db
from app.models.auth import User
from app.models.rbac import Role, Menu, Permission, UserRole, RoleMenu, RolePermission
from app.utils.access_policy import report_menu_access
from app.dashboard.routes.main import report_menu


class ReportMenuAccessTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY='test', SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                               SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(self.app)
        self.app.add_url_rule('/login', endpoint='dashboard.login', view_func=lambda: 'login')
        self.app.add_url_rule('/customerorderfulfilmentsummary', endpoint='fulfilment', view_func=lambda: 'report')
        self.app.add_url_rule('/customer-order-fulfilment-summary', endpoint='fulfilment')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.metadata.create_all(db.engine, tables=[m.__table__ for m in
            [User, Role, Menu, Permission, UserRole, RoleMenu, RolePermission]])
        self.role = Role(name='CUSTOMER OREDR CHECKER')
        self.user = User(user_id='1235', username='checker', email='checker@example.com',
                         password_hash='unused', is_active=True, roles=[self.role])
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_only_granted_reports_with_required_permission(self):
        granted = Menu(title='Granted', url='/customer-order-analysis')
        restricted = Menu(title='Restricted', url='/sales-stock-composition-analysis', permission_required='report.view')
        permission = Permission(name='report.view')
        db.session.add(permission)
        self.role.menus.extend([granted, restricted])
        db.session.commit()
        self.assertEqual(report_menu_access(self.user)['urls'], ['/customer-order-analysis'])
        self.role.permissions.append(permission)
        db.session.commit()
        self.assertEqual(len(report_menu_access(self.user)['urls']), 2)
        self.role.menus.remove(granted)
        db.session.commit()
        self.assertNotIn('/customer-order-analysis', report_menu_access(self.user)['urls'])

    def test_admin_and_super_admin_see_all(self):
        for name in ['ADMIN', 'SUPER_ADMIN']:
            self.role.name = name
            self.assertTrue(report_menu_access(self.user)['all_reports'])

    def test_menu_urls_with_query_or_slash_match_report_path(self):
        self.role.menus.extend([
            Menu(title='Analysis', url=' /customer-order-analysis? '),
            Menu(title='Monitoring', url='/customer-order-performance-monitoring/?page=1#details'),
            Menu(title='External', url='https://other.example/customer-order-analysis'),
        ])
        db.session.commit()
        self.assertEqual(report_menu_access(self.user)['urls'], [
            '/customer-order-analysis', '/customer-order-performance-monitoring'])

    def test_inactive_and_unassigned_users_see_none(self):
        self.assertEqual(report_menu_access(self.user), {'all_reports': False, 'urls': []})
        self.user.is_active = False
        self.assertEqual(report_menu_access(self.user), {'all_reports': False, 'urls': []})

    def test_route_expands_alias_and_ignores_stale_session_roles(self):
        self.role.menus.append(Menu(title='Fulfilment', url='/customer-order-fulfilment-summary'))
        db.session.commit()
        with self.app.test_request_context('/report-menu'):
            session['user_id'] = '1235'
            session['roles'] = ['ADMIN']
            with patch('app.dashboard.routes.main.Notification'), patch(
                'app.dashboard.routes.main.render_template', return_value='OK'
            ) as render:
                self.assertEqual(report_menu(), 'OK')
                access = render.call_args.kwargs['report_menu_access']
            self.assertFalse(access['all_reports'])
            self.assertIn('/customerorderfulfilmentsummary', access['urls'])

    def test_anonymous_redirected_to_login(self):
        with self.app.test_request_context('/report-menu'):
            self.assertEqual(report_menu().status_code, 302)


if __name__ == '__main__':
    unittest.main()
