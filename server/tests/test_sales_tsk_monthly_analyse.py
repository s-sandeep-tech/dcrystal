import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from flask import Flask
from werkzeug.datastructures import MultiDict
from app.services import sales_tsk_monthly_analyse as report
from app.dashboard.routes import sales_tsk_monthly_analyse as routes


def filters(**kwargs):
    return report.parse_filters(MultiDict(dict(start='2026-04-01', end='2026-06-30', **kwargs)))


def record(month, amount, key='1'):
    return dict(id=key, label='Section '+str(key), month=date(2026, month, 1),
                net_turnover=Decimal(amount), net_weight=Decimal('1.25'), pieces=Decimal(3),
                total_tsk=Decimal(10), mcprofit=Decimal(amount) / 10, row_count=1)


class MatrixTests(unittest.TestCase):
    def test_months_shares_growth_and_totals(self):
        data=report.build_matrix([record(4,100),record(5,150),record(4,300,'2'),record(5,50,'2')], filters())
        self.assertEqual(len(data['months']),3)
        first=next(r for r in data['rows'] if r['id']=='1')['months']
        self.assertEqual(first[0]['share'],25)
        self.assertEqual(first[1]['growth'],50)
        self.assertIsNone(first[0]['growth'])
        self.assertIsNone(first[2]['growth'])
        self.assertEqual(first[2]['pieces'],0)
        self.assertEqual(data['totals'][1]['growth'],-50)
        self.assertEqual(data['totals'][0]['pieces'],6)
        self.assertEqual(first[0]['mcprofit'], Decimal(10))
        self.assertEqual(first[2]['mcprofit'], 0)
        self.assertEqual(data['totals'][0]['mcprofit'], Decimal(40))

    def test_negative_zero_missing_and_partial_bases(self):
        data=report.build_matrix([record(4,-100),record(5,-50)],filters())
        self.assertEqual(data['rows'][0]['months'][1]['growth'],50)
        self.assertEqual(data['totals'][0]['mcprofit'], Decimal(-10))
        self.assertIsNone(data['rows'][0]['months'][0]['share'])
        for records in ([record(4,0),record(5,50)], [record(5,50)]):
            self.assertIsNone(report.build_matrix(records,filters())['rows'][0]['months'][1]['growth'])
        f=filters(); f['start']=date(2026,4,2)
        self.assertIsNone(report.build_matrix([record(4,100),record(5,150)],f)['rows'][0]['months'][1]['growth'])

    def test_group_allowlist_and_cross_year(self):
        for group in report.GROUPS:
            self.assertEqual(filters(group_by=group)['group_by'],group)
        with self.assertRaises(ValueError): filters(group_by='section; DROP TABLE x')
        f=filters(); f.update(start=date(2025,12,15),end=date(2026,2,2))
        self.assertEqual([m['month'] for m in report.month_list(f)],['2025-12-01','2026-01-01','2026-02-01'])
        self.assertEqual([m['is_partial'] for m in report.month_list(f)],[True,False,True])

    def test_schema_validation_and_safe_query(self):
        cur = MagicMock()
        cur.description = [SimpleNamespace(name=n) for n in ('group_id', 'group', 'mcprofit')]
        with self.assertRaisesRegex(report.source.SourceDataError, 'Source columns missing: pieces'):
            report.matrix(cur, filters(group_by='group'))
        cur.description.append(SimpleNamespace(name='pieces'))
        with patch.object(report.source,'query',return_value=[]) as query:
            report.matrix(cur,filters(group_by='group'))
            sql=query.call_args.args[1]
            self.assertIn('COALESCE(SUM(pieces::numeric), 0) AS pieces', sql)
            self.assertNotIn('barcode', sql)
            self.assertIn('GROUP BY "group_id", 3', sql)
            self.assertNotIn('2026-04-01',sql)
            self.assertIn('COALESCE(SUM(mcprofit), 0) AS mcprofit', sql)

    def test_empty_result(self):
        data=report.build_matrix([],filters())
        self.assertEqual(data['rows'],[])
        self.assertEqual(len(data['totals']),3)
        self.assertIsNone(data['totals'][0]['share'])

    def test_barcode_type_filter_uses_parameterized_source_flags(self):
        selected = filters(crystalbarcodeyn=['Y', 'n', 'Y'])
        self.assertEqual(selected['barcode_types'], ['Y', 'N'])
        with self.assertRaisesRegex(ValueError, 'Crystal barcode or Muziris barcode'):
            filters(crystalbarcodeyn='invalid')
        cur = MagicMock()
        cur.description = [SimpleNamespace(name=name) for name in ('section_id', 'section', 'pieces', 'mcprofit')]
        with self.assertRaisesRegex(report.source.SourceDataError, 'Source columns missing: crystalbarcodeyn'):
            report.matrix(cur, selected)
        cur.description.append(SimpleNamespace(name='crystalbarcodeyn'))
        with patch.object(report.source, 'query', return_value=[]) as query:
            report.matrix(cur, selected)
        _, sql, params = query.call_args.args
        self.assertIn('LOWER(BTRIM(crystalbarcodeyn::text)) = ANY(%s)', sql)
        self.assertEqual(params[-1], ['y', 'yes', 't', 'true', '1', 'n', 'no', 'f', 'false', '0'])

    def test_cells_allocated_once_per_group(self):
        with patch.object(report, 'empty_cell', wraps=report.empty_cell) as allocate:
            report.build_matrix([record(4, 100), record(5, 150), record(6, 200)], filters())
            self.assertEqual(allocate.call_count, 6)  # Three group cells and three totals.

    def test_transaction_memory_settings_for_both_segments(self):
        for segment in ('options', 'matrix'):
            with patch.object(report.source, 'source_cursor') as context, \
                    patch.object(report.source, 'options', return_value={}), \
                    patch.object(report, 'matrix', return_value={}):
                result = report.load_segment(segment, filters())
                cur = context.return_value.__enter__.return_value
                self.assertEqual([call.args[0] for call in cur.execute.call_args_list],
                                 ["SET LOCAL work_mem = '4MB'",
                                  'SET LOCAL max_parallel_workers_per_gather = 0'])
                if segment == 'options':
                    self.assertEqual(result['crystalbarcodeyn'], [
                        {'value': 'Y', 'label': 'Crystal barcode'}, {'value': 'N', 'label': 'Muziris barcode'},
                    ])


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__)
        self.app.add_url_rule('/api/sales-tsk-monthly-analyse/<segment>',view_func=routes.sales_tsk_monthly_analyse_segment)
        self.client=self.app.test_client()

    def test_anonymous(self):
        for segment in ['matrix','options']:
            self.assertEqual(self.client.get('/api/sales-tsk-monthly-analyse/'+segment).status_code,401)

    def test_other_report_grant_does_not_grant_new_report(self):
        user=SimpleNamespace(is_active=True,roles=[SimpleNamespace(name='READER',permissions=[],menus=[SimpleNamespace(url='/sales-tsk-analyse')])],username='reader',is_admin=False)
        with patch('app.utils.decorators.verify_jwt_in_request'),patch('app.utils.decorators.get_jwt_identity',return_value='1'),patch('app.extensions.db.session.get',return_value=user),patch.object(report,'load_segment') as load:
            for segment in ['matrix','options']:
                self.assertEqual(self.client.get('/api/sales-tsk-monthly-analyse/'+segment).status_code,403)
            load.assert_not_called()

    def test_response_and_errors(self):
        with self.app.test_request_context('/?start=2026-04-01&end=2026-06-30'),patch.object(report,'load_segment',return_value={'value':Decimal('1.25')}):
            response=routes.sales_tsk_monthly_analyse_segment.__wrapped__('matrix')
            self.assertEqual(response.json['data']['value'],1.25)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
        with self.app.test_request_context('/?group_by=invalid'),patch.object(report,'load_segment') as load:
            self.assertEqual(routes.sales_tsk_monthly_analyse_segment.__wrapped__('matrix')[1],400);load.assert_not_called()
        with self.app.test_request_context('/'),patch.object(report,'load_segment',side_effect=report.source.SourceDataError('Missing pieces')):
            self.assertEqual(routes.sales_tsk_monthly_analyse_segment.__wrapped__('matrix')[1],422)

if __name__=='__main__': unittest.main()
