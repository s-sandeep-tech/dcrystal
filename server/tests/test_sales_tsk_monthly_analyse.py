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
                total_tsk=Decimal(10), row_count=1)


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

    def test_negative_zero_missing_and_partial_bases(self):
        data=report.build_matrix([record(4,-100),record(5,-50)],filters())
        self.assertEqual(data['rows'][0]['months'][1]['growth'],50)
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
        cur=MagicMock(); cur.description=[]
        with self.assertRaises(report.source.SourceDataError): report.matrix(cur,filters())
        cur.description=[SimpleNamespace(name=n) for n in ['group_id','group','pcs']]
        with patch.object(report.source,'query',return_value=[]) as query:
            report.matrix(cur,filters(group_by='group'))
            sql=query.call_args.args[1]
            self.assertIn('SUM("pcs")',sql); self.assertIn('GROUP BY "group_id", 3',sql)
            self.assertNotIn('2026-04-01',sql)

    def test_empty_result(self):
        data=report.build_matrix([],filters())
        self.assertEqual(data['rows'],[])
        self.assertEqual(len(data['totals']),3)
        self.assertIsNone(data['totals'][0]['share'])


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
