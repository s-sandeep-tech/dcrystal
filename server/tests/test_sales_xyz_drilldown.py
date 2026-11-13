import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask
from werkzeug.datastructures import MultiDict

from app.dashboard.routes import sales_xyz_drilldown as routes
from app.services import sales_xyz_drilldown as report


def filters(**values):
    return report.parse_filters(MultiDict({'start': '2026-04-01', 'end': '2026-04-30', **values}))


class SalesXYZTests(unittest.TestCase):
    def test_categories_are_independent_and_respect_exact_boundaries(self):
        rows = [
            {'id': '1', 'label': 'One', 'pieces': 80, 'weight': 5, 'turnover': 15, 'profit': 2, 'tsk': 80},
            {'id': '2', 'label': 'Two', 'pieces': 15, 'weight': 80, 'turnover': 5, 'profit': 3, 'tsk': 5},
            {'id': '3', 'label': 'Three', 'pieces': 5, 'weight': 15, 'turnover': 80, 'profit': 4, 'tsk': 15},
            {'id': '4', 'label': 'Four', 'pieces': 0, 'weight': 0, 'turnover': 0, 'profit': -1, 'tsk': 0},
        ]
        totals = report.assign_categories(rows)
        self.assertEqual(totals, {'pieces': 100, 'weight': 100, 'turnover': 100, 'profit': 8})
        self.assertEqual([row['categories'] for row in rows], [
            {'pieces': 'A', 'weight': 'C', 'turnover': 'B', 'tsk': 'A'},
            {'pieces': 'B', 'weight': 'A', 'turnover': 'C', 'tsk': 'C'},
            {'pieces': 'C', 'weight': 'B', 'turnover': 'A', 'tsk': 'B'},
            dict.fromkeys(('pieces', 'weight', 'turnover', 'tsk'), 'Unclassified'),
        ])

    def test_path_is_validated_and_parameters_handle_missing_values(self):
        with self.assertRaisesRegex(ValueError, 'Invalid drill-down path'):
            report.parse_parent('[12]')
        with self.assertRaisesRegex(ValueError, 'Invalid drill-down path'):
            report.parse_parent('["1","2","3","4","5","6","7","8","9"]')
        parent = report.parse_parent('["4",null,"0.00"]')
        where, params = report.where_clause(filters(trans_type='INVOICE'), parent)
        self.assertIn('"purity_id"::text IS NOT DISTINCT FROM %s', where)
        self.assertEqual(params[-5:], [['INVOICE'], ['SHOP', 'FRANCHISE_SHOP'], '4', None, '0.00'])

    def test_leaf_query_groups_type_and_wide_range_and_preserves_totals(self):
        cursor = MagicMock()
        cursor.description = [SimpleNamespace(name=name) for name in (
            'pieces', 'net_weight', 'turn_over', 'tsk', 'trans_type', 'trans_date', 'date', 'make', 'branch_type',
            *(key for key, _, _ in report.LEVELS), 'type_id', 'type', 'wide_range_id', 'wide_range',
        )]
        cursor.fetchall.return_value = [{
            'id_0': '7', 'id_1': '8', 'label_0': 'Type A', 'label_1': '2–4',
            'pieces': Decimal('4'), 'weight': Decimal('1.25'), 'turnover': Decimal('80'),
            'tsk': Decimal('7'), 'invalid_rows': 0,
        }]
        result = report.drilldown(cursor, filters(), ['1'] * len(report.LEVELS))
        sql, params = cursor.execute.call_args.args
        self.assertIn('GROUP BY "type_id"::text, "wide_range_id"::text', sql)
        self.assertIn('SUM(pieces::numeric)', sql)
        self.assertIn('SUM(tsk::numeric)', sql)
        self.assertEqual(result['rows'][0]['categories']['tsk'], 'A')
        self.assertEqual(result['rows'][0]['profit'], Decimal('7'))
        self.assertEqual(result['totals']['profit'], Decimal('7'))
        self.assertEqual(params[-8:], ['1'] * 8)
        self.assertTrue(result['leaf'])
        self.assertEqual(result['rows'][0]['type'], 'Type A')
        self.assertEqual(result['rows'][0]['wide_range'], '2–4')
        self.assertEqual(result['totals']['weight'], Decimal('1.25'))

    def test_api_requires_its_own_grant(self):
        app = Flask(__name__)
        app.add_url_rule('/api/sales-xyz-drilldown/<segment>', view_func=routes.sales_xyz_drilldown_segment)
        client = app.test_client()
        self.assertEqual(client.get('/api/sales-xyz-drilldown/hierarchy').status_code, 401)
        role = SimpleNamespace(name='READER', permissions=[], menus=[])
        user = SimpleNamespace(is_active=True, roles=[role], username='reader', is_admin=False)
        with patch('app.utils.decorators.verify_jwt_in_request'), \
             patch('app.utils.decorators.get_jwt_identity', return_value='1'), \
             patch('app.extensions.db.session.get', return_value=user), \
             patch.object(report, 'source_cursor') as source:
            self.assertEqual(client.get('/api/sales-xyz-drilldown/hierarchy').status_code, 403)
            source.assert_not_called()
            role.menus = [SimpleNamespace(url=routes.REPORT, permission_required=None)]
            self.assertEqual(client.get('/api/sales-xyz-drilldown/hierarchy?parent=broken').status_code, 400)
            with patch.object(report, 'drilldown', return_value={'rows': []}) as query:
                response = client.get('/api/sales-xyz-drilldown/hierarchy')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['data'], {'rows': []})
                self.assertEqual(query.call_args.args[-1], [])
