import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask
from werkzeug.datastructures import MultiDict
from app.services import sales_qty_abc_analysis as report
from app.dashboard.routes import sales_qty_abc_analysis as routes


def filters(**kwargs):
    return report.parse_filters(MultiDict({'start': '2026-04-01', 'end': '2026-10-31', **kwargs}))


def record(qty, make='1', purity='1', **metrics):
    row = {key: '1' for key, _, _ in report.LEVELS}
    row.update({label: title + ' 1' for _, label, title in report.LEVELS})
    row.update(make_id=make, make='Make ' + str(make), purity_id=purity, purity='Purity ' + str(purity),
               sold_qty=qty, sold_weight=Decimal('1.25'), net_turnover=Decimal('100'), mcprofit=Decimal('10'), invalid_rows=0)
    row.update(metrics)
    return row


class CalculationTests(unittest.TestCase):
    def test_threshold_crossers_and_zero(self):
        data = report.build_tree([record(q, str(i)) for i, q in enumerate([70, 15, 11, 4, 0])])
        self.assertEqual([r['category'] for r in data['rows']], ['A', 'A', 'B', 'C', 'Unclassified'])
        self.assertEqual([r['cumulative'] for r in data['rows']], [70, 85, 96, 100, 100])
        self.assertEqual([r['rank'] for r in data['rows']], [1, 2, 3, 4, 5])
        exact = report.build_tree([record(q, str(i)) for i, q in enumerate([80, 15, 5])])
        self.assertEqual([r['category'] for r in exact['rows']], ['A', 'B', 'C'])
        self.assertEqual(report.build_tree([record(100)])['rows'][0]['category'], 'A')

    def test_rollups_parent_shares_and_full_path_identity(self):
        data = report.build_tree([record(60, '1', '1'), record(20, '1', '2'), record(20, '2', '1')])
        root = data['rows'][0]
        self.assertEqual(root['sold_qty'], 80)
        self.assertEqual(root['children'][0]['contribution'], 75)
        self.assertEqual(root['children'][0]['overall'], 60)
        self.assertEqual(root['children'][1]['category'], 'A')
        self.assertEqual(data['totals']['sold_weight'], Decimal('3.75'))
        def reconcile(node):
            if node['children']:
                for metric in report.METRICS:
                    self.assertEqual(node[metric], sum(c[metric] for c in node['children']))
                for child in node['children']: reconcile(child)
        for node in data['rows']: reconcile(node)
        self.assertEqual(data['rows'][1]['children'][0]['sold_qty'], 20)

    def test_ties_missing_and_empty(self):
        rows = [record(5, 'b'), record(5, 'a')]
        self.assertEqual(report.build_tree(rows), report.build_tree(list(reversed(rows))))
        missing = record(0, None)
        missing['make'] = None
        zero = report.build_tree([missing])['rows'][0]
        self.assertEqual(zero['label'], 'Unspecified')
        self.assertIsNone(zero['contribution'])
        self.assertIsNone(zero['cumulative'])
        self.assertEqual(zero['category'], 'Unclassified')
        self.assertEqual(report.build_tree([])['rows'], [])

    def test_filter_validation_and_parameterization(self):
        for args in ({'start': 'bad'}, {'end': '2026-03-01'}, {'end': '2027-04-01'}, {'trans_type': 'DROP'}):
            with self.assertRaises(ValueError): filters(**args)
        value = "x'); DROP TABLE sales; --"
        where, params = report.where_clause(filters(make_id=value))
        self.assertNotIn(value, where)
        self.assertIn([value], params)
        self.assertNotIn('"make_id"', report.where_clause(filters(make_id=value), options=True)[0])

    def test_schema_and_query_contract(self):
        cur = MagicMock(); cur.description = []
        with self.assertRaisesRegex(report.SourceDataError, 'sub_section_id'): report.validate_schema(cur)
        cur.fetchall.return_value = [record(4)]
        with patch.dict('os.environ', {'SALES_PREDICTION_RETURN_SIGN': 'signed'}):
            data = report.hierarchy(cur, filters())
        self.assertEqual(data['totals']['sold_qty'], 4)
        sql, params = cur.execute.call_args.args
        self.assertIn("COUNT(DISTINCT barcode) FILTER (WHERE trans_type = 'INVOICE')", sql)
        self.assertIn("trans_type = 'INVOICE' AND barcode IS NULL", sql)
        self.assertIn('"wide_range_id"', sql)
        self.assertNotIn('2026-04-01', sql)
        self.assertIn('LIMIT 20001', sql)
        cur.fetchall.return_value = [record(4, invalid_rows=1)]
        with self.assertRaises(report.SourceDataError): report.hierarchy(cur, filters())
        with patch.object(report, 'MAX_LEAVES', 0):
            with self.assertRaisesRegex(report.SourceDataError, 'Too many'): report.hierarchy(cur, filters())

    def test_readonly_connection_cleanup(self):
        conn = MagicMock()
        with patch('app.utils.sync_tasks.get_external_db_connection', return_value=conn):
            with self.assertRaises(ValueError):
                with report.source_cursor(): raise ValueError('failure')
        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once(); conn.close.assert_called_once()


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.add_url_rule('/api/sales-qty-abc-analysis/<segment>', view_func=routes.sales_qty_abc_analysis_segment)
        self.client = self.app.test_client()

    def test_anonymous_and_separate_grant(self):
        for segment in ['options', 'hierarchy']:
            self.assertEqual(self.client.get('/api/sales-qty-abc-analysis/' + segment).status_code, 401)
        user = SimpleNamespace(is_active=True, roles=[SimpleNamespace(name='READER', permissions=[], menus=[SimpleNamespace(url='/sales-tsk-monthly-analyse')])], username='reader', is_admin=False)
        with patch('app.utils.decorators.verify_jwt_in_request'), patch('app.utils.decorators.get_jwt_identity', return_value='1'), patch('app.extensions.db.session.get', return_value=user), patch.object(report, 'load_segment') as load:
            self.assertEqual(self.client.get('/api/sales-qty-abc-analysis/hierarchy').status_code, 403)
            load.assert_not_called()

    def test_response_and_failures(self):
        with self.app.test_request_context('/'), patch.object(report, 'load_segment', return_value={'qty': Decimal('2')}):
            response = routes.sales_qty_abc_analysis_segment.__wrapped__('hierarchy')
            self.assertEqual(response.json['data']['qty'], 2)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(routes.sales_qty_abc_analysis_segment.__wrapped__('unknown')[1], 404)
        with self.app.test_request_context('/?start=invalid'):
            self.assertEqual(routes.sales_qty_abc_analysis_segment.__wrapped__('hierarchy')[1], 400)
        for error, code in [(report.SourceDataError('Missing column'), 422), (RuntimeError('offline'), 503)]:
            with self.app.test_request_context('/'), patch.object(report, 'load_segment', side_effect=error):
                self.assertEqual(routes.sales_qty_abc_analysis_segment.__wrapped__('hierarchy')[1], code)


class MenuTests(unittest.TestCase):
    def test_registration_creates_only_new_menu_and_is_idempotent(self):
        from scripts import add_sales_qty_abc_analysis_menu as seed
        menu = SimpleNamespace(id=90)
        admin = SimpleNamespace(id=1)
        with patch.object(seed, 'Menu') as model, patch.object(seed, 'Role') as role, patch.object(seed, 'RoleMenu') as grant, patch.object(seed, 'db') as db, patch.object(seed, 'increment_rbac_version') as invalidate:
            model.query.filter_by.return_value.first.side_effect = [None, SimpleNamespace(parent_id=12)]
            model.return_value = menu
            role.query.filter_by.return_value.first.return_value = admin
            db.session.get.return_value = None
            seed.seed_abc_menu()
            self.assertEqual(model.call_args.kwargs['url'], '/sales-qty-abc-analysis')
            self.assertEqual(model.call_args.kwargs['parent_id'], 12)
            self.assertEqual(db.session.add.call_count, 2)
            grant.assert_called_once_with(role_id=1, menu_id=90)
            db.session.commit.assert_called_once()
            invalidate.assert_called_once()
            model.reset_mock(); grant.reset_mock(); db.reset_mock()
            model.query.filter_by.return_value.first.side_effect = None
            model.query.filter_by.return_value.first.return_value = menu
            db.session.get.return_value = object()
            seed.seed_abc_menu()
            model.assert_not_called(); grant.assert_not_called(); db.session.add.assert_not_called()


if __name__ == '__main__':
    unittest.main()
