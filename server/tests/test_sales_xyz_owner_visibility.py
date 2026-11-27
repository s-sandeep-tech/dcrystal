from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from werkzeug.datastructures import MultiDict

from app.services import sales_xyz_drilldown as report
from app.dashboard.routes import sales_xyz_drilldown as routes


class SalesXYZOwnerVisibilityTests(unittest.TestCase):
    def filters(self, roles, code):
        filters = report.parse_filters(MultiDict())
        filters['owner_visibility'] = report.owner_visibility(roles, code)
        return filters

    def test_each_owner_role_restricts_rows_and_options_with_bound_employee_code(self):
        for role, column in report.OWNER_ROLE_COLUMNS.items():
            for options in (False, True):
                with self.subTest(role=role, options=options):
                    where, params = report.where_clause(self.filters([role], ' 70580 '), options=options)
                    self.assertIn(f'BTRIM("{column}"::text) = %s', where)
                    self.assertEqual(params[2], '70580')
                    self.assertNotIn('70580', where)
                    other = set(report.OWNER_ROLE_COLUMNS.values()) - {column}
                    self.assertTrue(all(name not in where for name in other))

    def test_both_roles_use_or_and_missing_employee_code_returns_no_rows(self):
        filters = self.filters(list(report.OWNER_ROLE_COLUMNS), '70580')
        where, params = report.where_clause(filters)
        self.assertIn('(BTRIM("make_owner_emp_code"::text) = %s OR BTRIM("collection_owner_emp_code"::text) = %s)', where)
        self.assertEqual(params[2:4], ['70580', '70580'])
        where, _ = report.where_clause(self.filters(['MAKE_OWNER_USER'], None), options=True)
        self.assertIn(' AND FALSE', where)

    def test_other_roles_keep_existing_visibility(self):
        for role in ('ADMIN', 'SUPER_ADMIN', 'MANAGER_2', 'BUSINESS_HEAD', 'SHOWROOM_MANAGER', 'READER'):
            with self.subTest(role=role):
                filters = self.filters([role], '70580')
                self.assertEqual(filters['owner_visibility'], {})
                where, _ = report.where_clause(filters)
                self.assertNotIn('_owner_emp_code', where)

    def test_owner_columns_are_validated_for_options_and_hierarchy(self):
        filters = self.filters(['MAKE_OWNER_USER'], '70580')
        cursor = MagicMock()
        cursor.description = []
        with patch.object(report, 'validate_columns') as validate:
            report.options(cursor, filters, 'branch_id')
            self.assertIn('make_owner_emp_code', validate.call_args.args[1])
            report.drilldown(cursor, filters, [])
            self.assertIn('make_owner_emp_code', validate.call_args.args[1])

    def test_client_cannot_supply_or_override_owner_visibility(self):
        parsed = report.parse_filters(MultiDict([
            ('owner_visibility', '{}'), ('employee_code', 'OTHER'), ('make_owner_emp_code', 'OTHER')]))
        self.assertNotIn('owner_visibility', parsed)
        actor = SimpleNamespace(is_active=True, user_id='70580', roles=[SimpleNamespace(name='MAKE_OWNER_USER')])
        with patch.object(routes, 'get_jwt_identity', return_value='99'), patch.object(routes.db.session, 'get', return_value=actor) as get:
            visibility = routes.current_owner_visibility()
        self.assertEqual(visibility['employee_code'], '70580')
        get.assert_called_once_with(routes.User, 99)

    def test_cache_isolates_owners_roles_and_unrestricted_users_for_both_endpoints(self):
        app = Flask(__name__)
        app.add_url_rule('/<segment>', view_func=routes.sales_xyz_drilldown_segment.__wrapped__)
        entries = {}
        actor = SimpleNamespace(is_active=True, user_id='A', roles=[SimpleNamespace(name='MAKE_OWNER_USER')])

        def result(cursor, filters, *args):
            return filters['owner_visibility']

        def store(key, value, **kwargs):
            entries[key] = value

        with patch.object(routes, 'get_jwt_identity', return_value='1'), patch.object(
            routes.db.session, 'get', return_value=actor
        ), patch.object(routes, 'redis_client') as redis, patch.object(report, 'source_cursor') as source, patch.object(
            report, 'drilldown', side_effect=result
        ), patch.object(report, 'options', side_effect=result):
            redis.get.side_effect = entries.get
            redis.set.side_effect = store
            client = app.test_client()
            for endpoint in ('hierarchy', 'options?field=branch_id'):
                first = client.get('/' + endpoint).json
                self.assertEqual(first['data']['employee_code'], 'A')
                actor.user_id = 'B'
                second = client.get('/' + endpoint).json
                self.assertEqual(second['data']['employee_code'], 'B')
                actor.roles = [SimpleNamespace(name='COLLECTION_OWNER_USER')]
                third = client.get('/' + endpoint).json
                self.assertEqual(third['data']['columns'], ['collection_owner_emp_code'])
                actor.roles = [SimpleNamespace(name='READER')]
                self.assertEqual(client.get('/' + endpoint).json['data'], {})
                actor.user_id = 'A'
                actor.roles = [SimpleNamespace(name='MAKE_OWNER_USER')]
                self.assertEqual(client.get('/' + endpoint).json, first)
            self.assertEqual(source.call_count, 8)


if __name__ == '__main__':
    unittest.main()
